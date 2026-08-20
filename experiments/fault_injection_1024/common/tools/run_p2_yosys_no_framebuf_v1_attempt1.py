#!/usr/bin/env python3
"""Controlled Yosys attempt1 for P2-YOSYS-NO-FRAMEBUF-V1-001."""

from __future__ import annotations

import json
import shutil
import sys

import run_p0_no_framebuf_v1 as base


EXPERIMENT = base.EXPERIMENT
QUALIFICATION = (
    EXPERIMENT
    / "results"
    / "p2_rtl_no_framebuf_v1_001"
    / "attempt1"
    / "qualification.json"
)
CONTRACT = EXPERIMENT / "P2_YOSYS_NO_FRAMEBUF_V1_001.md"
ORIGINAL_P2 = EXPERIMENT / "projects" / "P2" / "top_p2_pfft_tmr.sv"
ISOLATED_P2 = (
    EXPERIMENT / "projects" / "P2" / "top_p2_pfft_tmr_no_framebuf_v1.sv"
)

base.RECORD = "P2-YOSYS-NO-FRAMEBUF-V1-001"
base.TOP = "top_p2_pfft_tmr_no_framebuf_v1"
base.RESULTS = (
    EXPERIMENT / "results" / "p2_yosys_no_framebuf_v1_001" / "attempt1"
)
base.LOGS = EXPERIMENT / "logs" / "p2_yosys_no_framebuf_v1_001" / "attempt1"
base.BUILD = EXPERIMENT / "build" / "p2_yosys_no_framebuf_v1_001" / "attempt1"
base.SOURCES = base.COMMON + (ORIGINAL_P2, ISOLATED_P2)
base.HISTORICAL = {
    "LC_estimate": 69464,
    "LUT1_to_LUT6": 95826,
    "FF": 12474,
    "DSP48E1": 1392,
    "RAMB18E1": 0,
    "RAMB36E1": 16,
    "BRAM36_equivalent": 16.0,
}


def main() -> int:
    if not QUALIFICATION.is_file():
        print("STOP qualification missing", file=sys.stderr)
        return 2
    qualified = json.loads(QUALIFICATION.read_text(encoding="utf-8"))
    if qualified.get("status") != "VERIFIED":
        print("STOP qualification is not VERIFIED", file=sys.stderr)
        return 2
    if base.RESULTS.exists() or base.LOGS.exists() or base.BUILD.exists():
        print("STOP attempt1 directory exists; refusing overwrite", file=sys.stderr)
        return 2
    base.RESULTS.mkdir(parents=True)
    shutil.copy2(QUALIFICATION, base.RESULTS / "qualification.json")
    base.write_json(base.RESULTS / "input_provenance.json", {
        "schema": "p2-yosys-no-framebuf-v1-001-input-provenance-v1",
        "record_id": base.RECORD,
        "contract": base.record(CONTRACT),
        "qualification": base.record(QUALIFICATION),
        "sources": [base.record(path) for path in base.SOURCES],
        "selected_top": base.TOP,
        "historical_baseline": base.HISTORICAL,
    })
    code = base.synthesize()
    if code != 0:
        return code

    raw_path = base.RESULTS / "resource_result.json"
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    resources = raw["resources"]
    final_path = base.RESULTS / "p2_resource_result.json"
    base.write_json(final_path, {
        "schema": "p2-yosys-no-framebuf-v1-001-resource-result-v1",
        "status": "VERIFIED",
        "record_id": base.RECORD,
        "scope": "Yosys synth_xilinx -family xc7 estimate; not Vivado implementation",
        "selected_top": base.TOP,
        "qualification": base.record(base.RESULTS / "qualification.json"),
        "input_provenance": base.record(base.RESULTS / "input_provenance.json"),
        "version_gate": base.record(base.RESULTS / "yosys_version_gate.json"),
        "preflight": base.record(base.RESULTS / "preflight.json"),
        "raw_support_result": base.record(raw_path),
        "resources": resources,
        "historical_p2": base.HISTORICAL,
        "delta_vs_historical_p2": {
            key: resources[key] - value
            for key, value in base.HISTORICAL.items()
        },
        "cell_counts": raw["cell_counts"],
        "post_synthesis_netlist": raw["netlist"],
        "synthesis_log": raw["log"],
        "structure_boundary": {
            "tmr_stage_wrappers": 10,
            "terminal_frame_pair_buffer_instances": 0,
        },
    })
    print(json.dumps(resources, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
