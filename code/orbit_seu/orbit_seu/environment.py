"""Particle environments.

Two sources:

1. File import (engineering path): differential LET / proton / electron
   spectra exported from SPENVIS, AE9/AP9 or CREME96 runs. The parser is a
   tolerant whitespace-column reader with '#'/'%'/'!'/'*' comment lines.
   Imported spectra are assumed to be given for the same orbit and already
   transported through shielding (SPENVIS lets you specify both).

2. Built-in DEMO galactic-cosmic-ray toy model (SYNTHETIC, NOT engineering
   data): per-species power-law rigidity spectra, solar-modulation-free,
   mapped to LET via L = K*Z^2/beta^2 (K = 0.00166 MeV*cm^2/mg, MIP proton
   stopping in Si). The geomagnetic transmission is a hard rigidity cutoff
   R_ion > kappa * Rc(orbit point). Every demo output is stamped
   "SYNTHETIC-DEMO" and must not be used as a flight estimate.
"""
import math
import hashlib
from .constants import LET_K_DEMO
from .spectra import Spectrum

DEMO_SPECIES = [
    # name, Z, A, abundance-normalized j0 [1/cm^2/s/GV(pn)], rigidity index
    {"name": "p",  "Z": 1,  "A": 1,  "j0": 1.80, "gamma": 2.75},
    {"name": "He", "Z": 2,  "A": 4,  "j0": 0.14, "gamma": 2.75},
    {"name": "O",  "Z": 8,  "A": 16, "j0": 0.012, "gamma": 2.70},
    {"name": "Si", "Z": 14, "A": 28, "j0": 0.004, "gamma": 2.70},
    {"name": "Fe", "Z": 26, "A": 56, "j0": 0.003, "gamma": 2.65},
]
DEMO_SYNTHETIC = True  # banner flag consumed by the report writer


def _beta(rn):
    """rn: per-nucleon rigidity [GV]; nucleon mass 0.938 GeV."""
    m = 0.938
    return rn / math.sqrt(rn * rn + m * m)


def demo_gcr_let_spectra(cutoff_gv, species=None, kappa=1.0,
                         rn_min=0.35, rn_max=2.0e3, n=220):
    """Return {species: Spectrum over LET} transmitted through a vertical
    rigidity cutoff `cutoff_gv` (GV). Synthetic demo environment."""
    species = species or DEMO_SPECIES
    out = {}
    for sp in species:
        z, a = sp["Z"], sp["A"]
        ratio = a / z  # ion rigidity = (A/Z) * per-nucleon rigidity
        lets, fluxs = [], []
        for k in range(n):
            rn0 = rn_min * (rn_max / rn_min) ** (k / (n - 1))
            rn1 = rn_min * (rn_max / rn_min) ** ((k + 1) / (n - 1))
            rnc = math.sqrt(rn0 * rn1)
            ion_rig = ratio * rnc
            if ion_rig <= kappa * cutoff_gv:      # below cutoff: absorbed
                continue
            b0, b1, bc = _beta(rn0), _beta(rn1), _beta(rnc)
            l0, l1 = LET_K_DEMO * z * z / b0**2, LET_K_DEMO * z * z / b1**2
            phi_rn = sp["j0"] * rnc ** (-sp["gamma"])   # per GV(pn)
            dl_drn = abs((l1 - l0) / (rn1 - rn0))
            if dl_drn <= 0:
                continue
            lets.append(math.sqrt(l0 * l1))
            fluxs.append(phi_rn / dl_drn)         # per unit LET
        if len(lets) >= 2:
            order = sorted(range(len(lets)), key=lambda q: lets[q])
            xs = [lets[q] for q in order]
            ys = [fluxs[q] for q in order]
            # collapse duplicate/near-duplicate LET grid points
            X, Y = [xs[0]], [ys[0]]
            for q in range(1, len(xs)):
                if xs[q] / X[-1] > 1.0005:
                    X.append(xs[q]); Y.append(ys[q])
                else:
                    Y[-1] = max(Y[-1], ys[q])
            out[sp["name"]] = Spectrum(X, Y)
    return out


def load_spectrum_file(path, x_col=0, y_col=1, comment_chars="#%!;*"):
    """Whitespace column file -> Spectrum(x, y). Comment lines and any row
    with fewer than max(x_col,y_col)+1 numeric fields is skipped."""
    xs, ys = [], []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            s = line.strip()
            if not s or s[0] in comment_chars:
                continue
            parts = s.replace(",", " ").split()
            try:
                vals = [float(p) for p in parts]
            except ValueError:
                continue  # header row
            if len(vals) <= max(x_col, y_col):
                continue
            x, y = vals[x_col], vals[y_col]
            if x > 0 and y >= 0:
                xs.append(x); ys.append(y)
    if len(xs) < 2:
        raise ValueError(f"no plottable rows found in {path}")
    order = sorted(range(len(xs)), key=lambda q: xs[q])
    return Spectrum([xs[q] for q in order], [ys[q] for q in order])


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
