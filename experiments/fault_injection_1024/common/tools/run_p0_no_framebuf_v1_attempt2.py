#!/usr/bin/env python3
"""Sandbox-external isolated Yosys attempt2 for P0-NO-FRAMEBUF-V1-001."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import run_p0_no_framebuf_v1 as base


ATTEMPT1_RESULTS = (
    base.EXPERIMENT / "results" / "p0_no_framebuf_v1_001" / "attempt1"
)
base.RESULTS = (
    base.EXPERIMENT / "results" / "p0_no_framebuf_v1_001" / "attempt2"
)
base.LOGS = base.EXPERIMENT / "logs" / "p0_no_framebuf_v1_001" / "attempt2"
base.BUILD = base.EXPERIMENT / "build" / "p0_no_framebuf_v1_001" / "attempt2"


def main() -> int:
    source_qualification = ATTEMPT1_RESULTS / "qualification.json"
    if not source_qualification.is_file():
        print("STOP attempt1 qualification evidence missing", file=sys.stderr)
        return 2
    payload = json.loads(source_qualification.read_text(encoding="utf-8"))
    if payload.get("status") != "VERIFIED":
        print("STOP attempt1 qualification is not VERIFIED", file=sys.stderr)
        return 2
    if base.RESULTS.exists() or base.LOGS.exists() or base.BUILD.exists():
        print("STOP attempt2 artifact directory exists; refusing overwrite", file=sys.stderr)
        return 2
    base.RESULTS.mkdir(parents=True)
    shutil.copy2(source_qualification, base.RESULTS / "qualification.json")
    base.write_json(
        base.RESULTS / "attempt2_provenance.json",
        {
            "schema": "p0-no-framebuf-v1-001-attempt2-provenance-v1",
            "record_id": base.RECORD,
            "reason": "attempt1 preflight failed before read_verilog with GetShortPathName",
            "attempt1_qualification": base.record(source_qualification),
            "attempt1_preflight": base.record(ATTEMPT1_RESULTS / "preflight.json"),
            "policy": "new directories; no attempt1 artifact overwritten",
        },
    )
    return base.synthesize()


if __name__ == "__main__":
    raise SystemExit(main())
