#!/usr/bin/env python3
"""Architecture-neutral campaign recording and fault primitives.

This module intentionally contains no S0--P2 trial schedule, architecture
selection, stage map, or expected trial count.  Every project owns those
decisions in its single ``run_<id>.py`` file.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
import traceback
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from common.python.fixed_fft import ComplexWord
from common.python.protection import (
    arithmetic_643_decode,
    flip_component_bit,
    secded_decode,
    secded_encode_complex,
    tmr_vote,
)


EXPERIMENT_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = EXPERIMENT_DIR / "config"
CONTRACT_PATH = CONFIG_DIR / "seven_architecture_contract.json"
MATRIX_PATH = CONFIG_DIR / "seven_architecture_fault_matrix.json"
LEGACY_MATRIX_PATH = CONFIG_DIR / "legacy_protected_trial_set.json"
MEMORY_PATH = CONFIG_DIR / "seven_architecture_memory_map.json"
GATE_PATH = (
    EXPERIMENT_DIR / "results" / "p1_py_v3_001" / "python_gate.json"
)

FIELDNAMES = [
    "experiment_id", "contract_hash", "matrix_hash", "memory_hash",
    "legacy_matrix_hash", "gate_hash", "script_hash", "model_hash",
    "architecture_id", "group", "frame_id", "stage", "fault_domain",
    "boundary", "position", "path_or_lane", "replica", "symbol",
    "component", "bit", "buffer_address", "original_locations", "golden",
    "observed_pre_recovery", "observed_post_recovery",
    "expected_residual_pre_fault", "expected_residual_reference_after_fault",
    "check_outputs_pre_fault", "check_outputs_at_decoder", "detected",
    "corrected", "masked", "final_match", "sdc", "expected_class",
    "pass_fail",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def serializable(value):
    if isinstance(value, ComplexWord):
        return [value.real, value.imag]
    if (
        hasattr(value, "real")
        and hasattr(value, "imag")
        and not isinstance(value, (int, float, complex))
    ):
        return [value.real, value.imag]
    if isinstance(value, (tuple, list)):
        return [serializable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): serializable(item) for key, item in value.items()}
    return value


def compact(value) -> str:
    return json.dumps(serializable(value), separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True)
class ContractBundle:
    contract: dict
    matrix: dict
    legacy: dict
    memory: dict
    gate: dict


def load_contract_bundle(architecture_id: str) -> ContractBundle:
    contract = load_json(CONTRACT_PATH)
    matrix = load_json(MATRIX_PATH)
    legacy = load_json(LEGACY_MATRIX_PATH)
    memory = load_json(MEMORY_PATH)
    gate = load_json(GATE_PATH)
    if contract.get("schema_version") != 5 or matrix.get("schema_version") != 5:
        raise RuntimeError("schema-v5 configuration is required")
    if any(
        item.get("status") != "FROZEN"
        for item in (contract, matrix, memory)
    ):
        raise RuntimeError(
            "V3 contracts are not frozen; project execution is intentionally blocked"
        )
    if gate.get("status") != "VERIFIED":
        raise RuntimeError("seven-project Python qualification gate is not VERIFIED")
    if gate.get("architecture_status", {}).get(architecture_id) != "VERIFIED":
        raise RuntimeError(f"{architecture_id} Python qualification is not VERIFIED")
    if sha256_file(LEGACY_MATRIX_PATH) != matrix[
        "protected_campaign_inheritance"
    ]["sha256"]:
        raise RuntimeError("inherited protected trial matrix hash changed")
    return ContractBundle(contract, matrix, legacy, memory, gate)


class Recorder:
    """CSV writer bound to exactly one architecture."""

    def __init__(
        self,
        writer: csv.DictWriter,
        common_fields: dict,
        architecture_id: str,
        group: str,
    ):
        self.writer = writer
        self.common = common_fields
        self.architecture_id = architecture_id
        self.group = group
        self.counts: dict[str, dict[str, int]] = defaultdict(
            lambda: {"trials": 0, "pass": 0, "fail": 0, "sdc": 0}
        )
        self.total = 0

    def write(
        self,
        *,
        frame_id: str,
        stage,
        fault_domain: str,
        boundary: str,
        position="",
        path_or_lane="",
        replica="",
        symbol="",
        component="",
        bit="",
        buffer_address="",
        original_locations="",
        golden=None,
        observed_pre=None,
        observed_post=None,
        residual_pre=None,
        residual_reference=None,
        checks_pre=None,
        checks_at_decoder=None,
        detected=False,
        corrected=False,
        masked=False,
        final_match=False,
        expected_class: str,
        passed: bool,
    ) -> None:
        sdc = bool(
            not final_match
            and expected_class not in {"declared_out_of_capability", "no_fault"}
        )
        row = {
            **self.common,
            "architecture_id": self.architecture_id,
            "group": self.group,
            "frame_id": frame_id,
            "stage": stage,
            "fault_domain": fault_domain,
            "boundary": boundary,
            "position": position,
            "path_or_lane": path_or_lane,
            "replica": replica,
            "symbol": symbol,
            "component": component,
            "bit": bit,
            "buffer_address": buffer_address,
            "original_locations": (
                compact(original_locations) if original_locations != "" else ""
            ),
            "golden": compact(golden),
            "observed_pre_recovery": compact(observed_pre),
            "observed_post_recovery": compact(observed_post),
            "expected_residual_pre_fault": (
                compact(residual_pre) if residual_pre is not None else ""
            ),
            "expected_residual_reference_after_fault": (
                compact(residual_reference)
                if residual_reference is not None
                else ""
            ),
            "check_outputs_pre_fault": (
                compact(checks_pre) if checks_pre is not None else ""
            ),
            "check_outputs_at_decoder": (
                compact(checks_at_decoder)
                if checks_at_decoder is not None
                else ""
            ),
            "detected": int(bool(detected)),
            "corrected": int(bool(corrected)),
            "masked": int(bool(masked)),
            "final_match": int(bool(final_match)),
            "sdc": int(sdc),
            "expected_class": expected_class,
            "pass_fail": "PASS" if passed else "FAIL",
        }
        self.writer.writerow(row)
        bucket = self.counts[fault_domain]
        bucket["trials"] += 1
        bucket["pass" if passed else "fail"] += 1
        bucket["sdc"] += int(sdc)
        self.total += 1


class HashSink:
    """Text sink used for deterministic, non-persistent replay."""

    def __init__(self):
        self.digest = hashlib.sha256()

    def write(self, value: str) -> int:
        encoded = value.encode("utf-8")
        self.digest.update(encoded)
        return len(value)

    def hexdigest(self) -> str:
        return self.digest.hexdigest().upper()


def record_no_fault(
    recorder: Recorder,
    frame_id: str,
    digest: str,
    boundary: str,
) -> None:
    recorder.write(
        frame_id=frame_id,
        stage="1-10",
        fault_domain="no_fault",
        boundary=boundary,
        golden=digest,
        observed_pre=digest,
        observed_post=digest,
        final_match=True,
        expected_class="no_fault",
        passed=True,
    )


def memory_trial(
    recorder: Recorder,
    frame_id: str,
    stage: int,
    position,
    lane,
    golden: ComplexWord,
    bit: int,
) -> None:
    encoded = secded_encode_complex(golden)
    received = encoded ^ (1 << bit)
    decoded = secded_decode(received)
    match = decoded.complex_word == golden
    recorder.write(
        frame_id=frame_id,
        stage=stage,
        fault_domain="storage",
        boundary="memory_secded_decoder_input",
        position=position,
        path_or_lane=lane,
        bit=bit,
        golden=golden,
        observed_pre=received,
        observed_post=decoded.complex_word,
        detected=decoded.detected,
        corrected=decoded.corrected,
        final_match=match,
        expected_class="single_codeword_bit_corrected",
        passed=decoded.detected and decoded.corrected and match,
    )


def arithmetic_trials(
    recorder: Recorder,
    frame_id: str,
    stage: int,
    position,
    group,
    components: Sequence[str],
    bits: Sequence[int],
    boundary: str = "independent_operator_arithmetic_decoder_input",
    buffer_address="",
    original_locations="",
) -> None:
    golden = group.functional
    residual = group.expected_residual
    checks = group.checks
    for symbol in range(6):
        for component in components:
            for bit in bits:
                received = list(group.outputs)
                received[symbol] = flip_component_bit(
                    received[symbol], component, bit
                )
                decoded = arithmetic_643_decode(received, residual)
                match = decoded.functional == golden
                passed = (
                    decoded.detected
                    and decoded.corrected
                    and decoded.location == symbol
                    and match
                    and (symbol >= 4 or tuple(received[4:]) == checks)
                    and group.expected_residual == residual
                )
                recorder.write(
                    frame_id=frame_id,
                    stage=stage,
                    fault_domain="computation",
                    boundary=boundary,
                    position=position,
                    symbol=symbol,
                    component=component,
                    bit=bit,
                    buffer_address=buffer_address,
                    original_locations=original_locations,
                    golden=golden,
                    observed_pre=received,
                    observed_post=decoded.functional,
                    residual_pre=residual,
                    residual_reference=group.expected_residual,
                    checks_pre=checks,
                    checks_at_decoder=tuple(received[4:]),
                    detected=decoded.detected,
                    corrected=decoded.corrected,
                    final_match=match,
                    expected_class=(
                        "single_independent_operator_symbol_corrected"
                    ),
                    passed=passed,
                )


def inject_and_decode(group, symbol: int, component: str, bit: int):
    """Architecture-neutral single-symbol injection for qualification tools."""

    received = list(group.outputs)
    received[symbol] = flip_component_bit(
        received[symbol], component, bit
    )
    decoded = arithmetic_643_decode(received, group.expected_residual)
    return tuple(received), decoded


def tmr_trials(
    recorder: Recorder,
    frame_id: str,
    stage: int,
    domain: str,
    position,
    golden: ComplexWord,
    components: Sequence[str],
    bits: Sequence[int],
) -> None:
    for replica in range(3):
        for component in components:
            for bit in bits:
                copies = [golden, golden, golden]
                copies[replica] = flip_component_bit(
                    golden, component, bit
                )
                voted, detected = tmr_vote(copies)
                match = voted == golden
                recorder.write(
                    frame_id=frame_id,
                    stage=stage,
                    fault_domain=domain,
                    boundary="complete_stage_replica_voter_input",
                    position=position,
                    replica=replica,
                    component=component,
                    bit=bit,
                    golden=golden,
                    observed_pre=copies,
                    observed_post=voted,
                    detected=detected,
                    masked=match,
                    final_match=match,
                    expected_class=(
                        "single_complete_stage_replica_effect_masked"
                    ),
                    passed=detected and match,
                )


def run_project(
    *,
    architecture_id: str,
    group: str,
    expected_trials: int,
    project_file: Path,
    execute_trials: Callable[[Recorder, ContractBundle], dict | None],
    evidence_boundary: str,
    results_directory: Path | None = None,
) -> int:
    """Run one architecture-owned deterministic campaign."""

    project_results = (
        results_directory
        if results_directory is not None
        else project_file.parent / "results"
    )
    raw_path = project_results / f"{architecture_id.lower()}_fault_raw.csv"
    summary_path = project_results / f"{architecture_id.lower()}_fault_summary.json"
    log_path = project_results / f"{architecture_id.lower()}_fault_run.json"
    try:
        bundle = load_contract_bundle(architecture_id)
        common_fields = {
            "experiment_id": bundle.contract["experiment_id"],
            "contract_hash": sha256_file(CONTRACT_PATH),
            "matrix_hash": sha256_file(MATRIX_PATH),
            "memory_hash": sha256_file(MEMORY_PATH),
            "legacy_matrix_hash": sha256_file(LEGACY_MATRIX_PATH),
            "gate_hash": sha256_file(GATE_PATH),
            "script_hash": sha256_file(project_file),
            "model_hash": sha256_file(project_file),
        }
        project_results.mkdir(parents=True, exist_ok=True)
        with raw_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(
                stream, fieldnames=FIELDNAMES, lineterminator="\n"
            )
            writer.writeheader()
            recorder = Recorder(
                writer, common_fields, architecture_id, group
            )
            extras = execute_trials(recorder, bundle) or {}
        raw_hash = sha256_file(raw_path)

        replay_sink = HashSink()
        replay_writer = csv.DictWriter(
            replay_sink, fieldnames=FIELDNAMES, lineterminator="\n"
        )
        replay_writer.writeheader()
        replay_recorder = Recorder(
            replay_writer, common_fields, architecture_id, group
        )
        execute_trials(replay_recorder, bundle)
        replay_hash = replay_sink.hexdigest()
        deterministic = (
            raw_hash == replay_hash
            and recorder.total == replay_recorder.total
            and dict(recorder.counts) == dict(replay_recorder.counts)
        )
        failures = sum(item["fail"] for item in recorder.counts.values())
        sdc = sum(item["sdc"] for item in recorder.counts.values())
        count_pass = recorder.total == expected_trials
        status = (
            "VERIFIED"
            if deterministic and count_pass and failures == 0 and sdc == 0
            else "FAILED"
        )
        summary = {
            **common_fields,
            "status": status,
            "architecture_id": architecture_id,
            "group": group,
            "trial_count": recorder.total,
            "expected_trial_count": expected_trials,
            "expected_count_pass": count_pass,
            "domains": dict(sorted(recorder.counts.items())),
            "failures": failures,
            "sdc": sdc,
            "determinism": {
                "method": "second_in_process_full_row_replay_to_sha256_sink",
                "raw_sha256": raw_hash,
                "replay_sha256": replay_hash,
                "pass": deterministic,
            },
            "raw_csv": {"path": str(raw_path), "sha256": raw_hash},
            "evidence_boundary": evidence_boundary,
            **extras,
        }
        exit_code = 0 if status == "VERIFIED" else 2
    except Exception as error:
        project_results.mkdir(parents=True, exist_ok=True)
        summary = {
            "experiment_id": "FFT1024-SEVEN-ARCH-V2",
            "architecture_id": architecture_id,
            "status": "FAILED",
            "error_type": type(error).__name__,
            "error": str(error),
            "traceback": traceback.format_exc().splitlines(),
        }
        exit_code = 2

    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    summary_hash = sha256_file(summary_path)
    log_path.write_text(
        json.dumps(
            {
                "command": f"{sys.executable} {project_file}",
                "status": summary["status"],
                "trial_count": summary.get("trial_count"),
                "raw_sha256": summary.get("raw_csv", {}).get("sha256"),
                "summary_sha256": summary_hash,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": summary["status"],
                "architecture_id": architecture_id,
                "trial_count": summary.get("trial_count"),
                "summary": str(summary_path),
                "summary_sha256": summary_hash,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return exit_code


__all__ = [
    "ContractBundle",
    "Recorder",
    "arithmetic_trials",
    "compact",
    "inject_and_decode",
    "memory_trial",
    "record_no_fault",
    "run_project",
    "sha256_file",
    "tmr_trials",
]
