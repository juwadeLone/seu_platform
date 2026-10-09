"""Device sensitivity models.

Heavy-ion cross-section: two-parameter-saturated Weibull in LET
(sigma in cm^2 per bit or per device -- the caller defines the normalization
and must use the same normalization for the reported rates).

Proton cross-section: measured table sigma(E) only. Analytic Bendel fits are
deliberately not implemented in v0.1 because getting their constants wrong
is worse than requiring a table; see README roadmap.
"""
import math
from .spectra import Spectrum
from .rates import heavy_ion_rate_per_s


class WeibullLET:
    """sigma(L) = sigma_sat * [1 - exp(-((L - Lth)/W)^s)], L > Lth."""

    def __init__(self, let_threshold, width, shape, sigma_sat):
        if let_threshold < 0 or width <= 0 or shape <= 0 or sigma_sat < 0:
            raise ValueError("invalid Weibull parameters")
        self.lth = float(let_threshold)
        self.w = float(width)
        self.s = float(shape)
        self.sat = float(sigma_sat)

    def sigma(self, let):
        if let <= self.lth:
            return 0.0
        x = (let - self.lth) / self.w
        return self.sat * (1.0 - math.exp(-(x ** self.s)))

    def describe(self):
        return (f"Weibull LET: Lth={self.lth} MeV*cm^2/mg, W={self.w}, "
                f"s={self.s}, sigma_sat={self.sat:g} cm^2")


class TableSigma:
    """Arbitrary measured cross-section table sigma(x), x = LET or energy."""

    def __init__(self, xs, ys):
        self._tab = Spectrum(xs, ys)

    def sigma(self, x):
        return self._tab(x)

    def describe(self):
        return (f"table sigma: {len(self._tab.xs)} points, "
                f"x in [{self._tab.xs[0]:g}, {self._tab.xs[-1]:g}]")


class AnchorSigma:
    """Lower-bound proton cross-section from a single measured anchor point.

    sigma(E) = sigma_anchor for E >= anchor, else 0. Integrating the measured
    cross-section only over flux above the anchor energy gives a defensible
    UNDERESTIMATE of the true rate (sigma generally keeps rising with E, and
    the sub-anchor flux contribution is not counted at all). Used only when a
    domain has exactly one citable measured point — an energy-dependent table
    replaces it as soon as one exists. Reported as mode='lower_bound'.
    """

    mode = "lower_bound"

    def __init__(self, anchor_e_mev, sigma):
        if anchor_e_mev <= 0 or sigma <= 0:
            raise ValueError("anchor needs positive energy and sigma")
        self.e0 = float(anchor_e_mev)
        self.s = float(sigma)

    def sigma(self, e):
        return self.s if e >= self.e0 else 0.0

    def describe(self):
        return (f"anchor sigma (lower bound): {self.s:g} cm^2 for "
                f"E>={self.e0:g} MeV")


def build_proton_sigma(spec):
    """Per-domain proton sigma(E) model. Accepted shapes:
      {"anchor_E_mev": E, "sigma_cm2_per_bit": s, ...} -> AnchorSigma (bound)
      {"table": [[E, sigma], ...]}                  -> TableSigma (inline)
      {"file": path, "columns": {"x": 0, "y": 1}}  -> TableSigma (file)
    Returns (model, mode, meta) where meta echoes the provenance fields."""
    if not spec:
        return None, None, None
    if "anchor_E_mev" in spec:
        return (AnchorSigma(spec["anchor_E_mev"],
                            spec["sigma_cm2_per_bit"]),
                "lower_bound",
                {k: spec[k] for k in ("source", "note") if k in spec})
    if "table" in spec:
        xs = [float(p[0]) for p in spec["table"]]
        ys = [float(p[1]) for p in spec["table"]]
        return (TableSigma(xs, ys), "table",
                {k: spec[k] for k in ("source", "note") if k in spec})
    if "file" in spec:
        from .environment import load_spectrum_file
        cols = spec.get("columns", {"x": 0, "y": 1})
        tab = load_spectrum_file(spec["file"],
                                 x_col=cols.get("x", 0),
                                 y_col=cols.get("y", 1))
        return (TableSigma(tab.xs, tab.ys), "table",
                {"file": spec["file"],
                 **{k: spec[k] for k in ("source", "note") if k in spec}})
    raise ValueError("proton_sigma needs anchor_E_mev, table or file")


def build_device_sigma(spec):
    """spec: dict with either 'heavy_ion_weibull' or 'sigma_table'
    (path to whitespace column file; configurable x/y columns)."""
    if "heavy_ion_weibull" in spec and spec["heavy_ion_weibull"]:
        w = spec["heavy_ion_weibull"]
        return WeibullLET(w["let_threshold"], w["width"], w["shape"],
                          w["sigma_sat_cm2_per_bit"])
    if "heavy_ion_weibull_by_domain" in spec and spec["heavy_ion_weibull_by_domain"]:
        return DomainWeibull(spec["heavy_ion_weibull_by_domain"])
    if "sigma_table" in spec and spec["sigma_table"]:
        from .environment import load_spectrum_file
        cols = spec.get("sigma_table_columns", {"x": 0, "y": 1})
        tab = load_spectrum_file(spec["sigma_table"],
                                 x_col=cols["x"], y_col=cols["y"])
        return TableSigma(tab.xs, tab.ys)
    raise ValueError("device needs heavy_ion_weibull or sigma_table")


class DomainWeibull:
    """Per-domain (CRAM/BRAM/FF/...) heavy-ion Weibull cross-sections.

    Each domain carries its own WeibullLET and an optional bit count. The
    device-level rate is the sum over domains of (bits_d * rate_per_bit_d).
    Single-group 'heavy_ion_weibull' remains the fallback path.
    """
    def __init__(self, per_domain):
        self.domains = {}
        for name, v in per_domain.items():
            wb = WeibullLET(v["let_threshold"], v["width"], v["shape"],
                            v["sigma_sat_cm2_per_bit"])
            proton, pmode, pmeta = build_proton_sigma(v.get("proton_sigma"))
            self.domains[name] = {"wb": wb, "bits": v.get("bits"),
                                  "proton": proton, "proton_mode": pmode,
                                  "proton_meta": pmeta}

    def domain_sigma(self, domain, let):
        return self.domains[domain]["wb"].sigma(let)

    def species_domain_rates_day(self, spectra):
        """{species: {domain: events/day/bit}} for each input spectrum."""
        return {name: {k: heavy_ion_rate_per_s(sp, d["wb"]) * 86400.0
                       for k, d in self.domains.items()}
                for name, sp in spectra.items()}

    def domain_rates_day(self, spectra):
        """Return (per_domain /day/bit, total /day/device).

        spectra: dict name -> Spectrum (LET differential flux).
        per_domain value is the domain-averaged upset rate per bit;
        total is summed over domains that declare a bit count.
        """
        per = {k: 0.0 for k in self.domains}
        for sp in spectra.values():
            for k, d in self.domains.items():
                per[k] += heavy_ion_rate_per_s(sp, d["wb"]) * 86400.0
        total_dev = 0.0
        for k, d in self.domains.items():
            if d["bits"]:
                total_dev += d["bits"] * per[k]
        return per, total_dev

    def describe(self):
        parts = []
        for k, d in self.domains.items():
            b = d["bits"]
            s = f"{k}: {d['wb'].describe()}" + (f" bits={b}" if b else " bits=n/a")
            if d.get("proton") is not None:
                s += f" | proton[{d['proton_mode']}]: {d['proton'].describe()}"
            parts.append(s)
        return "DomainWeibull [" + " | ".join(parts) + "]"
