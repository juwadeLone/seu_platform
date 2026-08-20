"""WP3 hand scan: cross-stage rate vs a0 and theta. Trend only, not statistics."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from layout_ecc.functional import ensure_golden
from layout_ecc.functional_mapper import classify_strike_faults, map_flipped, replay_strike
from layout_ecc.layout_import import load_primitive_map
from layout_ecc.strike import run_strike

CSV = ROOT / "data" / "layout" / "p1_ooc_win" / "primitive_map.csv"
OUT = ROOT / "data" / "wp3_cross_stage_scan.json"


def main():
    layout = load_primitive_map(str(CSV))
    golden = ensure_golden()
    x0, y0 = layout["default_x0"], layout["default_y0"]
    a0s = [4, 8, 12, 16, 20]
    thetas = [0, 45, 60]
    n_seed = 20
    cells = []
    for a0 in a0s:
        for theta in thetas:
            n_cross = 0
            n_ok = 0
            for seed in range(n_seed):
                out = run_strike(layout, x0, y0, 15, theta, 30, a0=a0, seed=seed)
                recs = map_flipped(out["flipped"], strike_id=f"a{a0}t{theta}s{seed}")
                summary = classify_strike_faults(recs)
                n_ok += 1
                if summary["cross_stage"]:
                    n_cross += 1
            cells.append({
                "a0": a0, "theta": theta, "n": n_ok,
                "cross_stage_rate": n_cross / n_ok if n_ok else 0.0,
            })
    # one closed-loop replay
    demo = run_strike(layout, x0, y0, 15, 45, 30, a0=12, seed=1)
    _recs, demo_sum = replay_strike(
        demo["flipped"], golden=golden, max_inject=4, strike_id="demo")
    payload = {
        "x0": x0, "y0": y0, "n_seed": n_seed,
        "cells": cells,
        "demo": {
            "n_flipped": demo["n_flipped"],
            "stages": demo_sum["stages"],
            "roles": demo_sum["roles"],
            "outcomes": demo_sum["outcomes"],
            "preview_class": demo["preview_class"],
        },
        "note": "trend scan only; not a fitted sigma or mission rate",
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"{'a0':>4} {'th':>4} {'rate':>8}")
    for c in cells:
        print(f"{c['a0']:4d} {c['theta']:4d} {c['cross_stage_rate']:8.3f}")
    print("demo stages", demo_sum["stages"], "outcomes", demo_sum["outcomes"])
    # monotonic-in-a0 check at theta=45
    sub = [c["cross_stage_rate"] for c in cells if c["theta"] == 45]
    print("theta=45 rates", sub, "nondecreasing", all(
        sub[i] <= sub[i + 1] + 0.15 for i in range(len(sub) - 1)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
