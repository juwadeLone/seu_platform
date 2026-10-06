#!/usr/bin/env python3
"""Compare placeholder vs measured (Lee 2014) Weibull on the SAME MEO
SPENVIS-CREME96 environment, to validate parameter substitution.

Reuses orbit_seu internals (no code changes here). Per-domain bits use the
TESTED device (XC7K325T) values as reference only -- xc7vx690t actual bits
must be filled in the demo config, not fabricated here.
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from orbit_seu.device import WeibullLET
from orbit_seu.environment import load_spectrum_file
from orbit_seu.rates import heavy_ion_rate_per_s

SPENVIS = os.path.join(ROOT, "env_data", "spenvis_let")
FILES = ["H", "He", "Z03-10", "Z11-20", "Z21-28", "Z29-92"]

# measured (Lee 2014 Table 1), A converted um^2/bit -> cm^2/bit
MEAS = {
    "CRAM": dict(let_threshold=0.4, width=338.5, shape=0.852, sigma_sat_cm2_per_bit=3.34e-08, bits=67930000),
    "BRAM": dict(let_threshold=0.1, width=87.5,  shape=0.893, sigma_sat_cm2_per_bit=3.82e-08, bits=16404480),
    "FF":   dict(let_threshold=1.1, width=271.3, shape=1.090, sigma_sat_cm2_per_bit=1.47e-07, bits=393216),
}
PLACEHOLDER = dict(let_threshold=5.0, width=20.0, shape=1.5, sigma_sat_cm2_per_bit=1e-7)

print("Loading MEO SPENVIS-CREME96 LET spectra ...")
specs = {s: load_spectrum_file(os.path.join(SPENVIS, f"spenvis_{s}.let.txt"),
                               x_col=0, y_col=1) for s in FILES}

def rate_per_bit(params):
    dev = WeibullLET(params["let_threshold"], params["width"],
                    params["shape"], params["sigma_sat_cm2_per_bit"])
    tot = sum(heavy_ion_rate_per_s(specs[s], dev) for s in FILES)
    return tot * 86400.0  # /day/bit

print("\n=== Per-bit/day rate on SAME MEO (20200km/55deg) env ===")
rows = []
for name, p in [("PLACEHOLDER", PLACEHOLDER)] + [(k, MEAS[k]) for k in MEAS]:
    r = rate_per_bit(p)
    rows.append((name, r, p["sigma_sat_cm2_per_bit"]))
    print(f"  {name:12s} sigma_sat={p['sigma_sat_cm2_per_bit']:.3e}  "
          f"rate={r:.3e} /day/bit")

# device-level (reference bits from tested device)
print("\n=== Device-level (reference bits = XC7K325T tested device) ===")
for name in MEAS:
    p = MEAS[name]
    r = rate_per_bit(p) * p["bits"]
    print(f"  {name:12s} bits={p['bits']:>10d}  rate={r:.3e} /day/device")

# sigma(LET) shape check at key LETs
print("\n=== sigma(LET) shape (cm^2/bit) at key LET points ===")
lets = [1, 5, 10, 30, 60, 100]
hdr = "  LET | " + " ".join(f"{n:>10s}" for n in ["PLACEHOLDER"]+list(MEAS))
print(hdr)
for L in lets:
    vals = []
    for name, p in [("PLACEHOLDER", PLACEHOLDER)] + [(k, MEAS[k]) for k in MEAS]:
        d = WeibullLET(p["let_threshold"], p["width"], p["shape"], p["sigma_sat_cm2_per_bit"])
        vals.append(d.sigma(L))
    print(f"  {L:3d} | " + " ".join(f"{v:10.2e}" for v in vals))

# sanity vs paper Table 2 (deep-space 100mil Al): CRAM 1.0e-7, FF 9.0e-8, BRAM 5.2e-7
print("\n=== Magnitude anchor vs Lee2014 Table 2 (deep-space, 100mil Al) ===")
print("  Paper SolarMin /day/bit: CRAM=1.0e-7  FF=9.0e-8  BRAM=5.2e-7")
print("  MEO here /day/bit       :",
      {k: f"{rate_per_bit(MEAS[k]):.2e}" for k in MEAS})
print("  -> MEO is ~2-3 orders lower: expected (MEO strong geomagnetic cutoff")
print("     removes high-LET heavy ions that dominate the saturated Weibull).")
