#!/usr/bin/env python3
"""SC-01 Diagnostic: Scan syndrome distribution for threshold derivation.

For S3 arithmetic ECC groups (stages 1-8, positions [0, 63, 127, 255]):
  1. Capture no-fault syndrome (= expected_residual, should be WIDE_ZERO after compensation)
  2. For each single-bit flip (symbol 0-5, component real/imag, bit 0-34):
     record the syndrome components (sy0_real, sy0_imag, sy1_real, sy1_imag)
  3. Output distribution statistics

This tells us:
  - The no-fault residual magnitude (should be 0 after compensation)
  - The minimum |syndrome| from any single-bit flip (threshold upper bound)
  - The distribution of syndrome magnitudes
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

EXPERIMENT = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENT))

from common.python.fixed_fft import (
    ComplexWord,
    butterfly_scaled,
    canonical_dif_stage,
    generate_frame,
    multiply_twiddle,
    subfft_1024,
)
from common.python.protection import (
    WideComplex,
    WIDE_ZERO,
    arithmetic_643_capture_residual,
    arithmetic_643_encode,
    arithmetic_643_syndrome,
    flip_component_bit,
)
from common.python.campaign_support import load_json, LEGACY_MATRIX_PATH


def operator_output(a, b, branch, exponent, n_points):
    upper, lower = butterfly_scaled(a, b)
    value = upper if branch == "upper" else lower
    return multiply_twiddle(value, n_points, exponent) if exponent else value


def classic_operator_input(state, stage, position):
    n_points = len(state)
    length = 1 << (n_points.bit_length() - stage)
    depth = length // 2
    base = (position // length) * length
    within = position - base
    if within < depth:
        offset, branch, exponent = within, "upper", 0
    else:
        offset = within - depth
        branch = "lower"
        exponent = offset * (n_points // length)
    return (state[base + offset], state[base + depth + offset], branch, exponent, n_points)


def build_operator_groups(frame, positions):
    selected = tuple(positions)
    states = [[frame[4 * sample + lane] for sample in range(256)] for lane in range(4)]
    reports = {}
    for stage in range(1, 9):
        groups = {}
        for position in selected:
            inputs = [classic_operator_input(states[lane], stage, position) for lane in range(4)]
            encoded_a = tuple(arithmetic_643_encode([inp[0] for inp in inputs]))
            encoded_b = tuple(arithmetic_643_encode([inp[1] for inp in inputs]))
            outputs = tuple(
                operator_output(encoded_a[index], encoded_b[index],
                                inputs[index % 4][2], inputs[index % 4][3], inputs[index % 4][4])
                for index in range(6)
            )
            residual = arithmetic_643_capture_residual(outputs)
            groups[position] = {
                "outputs": outputs,
                "functional": outputs[:4],
                "checks": (outputs[4], outputs[5]),
                "expected_residual": residual,
            }
        reports[stage] = groups
        states = [list(canonical_dif_stage(state, stage).values) for state in states]
    return reports


def main():
    legacy = load_json(LEGACY_MATRIX_PATH)
    frame_id = legacy["fault_frames"][0]
    frame_spec = next(s for s in legacy["no_fault_frames"] if s["id"] == frame_id)
    frame = generate_frame(frame_spec)

    positions = legacy["trial_schedule"]["S3"]["arithmetic_group_positions"]
    components = legacy["components"]
    bits = legacy["component_bits"]

    groups = build_operator_groups(frame, positions)

    results_dir = EXPERIMENT / "results" / "sc01_threshold_v1_001"
    results_dir.mkdir(parents=True, exist_ok=True)

    csv_path = results_dir / "syndrome_distribution.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "stage", "position", "symbol", "component", "bit",
            "sy0_real", "sy0_imag", "sy1_real", "sy1_imag",
            "max_abs_syndrome", "no_fault_residual_max",
        ])

        no_fault_max = 0
        total_trials = 0
        syndrome_magnitudes = []

        for stage in range(1, 9):
            for position in positions:
                group = groups[stage][position]
                residual = group["expected_residual"]
                outputs = group["outputs"]

                # No-fault syndrome (should be zero after compensation)
                no_fault_syndrome = arithmetic_643_syndrome(outputs, residual)
                nf_max = max(abs(no_fault_syndrome[0].real), abs(no_fault_syndrome[0].imag),
                             abs(no_fault_syndrome[1].real), abs(no_fault_syndrome[1].imag))
                if nf_max > no_fault_max:
                    no_fault_max = nf_max

                for symbol in range(6):
                    for component in components:
                        for bit in bits:
                            received = list(outputs)
                            received[symbol] = flip_component_bit(received[symbol], component, bit)
                            syndrome = arithmetic_643_syndrome(received, residual)
                            sy0r, sy0i = syndrome[0].real, syndrome[0].imag
                            sy1r, sy1i = syndrome[1].real, syndrome[1].imag
                            max_abs = max(abs(sy0r), abs(sy0i), abs(sy1r), abs(sy1i))
                            syndrome_magnitudes.append(max_abs)
                            writer.writerow([stage, position, symbol, component, bit,
                                             sy0r, sy0i, sy1r, sy1i, max_abs, nf_max])
                            total_trials += 1

    # Statistics
    syndrome_magnitudes.sort()
    n = len(syndrome_magnitudes)
    zero_count = sum(1 for m in syndrome_magnitudes if m == 0)
    nonzero = [m for m in syndrome_magnitudes if m > 0]
    min_nonzero = min(nonzero) if nonzero else 0
    max_syndrome = syndrome_magnitudes[-1] if syndrome_magnitudes else 0

    stats = {
        "total_trials": total_trials,
        "no_fault_residual_max": no_fault_max,
        "zero_syndrome_count": zero_count,
        "zero_syndrome_pct": round(100 * zero_count / n, 2) if n else 0,
        "nonzero_count": len(nonzero),
        "min_nonzero_syndrome": min_nonzero,
        "max_syndrome": max_syndrome,
        "percentiles": {
            "p1": syndrome_magnitudes[n // 100] if n else 0,
            "p5": syndrome_magnitudes[n // 20] if n else 0,
            "p10": syndrome_magnitudes[n // 10] if n else 0,
            "p25": syndrome_magnitudes[n // 4] if n else 0,
            "p50": syndrome_magnitudes[n // 2] if n else 0,
            "p75": syndrome_magnitudes[3 * n // 4] if n else 0,
            "p90": syndrome_magnitudes[9 * n // 10] if n else 0,
            "p95": syndrome_magnitudes[19 * n // 20] if n else 0,
            "p99": syndrome_magnitudes[99 * n // 100] if n else 0,
        },
        "histogram_0_to_10": [
            {"value": v, "count": sum(1 for m in syndrome_magnitudes if m == v)}
            for v in range(11)
        ],
        "histogram_small_values": [
            {"value": v, "count": sum(1 for m in syndrome_magnitudes if m == v)}
            for v in range(min(100, max_syndrome + 1))
        ],
    }

    stats_path = results_dir / "syndrome_stats.json"
    stats_path.write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps(stats, indent=2))
    print(f"\nCSV: {csv_path}")
    print(f"Stats: {stats_path}")


if __name__ == "__main__":
    main()
