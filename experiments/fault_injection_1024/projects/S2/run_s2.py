#!/usr/bin/env python3
"""S2: ten-stage full-TMR SubFFT fault campaign."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

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
from common.python.fixed_fft import generate_frame, subfft_1024  # noqa: E402
from common.python.protection import flip_component_bit, tmr_vote  # noqa: E402


ARCHITECTURE_ID = "S2"
GROUP = "SubFFT"
EXPECTED_TRIALS = 16809


def execute_s2(recorder: Recorder, bundle: ContractBundle) -> dict:
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
    result = subfft_1024(frames[frame_id])
    for stage in range(1, 11):
        for domain in ("storage", "computation"):
            for position in legacy["pfft_physical_indices"]:
                tmr_trials(
                    recorder,
                    frame_id,
                    stage,
                    domain,
                    position,
                    result.stages[stage - 1].values[position],
                    legacy["components"],
                    legacy["component_bits"],
                )

    golden = frames[frame_id][0]
    copies = [golden, golden, golden]
    copies[0] = flip_component_bit(golden, "real", 0)
    copies[1] = flip_component_bit(golden, "real", 0)
    voted, detected = tmr_vote(copies)
    recorder.write(
        frame_id=frame_id,
        stage=1,
        fault_domain="out_of_capability",
        boundary="complete_stage_replica_voter_input",
        position=0,
        replica="0+1",
        component="real",
        bit=0,
        golden=golden,
        observed_pre=copies,
        observed_post=voted,
        detected=detected,
        masked=voted == golden,
        final_match=voted == golden,
        expected_class="declared_out_of_capability",
        passed=voted != golden,
    )
    return {"protection_claim": "single_complete_stage_replica_effect"}


if __name__ == "__main__":
    raise SystemExit(
        run_project(
            architecture_id=ARCHITECTURE_ID,
            group=GROUP,
            expected_trials=EXPECTED_TRIALS,
            project_file=Path(__file__).resolve(),
            execute_trials=execute_s2,
            evidence_boundary=(
                "S2 injects one effect at a time into one of three complete "
                "stage replicas; the local voter is the recovery boundary."
            ),
        )
    )
