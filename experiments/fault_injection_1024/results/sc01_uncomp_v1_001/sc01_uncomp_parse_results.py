#!/usr/bin/env python3
"""Parse SC-01 方案B un-compensated RTL fault-injection logs."""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAT = re.compile(
    r"TRIAL stage=(\d+) symbol=(\d+) component=(\w+) bit=(\d+) detected=(\d+) "
    r"corrected=(\d+) location=(\S+) match=(\d+) category=(\w+)"
)
CATS = ["corrected_bitexact", "corrected_bounded", "detected_only",
        "silent_bounded", "silent_unbounded", "miscorrection"]


def parse_log(path):
    log = HERE / path
    if not log.exists():
        return None
    trials = []
    summaries = []
    with open(log) as f:
        for line in f:
            m = PAT.match(line.strip())
            if m:
                g = m.groups()
                trials.append({
                    "stage": int(g[0]), "symbol": int(g[1]),
                    "component": g[2], "bit": int(g[3]),
                    "detected": int(g[4]), "corrected": int(g[5]),
                    "location": g[6], "match": int(g[7]), "category": g[8],
                })
            if line.startswith("SUMMARY "):
                parts = line.strip().split()
                d = {"metric": parts[1]}
                for p in parts[2:]:
                    k, v = p.split("=")
                    d[k] = float(v) if "." in v and v.replace(".", "", 1).isdigit() else int(v)
                summaries.append(d)
    if not trials and not summaries:
        return None
    counts = Counter(t["category"] for t in trials)
    by_stage = defaultdict(Counter)
    for t in trials:
        by_stage[t["stage"]][t["category"]] += 1
    total = len(trials)
    return {
        "total_trials": total,
        "counts": {c: counts.get(c, 0) for c in CATS},
        "recovery_bitexact_pct": round(100.0 * counts["corrected_bitexact"] / total, 2) if total else 0.0,
        "recovery_bounded_pct": round(100.0 * (counts["corrected_bitexact"] + counts["corrected_bounded"]) / total, 2) if total else 0.0,
        "detection_rate_pct": round(100.0 * (counts["corrected_bitexact"] + counts["corrected_bounded"] + counts["detected_only"]) / total, 2) if total else 0.0,
        "per_stage": {str(s): {c: by_stage[s].get(c, 0) for c in CATS} for s in sorted(by_stage)},
        "summary_lines": summaries,
    }


def main():
    results = {}
    for path in ["sc01_uncomp_run_full_tau8.log", "sc01_uncomp_run_st1_tau8.log"]:
        r = parse_log(path)
        if r:
            results[path] = r
            c = r["counts"]
            print(f"{path}: total={r['total_trials']} "
                  f"bitexact={c['corrected_bitexact']} bounded={c['corrected_bounded']} "
                  f"det_only={c['detected_only']} sil_b={c['silent_bounded']} "
                  f"sil_u={c['silent_unbounded']} miscorr={c['miscorrection']} "
                  f"recov_bitexact={r['recovery_bitexact_pct']}% "
                  f"recov_bounded={r['recovery_bounded_pct']}% "
                  f"detect={r['detection_rate_pct']}%")
    out = HERE / "sc01_uncomp_results.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"written: {out}")


if __name__ == "__main__":
    main()
