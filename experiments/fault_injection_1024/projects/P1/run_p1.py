#!/usr/bin/env python3
"""P1: Stage-1--7/10 arithmetic ECC, SECDED, and Stage-8--9 TMR.

Stage 10 groups four complete radix-2 butterflies from two adjacent four-lane
beats.  The four upper outputs and four lower outputs form independent
``[6,4,3]`` codewords.  No cross-position or cross-frame Stage-8 ECC grouping
is part of this architecture.
"""

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
    exchange_phi,
    generate_frame,
    multiply_twiddle,
    pfft_1024,
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


ARCHITECTURE_ID = "P1"
GROUP = "PFFT"
EXPECTED_TRIALS = 124834


@dataclass(frozen=True)
class OperatorInput:
    a: ComplexWord
    b: ComplexWord
    branch: str
    exponent: int
    n_points: int
    frame: int | None = None
    physical_index: int | None = None

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


def independent_operator_group(
    inputs: Sequence[OperatorInput],
) -> IndependentOperatorGroup:
    if len(inputs) != 4:
        raise ValueError("P1 arithmetic group requires four functional symbols")
    signatures = {item.signature for item in inputs}
    if len(signatures) != 1:
        raise ValueError(f"P1 operator group is heterogeneous: {signatures}")
    n_points, exponent, branch = next(iter(signatures))
    encoded_a = tuple(arithmetic_643_encode([item.a for item in inputs]))
    encoded_b = tuple(arithmetic_643_encode([item.b for item in inputs]))
    outputs: list[ComplexWord] = []
    for a, b in zip(encoded_a, encoded_b):
        upper, lower = butterfly_scaled(a, b)
        value = upper if branch == "upper" else lower
        outputs.append(
            multiply_twiddle(value, n_points, exponent)
            if exponent
            else value
        )
    output_tuple = tuple(outputs)
    return IndependentOperatorGroup(
        tuple(inputs),
        encoded_a,
        encoded_b,
        output_tuple,
        arithmetic_643_capture_residual(output_tuple),
    )


def pfft_stage_inputs(
    frame: Sequence[ComplexWord],
) -> tuple[tuple[ComplexWord, ...], ...]:
    if len(frame) != 1024:
        raise ValueError("P1 requires a 1024-sample frame")
    result = pfft_1024(frame)
    states: list[tuple[ComplexWord, ...]] = [tuple(frame)]
    states.extend(trace.values for trace in result.stages[:-1])
    return tuple(states)


def operator_input(
    state: Sequence[ComplexWord],
    stage: int,
    physical_index: int,
    phi: Sequence[Sequence[int]],
    frame: int | None = None,
) -> OperatorInput:
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
    return OperatorInput(
        state[base + offset],
        state[base + depth + offset],
        branch,
        exponent,
        n_points,
        frame,
        physical_index,
    )


def direct_operator_groups(
    frame: Sequence[ComplexWord],
    stages: Iterable[int],
    beats: Iterable[int],
) -> dict[int, dict[int, IndependentOperatorGroup]]:
    selected = tuple(beats)
    states = pfft_stage_inputs(frame)
    phi = exchange_phi(1024)
    reports: dict[int, dict[int, IndependentOperatorGroup]] = {}
    for stage in stages:
        reports[stage] = {}
        for beat in selected:
            reports[stage][beat] = independent_operator_group(
                [
                    operator_input(
                        states[stage - 1],
                        stage,
                        physical_index,
                        phi,
                    )
                    for physical_index in range(4 * beat, 4 * beat + 4)
                ]
            )
    return reports


def stage10_operator_groups(
    frame: Sequence[ComplexWord],
) -> tuple[
    tuple[IndependentOperatorGroup, IndependentOperatorGroup], ...
]:
    """Build 128 two-beat groups covering all 512 Stage-10 butterflies.

    Each eight-symbol window contains four complete butterflies:
    ``(0,1), (2,3), (4,5), (6,7)``.  Even physical indices are the four
    upper outputs and odd physical indices are the four lower outputs.
    """

    input_state = pfft_stage_inputs(frame)[9]
    phi = [[0] * 1024 for _ in range(9)]
    groups: list[
        tuple[IndependentOperatorGroup, IndependentOperatorGroup]
    ] = []
    for two_beat_group in range(128):
        base = 8 * two_beat_group
        upper = independent_operator_group(
            [
                operator_input(input_state, 10, base + offset, phi)
                for offset in (0, 2, 4, 6)
            ]
        )
        lower = independent_operator_group(
            [
                operator_input(input_state, 10, base + offset, phi)
                for offset in (1, 3, 5, 7)
            ]
        )
        groups.append((upper, lower))
    return tuple(groups)


def execute_p1(recorder: Recorder, bundle: ContractBundle) -> dict:
    legacy = bundle.legacy
    specs = {item["id"]: item for item in legacy["no_fault_frames"]}
    frames = {
        frame_id: generate_frame(specs[frame_id])
        for frame_id in bundle.matrix["no_fault_frames"]
    }
    for frame_id, frame in frames.items():
        digest = hashlib.sha256(
            compact(pfft_1024(frame).output).encode("utf-8")
        ).hexdigest().upper()
        record_no_fault(
            recorder,
            frame_id,
            digest,
            "group_output_stream_with_common_2x1024_reorder_buffer",
        )

    frame_id = legacy["fault_frames"][0]
    frame = frames[frame_id]
    result = pfft_1024(frame)
    components = legacy["components"]
    bits = legacy["component_bits"]
    direct = direct_operator_groups(
        frame, range(1, 8), legacy["pfft_direct_group_beats"]
    )
    stage10 = stage10_operator_groups(frame)

    for stage in (8, 9):
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

    for stage in range(1, 8):
        for position in legacy["pfft_physical_indices"]:
            golden = result.stages[stage - 1].values[position]
            for bit in legacy["memory_codeword_bits"]:
                memory_trial(
                    recorder,
                    frame_id,
                    stage,
                    position,
                    position % 4,
                    golden,
                    bit,
                )

    for stage in range(1, 8):
        for beat in legacy["pfft_direct_group_beats"]:
            arithmetic_trials(
                recorder,
                frame_id,
                stage,
                beat,
                direct[stage][beat],
                components,
                bits,
            )

    for two_beat_group, (upper, lower) in enumerate(stage10):
        for branch, group in (("upper", upper), ("lower", lower)):
            arithmetic_trials(
                recorder,
                frame_id,
                10,
                f"two_beat:{two_beat_group}:{branch}",
                group,
                components,
                bits,
                boundary=(
                    "stage10_two_adjacent_beats_complete_butterflies_"
                    f"{branch}_decoder_input"
                ),
                original_locations=tuple(
                    item.physical_index for item in group.inputs
                ),
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

    group = direct[1][legacy["pfft_direct_group_beats"][0]]
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
            "stage1_7_single_memory_or_independent_operator_symbol_effect;"
            "stage8_9_single_complete_replica_effect;"
            "stage10_two_beat_independent_operator_symbol_effect"
        ),
        "p1_stage10": {
            "two_beat_groups": len(stage10),
            "functional_butterflies_per_group": 4,
            "upper_codewords": len(stage10),
            "lower_codewords": len(stage10),
            "covered_physical_outputs": 1024,
            "alignment": "one_input_beat_plus_one_output_beat_registers",
            "cross_frame_grouping": False,
        },
    }


if __name__ == "__main__":
    raise SystemExit(
        run_project(
            architecture_id=ARCHITECTURE_ID,
            group=GROUP,
            expected_trials=EXPECTED_TRIALS,
            project_file=Path(__file__).resolve(),
            execute_trials=execute_p1,
            evidence_boundary=(
                "P1 owns Stage-1--7 direct common-operator groups, Stage-8/9 "
                "full-stage TMR, and Stage-10 two-adjacent-beat complete-"
                "butterfly upper/lower arithmetic ECC groups."
            ),
            results_directory=(
                Path(__file__).resolve().parent
                / "results"
                / "p1_py_v3_001"
            ),
        )
    )
