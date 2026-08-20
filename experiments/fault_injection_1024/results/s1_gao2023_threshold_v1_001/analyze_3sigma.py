#!/usr/bin/env python3
"""Gao 2023-style 3-sigma threshold from a fault-free syndrome CSV."""
from __future__ import annotations

import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parent
CSV_PATH = OUT / "syndrome_faultfree.csv"
RECORD = sys.argv[1] if len(sys.argv) > 1 else "UNKNOWN"
DUT = sys.argv[2] if len(sys.argv) > 2 else ""


def stats(values: list[int]) -> dict:
    n = len(values)
    if n == 0:
        return {"n": 0, "mean": None, "sigma": None, "M": None, "three_sigma": None}
    mean = statistics.fmean(values)
    sigma = statistics.stdev(values) if n > 1 else 0.0
    mabs = max(abs(v) for v in values)
    return {"n": n, "mean": mean, "sigma": sigma, "M": mabs, "three_sigma": 3.0 * sigma}


def main() -> None:
    with CSV_PATH.open() as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        comps = [c for c in fieldnames if c not in ("cycle", "stage", "found")]
        rows = []
        for rec in reader:
            found_raw = rec.get("found") or "0"
            try:
                found_i = int(found_raw)
            except ValueError:
                found_i = 0
            try:
                rows.append(
                    {
                        "stage": int(rec["stage"]),
                        "found": found_i,
                        **{c: int(rec[c]) for c in comps},
                    }
                )
            except ValueError:
                continue
    if not rows:
        raise SystemExit("empty syndrome CSV")

    by_stage: dict[int, dict[str, list[int]]] = defaultdict(lambda: {c: [] for c in comps})
    pooled = {c: [] for c in comps}
    linf = []
    found_fire = 0
    for rec in rows:
        linf.append(max(abs(rec[c]) for c in comps))
        found_fire += rec["found"]
        for c in comps:
            by_stage[rec["stage"]][c].append(rec[c])
            pooled[c].append(rec[c])

    stages = sorted(by_stage)
    per_stage = {}
    stage_sigma_max = {}
    for st in stages:
        per_stage[str(st)] = {c: stats(by_stage[st][c]) for c in comps}
        sigs = [per_stage[str(st)][c]["sigma"] for c in comps]
        stage_sigma_max[str(st)] = max(s for s in sigs if s is not None)

    pooled_stats = {c: stats(pooled[c]) for c in comps}
    sigma_max = max(pooled_stats[c]["sigma"] for c in comps)
    m_global = max(pooled_stats[c]["M"] for c in comps)
    three = 3.0 * sigma_max
    th_ceil = int(math.ceil(three - 1e-12)) if three > 0 else 0
    th_round = int(round(three))

    def fa_rate(th: int) -> float:
        if th <= 0:
            return 1.0
        hit = sum(1 for rec in rows if any(abs(rec[c]) > th for c in comps))
        return hit / len(rows)

    payload = {
        "record": RECORD,
        "dut": DUT,
        "method": "Gao 2023 Th=3*sigma of fault-free check quantity",
        "components": comps,
        "n_samples": len(rows),
        "pooled_per_component": pooled_stats,
        "per_stage": per_stage,
        "sigma_max_pooled": sigma_max,
        "M_global": m_global,
        "three_sigma_max": three,
        "Th_ceil_3sigma": th_ceil,
        "Th_round_3sigma": th_round,
        "calibration_FA_any_component_gt_Th_ceil": fa_rate(th_ceil),
        "calibration_FA_any_component_gt_Th_round": fa_rate(th_round),
        "hardware_found_fires_on_this_trace": found_fire,
        "Linf_max": max(linf),
        "stage_sigma_max": stage_sigma_max,
        "note": "Th=0 is rejected for fixed-point recovery; if Th_ceil==0 stop and ask.",
    }
    (OUT / "threshold_3sigma.json").write_text(json.dumps(payload, indent=2) + "\n")

    lines = [
        f"# {RECORD} Gao 2023 3σ 标定结果",
        "",
        f"- DUT：{DUT}",
        f"- 样本数：{len(rows)}",
        f"- 全局 M = max|sy| = {m_global}",
        f"- 分量 σ 最大 = {sigma_max:.6f}",
        f"- 3σ = {three:.6f}",
        f"- 建议整数门限 Th = ceil(3σ) = **{th_ceil}**（四舍五入 = {th_round}）",
        f"- 标定集虚警 |sy|>Th_ceil：{payload['calibration_FA_any_component_gt_Th_ceil']:.6g}",
        f"- 现网 found 触发次数：{found_fire}",
        "",
        "## 分量（全级合并）",
        "",
        "| 分量 | n | mean | σ | 3σ | M |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for c in comps:
        s = pooled_stats[c]
        lines.append(
            f"| {c} | {s['n']} | {s['mean']:.6f} | {s['sigma']:.6f} | {s['three_sigma']:.6f} | {s['M']} |"
        )
    lines.extend(["", "## 逐级 σ_max / M", "", "| stage | n | σ_max | ceil(3σ) | M |", "|---|---:|---:|---:|---:|"])
    for st in stages:
        sig = stage_sigma_max[str(st)]
        m_st = max(per_stage[str(st)][c]["M"] for c in comps)
        n_st = per_stage[str(st)][comps[0]]["n"]
        lines.append(f"| {st} | {n_st} | {sig:.6f} | {int(math.ceil(3 * sig - 1e-12))} | {m_st} |")
    (OUT / "threshold_3sigma.md").write_text("\n".join(lines) + "\n")
    print((OUT / "threshold_3sigma.md").read_text())
    if th_ceil == 0:
        raise SystemExit("Th_ceil=0; stop and ask (fixed-point must have a threshold).")


if __name__ == "__main__":
    main()
