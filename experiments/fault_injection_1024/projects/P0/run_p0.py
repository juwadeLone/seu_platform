#!/usr/bin/env python3
"""P0: unprotected PFFT baseline campaign."""

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
from common.python.fixed_fft import generate_frame, pfft_no_exchange_1024  # noqa: E402


ARCHITECTURE_ID = "P0"
GROUP = "PFFT"
EXPECTED_TRIALS = 8


def execute_p0(recorder: Recorder, bundle: ContractBundle) -> dict:
    specs = {item["id"]: item for item in bundle.legacy["no_fault_frames"]}
    for frame_id in bundle.matrix["no_fault_frames"]:
        output = pfft_no_exchange_1024(generate_frame(specs[frame_id])).output
        digest = hashlib.sha256(compact(output).encode("utf-8")).hexdigest().upper()
        record_no_fault(
            recorder,
            frame_id,
            digest,
            "group_output_stream_with_common_2x1024_reorder_buffer",
        )
    return {"protection_claim": "none"}


if __name__ == "__main__":
    raise SystemExit(
        run_project(
            architecture_id=ARCHITECTURE_ID,
            group=GROUP,
            expected_trials=EXPECTED_TRIALS,
            project_file=Path(__file__).resolve(),
            execute_trials=execute_p0,
            evidence_boundary=(
                "P0 is an independent complete PFFT functional baseline with "
                "the common frame buffer; it makes no recovery claim."
            ),
        )
    )
