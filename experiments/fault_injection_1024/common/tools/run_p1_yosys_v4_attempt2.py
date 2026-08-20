#!/usr/bin/env python3
"""Controlled-environment attempt2 for P1-YOSYS-V4-001."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import run_p1_yosys_v4 as base


EXPERIMENT = base.EXPERIMENT
WORKSPACE = base.WORKSPACE
RESULTS = EXPERIMENT / "results" / "p1_yosys_v4_001" / "attempt2"
LOGS = EXPERIMENT / "logs" / "p1_yosys_v4_001" / "attempt2"
BUILD = EXPERIMENT / "build" / "p1_yosys_v4_001" / "attempt2"
ATTEMPT1_BUILD = EXPERIMENT / "build" / "p1_yosys_v4_001" / "attempt1"
ATTEMPT1_RESULTS = EXPERIMENT / "results" / "p1_yosys_v4_001" / "attempt1"
ATTEMPT1_RUNNER = Path(__file__).with_name("run_p1_yosys_v4.py")
OSS_ROOT = base.YOSYS.parents[1]


def controlled_environment() -> dict[str, str]:
    """Match the successful PFFT-RES-V3-001 attempt2 env construction."""
    env = os.environ.copy()
    env["YOSYSHQ_ROOT"] = str(OSS_ROOT) + "\\"
    env["PATH"] = (
        str(OSS_ROOT / "bin")
        + os.pathsep
        + str(OSS_ROOT / "lib")
        + os.pathsep
        + env.get("PATH", "")
    )
    env["PYTHON_EXECUTABLE"] = str(OSS_ROOT / "lib" / "python3.exe")
    return env


def write_json(path: Path, payload: object) -> None:
    base.write_json(path, payload)


def run_process(
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    stdout_path: Path,
    stderr_path: Path,
) -> int:
    with stdout_path.open("w", encoding="utf-8", newline="\n") as stdout_stream:
        with stderr_path.open("w", encoding="utf-8", newline="\n") as stderr_stream:
            completed = subprocess.run(
                command,
                cwd=cwd,
                env=env,
                stdout=stdout_stream,
                stderr=stderr_stream,
                check=False,
            )
    return completed.returncode


def main() -> int:
    if any(path.exists() for path in (RESULTS, LOGS, BUILD)):
        raise RuntimeError("attempt2 artifacts already exist; refusing implicit rerun")
    RESULTS.mkdir(parents=True)
    LOGS.mkdir(parents=True)
    BUILD.mkdir(parents=True)

    attempt1_validation_path = ATTEMPT1_RESULTS / "input_validation.json"
    attempt1_validation = json.loads(
        attempt1_validation_path.read_text(encoding="utf-8")
    )
    if attempt1_validation.get("status") != "VERIFIED":
        raise RuntimeError("attempt1 frozen input validation is not VERIFIED")

    staged_records = attempt1_validation.get("staged_sources", [])
    if len(staged_records) != 7:
        raise RuntimeError("attempt1 does not contain exactly seven staged RTL inputs")
    frozen_sources: list[Path] = []
    input_checks: list[dict[str, object]] = []
    for record in staged_records:
        staged_relative = record["staged"]["path"]
        staged_path = WORKSPACE / staged_relative
        expected = record["staged"]["sha256"]
        measured = base.sha256(staged_path)
        input_checks.append(
            {
                "path": staged_relative,
                "attempt1_sha256": expected,
                "attempt2_prelaunch_sha256": measured,
                "match": expected == measured,
            }
        )
        frozen_sources.append(staged_path)
    if not all(item["match"] for item in input_checks):
        raise RuntimeError("attempt1 frozen RTL hash mismatch")

    env = controlled_environment()
    temporary_root = Path(tempfile.gettempdir()).resolve()
    stage = temporary_root / ("P1V4A2" + uuid.uuid4().hex[:8].upper())
    if not str(stage).isascii() or not re.fullmatch(r"P1V4A2[0-9A-F]{8}", stage.name):
        raise RuntimeError(f"temporary directory is not a valid unique ASCII path: {stage}")
    stage.mkdir()

    startup_environment = {
        "schema": "p1-yosys-v4-001-attempt2-startup-environment-v1",
        "captured_before_yosys_start": True,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "runner": base.file_record(Path(__file__)),
        "attempt1_runner_template": base.file_record(ATTEMPT1_RUNNER),
        "attempt1_input_validation": base.file_record(attempt1_validation_path),
        "frozen_input_checks": input_checks,
        "yosys": {
            "path": str(base.YOSYS),
            "sha256": base.sha256(base.YOSYS),
            "size_bytes": base.YOSYS.stat().st_size,
        },
        "working_directory": str(stage),
        "working_directory_is_ascii": str(stage).isascii(),
        "environment": dict(sorted(env.items(), key=lambda item: item[0].upper())),
        "selected_environment": {
            name: env.get(name)
            for name in (
                "PATH",
                "PYTHONHOME",
                "PYTHONPATH",
                "YOSYSHQ_ROOT",
                "OSS_ROOT",
                "PYTHON_EXECUTABLE",
                "QT_PLUGIN_PATH",
                "GTK_EXE_PREFIX",
                "GTK_DATA_PREFIX",
                "GDK_PIXBUF_MODULEDIR",
                "GDK_PIXBUF_MODULE_FILE",
            )
        },
        "path_entries": env.get("PATH", "").split(os.pathsep),
        "windows_dll_search_context": {
            "application_directory": str(base.YOSYS.parent),
            "working_directory": str(stage),
            "system32": os.environ.get("SystemRoot", r"C:\Windows") + r"\System32",
            "windows_directory": os.environ.get("SystemRoot", r"C:\Windows"),
            "path_entries": env.get("PATH", "").split(os.pathsep),
        },
    }
    environment_path = RESULTS / "startup_environment.json"
    write_json(environment_path, startup_environment)

    version_command = [str(base.YOSYS), "-V"]
    version_sidecar = {
        "schema": "p1-yosys-v4-001-attempt2-version-command-v1",
        "command": version_command,
        "cwd": str(stage),
        "environment_snapshot": base.rel(environment_path),
        "environment_snapshot_sha256": base.sha256(environment_path),
    }
    write_json(LOGS / "yosys_version.command.json", version_sidecar)
    version_stdout = LOGS / "yosys_version.stdout.log"
    version_stderr = LOGS / "yosys_version.stderr.log"
    version_exit = run_process(
        version_command, stage, env, version_stdout, version_stderr
    )
    version_gate = {
        "schema": "p1-yosys-v4-001-attempt2-version-gate-v1",
        "status": "VERIFIED" if version_exit == 0 else "FAILED",
        "exit_code": version_exit,
        "exit_code_hex": f"0x{version_exit & 0xFFFFFFFF:08X}",
        "stdout": base.file_record(version_stdout),
        "stderr": base.file_record(version_stderr),
        "command_sidecar": base.file_record(LOGS / "yosys_version.command.json"),
        "read_verilog_executed": False,
    }
    version_gate_path = RESULTS / "yosys_version_gate.json"
    write_json(version_gate_path, version_gate)
    if version_exit != 0:
        print(f"FAILED_YOSYS_VERSION {version_gate['exit_code_hex']}")
        return 1

    # Only after the version gate passes are RTL and scripts staged.
    stage_sources: list[Path] = []
    for index, source in enumerate(frozen_sources):
        target = stage / f"s{index}_{source.name.split('_', 1)[-1]}"
        shutil.copy2(source, target)
        if base.sha256(target) != base.sha256(source):
            raise RuntimeError(f"attempt2 staged hash mismatch: {source}")
        stage_sources.append(target)

    read_line = "read_verilog -sv " + " ".join(path.name for path in stage_sources)
    preflight_script = stage / "preflight.ys"
    preflight_script.write_text(
        "\n".join(
            (
                read_line,
                f"hierarchy -check -top {base.TOP}",
                "check",
                "write_json P1_hierarchy.json",
                "stat",
                "",
            )
        ),
        encoding="utf-8",
        newline="\n",
    )
    synthesis_script = stage / "synthesis.ys"
    synthesis_script.write_text(
        "\n".join(
            (
                read_line,
                f"hierarchy -check -top {base.TOP}",
                "write_json P1_hierarchy.json",
                f"synth_xilinx -family xc7 -top {base.TOP}",
                "stat",
                "write_json P1_netlist.json",
                "",
            )
        ),
        encoding="utf-8",
        newline="\n",
    )
    script_manifest = {
        "schema": "p1-yosys-v4-001-attempt2-script-manifest-v1",
        "derivation": "exact expansion of frozen attempt1 runner script templates",
        "attempt1_runner": base.file_record(ATTEMPT1_RUNNER),
        "preflight": base.file_record(preflight_script),
        "synthesis": base.file_record(synthesis_script),
        "flow": "synth_xilinx -family xc7 -top top_p1_pfft_ecc",
    }
    write_json(RESULTS / "script_manifest.json", script_manifest)

    preflight_command = [
        str(base.YOSYS),
        "-l",
        str(stage / "preflight_yosys.log"),
        "-s",
        str(preflight_script),
    ]
    write_json(
        LOGS / "yosys_preflight.command.json",
        {
            "command": preflight_command,
            "cwd": str(stage),
            "environment_snapshot_sha256": base.sha256(environment_path),
        },
    )
    preflight_exit = run_process(
        preflight_command,
        stage,
        env,
        LOGS / "yosys_preflight.stdout.log",
        LOGS / "yosys_preflight.stderr.log",
    )
    for name in ("preflight_yosys.log", "P1_hierarchy.json", "preflight.ys"):
        source = stage / name
        if source.exists():
            shutil.copy2(source, BUILD / name)
    preflight_ok = (
        preflight_exit == 0
        and (BUILD / "P1_hierarchy.json").exists()
        and (BUILD / "preflight_yosys.log").exists()
    )
    preflight_result = {
        "schema": "p1-yosys-v4-001-attempt2-preflight-v1",
        "status": "VERIFIED" if preflight_ok else "FAILED",
        "exit_code": preflight_exit,
        "command": base.file_record(LOGS / "yosys_preflight.command.json"),
        "stdout": base.file_record(LOGS / "yosys_preflight.stdout.log"),
        "stderr": base.file_record(LOGS / "yosys_preflight.stderr.log"),
        "yosys_log": base.file_record(BUILD / "preflight_yosys.log")
        if (BUILD / "preflight_yosys.log").exists()
        else None,
        "hierarchy": base.file_record(BUILD / "P1_hierarchy.json")
        if (BUILD / "P1_hierarchy.json").exists()
        else None,
    }
    write_json(RESULTS / "preflight.json", preflight_result)
    if not preflight_ok:
        print("FAILED_PREFLIGHT")
        return 1

    synthesis_command = [
        str(base.YOSYS),
        "-l",
        str(stage / "synthesis_yosys.log"),
        "-s",
        str(synthesis_script),
    ]
    write_json(
        LOGS / "yosys_synthesis.command.json",
        {
            "command": synthesis_command,
            "cwd": str(stage),
            "environment_snapshot_sha256": base.sha256(environment_path),
        },
    )
    synthesis_exit = run_process(
        synthesis_command,
        stage,
        env,
        LOGS / "yosys_synthesis.stdout.log",
        LOGS / "yosys_synthesis.stderr.log",
    )
    for name in ("synthesis_yosys.log", "P1_hierarchy.json", "P1_netlist.json", "synthesis.ys"):
        source = stage / name
        if source.exists():
            shutil.copy2(source, BUILD / name)
    if synthesis_exit != 0 or not (BUILD / "P1_netlist.json").exists():
        write_json(
            RESULTS / "resource_result.json",
            {
                "status": "FAILED_SYNTHESIS",
                "exit_code": synthesis_exit,
                "stdout": base.file_record(LOGS / "yosys_synthesis.stdout.log"),
                "stderr": base.file_record(LOGS / "yosys_synthesis.stderr.log"),
                "log": base.file_record(BUILD / "synthesis_yosys.log")
                if (BUILD / "synthesis_yosys.log").exists()
                else None,
            },
        )
        print("FAILED_SYNTHESIS")
        return 1

    pre_walk = base.hierarchy_walk(
        json.loads((BUILD / "P1_hierarchy.json").read_text(encoding="utf-8"))
    )
    post_walk = base.hierarchy_walk(
        json.loads((BUILD / "P1_netlist.json").read_text(encoding="utf-8"))
    )
    structure = base.structure_audit(pre_walk)
    blackboxes = base.blackbox_audit(post_walk)
    synthesis_log = (BUILD / "synthesis_yosys.log").read_text(
        encoding="utf-8", errors="replace"
    )
    warnings = [
        line.strip()
        for line in synthesis_log.splitlines()
        if re.search(r"\bwarning\b", line, re.I)
    ]
    critical_warnings = [
        line for line in warnings if base.CRITICAL_WARNING.search(line)
    ]
    counts = post_walk["leaf_counts"]
    lc_matches = re.findall(r"Estimated number of LCs:\s*(\d+)", synthesis_log)
    distributed = {
        name: count
        for name, count in sorted(counts.items())
        if (name.startswith("RAM") and not name.startswith("RAMB"))
        or name.startswith("SRL")
    }
    resources = {
        "LC_estimate": int(lc_matches[-1]) if lc_matches else None,
        "LUT1_to_LUT6": sum(counts[f"LUT{index}"] for index in range(1, 7)),
        "FF": sum(counts[name] for name in base.FF_TYPES),
        "DSP48E1": counts["DSP48E1"],
        "RAMB18E1": counts["RAMB18E1"],
        "RAMB36E1": counts["RAMB36E1"],
        "BRAM36_equivalent": counts["RAMB36E1"] + 0.5 * counts["RAMB18E1"],
        "distributed_memory_cells_total": sum(distributed.values()),
        "distributed_memory_cells": distributed,
    }
    diagnostic = {
        "generic_complex_multipliers": {
            "expected": 48,
            "measured": pre_walk["module_counts"]["fft_complex_mul_q28"],
        },
        "DSP48E1": {"expected": 768, "measured": counts["DSP48E1"]},
    }
    diagnostic_pass = all(
        item["expected"] == item["measured"] for item in diagnostic.values()
    )
    audit_pass = (
        structure["status"] == "VERIFIED"
        and blackboxes["status"] == "VERIFIED"
        and not critical_warnings
        and resources["LC_estimate"] is not None
    )
    status = (
        "VERIFIED"
        if audit_pass and diagnostic_pass
        else "FAILED_TARGET_DIAGNOSTIC"
        if audit_pass
        else "FAILED_POST_SYNTHESIS_AUDIT"
    )
    result = {
        "schema": "p1-yosys-v4-001-attempt2-resource-result-v1",
        "record_id": "P1-YOSYS-V4-001",
        "attempt": "attempt2",
        "status": status,
        "scope": "Yosys synth_xilinx -family xc7 resource estimate; not Vivado implementation",
        "yosys_version": version_stdout.read_text(encoding="utf-8", errors="replace").strip(),
        "resources": resources,
        "target_diagnostic": diagnostic,
        "structure_audit": structure,
        "warning_audit": {
            "status": "VERIFIED" if not critical_warnings else "FAILED",
            "warnings": warnings,
            "critical_warnings": critical_warnings,
        },
        "blackbox_audit": blackboxes,
        "cell_counts": dict(sorted(counts.items())),
        "startup_environment": base.file_record(environment_path),
        "version_gate": base.file_record(version_gate_path),
        "preflight": base.file_record(RESULTS / "preflight.json"),
        "script_manifest": base.file_record(RESULTS / "script_manifest.json"),
        "synthesis_log": base.file_record(BUILD / "synthesis_yosys.log"),
        "pre_synthesis_hierarchy": base.file_record(BUILD / "P1_hierarchy.json"),
        "post_synthesis_netlist": base.file_record(BUILD / "P1_netlist.json"),
        "synthesis_command": base.file_record(LOGS / "yosys_synthesis.command.json"),
    }
    result_path = RESULTS / "resource_result.json"
    write_json(result_path, result)
    print(f"{status} {base.sha256(result_path)}")
    return 0 if status == "VERIFIED" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
