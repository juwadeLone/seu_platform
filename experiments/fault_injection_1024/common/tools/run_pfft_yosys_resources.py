#!/usr/bin/env python3
"""P0/P1/P2 Yosys resource runner for PFFT-RES-V2-001."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import run_yosys_resources as base


HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
CONFIG = EXPERIMENT / "config" / "pfft_resource_reevaluation_v2.json"
MEMORY_MAP = EXPERIMENT / "config" / "seven_architecture_memory_map.json"
RESULTS = EXPERIMENT / "results" / "pfft_resource_v2_001"
QUALIFICATION = RESULTS / "qualification_attempt2" / "rtl_qualification.json"
MANIFEST = RESULTS / "qualification_attempt2" / "rtl_structure_manifest.json"
LOGS = EXPERIMENT / "logs" / "pfft_resource_v2_001"
BUILD = EXPERIMENT / "build" / "pfft_resource_v2_001" / "yosys"
ARCH_ORDER = ("P0", "P1", "P2")
EXPECTED_SOURCES = (
    "common/rtl/twiddle_rom_1024.sv",
    "common/rtl/fft_common.sv",
    "common/rtl/protection_rtl.sv",
    "common/rtl/datapath_v5.sv",
    "common/rtl/protection_primitives_v5.sv",
    "common/rtl/protected_stages_v5.sv",
    "projects/P0/top_p0_pfft_unprotected.sv",
    "projects/P1/top_p1_pfft_ecc.sv",
    "projects/P2/top_p2_pfft_tmr.sv",
)

base.RESULTS = RESULTS
base.LOGS = LOGS
base.BUILD = BUILD
base.ARCH_ORDER = ARCH_ORDER


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    required = (
        CONFIG,
        MEMORY_MAP,
        QUALIFICATION,
        MANIFEST,
        base.YOSYS,
        base.YOSYS_RUNTIME,
    )
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise base.GateFailure("input_validation", "missing frozen inputs", details=missing)

    config = base.load(CONFIG)
    memory_map = base.load(MEMORY_MAP)
    qualification = base.load(QUALIFICATION)
    manifest = base.load(MANIFEST)
    failures: list[str] = []
    if config.get("status") != "FROZEN":
        failures.append("PFFT Yosys contract is not FROZEN")
    if memory_map.get("status") != "FROZEN":
        failures.append("memory map is not FROZEN")
    if qualification.get("status") != "VERIFIED":
        failures.append("PFFT RTL qualification is not VERIFIED")
    if manifest.get("status") != "VERIFIED":
        failures.append("PFFT RTL structure manifest is not VERIFIED")
    if tuple(config.get("source_files", ())) != EXPECTED_SOURCES:
        failures.append("source_files do not equal the frozen PFFT nine-file source set")
    if tuple(config.get("tops", {}).keys()) != ARCH_ORDER:
        failures.append("top ordering is not P0,P1,P2")
    if set(qualification.get("bit_exact", {})) != set(ARCH_ORDER):
        failures.append("RTL qualification does not contain exactly P0,P1,P2")
    if qualification.get("manifest_sha256", "").upper() != base.sha256(MANIFEST):
        failures.append("qualification manifest hash does not match current manifest")
    if config.get("target_evidence", {}).get("synth_xilinx_family") != "xc7":
        failures.append("synth_xilinx family is not xc7")
    missing_sources = [
        str(EXPERIMENT / relative)
        for relative in config.get("source_files", ())
        if not (EXPERIMENT / relative).exists()
    ]
    if missing_sources:
        failures.append("missing source files: " + ", ".join(missing_sources))

    referenced_profiles = {
        profile
        for profiles in config.get("architecture_memory_profiles", {}).values()
        for profile in profiles
    }
    if not referenced_profiles.issubset(config.get("memory_profiles", {})):
        failures.append("architecture references an undefined memory profile")

    long_hash = base.sha256(base.YOSYS)
    runtime_hash = base.sha256(base.YOSYS_RUNTIME)
    if long_hash != runtime_hash:
        failures.append("long-path and runtime-short-path Yosys hashes differ")
    version = base.tool_version()
    if version != config.get("version"):
        failures.append(f"Yosys version mismatch: {version!r}")
    if failures:
        raise base.GateFailure(
            "input_validation",
            "frozen PFFT input validation failed",
            details=failures,
        )

    validation = {
        "schema": "pfft-resource-v2-001-input-validation-v1",
        "status": "VERIFIED",
        "timestamp_utc": utc_now(),
        "config": str(CONFIG),
        "config_sha256": base.sha256(CONFIG),
        "memory_map": str(MEMORY_MAP),
        "memory_map_sha256": base.sha256(MEMORY_MAP),
        "qualification": str(QUALIFICATION),
        "qualification_sha256": base.sha256(QUALIFICATION),
        "manifest": str(MANIFEST),
        "manifest_sha256": base.sha256(MANIFEST),
        "yosys_specified_executable": str(base.YOSYS),
        "yosys_runtime_alias": str(base.YOSYS_RUNTIME),
        "yosys_executable_sha256": long_hash,
        "yosys_version": version,
        "python": sys.executable,
        "python_sha256": base.sha256(Path(sys.executable)),
        "sources": [
            {
                "relative_path": relative,
                "absolute_path": str(EXPERIMENT / relative),
                "sha256": base.sha256(EXPERIMENT / relative),
            }
            for relative in config["source_files"]
        ],
        "tops": config["tops"],
    }
    return config, validation


def write_failure(
    path: Path,
    error: base.GateFailure,
    validation: dict[str, Any] | None,
    completed: list[dict[str, Any]],
    attempt: str,
) -> None:
    base.write_json(
        path,
        {
            "schema": "pfft-resource-v2-001-failure-v1",
            "status": "FAILED" if error.stage in {"preflight", "synthesis"} else "BLOCKED",
            "timestamp_utc": utc_now(),
            "attempt": attempt,
            "stage": error.stage,
            "architecture_id": error.architecture_id,
            "message": str(error),
            "details": error.details,
            "validation": validation,
            "completed_architectures": completed,
            "policy": "no_silent_retry_no_final_table_on_any_failure",
        },
    )


def run_preflight(config: dict[str, Any], validation: dict[str, Any]) -> int:
    directory = BUILD / "preflight"
    output = RESULTS / "yosys_preflight.json"
    if directory.exists() or output.exists():
        raise base.GateFailure("preflight", "preflight artifacts already exist; refusing an implicit rerun")
    directory.mkdir(parents=True)
    statuses: dict[str, Any] = {}
    for architecture_id in ARCH_ORDER:
        print(f"PREFLIGHT START {architecture_id}", flush=True)
        script = base.write_script(config, architecture_id, "preflight", directory)
        log = LOGS / f"yosys_preflight_{architecture_id}.log"
        result = base.run_yosys(config, architecture_id, "preflight", script, log, directory)
        statuses[architecture_id] = {
            "exit_code": result.returncode,
            "script": str(script),
            "script_sha256": base.sha256(script),
            "log": str(log),
            "log_sha256": base.sha256(log),
        }
        print(f"PREFLIGHT END {architecture_id} exit={result.returncode}", flush=True)
        if result.returncode != 0:
            base.write_json(
                output,
                {
                    "schema": "pfft-resource-v2-001-preflight-v1",
                    "status": "FAILED",
                    "validation": validation,
                    "tops": statuses,
                },
            )
            return 2
    base.write_json(
        output,
        {
            "schema": "pfft-resource-v2-001-preflight-v1",
            "status": "VERIFIED",
            "validation": validation,
            "tops": statuses,
        },
    )
    print(f"PREFLIGHT VERIFIED {output} SHA256={base.sha256(output)}", flush=True)
    return 0


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# PFFT-RES-V2-001 Yosys resource audit",
        "",
        f"Overall status: **{summary['status']}**",
        "",
        f"- Tool: `{summary['yosys_version']}`",
        "- Flow: `synth_xilinx -family xc7` on the frozen P0/P1/P2 source set.",
        "- Boundary: synthesis resource estimates only; not Vivado post-implementation utilization, timing, Fmax, power, or board measurement.",
        "- Baseline: P1 and P2 are compared only with the complete unprotected P0 top.",
        "- LUT/LC, FF, DSP48E1 and BRAM remain separate metrics; they are not added into one total.",
        "",
        "| ID | LUT (est. LC) | FF | DSP48E1 | RAMB18 | RAMB36 | BRAM36 equiv. |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary["group"]:
        lines.append(
            f"| {row['architecture_id']} | {row['lut']} | {row['ff']} | {row['dsp']} | "
            f"{row['bram18']} | {row['bram36']} | {row['bram36_equivalent']} |"
        )
    lines.extend(("", "## Pre-run DSP diagnostic", ""))
    for item in summary["dsp_diagnostic"]["checks"]:
        lines.append(
            f"- {item['architecture_id']}: expected {item['expected_DSP48E1']}, "
            f"measured {item['measured_DSP48E1']}, pass={item['pass']}."
        )
    lines.append("")
    return "\n".join(lines)


def run_formal(config: dict[str, Any], validation: dict[str, Any], attempt: str) -> int:
    if attempt != "attempt1":
        raise base.GateFailure("runner", "PFFT-RES-V2-001 authorizes only attempt1")
    directory = BUILD / attempt
    failure_path = RESULTS / f"yosys_{attempt}_failure.json"
    final_paths = (
        RESULTS / "yosys_pfft_summary.json",
        RESULTS / "yosys_pfft_group.csv",
        RESULTS / "yosys_pfft_memory_mapping_audit.json",
        RESULTS / "yosys_pfft_resource_audit.md",
    )
    if directory.exists() or failure_path.exists() or any(path.exists() for path in final_paths):
        raise base.GateFailure("runner", "formal attempt or final artifacts already exist; refusing an implicit rerun")
    directory.mkdir(parents=True)
    rows: list[dict[str, Any]] = []
    try:
        for architecture_id in ARCH_ORDER:
            print(f"SYNTHESIS START {architecture_id}", flush=True)
            script = base.write_script(config, architecture_id, "synth", directory)
            log = LOGS / f"yosys_{attempt}_{architecture_id}.log"
            result = base.run_yosys(config, architecture_id, "synth", script, log, directory)
            if result.returncode != 0:
                raise base.GateFailure(
                    "synthesis",
                    f"Yosys exited {result.returncode}",
                    architecture_id,
                    {"log": str(log), "log_sha256": base.sha256(log)},
                )
            netlist = directory / f"{architecture_id}_netlist.json"
            if not netlist.exists():
                raise base.GateFailure("synthesis", "Yosys did not produce JSON netlist", architecture_id)
            row = base.parse_synthesis(config, architecture_id, script, log, netlist)
            rows.append(row)
            print(
                f"SYNTHESIS END {architecture_id} status={row['status']} "
                f"LUT={row['lut']} FF={row['ff']} DSP={row['dsp']} "
                f"BRAM36eq={row['bram36_equivalent']}",
                flush=True,
            )
            if row["status"] != "VERIFIED":
                raise base.GateFailure(
                    "post_synthesis_audit",
                    "architecture failed a frozen post-synthesis gate",
                    architecture_id,
                    row,
                )

        consistency = base.cross_architecture_mapping(rows)
        if consistency["status"] != "VERIFIED":
            raise base.GateFailure(
                "cross_architecture_mapping",
                "same-geometry memory primitive fingerprints differ",
                details=consistency,
            )

        diagnostics = []
        for row in rows:
            expected = config["pre_run_dsp_diagnostic"][row["architecture_id"]]["expected_DSP48E1"]
            diagnostics.append(
                {
                    "architecture_id": row["architecture_id"],
                    "expected_DSP48E1": expected,
                    "measured_DSP48E1": row["dsp"],
                    "pass": row["dsp"] == expected,
                }
            )
        dsp_diagnostic = {
            "status": "VERIFIED" if all(item["pass"] for item in diagnostics) else "BLOCKED",
            "checks": diagnostics,
        }
        if dsp_diagnostic["status"] != "VERIFIED":
            raise base.GateFailure(
                "post_synthesis_dsp_diagnostic",
                "measured DSP count differs from the frozen pre-run structural diagnostic",
                details=dsp_diagnostic,
            )

        group = base.with_baseline_deltas(rows, "P0")
        csv_path = RESULTS / "yosys_pfft_group.csv"
        mapping_path = RESULTS / "yosys_pfft_memory_mapping_audit.json"
        summary_path = RESULTS / "yosys_pfft_summary.json"
        markdown_path = RESULTS / "yosys_pfft_resource_audit.md"
        base.write_group_csv(csv_path, group)
        base.write_json(
            mapping_path,
            {
                "schema": "pfft-resource-v2-001-memory-audit-v1",
                "status": "VERIFIED",
                "per_architecture": {
                    row["architecture_id"]: row["memory_mapping_audit"] for row in rows
                },
                "cross_architecture_consistency": consistency,
            },
        )
        summary = {
            "schema": "pfft-resource-v2-001-summary-v1",
            "status": "VERIFIED",
            "timestamp_utc": utc_now(),
            "attempt": attempt,
            "evidence_class": "same-flow complete-RTL Yosys xc7 synthesis resource estimate",
            "yosys_executable": str(base.YOSYS),
            "yosys_executable_sha256": base.sha256(base.YOSYS),
            "yosys_version": config["version"],
            "family": "xc7",
            "target_device_context": config["target_evidence"]["device"],
            "validation": validation,
            "runner": str(Path(__file__)),
            "runner_sha256": base.sha256(Path(__file__)),
            "baseline": "P0",
            "group": group,
            "dsp_diagnostic": dsp_diagnostic,
            "cross_architecture_memory_consistency": consistency,
            "artifacts": {
                "pfft_csv": str(csv_path),
                "memory_audit": str(mapping_path),
                "markdown_audit": str(markdown_path),
            },
            "claim_boundary": config["claim_boundary"],
        }
        base.write_json(summary_path, summary)
        markdown_path.write_text(render_markdown(summary), encoding="utf-8", newline="\n")
        print(
            json.dumps(
                {
                    "status": "VERIFIED",
                    "summary": str(summary_path),
                    "summary_sha256": base.sha256(summary_path),
                    "pfft_csv_sha256": base.sha256(csv_path),
                    "memory_audit_sha256": base.sha256(mapping_path),
                    "markdown_audit_sha256": base.sha256(markdown_path),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        return 0
    except Exception as unexpected:
        error = unexpected if isinstance(unexpected, base.GateFailure) else base.GateFailure(
            "runner_internal",
            repr(unexpected),
            details={"exception_type": type(unexpected).__name__},
        )
        write_failure(failure_path, error, validation, rows, attempt)
        print(
            f"STOP {error.stage} architecture={error.architecture_id} "
            f"evidence={failure_path} SHA256={base.sha256(failure_path)}",
            flush=True,
        )
        return 2


def main() -> int:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--validate-only", action="store_true")
    action.add_argument("--preflight", action="store_true")
    action.add_argument("--synthesize", action="store_true")
    parser.add_argument("--attempt", default="attempt1")
    args = parser.parse_args()

    RESULTS.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    if args.validate_only:
        validation_path = RESULTS / "yosys_input_validation.json"
    elif args.preflight:
        validation_path = RESULTS / "yosys_preflight_input_validation.json"
    else:
        validation_path = RESULTS / f"yosys_{args.attempt}_input_validation.json"
    if validation_path.exists():
        raise base.GateFailure("runner", f"validation artifact already exists: {validation_path}")

    try:
        config, validation = validate_inputs()
        base.write_json(validation_path, validation)
        print(
            f"INPUT VALIDATION VERIFIED {validation_path} "
            f"SHA256={base.sha256(validation_path)}",
            flush=True,
        )
        if args.validate_only:
            return 0
        if args.preflight:
            return run_preflight(config, validation)
        return run_formal(config, validation, args.attempt)
    except base.GateFailure as error:
        write_failure(validation_path, error, None, [], args.attempt)
        print(f"STOP {error.stage}: {error}", flush=True)
        if error.details is not None:
            print(json.dumps(error.details, ensure_ascii=False, indent=2), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
