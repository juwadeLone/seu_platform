"""WP6: dump SDF delay table."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from layout_ecc.lifetime import delay_table, map_cycle, masked_by_lifetime

OUT = ROOT / "data" / "wp6_lifetime.json"


def main():
    table = delay_table()
    examples = []
    for stage, cyc, addr, lane, role in (
        (1, 0, 0, 0, "delay"),
        (5, 40, 3, 2, "delay"),
        (8, 9, None, 0, "replica"),
        (10, 4, 1, 3, "ecc"),
    ):
        ident = map_cycle(stage, cyc, address=addr, lane=lane)
        ident.update(masked_by_lifetime(ident, role))
        examples.append(ident)
    payload = {"table": table, "examples": examples}
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")
    print("depth", table["depth_by_stage"])
    print("source", table["source"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
