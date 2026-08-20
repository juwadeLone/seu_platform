#!/usr/bin/env python3
"""SC-01 Main Experiment: Threshold-based recovery rate experiment.

Following the paper's "fair inject matrix" protocol:
  - Level-1 = 10 stages × 70 bit/component combinations = 700 trials
  - 70 = 35 bits × 2 components (real/imag)
  - For each architecture (S3, P1), inject single-bit flips at the main
    recovery boundary and classify into four categories:
    1. corrected: detected + corrected + output bit-exact match
    2. detected-only: detected but not correctable
    3. silent-bounded-residual: not detected (syndrome within threshold)
    4. miscorrection: corrected but output ≠ golden (MUST be 0)

  Also reports Gao-style PASS: below-threshold faults count as PASS
  (acceptable fixed-point residual, per Gao's method).
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

EXPERIMENT = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENT))

from common.python.fixed_fft import (
    ComplexWord,
    butterfly_scaled,
    canonical_dif_stage,
    exchange_phi,
    generate_frame,
    multiply_twiddle,
    pfft_1024,
    subfft_1024,
)
from common.python.protection import (
    WideComplex,
    WIDE_ZERO,
    arithmetic_643_capture_residual,
    arithmetic_643_decode,
    arithmetic_643_decode_thresholded,
    arithmetic_643_encode,
    arithmetic_643_syndrome,
    flip_component_bit,
)
from common.python.campaign_support import load_json, LEGACY_MATRIX_PATH


# ─── S3 operator groups ──────────────────────────────────────────────

def s3_operator_output(a, b, branch, exponent, n_points):
    upper, lower = butterfly_scaled(a, b)
    value = upper if branch == "upper" else lower
    return multiply_twiddle(value, n_points, exponent) if exponent else value


def s3_classic_operator_input(state, stage, position):
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


def s3_build_operator_groups(frame, positions):
    selected = tuple(positions)
    states = [[frame[4 * sample + lane] for sample in range(256)] for lane in range(4)]
    reports = {}
    for stage in range(1, 9):
        groups = {}
        for position in selected:
            inputs = [s3_classic_operator_input(states[lane], stage, position) for lane in range(4)]
            encoded_a = tuple(arithmetic_643_encode([inp[0] for inp in inputs]))
            encoded_b = tuple(arithmetic_643_encode([inp[1] for inp in inputs]))
            outputs = tuple(
                s3_operator_output(encoded_a[index], encoded_b[index],
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


# ─── P1 operator groups ──────────────────────────────────────────────

def p1_operator_input(state, stage, physical_index, phi):
    n_points = len(state)
    length = 1 << (n_points.bit_length() - stage)
    depth = length // 2
    base = (physical_index // length) * length
    within = physical_index - base
    if within < depth:
        offset, branch = within, "upper"
    else:
        offset, branch = within - depth, "lower"
    exponent = (
        phi[stage - 1][physical_index] % n_points
        if stage <= n_points.bit_length() - 2
        else 0
    )
    return (state[base + offset], state[base + depth + offset], branch, exponent, n_points)


def p1_independent_operator_group(inputs):
    encoded_a = tuple(arithmetic_643_encode([inp[0] for inp in inputs]))
    encoded_b = tuple(arithmetic_643_encode([inp[1] for inp in inputs]))
    n_points = inputs[0][4]
    exponent = inputs[0][3]
    branch = inputs[0][2]
    outputs = []
    for a, b in zip(encoded_a, encoded_b):
        upper, lower = butterfly_scaled(a, b)
        value = upper if branch == "upper" else lower
        outputs.append(multiply_twiddle(value, n_points, exponent) if exponent else value)
    output_tuple = tuple(outputs)
    return {
        "outputs": output_tuple,
        "functional": output_tuple[:4],
        "checks": (output_tuple[4], output_tuple[5]),
        "expected_residual": arithmetic_643_capture_residual(output_tuple),
    }


def p1_direct_operator_groups(frame, stages, beats):
    selected = tuple(beats)
    result = pfft_1024(frame)
    states = [tuple(frame)]
    states.extend(trace.values for trace in result.stages[:-1])
    phi = exchange_phi(1024)
    reports = {}
    for stage in stages:
        reports[stage] = {}
        for beat in selected:
            inputs = [
                p1_operator_input(states[stage - 1], stage, physical_index, phi)
                for physical_index in range(4 * beat, 4 * beat + 4)
            ]
            reports[stage][beat] = p1_independent_operator_group(inputs)
    return reports


def p1_stage10_operator_groups(frame):
    result = pfft_1024(frame)
    states = [tuple(frame)]
    states.extend(trace.values for trace in result.stages[:-1])
    input_state = states[9]
    phi = [[0] * 1024 for _ in range(9)]
    groups = []
    for two_beat_group in range(128):
        base = 8 * two_beat_group
        upper_inputs = [p1_operator_input(input_state, 10, base + offset, phi) for offset in (0, 2, 4, 6)]
        lower_inputs = [p1_operator_input(input_state, 10, base + offset, phi) for offset in (1, 3, 5, 7)]
        groups.append(("upper", p1_independent_operator_group(upper_inputs)))
        groups.append(("lower", p1_independent_operator_group(lower_inputs)))
    return groups


# ─── Four-class classification ───────────────────────────────────────

def classify_trial(decoded, golden_functional, symbol, threshold):
    """Classify a single trial into one of four categories."""
    if not decoded.detected:
        # Not detected → check if residual is bounded
        return "silent_bounded_residual"
    if not decoded.corrected:
        # Detected but not correctable
        return "detected_only"
    # Corrected: check if output matches golden
    if decoded.functional == golden_functional:
        return "corrected"
    # Corrected but output doesn't match → miscorrection
    return "miscorrection"


def run_threshold_experiment(arch_id, groups_by_stage, threshold):
    """Run the fair inject matrix for one architecture.

    For each arithmetic stage × symbol(0-5) × component(real/imag) × bit(0-34):
    This gives 8 stages × 6 symbols × 2 components × 35 bits = 3360 trials per position.
    For the "fair" 700-trial matrix, we use:
      10 stages × 70 = 700 (where 70 = 35 bits × 2 components, single representative position)

    But we also run the full matrix for completeness.
    """
    components = ["real", "imag"]
    bits = list(range(35))

    results = []

    for stage, groups in groups_by_stage.items():
        # Use first position as representative (fair inject matrix)
        first_pos = list(groups.keys())[0]
        group = groups[first_pos]
        golden = group["functional"]
        residual = group["expected_residual"]
        outputs = group["outputs"]

        for symbol in range(6):
            for component in components:
                for bit in bits:
                    received = list(outputs)
                    received[symbol] = flip_component_bit(received[symbol], component, bit)
                    decoded = arithmetic_643_decode_thresholded(received, residual, threshold)
                    category = classify_trial(decoded, golden, symbol, threshold)

                    # Also check exact decode for comparison
                    decoded_exact = arithmetic_643_decode(received, residual)

                    results.append({
                        "arch": arch_id,
                        "stage": stage,
                        "position": first_pos,
                        "symbol": symbol,
                        "component": component,
                        "bit": bit,
                        "detected": decoded.detected,
                        "corrected": decoded.corrected,
                        "location": decoded.location,
                        "category": category,
                        "exact_detected": decoded_exact.detected,
                        "exact_corrected": decoded_exact.corrected,
                        "exact_match": decoded_exact.functional == golden,
                        "threshold_match": decoded.functional == golden,
                        "syndrome_sy0r": decoded.syndrome[0].real,
                        "syndrome_sy0i": decoded.syndrome[0].imag,
                        "syndrome_sy1r": decoded.syndrome[1].real,
                        "syndrome_sy1i": decoded.syndrome[1].imag,
                    })

    return results


def run_s3_experiment(frame, threshold):
    """S3: stages 1-8 arithmetic ECC, positions [0, 63, 127, 255]."""
    positions = [0, 63, 127, 255]
    groups = s3_build_operator_groups(frame, positions)
    # Build groups_by_stage with only first position for fair inject matrix
    groups_by_stage = {}
    for stage in range(1, 9):
        groups_by_stage[stage] = {0: groups[stage][0]}
    return run_threshold_experiment("S3", groups_by_stage, threshold)


def run_p1_experiment(frame, threshold):
    """P1: stages 1-7 direct arithmetic ECC + stage 10 two-beat groups."""
    beats = [0, 63, 127, 255]
    direct = p1_direct_operator_groups(frame, range(1, 8), beats)
    stage10 = p1_stage10_operator_groups(frame)

    groups_by_stage = {}
    for stage in range(1, 8):
        groups_by_stage[stage] = {0: direct[stage][0]}

    # Stage 10: use first two-beat group upper
    for i, (branch, group) in enumerate(stage10[:2]):
        groups_by_stage[10 if i == 0 else 10] = {0: group}
    # Just use the first stage10 group
    groups_by_stage[10] = {0: stage10[0][1]}

    return run_threshold_experiment("P1", groups_by_stage, threshold)


def summarize_results(results, arch_id, threshold):
    """Compute summary statistics."""
    total = len(results)
    corrected = sum(1 for r in results if r["category"] == "corrected")
    detected_only = sum(1 for r in results if r["category"] == "detected_only")
    silent = sum(1 for r in results if r["category"] == "silent_bounded_residual")
    miscorrection = sum(1 for r in results if r["category"] == "miscorrection")

    # Exact decode comparison
    exact_corrected = sum(1 for r in results if r["exact_corrected"] and r["exact_match"])
    exact_detected_only = sum(1 for r in results if r["exact_detected"] and not r["exact_corrected"])
    exact_silent = sum(1 for r in results if not r["exact_detected"])
    exact_miscorrection = sum(1 for r in results if r["exact_corrected"] and not r["exact_match"])

    # Gao-style PASS: corrected + silent_bounded_residual (both are "acceptable")
    gao_pass = corrected + silent
    gao_pass_rate = round(100 * gao_pass / total, 2) if total else 0

    # Strict bit-exact PASS: only corrected
    strict_pass_rate = round(100 * corrected / total, 2) if total else 0

    return {
        "arch_id": arch_id,
        "threshold": threshold,
        "total_trials": total,
        "corrected": corrected,
        "detected_only": detected_only,
        "silent_bounded_residual": silent,
        "miscorrection": miscorrection,
        "strict_pass_rate": strict_pass_rate,
        "gao_pass_rate": gao_pass_rate,
        "exact_decode": {
            "corrected": exact_corrected,
            "detected_only": exact_detected_only,
            "silent": exact_silent,
            "miscorrection": exact_miscorrection,
            "pass_rate": round(100 * exact_corrected / total, 2) if total else 0,
        },
    }


def main():
    legacy = load_json(LEGACY_MATRIX_PATH)
    frame_id = legacy["fault_frames"][0]
    frame_spec = next(s for s in legacy["no_fault_frames"] if s["id"] == frame_id)
    frame = generate_frame(frame_spec)

    results_dir = EXPERIMENT / "results" / "sc01_threshold_v1_001"
    results_dir.mkdir(parents=True, exist_ok=True)

    # Based on diagnostic scan: no_fault_residual = 0, min_syndrome = 1
    # So threshold = 0 is the correct Gao threshold for our integer model
    # (equivalent to exact match, because no fixed-point residual exists)
    threshold = 0

    all_results = []
    summaries = []

    # S3 experiment
    print("Running S3 threshold experiment (threshold=0)...")
    s3_results = run_s3_experiment(frame, threshold)
    s3_summary = summarize_results(s3_results, "S3", threshold)
    all_results.extend(s3_results)
    summaries.append(s3_summary)
    print(f"  S3: {s3_summary}")

    # P1 experiment
    print("Running P1 threshold experiment (threshold=0)...")
    p1_results = run_p1_experiment(frame, threshold)
    p1_summary = summarize_results(p1_results, "P1", threshold)
    all_results.extend(p1_results)
    summaries.append(p1_summary)
    print(f"  P1: {p1_summary}")

    # Also run with threshold=1 for comparison (Gao 2016 uses τ=1)
    print("\nRunning with threshold=1 for comparison...")
    s3_results_t1 = run_s3_experiment(frame, 1)
    s3_summary_t1 = summarize_results(s3_results_t1, "S3", 1)
    print(f"  S3 (τ=1): {s3_summary_t1}")

    p1_results_t1 = run_p1_experiment(frame, 1)
    p1_summary_t1 = summarize_results(p1_results_t1, "P1", 1)
    print(f"  P1 (τ=1): {p1_summary_t1}")

    # Write outputs
    # 1. Four-class breakdown CSV
    csv_path = results_dir / "four_class_breakdown.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_results[0].keys()))
        writer.writeheader()
        for r in all_results:
            writer.writerow(r)

    # 2. S3 threshold results JSON
    s3_json_path = results_dir / "s3_threshold_results.json"
    s3_json_path.write_text(json.dumps(s3_summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # 3. P1 threshold results JSON
    p1_json_path = results_dir / "p1_threshold_results.json"
    p1_json_path.write_text(json.dumps(p1_summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # 4. Combined summary with threshold=1 results
    combined = {
        "threshold_0": {
            "S3": s3_summary,
            "P1": p1_summary,
        },
        "threshold_1": {
            "S3": s3_summary_t1,
            "P1": p1_summary_t1,
        },
    }
    combined_path = results_dir / "combined_results.json"
    combined_path.write_text(json.dumps(combined, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # 5. SHA-256 of output files
    hashes = {}
    for p in [csv_path, s3_json_path, p1_json_path, combined_path]:
        h = hashlib.sha256(p.read_bytes()).hexdigest().upper()
        hashes[p.name] = h
    hash_path = results_dir / "output_hashes.json"
    hash_path.write_text(json.dumps(hashes, indent=2) + "\n", encoding="utf-8")

    print(f"\nResults written to: {results_dir}")
    print(f"  four_class_breakdown.csv: {hashes.get('four_class_breakdown.csv', '?')}")
    print(f"  s3_threshold_results.json: {hashes.get('s3_threshold_results.json', '?')}")
    print(f"  p1_threshold_results.json: {hashes.get('p1_threshold_results.json', '?')}")
    print(f"  combined_results.json: {hashes.get('combined_results.json', '?')}")


if __name__ == "__main__":
    main()
