"""WP4 geometry metrics. No injection, no Vivado.

Usage: python scripts/wp4_geometry_metrics.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from layout_ecc.geom_metrics import (
    compute_all, explain_saturation, geometric_cross_scan, stage_bboxes,
    stage_points,
)
from layout_ecc.layout_import import load_primitive_map

CSV = ROOT / "data" / "layout" / "p1_ooc_win" / "primitive_map.csv"
WP3 = ROOT / "data" / "wp3_cross_stage_scan.json"
OUT = ROOT / "data" / "wp4_geometry.json"


def main():
    print("loading", CSV, flush=True)
    layout = load_primitive_map(str(CSV))
    print("layout loaded", layout["n_sites"], "sites", flush=True)
    geo = compute_all(layout)
    print("bboxes/adjacency/distance done", flush=True)
    a0s = [4, 8, 12, 16, 20]
    thetas = [0, 45, 60]
    scan = geometric_cross_scan(layout, a0s, thetas, n_uniform=80, seed=1)
    boxes = {int(k): v for k, v in geo["bboxes"].items()}
    explain = explain_saturation(
        boxes, geo["adjacency"], geo["min_distance"],
        adj8=geo.get("adjacency_diag"))
    wp3 = json.loads(WP3.read_text(encoding="utf-8")) if WP3.is_file() else {}
    wp3_map = {(c["a0"], c["theta"]): c["cross_stage_rate"]
               for c in wp3.get("cells", [])}
    compare = []
    for c in scan["cells"]:
        compare.append({
            "a0": c["a0"], "theta": c["theta"],
            "wp3_flip_cross_rate": wp3_map.get((c["a0"], c["theta"])),
            "geom_centroid_n_stages": c["centroid_n_stages"],
            "geom_centroid_cross": c["centroid_cross"],
            "geom_uniform_cross_rate": c["uniform_cross_rate"],
            "geom_uniform_mean_n_stages": c["uniform_mean_n_stages"],
        })
    # drop full point lists from the archive json (too large); keep bboxes
    payload = {
        "note": "RPM grid units, not microns. No injection.",
        "bboxes": geo["bboxes"],
        "adjacency": geo["adjacency"],
        "adjacency_diag": geo.get("adjacency_diag"),
        "min_distance": geo["min_distance"],
        "explain_a0_ge_8": explain,
        "geometric_scan": scan,
        "vs_wp3": compare,
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")
    print("stage thickness (min of bbox w,h) and n_sites:")
    for st in range(1, 11):
        b = boxes.get(st)
        if not b:
            continue
        print(f"  s{st}: n={b['n_sites']:5d}  "
              f"{b['width']:3d}x{b['height']:3d}  thick={b['thickness']:3d}  "
              f"cx={b['centroid_x']:.1f} cy={b['centroid_y']:.1f}")
    print("adjacency (shared 4-neighbour edges):")
    if geo["adjacency"]:
        for e in geo["adjacency"]:
            print(f"  s{e['a']}-s{e['b']}: {e['shared_edges']}")
    else:
        print("  (none)")
    print("adjacency (8-neighbour / diagonal):")
    for e in geo.get("adjacency_diag") or []:
        print(f"  s{e['a']}-s{e['b']}: {e['shared_edges']}")
    if not geo.get("adjacency_diag"):
        print("  (none)")
    print("consecutive min dist:")
    mat = geo["min_distance"]["matrix"]
    sts = geo["min_distance"]["stages"]
    for i in range(len(sts) - 1):
        print(f"  s{sts[i]}-s{sts[i+1]}: {mat[i][i+1]}")
    print(explain["reason"])
    print(f"{'a0':>4} {'th':>4} {'wp3':>8} {'geomU':>8} {'centN':>6}")
    for c in compare:
        w = c["wp3_flip_cross_rate"]
        print(f"{c['a0']:4d} {c['theta']:4d} "
              f"{(w if w is not None else -1):8.3f} "
              f"{c['geom_uniform_cross_rate']:8.3f} "
              f"{c['geom_centroid_n_stages']:6d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
