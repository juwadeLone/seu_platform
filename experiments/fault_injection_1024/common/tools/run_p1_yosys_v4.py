#!/usr/bin/env python3
"""Fail-fast P1-only Yosys xc7 resource run for P1-YOSYS-V4-001."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
WORKSPACE = HERE.parents[3]
RTL = EXPERIMENT / "common" / "rtl"
P1 = EXPERIMENT / "projects" / "P1"
RESULTS = EXPERIMENT / "results" / "p1_yosys_v4_001" / "attempt1"
LOGS = EXPERIMENT / "logs" / "p1_yosys_v4_001" / "attempt1"
BUILD = EXPERIMENT / "build" / "p1_yosys_v4_001" / "attempt1"
STAGED = BUILD / "staged_sources"
YOSYS_BUILD = BUILD / "yosys"
YOSYS = Path(r"C:\Users\pc\Downloads\oss-cad-suite\bin\yosys.exe")
TOP = "top_p1_pfft_ecc"
QUALIFICATION = (
    EXPERIMENT
    / "results"
    / "p1_rtl_v4_001"
    / "qualification_attempt1"
    / "qualification.json"
)
SOURCES = (
    RTL / "twiddle_rom_1024.sv",
    RTL / "fft_common.sv",
    RTL / "protection_rtl.sv",
    RTL / "datapath_v5.sv",
    RTL / "protection_primitives_v5.sv",
    RTL / "protected_stages_v5.sv",
    P1 / "top_p1_pfft_ecc.sv",
)
FF_TYPES = ("FDRE", "FDSE", "FDCE", "FDPE")
CRITICAL_WARNING = re.compile(
    r"blackbox|unresolved|not found|multiple conflicting drivers|has no driver|"
    r"implicitly declared|logic loop",
    re.I,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def rel(path: Path) -> str:
    try:
        return path.relative_to(WORKSPACE).as_posix()
    except ValueError:
        return path.as_posix()


def file_record(path: Path) -> dict[str, object]:
    return {"path": rel(path), "sha256": sha256(path), "size_bytes": path.stat().st_size}


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def clean(value: str) -> str:
    return str(value).lstrip("\\")


def is_blackbox(module: dict[str, object]) -> bool:
    return str(module.get("attributes", {}).get("blackbox", "0")) in {
        "1",
        "00000000000000000000000000000001",
    }


def module_label(key: str, module: dict[str, object]) -> str:
    return clean(str(module.get("attributes", {}).get("hdlname", key)))


def cell_label(key: str, cell: dict[str, object]) -> str:
    return clean(str(cell.get("attributes", {}).get("hdlname", key)))


def hierarchy_walk(netlist: dict[str, object]) -> dict[str, object]:
    modules = netlist["modules"]
    if TOP not in modules:
        raise RuntimeError(f"top absent from JSON hierarchy: {TOP}")
    module_counts: Counter[str] = Counter()
    leaf_counts: Counter[str] = Counter()
    paths_by_module: dict[str, list[str]] = {}
    active: set[str] = set()

    def walk(module_key: str, path: str) -> None:
        if module_key in active:
            raise RuntimeError(f"recursive hierarchy: {module_key}")
        active.add(module_key)
        module = modules[module_key]
        for local_name, cell in module.get("cells", {}).items():
            child_type = cell["type"]
            instance = cell_label(local_name, cell)
            child_path = f"{path}/{instance}"
            child = modules.get(child_type)
            if child is not None and not is_blackbox(child):
                label = module_label(child_type, child)
                module_counts[label] += 1
                paths_by_module.setdefault(label, []).append(child_path)
                walk(child_type, child_path)
            else:
                leaf_counts[clean(child_type)] += 1
        active.remove(module_key)

    walk(TOP, TOP)
    return {
        "module_counts": module_counts,
        "leaf_counts": leaf_counts,
        "paths_by_module": paths_by_module,
        "modules": modules,
    }


def blackbox_audit(walk: dict[str, object]) -> dict[str, object]:
    modules = walk["modules"]
    critical: list[str] = []
    allowed: list[str] = []
    for cell_type in sorted(walk["leaf_counts"]):
        module = modules.get(cell_type)
        if module is None:
            if cell_type.startswith(("$", "BUFG", "CARRY", "DSP", "FD", "IBUF", "INV", "LUT", "MUXF", "OBUF", "RAM", "SRL")):
                allowed.append(cell_type)
            else:
                critical.append(cell_type)
            continue
        if is_blackbox(module):
            source = str(module.get("attributes", {}).get("src", "")).replace("\\", "/").lower()
            if "/share/yosys/xilinx/" in source:
                allowed.append(cell_type)
            else:
                critical.append(cell_type)
    return {
        "status": "VERIFIED" if not critical else "FAILED",
        "allowed_primitive_blackboxes": allowed,
        "critical_blackboxes": critical,
    }


def structure_audit(pre: dict[str, object]) -> dict[str, object]:
    counts = pre["module_counts"]
    checks = {
        "stage8_tmr_wrapper": counts["p1_tmr_pfft_stage8_v4"] == 1,
        "stage8_complete_replicas": counts["p1_stage8_functional_v3"] == 3,
        "stage9_tmr_wrapper": counts["p1_tmr_pfft_stage9_v3"] == 1,
        "stage9_complete_replicas": counts["p1_pfft_stage9_exchange_v3"] == 3,
        "stage10_two_beat_ecc": counts["p1_stage10_two_beat_ecc_v4"] == 1,
        "stage10_one_643_operator": counts["independent_butterfly_ecc_v5"] == 1,
        "stage10_two_decode_boundaries": counts["arithmetic_boundary_from_clean_v5"] >= 2,
        "legacy_stage8_scheduler_unreachable": counts["p1_stage8_single_check_pair_scheduler_v3"] == 0,
        "legacy_stage10_tmr_unreachable": counts["p1_tmr_pfft_stage10_v3"] == 0,
        "generic_complex_multiplier_target": counts["fft_complex_mul_q28"] == 48,
    }
    return {
        "status": "VERIFIED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "selected_module_counts": {
            name: counts[name]
            for name in (
                "p1_tmr_pfft_stage8_v4",
                "p1_stage8_functional_v3",
                "p1_tmr_pfft_stage9_v3",
                "p1_pfft_stage9_exchange_v3",
                "p1_stage10_two_beat_ecc_v4",
                "independent_butterfly_ecc_v5",
                "arithmetic_boundary_from_clean_v5",
                "p1_stage8_single_check_pair_scheduler_v3",
                "p1_tmr_pfft_stage10_v3",
                "fft_complex_mul_q28",
            )
        },
    }


def run_yosys(script: Path, log: Path, sidecar: Path) -> int:
    command = [str(YOSYS), "-l", str(log), "-s", str(script)]
    write_json(
        sidecar,
        {
            "command": command,
            "cwd": str(YOSYS_BUILD),
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        },
    )
    with (LOGS / f"{script.stem}_launcher.log").open("w", encoding="utf-8", newline="\n") as output:
        completed = subprocess.run(
            command,
            cwd=YOSYS_BUILD,
            stdout=output,
            stderr=subprocess.STDOUT,
            check=False,
        )
    return completed.returncode


def main() -> int:
    if any(path.exists() for path in (RESULTS, LOGS, BUILD)):
        raise RuntimeError("attempt1 artifacts already exist; refusing implicit rerun")
    for path in (RESULTS, LOGS, STAGED, YOSYS_BUILD):
        path.mkdir(parents=True)

    qualification = json.loads(QUALIFICATION.read_text(encoding="utf-8"))
    validation_failures: list[str] = []
    if qualification.get("status") != "VERIFIED":
        validation_failures.append("P1 RTL V4 qualification is not VERIFIED")
    if not YOSYS.is_file():
        validation_failures.append(f"fixed Yosys missing: {YOSYS}")
    for source in SOURCES:
        if not source.is_file():
            validation_failures.append(f"missing source: {source}")

    staged_records = []
    if not validation_failures:
        for index, source in enumerate(SOURCES):
            target = STAGED / f"{index:02d}_{source.name}"
            shutil.copy2(source, target)
            if sha256(source) != sha256(target):
                validation_failures.append(f"staged hash mismatch: {source}")
            staged_records.append(
                {"source": file_record(source), "staged": file_record(target)}
            )

    validation = {
        "schema": "p1-yosys-v4-001-input-validation-v1",
        "status": "VERIFIED" if not validation_failures else "FAILED",
        "tool": str(YOSYS),
        "qualification": file_record(QUALIFICATION),
        "sources": [file_record(path) for path in SOURCES if path.exists()],
        "staged_sources": staged_records,
        "failures": validation_failures,
    }
    write_json(RESULTS / "input_validation.json", validation)
    if validation_failures:
        print("FAILED_INPUT_VALIDATION")
        return 1

    version_result = subprocess.run(
        [str(YOSYS), "-V"],
        cwd=YOSYS_BUILD,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    (LOGS / "yosys_version.log").write_text(version_result.stdout, encoding="utf-8")
    if version_result.returncode != 0:
        write_json(
            RESULTS / "preflight.json",
            {"status": "FAILED", "stage": "yosys_version", "exit_code": version_result.returncode},
        )
        print("FAILED_YOSYS_VERSION")
        return 1

    read_line = "read_verilog -sv " + " ".join(path.name for path in sorted(STAGED.iterdir()))
    pre_hierarchy = YOSYS_BUILD / "P1_hierarchy.json"
    preflight_script = YOSYS_BUILD / "preflight.ys"
    preflight_script.write_text(
        "\n".join(
            (
                read_line,
                f"hierarchy -check -top {TOP}",
                "check",
                f"write_json {pre_hierarchy.name}",
                "stat",
                "",
            )
        ),
        encoding="utf-8",
        newline="\n",
    )
    # Scripts execute in YOSYS_BUILD, so expose staged source basenames there.
    for source in sorted(STAGED.iterdir()):
        shutil.copy2(source, YOSYS_BUILD / source.name)
    preflight_log = LOGS / "yosys_preflight.log"
    preflight_exit = run_yosys(
        preflight_script, preflight_log, LOGS / "yosys_preflight.command.json"
    )
    preflight = {
        "status": "VERIFIED" if preflight_exit == 0 and pre_hierarchy.exists() else "FAILED",
        "exit_code": preflight_exit,
        "yosys_version": version_result.stdout.strip(),
        "script": file_record(preflight_script),
        "log": file_record(preflight_log) if preflight_log.exists() else None,
        "hierarchy": file_record(pre_hierarchy) if pre_hierarchy.exists() else None,
    }
    write_json(RESULTS / "preflight.json", preflight)
    if preflight["status"] != "VERIFIED":
        print("FAILED_PREFLIGHT")
        return 1

    netlist = YOSYS_BUILD / "P1_netlist.json"
    synth_script = YOSYS_BUILD / "synthesis.ys"
    synth_script.write_text(
        "\n".join(
            (
                read_line,
                f"hierarchy -check -top {TOP}",
                f"write_json {pre_hierarchy.name}",
                f"synth_xilinx -family xc7 -top {TOP}",
                "stat",
                f"write_json {netlist.name}",
                "",
            )
        ),
        encoding="utf-8",
        newline="\n",
    )
    synth_log = LOGS / "yosys_synthesis.log"
    synth_exit = run_yosys(
        synth_script, synth_log, LOGS / "yosys_synthesis.command.json"
    )
    if synth_exit != 0 or not netlist.exists():
        write_json(
            RESULTS / "resource_result.json",
            {
                "status": "FAILED_SYNTHESIS",
                "exit_code": synth_exit,
                "script": file_record(synth_script),
                "log": file_record(synth_log) if synth_log.exists() else None,
            },
        )
        print("FAILED_SYNTHESIS")
        return 1

    pre_walk = hierarchy_walk(json.loads(pre_hierarchy.read_text(encoding="utf-8")))
    post_walk = hierarchy_walk(json.loads(netlist.read_text(encoding="utf-8")))
    structure = structure_audit(pre_walk)
    blackboxes = blackbox_audit(post_walk)
    log_text = synth_log.read_text(encoding="utf-8", errors="replace")
    warnings = [
        line.strip()
        for line in log_text.splitlines()
        if re.search(r"\bwarning\b", line, re.I)
    ]
    critical_warnings = [line for line in warnings if CRITICAL_WARNING.search(line)]
    counts = post_walk["leaf_counts"]
    lc_matches = re.findall(r"Estimated number of LCs:\s*(\d+)", log_text)
    distributed = {
        name: count
        for name, count in sorted(counts.items())
        if (name.startswith("RAM") and not name.startswith("RAMB")) or name.startswith("SRL")
    }
    resources = {
        "LC_estimate": int(lc_matches[-1]) if lc_matches else None,
        "LUT1_to_LUT6": sum(counts[f"LUT{index}"] for index in range(1, 7)),
        "FF": sum(counts[name] for name in FF_TYPES),
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
        "schema": "p1-yosys-v4-001-resource-result-v1",
        "record_id": "P1-YOSYS-V4-001",
        "status": status,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Yosys synth_xilinx -family xc7 resource estimate; not Vivado implementation",
        "yosys_version": version_result.stdout.strip(),
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
        "input_validation": file_record(RESULTS / "input_validation.json"),
        "preflight": file_record(RESULTS / "preflight.json"),
        "script": file_record(synth_script),
        "log": file_record(synth_log),
        "pre_synthesis_hierarchy": file_record(pre_hierarchy),
        "post_synthesis_netlist": file_record(netlist),
        "command_sidecar": file_record(LOGS / "yosys_synthesis.command.json"),
    }
    result_path = RESULTS / "resource_result.json"
    write_json(result_path, result)
    print(f"{status} {sha256(result_path)}")
    return 0 if status == "VERIFIED" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
