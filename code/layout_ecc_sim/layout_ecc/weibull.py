"""Lee 2014 heavy-ion Weibull σ(LET) for the strike flip model (M9).

σ is in cm²/bit. Kernel area must be in cm². Mixing µm² with cm² is a
1e8 unit error and is rejected.

DSP has no row in Lee Table 1: sigma_cm2() returns None and the strike
path never upsets DSP_STATE under flip_model='weibull'.
"""
from __future__ import annotations

import json
import math
import os

_JSON = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "data", "weibull_7series_measured.json"))

# layout_ecc domain → Lee Table 1 resource
DOMAIN_TO_LEE = {
    "CFG": "CRAM",
    "FF_STATE": "FF",
    "BRAM_STATE": "BRAM",
    "DSP_STATE": None,
}

UM2_TO_CM2 = 1e-8

_CURVES = None


def load_curves(path=None):
    """Load per-domain Weibull parameters from the measured JSON."""
    global _CURVES
    p = path or _JSON
    if _CURVES is not None and path is None:
        return _CURVES
    with open(p, encoding="utf-8") as fh:
        raw = json.load(fh)
    curves = {}
    for name, row in (raw.get("per_domain") or {}).items():
        curves[name] = {
            "let_threshold": float(row["let_threshold"]),
            "width": float(row["width"]),
            "shape": float(row["shape"]),
            "sigma_sat_cm2_per_bit": float(row["sigma_sat_cm2_per_bit"]),
            "source": row.get("source"),
        }
    if path is None:
        _CURVES = curves
    return curves


def sigma_cm2_from_params(let, let_threshold, width, shape, sigma_sat):
    """σ(L) = σsat · (1 − exp(−((L − Lth)/W)^s)) for L > Lth, else 0."""
    L = float(let)
    Lth = float(let_threshold)
    if L <= Lth:
        return 0.0
    x = (L - Lth) / float(width)
    if x <= 0:
        return 0.0
    return float(sigma_sat) * (1.0 - math.exp(-(x ** float(shape))))


def sigma_cm2(domain, let, curves=None):
    """Return σ in cm²/bit, or None if that domain has no Lee curve (DSP)."""
    lee = DOMAIN_TO_LEE.get(domain)
    if lee is None:
        return None
    curves = curves or load_curves()
    row = curves[lee]
    return sigma_cm2_from_params(
        let, row["let_threshold"], row["width"], row["shape"],
        row["sigma_sat_cm2_per_bit"])


def kernel_area_cm2(a, b, rpm_to_um, area_um2=None):
    """Ellipse area in cm².

    Prefer the anchored ``area_um2`` when given (physical kernel). Otherwise
    convert the grid-unit ellipse a, b through units.py RPM_TO_UM (UG475-calibrated, not an assumption).
    """
    if area_um2 is not None:
        return max(float(area_um2), 0.0) * UM2_TO_CM2
    rpm = float(rpm_to_um)
    a_um = float(a) * rpm
    b_um = float(b) * rpm
    return math.pi * a_um * b_um * UM2_TO_CM2


def mu_upsets(bits, sigma_cm2_per_bit, area_cm2):
    """Expected bit-upset count in one site×domain given one ion in A."""
    if sigma_cm2_per_bit is None or area_cm2 <= 0 or bits <= 0:
        return 0.0
    return float(bits) * float(sigma_cm2_per_bit) / float(area_cm2)


def p_at_least_one(mu):
    return 0.0 if mu <= 0 else 1.0 - math.exp(-float(mu))


def poisson(rng, mu):
    """Knuth Poisson; normal approx for large μ. Seeded via ``rng.random``."""
    mu = max(float(mu), 0.0)
    if mu == 0.0:
        return 0
    if mu > 50.0:
        return max(0, int(round(rng.gauss(mu, math.sqrt(mu)))))
    L = math.exp(-mu)
    k = 0
    p = 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= L:
            return k - 1
