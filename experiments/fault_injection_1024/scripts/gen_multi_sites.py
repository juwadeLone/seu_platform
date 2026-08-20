#!/usr/bin/env python3
"""Generate the N08 multi-stage fault-site tables.

This is only a deterministic site-table generator.  Fault injection remains in
the SystemVerilog RTL testbench; this script does not simulate or alter data.
"""
from __future__ import annotations

import argparse
import csv
import random
from collections import Counter
from pathlib import Path


def make_sites(seed: int, arch: str, k: int, trials: int):
    stages = list(range(1, 9)) if arch == "s3" else [1, 2, 3, 4, 5, 6, 7, 10]
    rng = random.Random(seed + (0 if arch == "s3" else 1009) + 31 * k)
    stage_ring = stages[:]
    symbols = list(range(6))
    bits = list(range(35))
    rng.shuffle(stage_ring)
    rng.shuffle(symbols)
    rng.shuffle(bits)
    rows = []
    event = 0
    for trial in range(trials):
        # Advance continuously through the shuffled ring.  This makes the
        # stage marginal exact whenever the total event count is divisible by
        # the eight eligible stages, while preserving a seed-dependent order.
        start = (trial * k) % len(stages)
        selected = [stage_ring[(start + j) % len(stages)] for j in range(k)]
        fields = []
        for stage in selected:
            fields.append((stage, symbols[event % 6], (event // 6) % 2, bits[event % 35]))
            event += 1
        rows.append((trial, fields))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260814)
    ap.add_argument("--arch", choices=("s3", "p1"), required=True)
    ap.add_argument("--k", type=int, choices=(2, 5, 8), required=True)
    ap.add_argument("--trials", type=int, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ns = ap.parse_args()
    rows = make_sites(ns.seed, ns.arch, ns.k, ns.trials)
    ns.out.parent.mkdir(parents=True, exist_ok=True)
    with ns.out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["trial", "sites(stage:symbol:component:bit;...)"])
        for trial, fields in rows:
            w.writerow([trial, ";".join(": ".replace(" ", "").join(map(str, x)) for x in fields)])

    stage_count = Counter(x[0] for _, fs in rows for x in fs)
    symbol_count = Counter(x[1] for _, fs in rows for x in fs)
    component_count = Counter(x[2] for _, fs in rows for x in fs)
    bit_count = Counter(x[3] for _, fs in rows for x in fs)
    print(f"arch={ns.arch} k={ns.k} trials={ns.trials} events={ns.k * ns.trials}")
    print("stage_counts=" + ",".join(f"{s}:{stage_count[s]}" for s in sorted(stages_for(ns.arch))))
    print("symbol_counts=" + ",".join(f"{s}:{symbol_count[s]}" for s in range(6)))
    print("component_counts=" + ",".join(f"{s}:{component_count[s]}" for s in range(2)))
    print(f"bit_min={min(bit_count.values())} bit_max={max(bit_count.values())}")
    return 0


def stages_for(arch: str):
    return range(1, 9) if arch == "s3" else (1, 2, 3, 4, 5, 6, 7, 10)


if __name__ == "__main__":
    raise SystemExit(main())
