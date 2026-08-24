#!/usr/bin/env python3
"""FREE executor: end-to-end SEU strike -> classification pipeline.

This is the runnable "executor" of the layout_ecc_sim platform. It loads the
P1 OOC proxy layout, fires one (or a sweep of) particle strikes with an
elliptical kernel, maps the flipped bits to functional faults, and classifies
the outcome (CORRECTED / DUE / SDC / MASKED) per the per-stage ECC model.

Exit code 0 means the pipeline ran and produced a result file.
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from layout_ecc.layout_import import load_primitive_map  # noqa: E402
from layout_ecc.strike import run_strike, g4_presets     # noqa: E402
from layout_ecc.functional_mapper import replay_strike    # noqa: E402
from layout_ecc.functional import ensure_golden            # noqa: E402

CSV = os.path.join(
    ROOT, "data", "layout", "p1_ooc_win", "primitive_map.csv")
GOLDEN = os.path.join(ROOT, "data", "golden", "p1_random_seeded.json")


def load_layout(verbose=True):
    if verbose:
        print(f"[load] {CSV}")
    t0 = time.time()
    layout = load_primitive_map(CSV)
    if verbose:
        print(f"[load] {layout['ncols']}x{layout['nrows']} grid, "
              f"{len(layout['tiles'])} sites, "
              f"{time.time()-t0:.2f}s")
    return layout


def fire(layout, x0, y0, a0, let=20.0, theta=45.0, phi=0.0, seed=1,
         kernel_model="legacy_linear", flip_model="bernoulli",
         verbose=True):
    if verbose:
        print(f"[strike] center=({x0:.1f},{y0:.1f}) a0={a0} "
              f"LET={let} theta={theta} phi={phi} seed={seed} "
              f"kernel={kernel_model} flip={flip_model}")
    t0 = time.time()
    res = run_strike(
        layout, x0=x0, y0=y0, let=let, theta_deg=theta, phi_deg=phi,
        a0=a0, seed=seed, kernel_model=kernel_model, flip_model=flip_model)
    # sub-cell kernel check: physical radius (anchored) vs one grid cell
    if res.get("radius_um") is not None and res.get("rpm_to_um"):
        half_grid = res["radius_um"] / res["rpm_to_um"]
        res["_sub_cell"] = half_grid < 1.0
        if verbose and res["_sub_cell"]:
            print(f"[WARN] kernel normal-incidence half-axis={half_grid:.3f} "
                  f"grid cells < 1 cell; physical kernel smaller than an "
                  f"occupied cell at RPM_TO_UM={res['rpm_to_um']} µm/grid -> "
                  f"0 candidate intersections (uncalibrated scale; use "
                  f"legacy_linear a0 for grid-space sweeping)")
    if verbose:
        print(f"[strike] candidates={res['n_candidates']} "
              f"flipped={res['n_flipped']} stages_hit={res['stages_hit']} "
              f"preview={res['preview_class']} ({time.time()-t0:.3f}s)")
    return res


def classify(res, golden, max_inject=8, verbose=True):
    if verbose:
        print(f"[replay] mapping {len(res['flipped'])} flipped bits -> "
              f"functional faults")
    t0 = time.time()
    records, summary = replay_strike(
        res["flipped"], golden=golden, max_inject=max_inject, strike_id="s0")
    summary["proxy"] = res["proxy"]
    summary["run_meta"] = {
        "x0": res["x0"], "y0": res["y0"], "a0": res["a0"],
        "let": res["let"], "theta_deg": res["theta_deg"],
        "phi_deg": res["phi_deg"], "seed": res["seed"],
        "kernel_model": res["kernel_model"],
        "flip_model": res["flip_model"],
        "area_um2": res.get("area_um2"),
        "radius_um": res.get("radius_um"),
        "n_candidates": res["n_candidates"],
        "n_flipped": res["n_flipped"],
        "preview_class": res["preview_class"],
        "stages_hit": res["stages_hit"],
    }
    if verbose:
        print(f"[replay] faults={summary['n_faults']} "
              f"cross_stage={summary['cross_stage']} "
              f"outcomes={summary.get('outcomes')} "
              f"({time.time()-t0:.3f}s)")
    return records, summary


def main():
    ap = argparse.ArgumentParser(description="FREE SEU executor")
    ap.add_argument("--x0", type=float, default=None, help="strike center x")
    ap.add_argument("--y0", type=float, default=None, help="strike center y")
    ap.add_argument("--a0", type=float, default=12.0, help="kernel half-axis")
    ap.add_argument("--let", type=float, default=20.0)
    ap.add_argument("--theta", type=float, default=45.0)
    ap.add_argument("--phi", type=float, default=0.0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--kernel", default="legacy_linear",
                    choices=["legacy_linear", "anchored"])
    ap.add_argument("--flip", default="bernoulli",
                    choices=["bernoulli", "pattern"])
    ap.add_argument("--preset", default=None,
                    help="named preset from g4_presets (e.g. multi_tile)")
    ap.add_argument("--out", default=os.path.join(ROOT, "data",
                    "free_exec_result.json"))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    v = not args.quiet

    layout = load_layout(verbose=v)
    golden = ensure_golden(os.path.join(ROOT, "data", "golden"))
    if v:
        print(f"[golden] {golden['sha256']}")

    # resolve center: explicit > preset > occupancy centroid
    if args.preset:
        presets = g4_presets(layout)
        if args.preset not in presets:
            sys.exit(f"unknown preset {args.preset}; have "
                     f"{sorted(presets)}")
        p = presets[args.preset]
        x0, y0, a0 = p["x0"], p["y0"], p.get("a0", args.a0)
        if v:
            print(f"[preset] {args.preset}: {p['label']}")
    elif args.x0 is not None and args.y0 is not None:
        x0, y0, a0 = args.x0, args.y0, args.a0
    else:
        # occupancy centroid (consistent with WP3/WP4)
        xs = [t["x"] + 0.5 for t in layout["tiles"] if t["is_used"]]
        ys = [t["y"] + 0.5 for t in layout["tiles"] if t["is_used"]]
        x0, y0, a0 = sum(xs) / len(xs), sum(ys) / len(ys), args.a0
        if v:
            print(f"[center] occupancy centroid=({x0:.1f},{y0:.1f})")

    res = fire(layout, x0, y0, a0, let=args.let, theta=args.theta,
               phi=args.phi, seed=args.seed, kernel_model=args.kernel,
               flip_model=args.flip, verbose=v)
    records, summary = classify(res, golden, verbose=v)

    payload = {
        "layout": "p1_ooc_win (xc7vx690tffg1761-2, Vivado 2018.3 OOC)",
        "records": records,
        "summary": summary,
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    if v:
        print(f"[done] wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
