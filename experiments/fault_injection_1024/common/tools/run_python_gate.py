#!/usr/bin/env python3
"""Run the P1-PY-V3-001 Python qualification gate.

This gate is deliberately independent of RTL.  It qualifies the two numeric
dataflows, the seven architecture identities, the stream contract, and every
protection construction needed before RTL implementation is allowed.
"""

from __future__ import annotations

import hashlib
import json
import sys
import traceback
from pathlib import Path
from typing import Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
EXPERIMENT_DIR = SCRIPT_DIR.parents[1]
if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

from common.python.fixed_fft import (  # noqa: E402
    DATA_WIDTH,
    ComplexWord,
    ZERO,
    classic_r2sdf_fft,
    error_metrics,
    generate_frame,
    pfft_1024,
    reference_fft,
    serialize_words,
    subfft_1024,
)
from common.python.protection import (  # noqa: E402
    CHECK_DOMAIN_WIDTH,
    MEMORY_CODEWORD_BITS,
    WIDE_ZERO,
    arithmetic_643_decode,
    arithmetic_643_syndrome,
    flip_component_bit,
    gao_743_capture_residual,
    gao_743_decode,
    gao_743_encode,
    gao_743_syndrome,
    secded_decode,
    secded_encode_complex,
    tmr_vote,
)
from common.python.campaign_support import inject_and_decode  # noqa: E402
from common.python.stream_contract import (  # noqa: E402
    PFFT_LATENCY_CYCLES,
    PFFT_PAIR_WAIT_AND_SYNC_READ_CYCLES,
    PHYSICAL_DELAY_DEPTHS,
    STAGE_FIRST_TOKEN_LATENCIES,
    STAGE_FIRST_VALID_CYCLES,
    SUBFFT_LATENCY_CYCLES,
    pfft_stream_trace,
    subfft_stream_trace,
)
from projects.S3.run_s3 import build_operator_groups as subfft_operator_groups  # noqa: E402
from projects.P1.run_p1 import (  # noqa: E402
    direct_operator_groups as pfft_direct_operator_groups,
    stage10_operator_groups,
)


CONFIG_DIR = EXPERIMENT_DIR / "config"
CONTRACT_PATH = CONFIG_DIR / "seven_architecture_contract.json"
MATRIX_PATH = CONFIG_DIR / "seven_architecture_fault_matrix.json"
MEMORY_PATH = CONFIG_DIR / "seven_architecture_memory_map.json"
LEGACY_MATRIX_PATH = CONFIG_DIR / "legacy_protected_trial_set.json"
RESULTS_DIR = EXPERIMENT_DIR / "results" / "p1_py_v3_001"
LOGS_DIR = EXPERIMENT_DIR / "logs" / "p1_py_v3_001"
RESULT_PATH = RESULTS_DIR / "python_gate.json"
LOG_PATH = LOGS_DIR / "python_gate.log"

ARCHITECTURES = ("S0", "S1", "S2", "S3", "P0", "P1", "P2")
SUBFFT_ARCHITECTURES = ("S0", "S1", "S2", "S3")
PFFT_ARCHITECTURES = ("P0", "P1", "P2")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def words_sha256(values: Sequence[ComplexWord]) -> str:
    payload = json.dumps(serialize_words(values), separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()


def validate_contract(contract: dict, matrix: dict, memory: dict, legacy: dict) -> dict:
    checks: dict[str, bool] = {
        "schema_v5": contract.get("schema_version") == 5 and matrix.get("schema_version") == 5,
        "frozen": all(item.get("status") == "FROZEN" for item in (contract, matrix, memory)),
        "experiment_id": len({contract.get("experiment_id"), matrix.get("experiment_id"), memory.get("experiment_id")}) == 1,
        "architectures": tuple(contract["scope"]["architectures"]) == ARCHITECTURES,
        "baseline_domains": matrix["architecture_domains"]["S0"]["no_fault_only"] is True
        and matrix["architecture_domains"]["P0"]["no_fault_only"] is True,
        "p1_stage_boundary": (
            contract["architectures"]["P1"]["stages_8_9"]
            == "full_stage_tmr"
            and contract["architectures"]["P1"]["stage_10"]
            == "two_adjacent_beats_four_complete_butterflies_upper_lower_6_4_3"
        ),
        "legacy_trial_hash": sha256_file(LEGACY_MATRIX_PATH)
        == matrix["protected_campaign_inheritance"]["sha256"],
        "legacy_trial_set_versioned": matrix["protected_campaign_inheritance"]["trial_sets_unchanged"] is False,
        "frame_ids": matrix["no_fault_frames"] == [item["id"] for item in legacy["no_fault_frames"]],
        "latencies": contract["stream_contract"]["subfft_latency_cycles"] == SUBFFT_LATENCY_CYCLES
        and contract["stream_contract"]["pfft_latency_cycles"] == PFFT_LATENCY_CYCLES
        and tuple(contract["stream_contract"]["stage_first_token_latencies"]) == STAGE_FIRST_TOKEN_LATENCIES,
        "stage10_alignment": (
            memory["small_alignment_registers"]["p1_stage10"]["input_beats"]
            == 1
            and memory["small_alignment_registers"]["p1_stage10"]["output_beats"]
            == 1
            and memory["small_alignment_registers"]["p1_stage10"]["raw_total_bits"]
            == 560
        ),
    }
    return {"checks": checks, "pass": all(checks.values())}


def build_frames(matrix: dict, legacy: dict) -> dict[str, list[ComplexWord]]:
    specs = {item["id"]: item for item in legacy["no_fault_frames"]}
    return {frame_id: generate_frame(specs[frame_id]) for frame_id in matrix["no_fault_frames"]}


def functional_audit(frames: dict[str, list[ComplexWord]]) -> tuple[dict, dict[str, object], dict[str, object]]:
    reports = []
    sub_results: dict[str, object] = {}
    p_results: dict[str, object] = {}
    for frame_id, frame in frames.items():
        sub = subfft_1024(frame)
        pfft = pfft_1024(frame)
        sub_results[frame_id] = sub
        p_results[frame_id] = pfft
        reference = reference_fft(frame)
        sub_hash = words_sha256(sub.output)
        pfft_hash = words_sha256(pfft.output)
        identity = {
            **{architecture: sub_hash for architecture in SUBFFT_ARCHITECTURES},
            **{architecture: pfft_hash for architecture in PFFT_ARCHITECTURES},
        }
        reports.append({
            "frame_id": frame_id,
            "architecture_output_sha256": identity,
            "subfft_metrics": error_metrics(sub.output, reference),
            "pfft_metrics": error_metrics(pfft.output, reference),
            "subfft_stage_count": len(sub.stages),
            "pfft_stage_count": len(pfft.stages),
            "subfft_depths": [stage.physical_delay_depth for stage in sub.stages],
            "pfft_depths": [stage.physical_delay_depth for stage in pfft.stages],
            "pass": len(sub.stages) == 10
            and len(pfft.stages) == 10
            and [stage.physical_delay_depth for stage in sub.stages] == list(PHYSICAL_DELAY_DEPTHS)
            and [stage.physical_delay_depth for stage in pfft.stages] == list(PHYSICAL_DELAY_DEPTHS),
        })
    return {"frames": reports, "pass": all(item["pass"] for item in reports)}, sub_results, p_results


def _audit_stream_output(trace, frames: dict[str, list[ComplexWord]], results: dict[str, object],
                         latency: int) -> dict:
    details = []
    passed = True
    ordered_ids = list(frames)
    for frame_number, frame_id in enumerate(ordered_ids):
        beats = [beat for beat in trace.output_beats if beat.frame_id == frame_id]
        expected_cycles = list(range(frame_number * 256 + latency, frame_number * 256 + latency + 256))
        indices = [index for beat in beats for index in beat.sample_indices]
        frame_pass = (
            len(beats) == 256
            and [beat.cycle for beat in beats] == expected_cycles
            and [beat.beat_index for beat in beats] == list(range(256))
            and [beat.beat_index for beat in beats if beat.last] == [255]
            and all(beat.valid for beat in beats)
            and sorted(indices) == list(range(1024))
            and all(
                beat.lanes[lane] == results[frame_id].output[beat.sample_indices[lane]]
                for beat in beats for lane in range(4)
            )
        )
        passed = passed and frame_pass
        details.append({
            "frame_id": frame_id,
            "first_valid_cycle": beats[0].cycle if beats else None,
            "last_valid_cycle": beats[-1].cycle if beats else None,
            "valid_beats": len(beats),
            "last_positions": [beat.beat_index for beat in beats if beat.last],
            "pass": frame_pass,
        })
    contiguous = all(
        right.cycle == left.cycle + 1
        for left, right in zip(trace.output_beats, trace.output_beats[1:])
    )
    return {"frames": details, "contiguous_across_frames": contiguous, "pass": passed and contiguous}


def stream_audit(frames: dict[str, list[ComplexWord]], sub_results: dict[str, object],
                 p_results: dict[str, object]) -> dict:
    ordered = list(frames.items())
    sub_trace = subfft_stream_trace(ordered)
    pfft_trace = pfft_stream_trace(ordered)
    child_counts = [len(child) for child in sub_trace.subfft_child_stages]
    child_depths = [[stage.physical_delay_depth for stage in child] for child in sub_trace.subfft_child_stages]
    child_starts = [[stage.output_first_cycle for stage in child] for child in sub_trace.subfft_child_stages]
    child_pass = (
        len(sub_trace.subfft_child_stages) == 4
        and child_counts == [8, 8, 8, 8]
        and all(depths == list(PHYSICAL_DELAY_DEPTHS[:8]) for depths in child_depths)
        and all(starts == list(STAGE_FIRST_VALID_CYCLES[:8]) for starts in child_starts)
    )
    sub_output = _audit_stream_output(sub_trace, frames, sub_results, SUBFFT_LATENCY_CYCLES)
    pfft_output = _audit_stream_output(pfft_trace, frames, p_results, PFFT_LATENCY_CYCLES)
    sub_pass = (
        child_pass
        and sub_trace.frame_latency_cycles == SUBFFT_LATENCY_CYCLES
        and tuple(sub_trace.stage_first_valid_cycles) == STAGE_FIRST_VALID_CYCLES
        and sub_output["pass"]
    )
    pfft_pass = (
        pfft_trace.frame_latency_cycles == PFFT_LATENCY_CYCLES
        and tuple(pfft_trace.stage_first_valid_cycles) == STAGE_FIRST_VALID_CYCLES
        and pfft_output["pass"]
    )
    return {
        "subfft": {
            "latency_cycles": SUBFFT_LATENCY_CYCLES,
            "child_count": len(sub_trace.subfft_child_stages),
            "child_stage_counts": child_counts,
            "child_depths": child_depths,
            "child_first_valid_cycles": child_starts,
            "output": sub_output,
            "pass": sub_pass,
        },
        "pfft": {
            "latency_cycles": PFFT_LATENCY_CYCLES,
            "pair_wait_and_sync_read_cycles": PFFT_PAIR_WAIT_AND_SYNC_READ_CYCLES,
            "common_reorder_buffer_complex_words": 2048,
            "output": pfft_output,
            "pass": pfft_pass,
        },
        "pass": sub_pass and pfft_pass,
    }


def secded_audit(frame: Sequence[ComplexWord], positions: Sequence[int]) -> dict:
    trials = failures = 0
    for position in positions:
        golden = frame[position]
        clean = secded_decode(secded_encode_complex(golden))
        if clean.detected or clean.complex_word != golden:
            failures += 1
        for bit in range(MEMORY_CODEWORD_BITS):
            trials += 1
            decoded = secded_decode(secded_encode_complex(golden) ^ (1 << bit))
            if not decoded.detected or not decoded.corrected or decoded.complex_word != golden:
                failures += 1
    return {"codeword_bits": MEMORY_CODEWORD_BITS, "trials": trials, "failures": failures, "pass": failures == 0}


def tmr_audit(frame: Sequence[ComplexWord], positions: Sequence[int]) -> dict:
    trials = failures = 0
    for position in positions:
        golden = frame[position]
        for replica in range(3):
            for component in ("real", "imag"):
                for bit in range(DATA_WIDTH):
                    trials += 1
                    copies = [golden, golden, golden]
                    copies[replica] = flip_component_bit(golden, component, bit)
                    voted, detected = tmr_vote(copies)
                    if not detected or voted != golden:
                        failures += 1
    return {"trials": trials, "failures": failures, "pass": failures == 0}


def subfft_independent_operator_audit(frame: Sequence[ComplexWord], sub_result) -> dict:
    groups = subfft_operator_groups(frame, range(256))
    group_count = closure_failures = functional_failures = injection_failures = 0
    sign_bit_trials = 0
    for stage, stage_groups in groups.items():
        for position, group in stage_groups.items():
            group_count += 1
            expected = tuple(sub_result.stages[stage - 1].values[4 * position + lane] for lane in range(4))
            functional_failures += int(group.functional != expected)
            closure_failures += int(arithmetic_643_syndrome(group.outputs, group.expected_residual) != (WIDE_ZERO, WIDE_ZERO))
            if position in (0, 63, 127, 255):
                checks_before = group.checks
                residual_before = group.expected_residual
                for symbol in range(4):
                    for component in ("real", "imag"):
                        for bit in (0, DATA_WIDTH - 1):
                            sign_bit_trials += int(bit == DATA_WIDTH - 1)
                            received, decoded = inject_and_decode(group, symbol, component, bit)
                            ok = (
                                tuple(received[4:]) == checks_before
                                and group.expected_residual == residual_before
                                and decoded.detected
                                and decoded.corrected
                                and decoded.location == symbol
                                and decoded.functional == expected
                            )
                            injection_failures += int(not ok)
    return {
        "stages": 8,
        "groups": group_count,
        "functional_mismatches": functional_failures,
        "compensated_closure_failures": closure_failures,
        "independent_check_injection_failures": injection_failures,
        "sign_bit_trials": sign_bit_trials,
        "check_symbols_source": "encoded_operator_inputs_then_independent_butterfly_and_twiddle",
        "pass": functional_failures == closure_failures == injection_failures == 0,
    }


def pfft_direct_operator_audit(frame: Sequence[ComplexWord], pfft_result) -> dict:
    groups = pfft_direct_operator_groups(frame, range(1, 8), range(256))
    group_count = functional_failures = closure_failures = injection_failures = 0
    signatures: dict[str, int] = {}
    for stage, stage_groups in groups.items():
        for beat, group in stage_groups.items():
            group_count += 1
            signature = str(group.inputs[0].signature)
            signatures[signature] = signatures.get(signature, 0) + 1
            expected = tuple(pfft_result.stages[stage - 1].values[4 * beat + lane] for lane in range(4))
            functional_failures += int(group.functional != expected)
            closure_failures += int(arithmetic_643_syndrome(group.outputs, group.expected_residual) != (WIDE_ZERO, WIDE_ZERO))
            if beat in (0, 63, 127, 255):
                for symbol in range(4):
                    for component in ("real", "imag"):
                        for bit in (0, DATA_WIDTH - 1):
                            received, decoded = inject_and_decode(group, symbol, component, bit)
                            ok = (
                                tuple(received[4:]) == group.checks
                                and decoded.detected
                                and decoded.corrected
                                and decoded.location == symbol
                                and decoded.functional == expected
                            )
                            injection_failures += int(not ok)
    return {
        "stages": 7,
        "groups": group_count,
        "operator_signatures": signatures,
        "functional_mismatches": functional_failures,
        "compensated_closure_failures": closure_failures,
        "independent_check_injection_failures": injection_failures,
        "pass": functional_failures == closure_failures == injection_failures == 0,
    }


def gao_complete_path_audit(frame: Sequence[ComplexWord]) -> dict:
    functional_inputs = [[frame[4 * sample + lane] for sample in range(256)] for lane in range(4)]
    coded_inputs = [[ZERO for _ in range(256)] for _ in range(7)]
    for sample in range(256):
        codeword = gao_743_encode([functional_inputs[lane][sample] for lane in range(4)])
        for path in range(7):
            coded_inputs[path][sample] = codeword[path]
    path_results = [classic_r2sdf_fft(path) for path in coded_inputs]
    path_outputs = [item[0].output for item in path_results]
    path_depths = [[stage.physical_delay_depth for stage in item[1]] for item in path_results]
    closure_failures = functional_failures = injection_failures = 0
    nonzero_raw_residuals = 0
    for sample in range(256):
        codeword = tuple(path_outputs[path][sample] for path in range(7))
        residual = gao_743_capture_residual(codeword)
        nonzero_raw_residuals += int(residual != (WIDE_ZERO, WIDE_ZERO, WIDE_ZERO))
        closure_failures += int(gao_743_syndrome(codeword, residual) != (WIDE_ZERO, WIDE_ZERO, WIDE_ZERO))
        decoded_clean = gao_743_decode(codeword, residual)
        expected = tuple(path_outputs[index][sample] for index in (2, 4, 5, 6))
        functional_failures += int(decoded_clean.functional != expected)
        if sample in (0, 63, 127, 255):
            for path in range(7):
                for component in ("real", "imag"):
                    for bit in (0, DATA_WIDTH - 1):
                        received = list(codeword)
                        received[path] = flip_component_bit(received[path], component, bit)
                        decoded = gao_743_decode(received, residual)
                        ok = decoded.detected and decoded.corrected and decoded.location == path and decoded.functional == expected
                        injection_failures += int(not ok)
    return {
        "functional_paths": 4,
        "coded_paths": 3,
        "complete_path_count": 7,
        "stages_per_path": [len(item[1]) for item in path_results],
        "depths_per_path": path_depths,
        "nonzero_pre_fault_residual_samples": nonzero_raw_residuals,
        "compensated_closure_failures": closure_failures,
        "functional_mismatches": functional_failures,
        "injection_failures": injection_failures,
        "pass": all(depths == list(PHYSICAL_DELAY_DEPTHS[:8]) for depths in path_depths)
        and closure_failures == functional_failures == injection_failures == 0,
    }


def pfft_stage10_audit(
    frame: Sequence[ComplexWord], pfft_result
) -> dict:
    groups = stage10_operator_groups(frame)
    covered: list[int] = []
    functional_failures = closure_failures = injection_failures = 0
    exact_signature_failures = 0
    upper_groups = lower_groups = 0

    for upper, lower in groups:
        for branch, operator_group in (("upper", upper), ("lower", lower)):
            if branch == "upper":
                upper_groups += 1
            else:
                lower_groups += 1
            positions = tuple(
                int(item.physical_index) for item in operator_group.inputs
            )
            covered.extend(positions)
            expected = tuple(
                pfft_result.stages[9].values[position]
                for position in positions
            )
            exact_signature_failures += int(
                len({item.signature for item in operator_group.inputs}) != 1
            )
            functional_failures += int(
                operator_group.functional != expected
            )
            closure_failures += int(
                arithmetic_643_syndrome(
                    operator_group.outputs,
                    operator_group.expected_residual,
                )
                != (WIDE_ZERO, WIDE_ZERO)
            )
            for symbol in range(6):
                for component in ("real", "imag"):
                    for bit in range(DATA_WIDTH):
                        _, decoded = inject_and_decode(
                            operator_group, symbol, component, bit
                        )
                        ok = (
                            decoded.detected
                            and decoded.corrected
                            and decoded.location == symbol
                            and decoded.functional == expected
                        )
                        injection_failures += int(not ok)

    coverage_pass = (
        len(groups) == 128
        and upper_groups == lower_groups == 128
        and len(covered) == 1024
        and sorted(covered) == list(range(1024))
        and len(set(covered)) == 1024
    )
    passed = (
        coverage_pass
        and exact_signature_failures == 0
        and functional_failures == 0
        and closure_failures == 0
        and injection_failures == 0
    )
    return {
        "two_beat_groups": len(groups),
        "upper_codewords": upper_groups,
        "lower_codewords": lower_groups,
        "covered_physical_outputs": len(covered),
        "unique_covered_physical_outputs": len(set(covered)),
        "input_alignment_beats": 1,
        "output_alignment_beats": 1,
        "raw_alignment_bits": 560,
        "secded_alignment_bits_if_used": 624,
        "cross_frame_grouping": False,
        "operator_signature_failures": exact_signature_failures,
        "functional_mismatches": functional_failures,
        "compensated_closure_failures": closure_failures,
        "arithmetic_injection_trials": (
            len(groups) * 2 * 6 * 2 * DATA_WIDTH
        ),
        "arithmetic_injection_failures": injection_failures,
        "pass": passed,
    }


def architecture_status(summary: dict) -> dict[str, str]:
    functional = summary["functional"]["pass"]
    sub_stream = summary["stream"]["subfft"]["pass"]
    pfft_stream_ok = summary["stream"]["pfft"]["pass"]
    secded = summary["protection_primitives"]["memory_secded"]["pass"]
    tmr = summary["protection_primitives"]["tmr"]["pass"]
    gao = summary["gao_complete_paths"]["pass"]
    sub_ecc = summary["subfft_independent_operator_ecc"]["pass"]
    p_direct = summary["pfft_direct_operator_ecc"]["pass"]
    p_stage10 = summary["pfft_stage10_two_beat_ecc"]["pass"]
    conditions = {
        "S0": functional and sub_stream,
        "S1": functional and sub_stream and gao and tmr,
        "S2": functional and sub_stream and tmr,
        "S3": functional and sub_stream and secded and sub_ecc and tmr,
        "P0": functional and pfft_stream_ok,
        "P1": functional and pfft_stream_ok and secded and p_direct and p_stage10 and tmr,
        "P2": functional and pfft_stream_ok and tmr,
    }
    return {architecture: "VERIFIED" if conditions[architecture] else "FAILED" for architecture in ARCHITECTURES}


def run_gate() -> dict:
    contract = load_json(CONTRACT_PATH)
    matrix = load_json(MATRIX_PATH)
    memory = load_json(MEMORY_PATH)
    legacy = load_json(LEGACY_MATRIX_PATH)
    contract_audit = validate_contract(contract, matrix, memory, legacy)
    if not contract_audit["pass"]:
        raise RuntimeError(f"frozen contract validation failed: {contract_audit['checks']}")
    frames = build_frames(matrix, legacy)
    functional, sub_results, p_results = functional_audit(frames)
    stream = stream_audit(frames, sub_results, p_results)
    fault_frame = frames[legacy["fault_frames"][0]]
    protection_primitives = {
        "memory_secded": secded_audit(fault_frame, legacy["pfft_physical_indices"]),
        "tmr": tmr_audit(fault_frame, legacy["pfft_physical_indices"]),
    }
    sub_ecc = subfft_independent_operator_audit(fault_frame, sub_results[legacy["fault_frames"][0]])
    p_direct = pfft_direct_operator_audit(fault_frame, p_results[legacy["fault_frames"][0]])
    p_stage10 = pfft_stage10_audit(
        fault_frame, p_results[legacy["fault_frames"][0]]
    )
    gao = gao_complete_path_audit(fault_frame)
    summary = {
        "experiment_id": contract["experiment_id"],
        "schema_version": contract["schema_version"],
        "source_authority": contract["implementation_provenance"]["authoritative_source"],
        "external_rtl_used": False,
        "config_hashes": {
            "contract": sha256_file(CONTRACT_PATH),
            "matrix": sha256_file(MATRIX_PATH),
            "memory": sha256_file(MEMORY_PATH),
            "legacy_matrix": sha256_file(LEGACY_MATRIX_PATH),
            "s3_model": sha256_file(EXPERIMENT_DIR / "projects" / "S3" / "run_s3.py"),
            "p1_model": sha256_file(EXPERIMENT_DIR / "projects" / "P1" / "run_p1.py"),
            "gate_script": sha256_file(Path(__file__)),
        },
        "contract_audit": contract_audit,
        "functional": functional,
        "stream": stream,
        "protection_primitives": protection_primitives,
        "gao_complete_paths": gao,
        "subfft_independent_operator_ecc": sub_ecc,
        "pfft_direct_operator_ecc": p_direct,
        "pfft_stage10_two_beat_ecc": p_stage10,
        "check_domain_width_bits": CHECK_DOMAIN_WIDTH,
    }
    summary["architecture_status"] = architecture_status(summary)
    summary["status"] = (
        "VERIFIED"
        if all(status == "VERIFIED" for status in summary["architecture_status"].values())
        else "FAILED"
    )
    return summary


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        summary = run_gate()
        exit_code = 0 if summary["status"] == "VERIFIED" else 2
    except Exception as error:  # preserve a machine-readable failure artifact
        summary = {
            "experiment_id": "FFT1024-SEVEN-ARCH-V2",
            "status": "FAILED",
            "error_type": type(error).__name__,
            "error": str(error),
            "traceback": traceback.format_exc().splitlines(),
            "external_rtl_used": False,
        }
        exit_code = 2
    RESULT_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    result_hash = sha256_file(RESULT_PATH)
    log = {
        "command": f"{sys.executable} {Path(__file__).resolve()}",
        "status": summary["status"],
        "result": str(RESULT_PATH),
        "result_sha256": result_hash,
    }
    LOG_PATH.write_text(
        json.dumps(log, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({
        "status": summary["status"],
        "architecture_status": summary.get("architecture_status"),
        "result": str(RESULT_PATH),
        "result_sha256": result_hash,
    }, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
