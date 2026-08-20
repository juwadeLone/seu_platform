"""WP2: one FF flip per stage, write deviation table. Does not edit experiments/."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from layout_ecc.functional import ensure_golden, scan_one_bit_per_stage

OUT = ROOT / "data" / "wp2_stage_scan.json"


def main():
    golden = ensure_golden()
    rows = scan_one_bit_per_stage(golden)
    payload = {
        "golden_sha256": golden["sha256"],
        "rows": [
            {k: v for k, v in r.items()
             if k not in ("note",)} | {"note": r["note"]}
            for r in rows
        ],
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"{'st':>3} {'outcome':<12} {'dev':>12} {'>2':>8} {'>3':>8}")
    for r in rows:
        print(f"{r['stage_id']:3d} {r['outcome']:<12} "
              f"{r['max_output_deviation']:12d} "
              f"{r['frac_over_threshold_2']:8.3f} "
              f"{r['frac_over_threshold_3']:8.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
