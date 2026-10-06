"""Build env_data/oneill_lis_coefficients.csv from the BON14 LIS table.

Source: NASA/TP-2015-218569 "Badhwar-O'Neill 2014 Galactic Cosmic Ray
Flux Model Description" (O'Neill, Golge, Slaba; public domain), Table 2
"LIS parameters used in the BON14 model" and Eq. (2):

    j_ion(T) = j0 * beta^delta * (T + T0)^(-gamma)      [particles/sr/m2/s/MeV/n]
    beta     = v/c = sqrt(1 - (T0/(T+T0))^2),  T0 = 938.272 MeV/n

The orbit_seu tool instead consumes a smooth double-broken power law in
rigidity:

    J_LIS(R) = J0 * R^g0 * (1+(R/R0)^2)^((g1-g0)/2) * (1+(R/R1)^2)^((g2-g1)/2)

This script samples the BON14 LIS on a log-rigidity grid and fits the
double-broken form per element by weighted least squares in log space
(linear in the exponents once R0/R1 are fixed; R0/R1 scanned on a grid).

Output CSV columns: Z,A,J0,gamma0,gamma1,gamma2,R0_GeV,R1_GeV
J0 units are (cm2 s sr GeV/n)^-1  (per-GeV differential intensity),
i.e. 1000x the per-MeV BON14 value -- matching gcr_bo.py conventions
where lis_rigidity() returns a per-GeV intensity.

Usage: python scripts/make_oneill_lis_csv.py [out_path]
"""
import csv
import math
import os
import sys

# ---- BON14 Table 2: Z, gamma, delta, j0 (per-MeV LIS amplitude) ----
# Extracted from NASA/TP-2015-218569 Table 2 (public domain).
BON14_TABLE = [
    # Z, gamma, delta, j0
    (1, 2.75, -2.82, 9.50e-4), (2, 2.80, -2.00, 4.53e-5),
    (3, 3.21, -0.69, 6.37e-8), (4, 2.93, 1.50, 1.20e-7),
    (5, 3.00, -0.40, 2.40e-7), (6, 2.70, -2.00, 1.60e-6),
    (7, 2.95, -0.60, 2.65e-7), (8, 2.73, -1.90, 1.50e-6),
    (9, 3.08, 0.40, 1.63e-8), (10, 2.75, -1.60, 2.35e-7),
    (11, 2.73, -1.80, 4.60e-8), (12, 2.70, -2.40, 3.03e-7),
    (13, 2.75, -1.40, 5.30e-8), (14, 2.65, -2.40, 2.65e-7),
    (15, 3.15, 2.00, 5.68e-9), (16, 2.70, -1.00, 5.78e-8),
    (17, 3.13, 2.00, 5.99e-9), (18, 2.90, 0.60, 1.68e-8),
    (19, 3.13, 0.80, 7.90e-9), (20, 2.75, -1.60, 3.23e-8),
    (21, 3.15, 0.40, 3.50e-9), (22, 3.00, -0.50, 1.44e-8),
    (23, 3.00, -0.50, 7.14e-9), (24, 2.90, -1.00, 1.78e-8),
    (25, 2.80, -1.00, 1.39e-8), (26, 2.60, -2.40, 2.00e-7),
    (27, 2.60, -2.50, 1.11e-9), (28, 2.55, -2.40, 1.19e-8),
]

# Most abundant isotope mass numbers (used for A/Z in rigidity mapping).
# BON14 LIS itself depends only on Z; A only enters the ion rigidity.
MASS_NUMBER = {
    1: 1, 2: 4, 3: 7, 4: 9, 5: 11, 6: 12, 7: 14, 8: 16, 9: 19, 10: 20,
    11: 23, 12: 24, 13: 27, 14: 28, 15: 31, 16: 32, 17: 35, 18: 40,
    19: 39, 20: 40, 21: 45, 22: 48, 23: 51, 24: 52, 25: 55, 26: 56,
    27: 59, 28: 58,
}

T0_MEV = 938.272     # nucleon rest energy [MeV/n]
NUC = 0.938272       # same in GeV/n


def bon14_lis_per_gev(z, gamma, delta, j0, r_gev):
    """BON14 LIS differential intensity at rigidity r_gev, per GeV/n.

    R = sqrt(T (T + 2 T0));  T in GeV/n;  j_ion per MeV/n -> x1000 per GeV/n.
    """
    t_gev = math.sqrt(r_gev * r_gev + NUC * NUC) - NUC
    t_mev = t_gev * 1000.0
    beta = math.sqrt(1.0 - (T0_MEV / (t_mev + T0_MEV)) ** 2)
    return 1000.0 * j0 * beta ** delta * (t_mev + T0_MEV) ** (-gamma)


def dbl_broken_log10(r_gev, j0, g0, g1, g2, r0, r1):
    """log10 of the double-broken power law (tool's lis_rigidity form)."""
    r = max(r_gev, 1e-9)
    f = (1.0 + (r / r0) ** 2) ** ((g1 - g0) / 2.0)
    g = (1.0 + (r / r1) ** 2) ** ((g2 - g1) / 2.0)
    return math.log10(j0) + g0 * math.log10(r) + math.log10(f) + math.log10(g)


def fit_element(gamma, delta, j0, r_grid):
    """Fit double-broken power law to BON14 LIS samples (log10 space).

    With R0/R1 fixed the model is linear in
        b = [log10 J0, g0, g1-g0, g2-g1].
    Grid-scan R0/R1 for the best residual (weighted RMS over log10 flux).
    """
    import numpy as np

    y = np.array([math.log10(bon14_lis_per_gev(1, gamma, delta, j0, r))
                  for r in r_grid])          # BON14 target (Z only in beta/T)
    lr = np.log10(r_grid)
    n = len(r_grid)

    r0_grid = np.logspace(-1.0, 5.0, 61)     # 0.1 GeV .. 1e5 GeV
    r1_grid = np.logspace(-1.0, 5.0, 61)
    best = None
    for r0 in r0_grid:
        f0 = 0.5 * np.log10(1.0 + (r_grid / r0) ** 2)
        for r1 in r1_grid:
            f1 = 0.5 * np.log10(1.0 + (r_grid / r1) ** 2)
            X = np.column_stack([np.ones(n), lr, f0, f1])
            b, *_ = np.linalg.lstsq(X, y, rcond=None)
            pred = X @ b
            resid = np.sqrt(np.mean((pred - y) ** 2))
            if best is None or resid < best[0]:
                best = (resid, b, r0, r1)
    resid, b, r0, r1 = best
    log10_j0, g0, g1mg0, g2mg1 = b
    return {
        "J0": 10.0 ** log10_j0, "g0": g0, "g1": g0 + g1mg0,
        "g2": g0 + g1mg0 + g2mg1, "R0": r0, "R1": r1,
        "rms_log10": resid,
    }


def main(out_path):
    r_grid = np.logspace(math.log10(0.3), math.log10(5.0e4), 160)
    rows = []
    report = []
    for z, gamma, delta, j0 in BON14_TABLE:
        a = MASS_NUMBER[z]
        fit = fit_element(gamma, delta, j0, r_grid)
        rows.append({
            "Z": z, "A": a, "J0": fit["J0"], "gamma0": fit["g0"],
            "gamma1": fit["g1"], "gamma2": fit["g2"],
            "R0_GeV": fit["R0"], "R1_GeV": fit["R1"],
        })
        report.append(
            f"Z={z:2d} A={a:2d}  g0={fit['g0']:+.3f} g1={fit['g1']:+.3f} "
            f"g2={fit['g2']:+.3f} R0={fit['R0']:.3f} R1={fit['R1']:.3g} "
            f"J0={fit['J0']:.3e}  rms={fit['rms_log10']:.4f} dex")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["Z", "A", "J0", "gamma0", "gamma1", "gamma2",
                            "R0_GeV", "R1_GeV"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"wrote {out_path} ({len(rows)} elements)")
    print("fit report (rms in dex = log10 flux error; 0.05 ~ 12%):")
    for line in report:
        print("  " + line)


if __name__ == "__main__":
    import numpy as np
    default = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                           "env_data", "oneill_lis_coefficients.csv")
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.normpath(default))
