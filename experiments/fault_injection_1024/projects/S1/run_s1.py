#!/usr/bin/env python3
"""S1: Gao [7,4,3] complete-SubFFT path ECC plus Stage-9/10 TMR."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Sequence

EXPERIMENT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EXPERIMENT))

from common.python.campaign_support import (  # noqa: E402
    ContractBundle,
    Recorder,
    compact,
    record_no_fault,
    run_project,
    tmr_trials,
)
from common.python.fixed_fft import (  # noqa: E402
    ComplexWord,
    ZERO,
    classic_r2sdf_fft,
    generate_frame,
    subfft_1024,
)
from common.python.protection import (  # noqa: E402
    flip_component_bit,
    gao_743_capture_residual,
    gao_743_decode,
    gao_743_encode,
)


ARCHITECTURE_ID = "S1"
GROUP = "SubFFT"
EXPECTED_TRIALS = 34729


def build_gao_codewords(
    frame: Sequence[ComplexWord],
) -> tuple[tuple[ComplexWord, ...], ...]:
    """Execute seven complete 256-point coded SubFFT paths."""

    functional = [
        [frame[4 * sample + lane] for sample in range(256)]
        for lane in range(4)
    ]
    coded_inputs = [[ZERO for _ in range(256)] for _ in range(7)]
    for sample in range(256):
        codeword = gao_743_encode(
            [functional[lane][sample] for lane in range(4)]
        )
        for path in range(7):
            coded_inputs[path][sample] = codeword[path]
    coded_outputs = [
        classic_r2sdf_fft(path_values)[0].output
        for path_values in coded_inputs
    ]
    return tuple(
        tuple(coded_outputs[path][sample] for path in range(7))
        for sample in range(256)
    )


def execute_s1(recorder: Recorder, bundle: ContractBundle) -> dict:
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
    codewords = build_gao_codewords(frame)
    components = legacy["components"]
    bits = legacy["component_bits"]

    schedule = legacy["trial_schedule"]["S1"]
    for origin_stage in schedule["path_effect_stages"]:
        for domain in schedule["path_effect_domains"]:
            for position in schedule["path_positions_per_lane"]:
                codeword = codewords[position]
                residual = gao_743_capture_residual(codeword)
                golden = gao_743_decode(codeword, residual).functional
                checks = (codeword[0], codeword[1], codeword[3])
                for path in legacy["architecture_domains"]["S1"]["paths"]:
                    for component in components:
                        for bit in bits:
                            received = list(codeword)
                            received[path] = flip_component_bit(
                                received[path], component, bit
                            )
                            decoded = gao_743_decode(received, residual)
                            match = decoded.functional == golden
                            recorder.write(
                                frame_id=frame_id,
                                stage=origin_stage,
                                fault_domain=domain,
                                boundary=(
                                    "stage8_complete_path_decoder_input_effect"
                                ),
                                position=position,
                                path_or_lane=path,
                                component=component,
                                bit=bit,
                                golden=golden,
                                observed_pre=received,
                                observed_post=decoded.functional,
                                residual_pre=residual,
                                residual_reference=(
                                    gao_743_capture_residual(codeword)
                                ),
                                checks_pre=checks,
                                checks_at_decoder=(
                                    received[0],
                                    received[1],
                                    received[3],
                                ),
                                detected=decoded.detected,
                                corrected=decoded.corrected,
                                final_match=match,
                                expected_class=(
                                    "single_complete_path_effect_corrected_at_stage8"
                                ),
                                passed=(
                                    decoded.detected
                                    and decoded.corrected
                                    and decoded.location == path
                                    and match
                                    and residual
                                    == gao_743_capture_residual(codeword)
                                ),
                            )

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

    codeword = codewords[0]
    residual = gao_743_capture_residual(codeword)
    received = list(codeword)
    received[0] = flip_component_bit(received[0], "real", 0)
    received[1] = flip_component_bit(received[1], "real", 0)
    decoded = gao_743_decode(received, residual)
    golden = gao_743_decode(codeword, residual).functional
    match = decoded.functional == golden
    recorder.write(
        frame_id=frame_id,
        stage=8,
        fault_domain="out_of_capability",
        boundary="stage8_complete_path_decoder_input",
        position=0,
        path_or_lane="0+1",
        component="real",
        bit=0,
        golden=golden,
        observed_pre=received,
        observed_post=decoded.functional,
        residual_pre=residual,
        residual_reference=residual,
        detected=decoded.detected,
        corrected=decoded.corrected,
        final_match=match,
        expected_class="declared_out_of_capability",
        passed=not (decoded.corrected and match),
    )
    return {
        "protection_claim": (
            "single_complete_path_effect_plus_stage9_10_single_replica_effect"
        )
    }


if __name__ == "__main__":
    raise SystemExit(
        run_project(
            architecture_id=ARCHITECTURE_ID,
            group=GROUP,
            expected_trials=EXPECTED_TRIALS,
            project_file=Path(__file__).resolve(),
            execute_trials=execute_s1,
            evidence_boundary=(
                "S1 owns seven complete coded SubFFT paths. Stage-1--8 "
                "path-confined effects are corrected only at the Stage-8 Gao "
                "decoder; Stages 9--10 use local full-stage TMR voters."
            ),
        )
    )
