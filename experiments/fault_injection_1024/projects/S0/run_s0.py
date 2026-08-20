#!/usr/bin/env python3
"""S0: unprotected SubFFT baseline campaign.

This file owns the complete S0 schedule.  It intentionally declares only
no-fault functional trials and makes no recovery claim.
"""

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
)
from common.python.fixed_fft import generate_frame, subfft_1024  # noqa: E402


ARCHITECTURE_ID = "S0"
GROUP = "SubFFT"
EXPECTED_TRIALS = 8


def execute_s0(recorder: Recorder, bundle: ContractBundle) -> dict:
    specs = {item["id"]: item for item in bundle.legacy["no_fault_frames"]}
    for frame_id in bundle.matrix["no_fault_frames"]:
        output = subfft_1024(generate_frame(specs[frame_id])).output
        digest = hashlib.sha256(compact(output).encode("utf-8")).hexdigest().upper()
        record_no_fault(
            recorder, frame_id, digest, "group_output_stream"
        )
    return {"protection_claim": "none"}


if __name__ == "__main__":
    raise SystemExit(
        run_project(
            architecture_id=ARCHITECTURE_ID,
            group=GROUP,
            expected_trials=EXPECTED_TRIALS,
            project_file=Path(__file__).resolve(),
            execute_trials=execute_s0,
            evidence_boundary=(
                "S0 is an independent complete SubFFT functional baseline; "
                "it supplies no detection, correction, or masking claim."
            ),
        )
    )
