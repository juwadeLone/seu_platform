"""Badhwar-O'Neill style galactic cosmic ray model with real-data support.

Composition (all published physics, no invented numbers):

1. LIS (local interstellar spectra): loaded per element from a coefficient
   CSV file. The intended public-domain source is the coefficient tables of
   the Badhwar-O'Neill model (P. M. O'Neill et al.), distributed in NASA
   technical memoranda (e.g. NASA/TM-2013-217978) which are public domain.
   The CSV format is documented in env_data/README.md; until the file is
   provided, this module raises a clear error instead of guessing numbers.

2. Solar modulation: Gleeson-Axford force-field approximation (1968),
   J_mod(T) = J_LIS(T + Phi) * T(T+2m) / [(T+Phi)(T+Phi+2m)],
   with Phi = (Z/A) * phi_mv.  This equation is standard and exact within
   the force-field approximation.

3. LET mapping: L = K Z^2 / beta^2 (K = 1.66e-3 MeV cm^2/mg, MIP proton
   stopping in Si). Rigidity cutoff transmission is applied on ion
   rigidity R = (A/Z) R_n as in the demo environment.

Units: kinetic energy per nucleon T in GeV/n, differential intensity in
(cm^-2 s^-1 sr^-1 (MeV/n)^-1) -> converted to omni directional flux by
multiplying 4*pi (documented convention, same as the demo environment).
"""
import csv
import math
import os

from .constants import LET_K_DEMO
from .spectra import Spectrum

NUCLEON_MASS_GEV = 0.938272

# Representative species set: the GCR flux is dominated by H and He; heavier
# ions matter for SEU through their LET. Group representative elements.
SPECIES = [
    # name, Z, A
    ("H", 1, 1), ("He", 2, 4), ("C", 6, 12), ("O", 8, 16),
    ("Mg", 12, 24), ("Si", 14, 28), ("Fe", 26, 56),
]

CSV_COLUMNS = ["Z", "A", "J0", "gamma0", "gamma1", "gamma2",
               "R0_GeV", "R1_GeV"]


class LisCoefficientError(RuntimeError):
    pass


def load_lis_coefficients(path):
    """Load per-element LIS coefficients.

    Expected CSV columns (header required):
    Z,A,J0,gamma0,gamma1,gamma2,R0_GeV,R1_GeV

    Functional form (see env_data/README.md for the full contract):
      J_LIS(R) = J0 * R^g0 * (1+(R/R0)^2)^((g1-g0)/2) * (1+(R/R1)^2)^((g2-g1)/2)
    a smooth broken power law (slopes g0 / g1 / g2 below R0, between, above).
    Providers converting the public-domain O'Neill coefficient tables must
    fit their table into this documented form (or extend this loader).
    """
    if not path or not os.path.isfile(path):
        raise LisCoefficientError(
            f"LIS coefficient file not found: {path}\n"
            "Provide it per env_data/README.md (public-domain source: "
            "NASA/TM-2013-217978 coefficient tables).")
    out = {}
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                z = int(row["Z"])
                rec = {
                    "Z": z, "A": int(row["A"]),
                    "J0": float(row["J0"]),
                    "g0": float(row["gamma0"]), "g1": float(row["gamma1"]),
                    "g2": float(row["gamma2"]),
                    "R0": float(row["R0_GeV"]), "R1": float(row["R1_GeV"]),
                }
            except (KeyError, ValueError) as exc:
                raise LisCoefficientError(f"bad CSV row {row!r}: {exc}")
            out[z] = rec
    return out


def lis_rigidity(coef, r_gev):
    """LIS differential intensity in rigidity at R [GeV].
    Smooth broken power law with two breaks (documented form):
      J = J0 * R^g0 * (1 + (R/R0)^2)^((g1-g0)/2) * (1 + (R/R1)^2)^((g2-g1)/2)
    giving slopes g0 below R0, g1 between, g2 above R1.
    """
    r = max(r_gev, 1e-6)
    f = (1.0 + (r / coef["R0"]) ** 2) ** ((coef["g1"] - coef["g0"]) / 2.0)
    g = (1.0 + (r / coef["R1"]) ** 2) ** ((coef["g2"] - coef["g1"]) / 2.0)
    return coef["J0"] * r ** coef["g0"] * f * g


def beta_from_t_per_nucleon(t_gev):
    return math.sqrt(1.0 - 1.0 / (1.0 + t_gev / NUCLEON_MASS_GEV) ** 2)


def modulated_spectrum(coef, phi_mv, n=160, t_min=0.05, t_max=2.0e4):
    """Force-field modulated differential intensity in kinetic energy per
    nucleon. Returns (Ts [GeV/n], J [1/cm2 s sr (MeV/n)]) sampled log-grid.

    J(T) = LIS(T + Phi) * [T (T + 2m)] / [(T+Phi)(T+Phi+2m)]
    where the LIS in energy per nucleon is obtained from the rigidity LIS:
    dT/dR = ... conversion J_T(T) = J_R(R) * dR/dT with R per NUCLEON.
    """
    z_over_a = coef["Z"] / float(coef["A"])
    phi_gev = z_over_a * phi_mv / 1000.0
    m = NUCLEON_MASS_GEV
    ts, js = [], []
    for k in range(n):
        t = t_min * (t_max / t_min) ** (k / (n - 1))
        t_lis = t + phi_gev
        if t_lis <= 0:
            continue
        r_n = math.sqrt(t_lis * (t_lis + 2.0 * m))     # rigidity per nucleon
        j_r = lis_rigidity(coef, r_n)                  # per GeV per sr
        dtdr = r_n / (t_lis + m)                       # dT/dR exact
        ratio = (t * (t + 2.0 * m)) / (t_lis * (t_lis + 2.0 * m))
        j_t = j_r * dtdr * ratio                       # per GeV per sr
        ts.append(t)
        js.append(max(j_t, 0.0))
    return ts, js


def let_spectra_from_gcr(coeffs, phi_mv, cutoff_gv, kappa=1.0,
                         omni_factor=4.0 * math.pi):
    """Build transmitted differential LET spectra per species.

    Rigidity cutoff: transmitted when R_ion = (A/Z) R_n > kappa * cutoff.
    LET: L = K Z^2 / beta^2 (same approximation as the demo environment,
    documented in README; no Bethe log term -> low-beta LET underestimated).
    """
    out = {}
    for name, z, a in SPECIES:
        if z not in coeffs:
            continue
        coef = dict(coeffs[z])
        coef["Z"], coef["A"] = z, a
        ts, js = modulated_spectrum(coef, phi_mv)
        if not ts:
            continue
        lets, fluxs = [], []
        for k in range(len(ts) - 1):
            t0, t1 = ts[k], ts[k + 1]
            b0 = beta_from_t_per_nucleon(t0)
            b1 = beta_from_t_per_nucleon(t1)
            l0 = LET_K_DEMO * z * z / b0 ** 2
            l1 = LET_K_DEMO * z * z / b1 ** 2
            tc = math.sqrt(t0 * t1)
            rn_c = math.sqrt(tc * (tc + 2 * NUCLEON_MASS_GEV))
            r_ion = (a / z) * rn_c
            if r_ion <= kappa * cutoff_gv:
                continue
            jc = js[k] * omni_factor               # -> omni (per GeV)
            dl_dt = abs(l1 - l0) / abs(t1 - t0)
            if dl_dt <= 0:
                continue
            lets.append(math.sqrt(l0 * l1))
            fluxs.append(jc / dl_dt)
        if len(lets) >= 2:
            order = sorted(range(len(lets)), key=lambda q: lets[q])
            xs = [lets[q] for q in order]
            ys = [fluxs[q] for q in order]
            X, Y = [xs[0]], [ys[0]]
            for q in range(1, len(xs)):
                if xs[q] / X[-1] > 1.0005:
                    X.append(xs[q]); Y.append(ys[q])
                else:
                    Y[-1] = max(Y[-1], ys[q])
            out[name] = Spectrum(X, Y)
    return out


DEFAULT_COEF_PATH = os.path.join(os.path.dirname(__file__),
                                 "env_data", "oneill_lis_coefficients.csv")


def build_gcr_environment(config):
    """config keys: phi_mv (default 600), coefficients_csv (path),
    rigidity_cutoff.kappa. Returns (spectra dict, provenance dict)."""
    env = config["environment"]
    phi = env.get("phi_mv", 600.0)
    csv_path = env.get("coefficients_csv",
                       os.path.normpath(DEFAULT_COEF_PATH))
    kappa = env.get("rigidity_cutoff", {}).get("kappa", 1.0)
    coeffs = load_lis_coefficients(csv_path)
    with open(csv_path, "rb") as fh:
        import hashlib
        sha = hashlib.sha256(fh.read()).hexdigest()
    cutoff = config.get("_cutoff_gv", 0.0)   # injected by mission.run
    spectra = let_spectra_from_gcr(coeffs, phi, cutoff, kappa)
    prov = {"lis_coefficients": csv_path, "sha256": sha,
            "phi_mv": phi, "model": "force-field modulation + file LIS"}
    return spectra, prov
