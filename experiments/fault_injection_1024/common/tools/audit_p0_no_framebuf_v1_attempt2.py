#!/usr/bin/env python3
"""Create a non-overwriting corrected recursive resource audit."""

from __future__ import annotations

import json
import re
import sys

import run_p0_no_framebuf_v1 as base


def main() -> int:
    results = base.EXPERIMENT / "results" / "p0_no_framebuf_v1_001" / "attempt2"
    build = base.EXPERIMENT / "build" / "p0_no_framebuf_v1_001" / "attempt2"
    logs = base.EXPERIMENT / "logs" / "p0_no_framebuf_v1_001" / "attempt2"
    output = results / "resource_result_corrected_recursive_leaf_audit.json"
    if output.exists():
        print("STOP corrected audit exists; refusing overwrite", file=sys.stderr)
        return 2
    original = results / "resource_result.json"
    netlist = build / "yosys" / "post_synthesis_netlist.json"
    synth_log = logs / "yosys_synthesis.log"
    for path in (original, netlist, synth_log):
        if not path.is_file():
            print(f"STOP missing evidence: {path}", file=sys.stderr)
            return 2
    counts = base.top_cell_counts(netlist)
    log_text = synth_log.read_text(encoding="utf-8")
    lc_matches = re.findall(r"Estimated number of LCs:\s+(\d+)", log_text)
    resources = {
        "LC_estimate": int(lc_matches[-1]) if lc_matches else None,
        "LUT1_to_LUT6": sum(counts[f"LUT{i}"] for i in range(1, 7)),
        "FF": sum(counts[name] for name in ("FDRE", "FDSE", "FDCE", "FDPE")),
        "DSP48E1": counts["DSP48E1"],
        "RAMB18E1": counts["RAMB18E1"],
        "RAMB36E1": counts["RAMB36E1"],
        "BRAM36_equivalent": counts["RAMB36E1"] + 0.5 * counts["RAMB18E1"],
        "distributed_memory_cells_total": sum(
            count
            for name, count in counts.items()
            if name.startswith("RAM") and name not in {"RAMB18E1", "RAMB36E1"}
        ),
    }
    base.write_json(output, {
        "schema": "p0-no-framebuf-v1-001-corrected-recursive-leaf-audit-v1",
        "status": "VERIFIED",
        "record_id": base.RECORD,
        "correction_reason": (
            "initial parser counted only direct top cells; first recursive audit "
            "also descended into Xilinx simulation-model modules instead of "
            "treating mapped Xilinx primitives as leaf cells"
        ),
        "synthesis_rerun": False,
        "original_result_preserved": base.record(original),
        "source_netlist": base.record(netlist),
        "source_log": base.record(synth_log),
        "resources": resources,
        "historical_p0": base.HISTORICAL,
        "delta_vs_historical_p0": {
            name: resources[name] - value
            for name, value in base.HISTORICAL.items()
        },
        "recursive_leaf_cell_counts": dict(sorted(counts.items())),
    })
    print(json.dumps(resources, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
