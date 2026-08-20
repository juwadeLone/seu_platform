"""WP8: legacy_linear vs anchored kernel. Does not overwrite wp3/wp4.

Usage: python scripts/wp8_kernel_compare.py
"""
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from layout_ecc.functional_mapper import classify_strike_faults, map_flipped
from layout_ecc.layout_import import load_primitive_map
from layout_ecc.strike import run_strike
from layout_ecc.units import constants_passport, let_to_area_table, radaelli_fit

CSV = ROOT / "data" / "layout" / "p1_ooc_win" / "primitive_map.csv"
OUT = ROOT / "data" / "wp8_kernel_compare.json"
THETA = 45.0
PHI = 30.0
LEGACY_A0 = 12.0
N_SEED = 20


def occupied_centres(layout, n, seed):
    pts = [(t["x"] + 0.5, t["y"] + 0.5)
           for t in layout["tiles"]
           if t.get("is_used") and int(t.get("stage_id") or -1) > 0]
    rng = random.Random(seed)
    return [pts[rng.randrange(len(pts))] for _ in range(n)] if pts else []


def summarise(out):
    recs = map_flipped(out["flipped"], strike_id="w")
    cls = classify_strike_faults(recs)
    return {
        "n_sites_covered": out["n_sites_covered"],
        "n_flipped": out["n_flipped"],
        "n_candidates": out["n_candidates"],
        "cross_stage": cls["cross_stage"],
        "n_stages": cls["n_stages"],
        "a": out["a"], "b": out["b"],
        "area_um2": out.get("area_um2"),
        "a0_eq_grid": out.get("a0_eq_grid"),
    }


def mean(rows, key):
    xs = [r[key] for r in rows]
    return sum(xs) / len(xs) if xs else 0.0


def main():
    print("kernel_model default is still legacy_linear", flush=True)
    print("loading", CSV, flush=True)
    layout = load_primitive_map(str(CSV))
    centres = occupied_centres(layout, N_SEED, seed=1)
    print("uniform occupied centres", len(centres), "theta", THETA, flush=True)
    table = let_to_area_table()
    cells = []
    for row in table:
        let = row["let"]
        legacy_rows, anchored_rows = [], []
        for i, (x0, y0) in enumerate(centres):
            leg = run_strike(layout, x0, y0, let, THETA, PHI, a0=LEGACY_A0,
                             seed=i + 1, kernel_model="legacy_linear")
            anc = run_strike(layout, x0, y0, let, THETA, PHI, a0=LEGACY_A0,
                             seed=i + 1, kernel_model="anchored")
            legacy_rows.append(summarise(leg))
            anchored_rows.append(summarise(anc))
        cell = {
            "let": let,
            "area_um2_anchored": row["area_um2"],
            "legacy_a0": LEGACY_A0,
            "n": N_SEED,
            "legacy": {
                "mean_n_sites": mean(legacy_rows, "n_sites_covered"),
                "mean_n_flipped": mean(legacy_rows, "n_flipped"),
                "cross_stage_rate": mean(legacy_rows, "cross_stage"),
                "mean_b_grid": mean(legacy_rows, "b"),
            },
            "anchored": {
                "mean_n_sites": mean(anchored_rows, "n_sites_covered"),
                "mean_n_flipped": mean(anchored_rows, "n_flipped"),
                "cross_stage_rate": mean(anchored_rows, "cross_stage"),
                "mean_b_grid": mean(anchored_rows, "b"),
                "a0_eq_grid": anchored_rows[0]["a0_eq_grid"] if anchored_rows else None,
            },
        }
        ls = cell["legacy"]["mean_n_sites"]
        ans = cell["anchored"]["mean_n_sites"]
        cell["site_overestimate_ratio"] = (ls / ans) if ans else None
        cells.append(cell)
        print(f"LET={let:5.1f}  A={row['area_um2']:.3f} um2  "
              f"legacy sites={ls:.1f}  anchored sites={ans:.2f}  "
              f"ratio={cell['site_overestimate_ratio']}", flush=True)
    fit = radaelli_fit()
    payload = {
        "note": "Uniform occupied centres, not occupancy centroid. "
                "Does not overwrite wp3/wp4.",
        "theta": THETA, "phi": PHI, "n_seed": N_SEED,
        "legacy_a0": LEGACY_A0,
        "passport": constants_passport(),
        "radaelli_fit": {
            "alpha": fit["alpha"], "c": fit["c"],
            "rmse_um2": fit["rmse_um2"],
            "residuals_um2": fit["residuals_um2"],
        },
        "cells": cells,
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("wrote", OUT)
    print("alpha", f"{fit['alpha']:.4f}", "rmse", f"{fit['rmse_um2']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
