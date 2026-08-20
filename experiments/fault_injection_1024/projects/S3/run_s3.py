#!/usr/bin/env python3
"""S3: Stage-1--8 SECDED/arithmetic ECC plus Stage-9/10 TMR."""

from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

EXPERIMENT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EXPERIMENT))

from common.python.campaign_support import (  # noqa: E402
    ContractBundle,
    Recorder,
    arithmetic_trials,
    compact,
    memory_trial,
    record_no_fault,
    run_project,
    tmr_trials,
)
from common.python.fixed_fft import (  # noqa: E402
    ComplexWord,
    butterfly_scaled,
    canonical_dif_stage,
    generate_frame,
    multiply_twiddle,
    subfft_1024,
)
from common.python.protection import (  # noqa: E402
    WideComplex,
    arithmetic_643_capture_residual,
    arithmetic_643_decode,
    arithmetic_643_encode,
    flip_component_bit,
    secded_decode,
    secded_encode_complex,
)


ARCHITECTURE_ID = "S3"
GROUP = "SubFFT"
EXPECTED_TRIALS = 26794


@dataclass(frozen=True)
class OperatorInput:
    a: ComplexWord
    b: ComplexWord
    branch: str
    exponent: int
    n_points: int

    @property
    def signature(self) -> tuple[int, int, str]:
        return self.n_points, self.exponent, self.branch


@dataclass(frozen=True)
class IndependentOperatorGroup:
    inputs: tuple[OperatorInput, ...]
    encoded_a: tuple[ComplexWord, ...]
    encoded_b: tuple[ComplexWord, ...]
    outputs: tuple[ComplexWord, ...]
    expected_residual: tuple[WideComplex, WideComplex]

    @property
    def functional(self) -> tuple[ComplexWord, ...]:
        return self.outputs[:4]

    @property
    def checks(self) -> tuple[ComplexWord, ComplexWord]:
        return self.outputs[4], self.outputs[5]


def operator_output(item: OperatorInput, a: ComplexWord, b: ComplexWord) -> ComplexWord:
    upper, lower = butterfly_scaled(a, b)
    value = upper if item.branch == "upper" else lower
    return (
        multiply_twiddle(value, item.n_points, item.exponent)
        if item.exponent
        else value
    )


def independent_operator_group(
    inputs: Sequence[OperatorInput],
) -> IndependentOperatorGroup:
    if len(inputs) != 4:
        raise ValueError("S3 arithmetic group requires four functional lanes")
    if len({item.signature for item in inputs}) != 1:
        raise ValueError("S3 group mixes different operators")
    encoded_a = tuple(arithmetic_643_encode([item.a for item in inputs]))
    encoded_b = tuple(arithmetic_643_encode([item.b for item in inputs]))
    outputs = tuple(
        operator_output(inputs[index % 4], encoded_a[index], encoded_b[index])
        for index in range(6)
    )
    return IndependentOperatorGroup(
        tuple(inputs),
        encoded_a,
        encoded_b,
        outputs,
        arithmetic_643_capture_residual(outputs),
    )


def classic_operator_input(
    state: Sequence[ComplexWord], stage: int, position: int
) -> OperatorInput:
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
    return OperatorInput(
        state[base + offset],
        state[base + depth + offset],
        branch,
        exponent,
        n_points,
    )


def build_operator_groups(
    frame: Sequence[ComplexWord], positions: Iterable[int]
) -> dict[int, dict[int, IndependentOperatorGroup]]:
    selected = tuple(positions)
    states = [
        [frame[4 * sample + lane] for sample in range(256)]
        for lane in range(4)
    ]
    reports: dict[int, dict[int, IndependentOperatorGroup]] = {}
    for stage in range(1, 9):
        reports[stage] = {
            position: independent_operator_group(
                [
                    classic_operator_input(states[lane], stage, position)
                    for lane in range(4)
                ]
            )
            for position in selected
        }
        states = [
            list(canonical_dif_stage(state, stage).values)
            for state in states
        ]
    return reports


def execute_s3(recorder: Recorder, bundle: ContractBundle) -> dict:
    legacy = bundle.legacy
    specs = {item["id"]: item for item in legacy["no_fault_frames"]}
    frames = {
        frame_id: generate_frame(specs[frame_id])
        for frame_id in bundle.matrix["no_fault_frames"]
    }
    for frame_id, frame in frames.items():
        digest = hashlib.sha256(
            compact(subfft_1024(frame).output).encode("utf-8")
        ).hexdigest().upper()
        record_no_fault(recorder, frame_id, digest, "group_output_stream")

    frame_id = legacy["fault_frames"][0]
    frame = frames[frame_id]
    result = subfft_1024(frame)
    positions = legacy["trial_schedule"]["S3"][
        "arithmetic_group_positions"
    ]
    groups = build_operator_groups(frame, positions)
    components = legacy["components"]
    bits = legacy["component_bits"]

    for stage in (9, 10):
        for domain in ("storage", "computation"):
            for position in legacy["pfft_physical_indices"]:
                tmr_trials(
                    recorder,
                    frame_id,
                    stage,
                    domain,
                    position,
                    result.stages[stage - 1].values[position],
                    components,
                    bits,
                )

    for stage in range(1, 9):
        for lane in range(4):
            for position in legacy["subfft_positions_per_lane"]:
                golden = result.stages[stage - 1].values[
                    4 * position + lane
                ]
                for bit in legacy["memory_codeword_bits"]:
                    memory_trial(
                        recorder,
                        frame_id,
                        stage,
                        position,
                        lane,
                        golden,
                        bit,
                    )
        for position in positions:
            arithmetic_trials(
                recorder,
                frame_id,
                stage,
                position,
                groups[stage][position],
                components,
                bits,
            )

    golden = frame[0]
    encoded = secded_encode_complex(golden)
    received_codeword = encoded ^ 1 ^ 2
    decoded_memory = secded_decode(received_codeword)
    recorder.write(
        frame_id=frame_id,
        stage=1,
        fault_domain="out_of_capability",
        boundary="memory_secded_decoder_input",
        position=0,
        bit="0+1",
        golden=golden,
        observed_pre=received_codeword,
        observed_post=decoded_memory.complex_word,
        detected=decoded_memory.detected,
        corrected=decoded_memory.corrected,
        final_match=decoded_memory.complex_word == golden,
        expected_class="declared_out_of_capability",
        passed=decoded_memory.detected and not decoded_memory.corrected,
    )

    group = groups[1][positions[0]]
    received = list(group.outputs)
    received[0] = flip_component_bit(received[0], "real", 0)
    received[1] = flip_component_bit(received[1], "real", 0)
    decoded = arithmetic_643_decode(received, group.expected_residual)
    match = decoded.functional == group.functional
    recorder.write(
        frame_id=frame_id,
        stage=1,
        fault_domain="out_of_capability",
        boundary="independent_operator_arithmetic_decoder_input",
        position=0,
        symbol="0+1",
        component="real",
        bit=0,
        golden=group.functional,
        observed_pre=received,
        observed_post=decoded.functional,
        residual_pre=group.expected_residual,
        residual_reference=group.expected_residual,
        checks_pre=group.checks,
        checks_at_decoder=tuple(received[4:]),
        detected=decoded.detected,
        corrected=decoded.corrected,
        final_match=match,
        expected_class="declared_out_of_capability",
        passed=not (decoded.corrected and match),
    )
    return {
        "protection_claim": (
            "stage1_8_single_memory_or_independent_operator_symbol_effect;"
            "stage9_10_single_complete_replica_effect"
        )
    }


if __name__ == "__main__":
    raise SystemExit(
        run_project(
            architecture_id=ARCHITECTURE_ID,
            group=GROUP,
            expected_trials=EXPECTED_TRIALS,
            project_file=Path(__file__).resolve(),
            execute_trials=execute_s3,
            evidence_boundary=(
                "S3 owns its Stage-1--8 SECDED and homogeneous four-lane "
                "independent-operator groups; Stages 9--10 use full-stage TMR."
            ),
        )
    )
