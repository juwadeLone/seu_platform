"""WP9: bernoulli vs MBU pattern flips on the WP8 anchored kernel.

Usage: python scripts/wp9_pattern_compare.py
"""
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from layout_ecc.functional_mapper import classify_strike_faults, map_flipped
from layout_ecc.layout_import import load_primitive_map
from layout_ecc.mbu_patterns import distribution_table
from layout_ecc.strike import run_strike
from layout_ecc.units import LET_REF, constants_passport

CSV = ROOT / "data" / "layout" / "p1_ooc_win" / "primitive_map.csv"
OUT = ROOT / "data" / "wp9_pattern_compare.json"
THETA = 45.0
PHI = 30.0
LET = LET_REF
N_SEED = 20
# Pattern needs a kernel large enough to have k candidates. SRAM-cluster
# A(LET=15) is sub-site; use a modest floor so k-sampling is observable,
# tagged as a scan-only enlargement (not a new physics claim).
PATTERN_AREA_FLOOR_UM2 = 1300.0
PATTERN_AREA_FLOOR_NOTE = (
    "assumption for this scan only: Radaelli SRAM-cluster areas are "
    "<< one FPGA site (WP8: anchored mean coverage = 1 site), so k>1 "
    "would only hit multiple domains of the same Site (same symbol_id). "
    "Floor A=1300 µm² is ~2.5 RPM-grid radii at RPM_TO_UM=8, enough to "
    "reach a neighbour Site so pattern vs bernoulli can differ on "
    "same-codeword multi-symbol. Not a literature area."
)


def occupied_centres(layout, n, seed):
    pts = [(t["x"] + 0.5, t["y"] + 0.5)
           for t in layout["tiles"]
           if t.get("is_used") and int(t.get("stage_id") or -1) > 0]
    rng = random.Random(seed)
    return [pts[rng.randrange(len(pts))] for _ in range(n)] if pts else []


def one(layout, x0, y0, seed, flip_model, shape=None):
    return run_strike(
        layout, x0, y0, LET, THETA, PHI, a0=12.0, seed=seed,
        kernel_model="anchored", area_um2=PATTERN_AREA_FLOOR_UM2,
        flip_model=flip_model, pattern_shape=shape or "cluster",
    )


def pack(out):
    recs = map_flipped(out["flipped"], strike_id="w")
    cls = classify_strike_faults(recs)
    return {
        "n_flipped": out["n_flipped"],
        "n_sites_covered": out["n_sites_covered"],
        "cross_stage": bool(cls["cross_stage"]),
        "n_multi_symbol": len(cls["same_codeword_multi_symbol"]),
        "has_multi_symbol": bool(cls["same_codeword_multi_symbol"]),
        "pattern_k": out.get("pattern_k"),
        "k_hist_key": out.get("pattern_k") if out.get("pattern_k") is not None
        else out["n_flipped"],
    }


def rate(rows, key):
    return sum(1 for r in rows if r[key]) / len(rows) if rows else 0.0


def mean(rows, key):
    return sum(r[key] for r in rows) / len(rows) if rows else 0.0


def main():
    print("loading", CSV, flush=True)
    layout = load_primitive_map(str(CSV))
    centres = occupied_centres(layout, N_SEED, seed=1)
    bern, clus, uni = [], [], []
    for i, (x0, y0) in enumerate(centres):
        seed = i + 1
        bern.append(pack(one(layout, x0, y0, seed, "bernoulli")))
        clus.append(pack(one(layout, x0, y0, seed, "pattern", "cluster")))
        uni.append(pack(one(layout, x0, y0, seed, "pattern", "uniform")))
        print(f"seed {seed:02d} bern k={bern[-1]['n_flipped']:3d} "
              f"cluster k={clus[-1]['n_flipped']} "
              f"msym {clus[-1]['has_multi_symbol']}", flush=True)

    def block(rows, name):
        hist = Counter(r["k_hist_key"] for r in rows)
        return {
            "name": name,
            "mean_n_flipped": mean(rows, "n_flipped"),
            "cross_stage_rate": rate(rows, "cross_stage"),
            "same_codeword_multi_symbol_rate": rate(rows, "has_multi_symbol"),
            "mean_n_multi_symbol_codewords": mean(rows, "n_multi_symbol"),
            "k_histogram": {str(k): int(v) for k, v in sorted(hist.items())},
        }

    payload = {
        "note": "Anchored kernel with site-scale area floor; see area_floor_note.",
        "let": LET, "theta": THETA, "phi": PHI, "n_seed": N_SEED,
        "area_um2": PATTERN_AREA_FLOOR_UM2,
        "area_floor_note": PATTERN_AREA_FLOOR_NOTE,
        "distribution": distribution_table(),
        "passport": constants_passport()["rpm_to_um"],
        "bernoulli": block(bern, "bernoulli"),
        "pattern_cluster": block(clus, "pattern_cluster"),
        "pattern_uniform": block(uni, "pattern_uniform"),
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("wrote", OUT)
    for key in ("bernoulli", "pattern_cluster", "pattern_uniform"):
        b = payload[key]
        print(f"{key}: flips={b['mean_n_flipped']:.2f} "
              f"cross={b['cross_stage_rate']:.3f} "
              f"multi_sym={b['same_codeword_multi_symbol_rate']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
