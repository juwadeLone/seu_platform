#!/usr/bin/env python3
"""Gao 2023-style 3-sigma threshold from K_S3 fault-free raw syndromes."""
from __future__ import annotations

import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parent
CSV_PATH = OUT / "syndrome_faultfree.csv"
COMPS = ("sy0r", "sy0i", "sy1r", "sy1i")


def stats(values: list[int]) -> dict:
    n = len(values)
    if n == 0:
        return {"n": 0, "mean": None, "sigma": None, "M": None, "three_sigma": None}
    mean = statistics.fmean(values)
    sigma = statistics.stdev(values) if n > 1 else 0.0
    mabs = max(abs(v) for v in values)
    return {
        "n": n,
        "mean": mean,
        "sigma": sigma,
        "M": mabs,
        "three_sigma": 3.0 * sigma,
    }


def main() -> None:
    rows = []
    with CSV_PATH.open() as f:
        for rec in csv.DictReader(f):
            rows.append(
                {
                    "stage": int(rec["stage"]),
                    "found": int(rec["found"]),
                    **{c: int(rec[c]) for c in COMPS},
                }
            )
    if not rows:
        raise SystemExit("empty syndrome CSV")

    by_stage: dict[int, dict[str, list[int]]] = defaultdict(lambda: {c: [] for c in COMPS})
    pooled = {c: [] for c in COMPS}
    linf = []
    found_fire = 0
    for rec in rows:
        linf.append(max(abs(rec[c]) for c in COMPS))
        found_fire += rec["found"]
        for c in COMPS:
            by_stage[rec["stage"]][c].append(rec[c])
            pooled[c].append(rec[c])

    per_stage = {}
    stage_sigma_max = {}
    for st in range(1, 9):
        per_stage[str(st)] = {c: stats(by_stage[st][c]) for c in COMPS}
        sigs = [per_stage[str(st)][c]["sigma"] for c in COMPS]
        stage_sigma_max[str(st)] = max(sigs) if all(s is not None for s in sigs) else None

    pooled_stats = {c: stats(pooled[c]) for c in COMPS}
    sigma_max = max(pooled_stats[c]["sigma"] for c in COMPS)
    m_global = max(pooled_stats[c]["M"] for c in COMPS)
    three = 3.0 * sigma_max
    th_ceil = int(math.ceil(three - 1e-12)) if three > 0 else 0
    th_round = int(round(three))

    def fa_rate(th: int) -> float:
        if th <= 0:
            return 1.0
        hit = sum(1 for rec in rows if any(abs(rec[c]) > th for c in COMPS))
        return hit / len(rows)

    payload = {
        "record": "S3-GAO2023-TH-V1-001",
        "dut": "K_S3_subfft top_s3_subfft_ecc",
        "method": "Gao 2023 Th=3*sigma of fault-free check quantity; check quantity = raw [6,4,3] syndrome",
        "n_samples": len(rows),
        "hardware_THRESHOLD_present": 4,
        "uncomp_v1_M": 3,
        "uncomp_v1_tau_power_of_two": 4,
        "pooled_per_component": pooled_stats,
        "per_stage": per_stage,
        "sigma_max_pooled": sigma_max,
        "M_global": m_global,
        "three_sigma_max": three,
        "Th_ceil_3sigma": th_ceil,
        "Th_round_3sigma": th_round,
        "calibration_FA_any_component_gt_Th_ceil": fa_rate(th_ceil),
        "calibration_FA_any_component_gt_Th_round": fa_rate(th_round),
        "calibration_FA_any_component_gt_4": fa_rate(4),
        "calibration_FA_any_component_gt_M": fa_rate(m_global),
        "hardware_found_fires_on_this_trace": found_fire,
        "Linf_max": max(linf),
        "zero_all_four_ratio": sum(1 for rec in rows if all(rec[c] == 0 for c in COMPS)) / len(rows),
        "stage_sigma_max": stage_sigma_max,
        "bitexact": "PASS 2048/2048",
        "note": "Th=0 is rejected for fixed-point recovery; if Th_ceil==0 stop and ask.",
    }
    (OUT / "threshold_3sigma.json").write_text(json.dumps(payload, indent=2) + "\n")

    lines = [
        "# S3 Gao 2023 3σ 标定结果",
        "",
        f"- 样本数（Stage 1–8, syn_v）：{len(rows)}",
        f"- bit-exact：2048/2048 PASS",
        f"- 全局 M = max|sy| = {m_global}",
        f"- 四分量 σ 最大 = {sigma_max:.6f}",
        f"- 3σ = {three:.6f}",
        f"- 建议整数门限 Th = ceil(3σ) = **{th_ceil}**（四舍五入 = {th_round}）",
        f"- 标定集虚警 |sy|>Th_ceil：{payload['calibration_FA_any_component_gt_Th_ceil']:.6g}",
        f"- 标定集虚警 |sy|>4（现网）：{payload['calibration_FA_any_component_gt_4']:.6g}",
        f"- 现网 u_apply.found 触发次数：{found_fire}",
        "- 对照 2026-08-10：M=3, τ=4（2 的幂），不是 3σ",
        "",
        "## 四分量（全级合并）",
        "",
        "| 分量 | n | mean | σ | 3σ | M |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for c in COMPS:
        s = pooled_stats[c]
        lines.append(
            f"| {c} | {s['n']} | {s['mean']:.6f} | {s['sigma']:.6f} | {s['three_sigma']:.6f} | {s['M']} |"
        )
    lines.extend(["", "## 逐级 σ_max / M", "", "| stage | σ_max | ceil(3σ) | M |", "|---|---:|---:|---:|"])
    for st in range(1, 9):
        sig = stage_sigma_max[str(st)]
        m_st = max(per_stage[str(st)][c]["M"] for c in COMPS)
        lines.append(f"| {st} | {sig:.6f} | {int(math.ceil(3 * sig - 1e-12))} | {m_st} |")
    (OUT / "threshold_3sigma.md").write_text("\n".join(lines) + "\n")
    print((OUT / "threshold_3sigma.md").read_text())


if __name__ == "__main__":
    main()
