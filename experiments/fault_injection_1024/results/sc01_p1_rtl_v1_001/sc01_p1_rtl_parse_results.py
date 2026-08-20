#!/usr/bin/env python3
"""Parse SC-01 P1 RTL fault-injection logs into a summary JSON."""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAT = re.compile(
    r"TRIAL stage=(\d+) symbol=(\d+) component=(\w+) bit=(\d+) detected=(\d+) "
    r"corrected=(\d+) location=(\S+) match=(\d+) category=(\w+)"
)
CATS = ["corrected", "detected_only", "silent_bounded_residual",
        "miscorrection", "silent_unbounded", "corrected_no_flag"]


def parse_log(path, tau, label):
    log = HERE / path
    if not log.exists():
        return None
    trials = []
    summary = None
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
            if line.startswith("SUMMARY threshold="):
                parts = line.strip().split()
                d = {}
                for p in parts[1:]:
                    k, v = p.split("=")
                    d[k] = int(v) if v.replace(".", "", 1).isdigit() else v
                summary = d
    if not trials and not summary:
        return None
    counts = Counter(t["category"] for t in trials)
    by_stage = defaultdict(Counter)
    for t in trials:
        by_stage[t["stage"]][t["category"]] += 1
    total = len(trials)
    return {
        "tau": tau, "label": label,
        "total_trials": total,
        "counts": {c: counts.get(c, 0) for c in CATS},
        "recovery_rate_strict_pct": round(100.0 * counts["corrected"] / total, 2) if total else 0.0,
        "recovery_rate_gao_pct": round(100.0 * (counts["corrected"] + counts["silent_bounded_residual"]) / total, 2) if total else 0.0,
        "per_stage": {str(s): {c: by_stage[s].get(c, 0) for c in CATS} for s in sorted(by_stage)},
        "summary_line": summary,
    }


def main():
    results = []
    candidates = [
        ("sc01_p1_rtl_run_full_tau0.log", 0, "full 3360 (tau=0)"),
        ("sc01_p1_rtl_run_s10_tau0.log", 0, "stage10 420 (tau=0)"),
        ("sc01_p1_rtl_run_st17_tau0.log", 0, "stages1-7 2940 (tau=0)"),
        ("sc01_p1_rtl_run_tau1.log", 1, "full 3360 (tau=1)"),
    ]
    for path, tau, label in candidates:
        r = parse_log(path, tau, label)
        if r:
            results.append(r)
            print(f"{label}: total={r['total_trials']} corrected={r['counts']['corrected']} "
                  f"det_only={r['counts']['detected_only']} silent_b={r['counts']['silent_bounded_residual']} "
                  f"silent_u={r['counts']['silent_unbounded']} miscorr={r['counts']['miscorrection']} "
                  f"strict={r['recovery_rate_strict_pct']}% gao={r['recovery_rate_gao_pct']}%")
    out = HERE / "sc01_p1_rtl_results.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"written: {out}")


if __name__ == "__main__":
    main()
