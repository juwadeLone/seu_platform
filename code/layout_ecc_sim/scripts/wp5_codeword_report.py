"""WP5: count inferred vs proxy codewords on the P1 layout."""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from layout_ecc.functional import inject_and_classify
from layout_ecc.layout_import import load_primitive_map

CSV = ROOT / "data" / "layout" / "p1_ooc_win" / "primitive_map.csv"
OUT = ROOT / "data" / "wp5_codeword_report.json"


def main():
    layout = load_primitive_map(str(CSV))
    conf = Counter()
    scheme = Counter()
    proxy_roles = Counter()
    inferred = 0
    for t in layout["tiles"]:
        c = t.get("codeword_confidence") or "proxy"
        conf[c] += 1
        if c == "inferred":
            inferred += 1
            scheme[t.get("codeword_scheme") or "?"] += 1
        else:
            proxy_roles[t.get("module_role") or "?"] += 1
    n = len(layout["tiles"])
    single = inject_and_classify(
        {"stage_id": 1, "module_role": "butterfly", "domain": "FF_STATE",
         "bit": 0, "symbol": 0})
    dual = inject_and_classify(
        {"stage_id": 4, "module_role": "ecc", "domain": "FF_STATE",
         "bit": 3, "symbol": 0, "n_faults": 2})
    payload = {
        "n_sites": n,
        "inferred_sites": inferred,
        "inferred_frac": inferred / n,
        "confidence": dict(conf),
        "inferred_schemes": dict(scheme),
        "proxy_roles": dict(proxy_roles),
        "proxy_reasons": {
            "CFG": "no essential-bit names in primitive_map.csv; needs bitstream/SEM",
            "control/twiddle LUT cones": "ii_s/rr_s and control FFs have no symbol index",
            "unknown/GND": "tie-offs",
        },
        "inject_cross_check": {
            "same_codeword_one_symbol": {
                "codeword_id": "s1:arith", "symbol_id": 0,
                "outcome": single["outcome"],
            },
            "same_codeword_two_symbols": {
                "codeword_id": "s4:arith", "symbol_ids": [0, 1],
                "outcome": dual["outcome"],
            },
        },
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")
    print("inferred", inferred, f"({100*inferred/n:.1f}%) of", n, "sites")
    print("schemes", dict(scheme))
    print("proxy by role", dict(proxy_roles))
    print("inject", single["outcome"], dual["outcome"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
