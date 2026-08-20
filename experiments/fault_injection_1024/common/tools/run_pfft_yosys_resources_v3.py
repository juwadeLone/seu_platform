#!/usr/bin/env python3
"""One-shot Yosys evidence flow for PFFT-RES-V3-001.

This runner implements the three commands frozen by
``PFFT_RESOURCE_REEVALUATION_V3.md``:

* ``--validate-only``
* ``--preflight``
* ``--synthesize --attempt attempt1``

The three PFFT projects are elaborated independently from the common six-file
RTL set plus exactly one project top.  The formal command preserves raw
measurements even when the D95 generic-complex-multiplier or DSP48E1 budget
does not match.  A mismatch is a hard failure and deliberately suppresses the
paper-facing comparison table.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
WORKSPACE = EXPERIMENT.parents[1]

CONTRACT = EXPERIMENT / "PFFT_RESOURCE_REEVALUATION_V3.md"
CONFIG = EXPERIMENT / "config" / "pfft_resource_reevaluation_v3.json"
MEMORY_MAP = EXPERIMENT / "config" / "pfft_resource_memory_map_v3.json"
INPUT_MANIFEST = EXPERIMENT / "config" / "pfft_resource_v3_input_manifest.json"
QUALIFICATION_RUNNER = (
    EXPERIMENT / "common" / "tools" / "run_pfft_resource_qualification_v3.py"
)
SCHEDULE = EXPERIMENT / "results" / "pfft_resource_v3_001" / "schedule_feasibility_attempt1.json"
VECTOR_MANIFEST = EXPERIMENT / "results" / "pfft_resource_v3_001" / "vector_manifest.json"
QUALIFICATION = (
    EXPERIMENT
    / "results"
    / "pfft_resource_v3_001"
    / "qualification_attempt1"
    / "rtl_qualification.json"
)
STRUCTURE_MANIFEST = QUALIFICATION.with_name("rtl_structure_manifest.json")

RESULTS = EXPERIMENT / "results" / "pfft_resource_v3_001"
LOGS = EXPERIMENT / "logs" / "pfft_resource_v3_001"
BUILD = EXPERIMENT / "build" / "pfft_resource_v3_001"

VALIDATION_RESULT = RESULTS / "yosys_input_validation.json"
PREFLIGHT_RESULT = RESULTS / "yosys_preflight.json"
RAW_RESULT = RESULTS / "yosys_raw_measurements_attempt1.json"
SUMMARY_RESULT = RESULTS / "yosys_pfft_summary.json"
CSV_RESULT = RESULTS / "yosys_pfft_group.csv"
MARKDOWN_RESULT = RESULTS / "yosys_pfft_resource_audit.md"

YOSYS = Path(r"C:\Users\pc\Downloads\oss-cad-suite\bin\yosys.exe")
OSS_ROOT = YOSYS.parents[1]

ARCH_ORDER = ("P0", "P1", "P2")
COMMON_SOURCES = (
    "common/rtl/twiddle_rom_1024.sv",
    "common/rtl/fft_common.sv",
    "common/rtl/protection_rtl.sv",
    "common/rtl/datapath_v5.sv",
    "common/rtl/protection_primitives_v5.sv",
    "common/rtl/protected_stages_v5.sv",
)
TOP_SOURCES = {
    "P0": "projects/P0/top_p0_pfft_unprotected.sv",
    "P1": "projects/P1/top_p1_pfft_ecc.sv",
    "P2": "projects/P2/top_p2_pfft_tmr.sv",
}
TB_SOURCES = {
    "P0": "projects/P0/tb_p0.sv",
    "P1": "projects/P1/tb_p1.sv",
    "P2": "projects/P2/tb_p2.sv",
}
EXPECTED_SOURCES = {
    architecture_id: COMMON_SOURCES + (TOP_SOURCES[architecture_id],)
    for architecture_id in ARCH_ORDER
}

EXPECTED_GENERIC_BY_STAGE = {
    "P0": [4, 4, 4, 4, 4, 4, 3, 2, 0, 0],
    "P1": [0, 6, 6, 6, 6, 6, 6, 4, 6, 0],
    "P2": [12, 12, 12, 12, 12, 12, 9, 6, 0, 0],
}
EXPECTED_DSP_BY_STAGE = {
    "P0": [64, 64, 64, 64, 64, 64, 48, 32, 0, 0],
    "P1": [0, 96, 96, 96, 96, 96, 96, 64, 96, 0],
    "P2": [192, 192, 192, 192, 192, 192, 144, 96, 0, 0],
}
EXPECTED_DSP_TOTAL = {"P0": 464, "P1": 736, "P2": 1392}
EXPECTED_TMR_STAGES = {
    "P0": (),
    "P1": (9, 10),
    "P2": tuple(range(1, 11)),
}

FF_TYPES = ("FDCE", "FDPE", "FDRE", "FDSE")
CRITICAL_WARNING_PATTERN = re.compile(
    r"blackbox|unresolved|not found|multiple conflicting drivers|has no driver|"
    r"unsupported|failed to map|cannot map",
    flags=re.IGNORECASE,
)
STAGE_PATTERN = re.compile(r"(?<![A-Za-z0-9_])s(10|[1-9])(?![A-Za-z0-9_])")


class GateFailure(RuntimeError):
    """A frozen gate failed; details are safe to serialize as evidence."""

    def __init__(
        self,
        stage: str,
        message: str,
        architecture_id: str | None = None,
        details: Any = None,
    ):
        super().__init__(message)
        self.stage = stage
        self.architecture_id = architecture_id
        self.details = details


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(WORKSPACE.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def resolve_record_path(value: str) -> Path:
    normalized = value.replace("\\", "/")
    candidate = Path(normalized)
    if candidate.is_absolute():
        return candidate.resolve()
    # Every workspace-owned record produced by the V3 vector, structure, and
    # input-manifest writers is workspace-relative.  This includes both
    # ``experiments/fault_injection_1024/...`` and the pre-edit
    # ``archive/migration/...`` snapshot manifest.  Resolving a generic
    # relative record against EXPERIMENT would silently manufacture
    # ``experiments/fault_injection_1024/archive/...`` and make validation fail
    # before Yosys starts.
    return (WORKSPACE / candidate).resolve()


def experiment_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(EXPERIMENT.resolve()).as_posix()
    except ValueError as error:
        raise GateFailure(
            "input_validation",
            "source record resolves outside the experiment root",
            details=str(path),
        ) from error


def yosys_environment() -> dict[str, str]:
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


def yosys_version() -> str:
    result = subprocess.run(
        [str(YOSYS), "-V"],
        env=yosys_environment(),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise GateFailure(
            "tool_validation",
            f"Yosys -V exited {result.returncode}",
            details=result.stdout,
        )
    version = result.stdout.strip()
    if not version:
        raise GateFailure("tool_validation", "Yosys -V returned an empty version string")
    return version


def record_hash(record: dict[str, Any]) -> str | None:
    for key, value in record.items():
        if key.lower() in {"sha256", "file_sha256", "executable_sha256"}:
            return str(value).upper()
    return None


def record_path(record: dict[str, Any]) -> str | None:
    for key in ("path", "relative_path", "absolute_path", "executable"):
        value = record.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def iter_hashed_records(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        if record_path(value) is not None and record_hash(value) is not None:
            yield value
        for child in value.values():
            yield from iter_hashed_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_hashed_records(child)


def indexed_input_manifest(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    for record in iter_hashed_records(manifest):
        raw_path = record_path(record)
        assert raw_path is not None
        path = resolve_record_path(raw_path)
        key = os.path.normcase(str(path))
        if key in indexed and record_hash(indexed[key]) != record_hash(record):
            failures.append(f"conflicting hashes for {path}")
        indexed[key] = record
    if failures:
        raise GateFailure(
            "input_validation",
            "input manifest contains conflicting file records",
            details=failures,
        )
    return indexed


def require_manifest_record(
    indexed: dict[str, dict[str, Any]],
    path: Path,
    failures: list[str],
) -> None:
    key = os.path.normcase(str(path.resolve()))
    record = indexed.get(key)
    if record is None:
        failures.append(f"input manifest does not record {display_path(path)}")
        return
    if not path.exists():
        failures.append(f"manifest-recorded path is missing: {display_path(path)}")
        return
    expected = record_hash(record)
    actual = sha256(path)
    if expected != actual:
        failures.append(
            f"input manifest hash mismatch for {display_path(path)}: "
            f"recorded={expected} current={actual}"
        )


def validate_all_manifest_records(
    indexed: dict[str, dict[str, Any]],
    failures: list[str],
) -> None:
    for key, record in sorted(indexed.items()):
        path = Path(key)
        if not path.exists():
            failures.append(f"manifest-recorded path is missing: {path}")
            continue
        actual = sha256(path)
        expected = record_hash(record)
        if actual != expected:
            failures.append(
                f"input manifest hash mismatch for {path}: "
                f"recorded={expected} current={actual}"
            )


def structure_sources(
    structure_manifest: dict[str, Any],
    failures: list[str],
) -> dict[str, list[dict[str, str]]]:
    raw = structure_manifest.get("sources_by_architecture")
    if not isinstance(raw, dict):
        failures.append("structure manifest lacks sources_by_architecture")
        return {architecture_id: [] for architecture_id in ARCH_ORDER}

    output: dict[str, list[dict[str, str]]] = {}
    for architecture_id in ARCH_ORDER:
        entries = raw.get(architecture_id)
        if not isinstance(entries, list):
            failures.append(f"structure manifest lacks source list for {architecture_id}")
            output[architecture_id] = []
            continue
        normalized: list[dict[str, str]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                failures.append(f"{architecture_id} source record is not an object")
                continue
            raw_path = entry.get("path") or entry.get("relative_path")
            recorded_hash = entry.get("sha256")
            if not isinstance(raw_path, str) or not isinstance(recorded_hash, str):
                failures.append(f"{architecture_id} source record lacks path/sha256")
                continue
            path = resolve_record_path(raw_path)
            try:
                relative = experiment_relative(path)
            except GateFailure as error:
                failures.append(str(error))
                continue
            if not path.exists():
                failures.append(f"{architecture_id} source missing: {relative}")
                continue
            current_hash = sha256(path)
            if current_hash != recorded_hash.upper():
                failures.append(
                    f"{architecture_id} source hash mismatch for {relative}: "
                    f"recorded={recorded_hash.upper()} current={current_hash}"
                )
            normalized.append(
                {
                    "relative_path": relative,
                    "absolute_path": str(path),
                    "sha256": current_hash,
                }
            )
        observed = tuple(item["relative_path"] for item in normalized)
        expected = EXPECTED_SOURCES[architecture_id]
        if observed != expected:
            failures.append(
                f"{architecture_id} source list must be exactly common six plus its own top; "
                f"observed={list(observed)} expected={list(expected)}"
            )
        output[architecture_id] = normalized
    return output


def validate_config(config: dict[str, Any], failures: list[str]) -> None:
    if config.get("experiment_id") != "PFFT-RES-V3-001":
        failures.append("config experiment_id is not PFFT-RES-V3-001")
    if config.get("yosys_executable", "").replace("\\", "/") != str(YOSYS).replace("\\", "/"):
        failures.append("config does not select the fixed Yosys executable")
    target = config.get("target", {})
    if target.get("family") != "xc7" or target.get("flow") != "synth_xilinx -family xc7":
        failures.append("config target is not the fixed xc7 synth_xilinx flow")
    if tuple(config.get("tops", {}).keys()) != ARCH_ORDER:
        failures.append("config top ordering is not exactly P0,P1,P2")
    expected_tops = {
        "P0": "top_p0_pfft_unprotected",
        "P1": "top_p1_pfft_ecc",
        "P2": "top_p2_pfft_tmr",
    }
    if config.get("tops") != expected_tops:
        failures.append(f"config tops differ from the V3 contract: {config.get('tops')}")
    if config.get("twiddle_schedules") != {
        "P0": "canonical_radix2_DIF_no_exchange",
        "P1": "D90_ECC_oriented_exchange",
        "P2": "canonical_radix2_DIF_no_exchange",
    }:
        failures.append("config twiddle schedules differ from the V3 contract")
    if config.get("result_root") != "results/pfft_resource_v3_001":
        failures.append("config result_root is not the V3 result directory")
    if config.get("log_root") != "logs/pfft_resource_v3_001":
        failures.append("config log_root is not the V3 log directory")
    if config.get("build_root") != "build/pfft_resource_v3_001":
        failures.append("config build_root is not the V3 build directory")
    if config.get("stop_on_first_failure") is not True:
        failures.append("config stop_on_first_failure is not true")
    if config.get("no_automatic_retry") is not True:
        failures.append("config no_automatic_retry is not true")

    hypothesis = config.get("dsp_hypothesis", {})
    if hypothesis.get("dsp_per_generic_complex_multiplier") != 16:
        failures.append("config DSP-per-generic-complex-multiplier is not 16")
    for architecture_id in ARCH_ORDER:
        item = hypothesis.get(architecture_id, {})
        generic = item.get("generic_complex_multipliers_by_stage")
        dsp_by_stage = item.get("DSP48E1_by_stage")
        total = item.get("DSP48E1_total")
        if generic != EXPECTED_GENERIC_BY_STAGE[architecture_id]:
            failures.append(f"{architecture_id} generic multiplier budget differs from D95")
        if dsp_by_stage != EXPECTED_DSP_BY_STAGE[architecture_id]:
            failures.append(f"{architecture_id} stage DSP budget differs from D95")
        if total != EXPECTED_DSP_TOTAL[architecture_id]:
            failures.append(f"{architecture_id} total DSP budget differs from D95")
        if isinstance(generic, list) and sum(generic) * 16 != EXPECTED_DSP_TOTAL[architecture_id]:
            failures.append(f"{architecture_id} generic-to-DSP arithmetic is inconsistent")
        if isinstance(dsp_by_stage, list) and sum(dsp_by_stage) != EXPECTED_DSP_TOTAL[architecture_id]:
            failures.append(f"{architecture_id} stage-to-total DSP arithmetic is inconsistent")


def validate_qualification(
    qualification: dict[str, Any],
    structure_manifest: dict[str, Any],
    failures: list[str],
) -> None:
    if qualification.get("status") != "VERIFIED":
        failures.append("RTL qualification is not VERIFIED")
    if structure_manifest.get("status") != "VERIFIED":
        failures.append("RTL structure manifest is not VERIFIED")
    bit_exact = qualification.get("bit_exact")
    if not isinstance(bit_exact, dict) or set(bit_exact) != set(ARCH_ORDER):
        failures.append("RTL qualification bit_exact set is not exactly P0/P1/P2")
        return
    for architecture_id in ARCH_ORDER:
        item = bit_exact.get(architecture_id, {})
        expected_fields = {
            "status": "VERIFIED",
            "beats": 2048,
            "measured_latency_cycles": 525,
            "gap_errors": 0,
            "last_errors": 0,
            "data_errors": 0,
        }
        for field, expected in expected_fields.items():
            if item.get(field) != expected:
                failures.append(
                    f"{architecture_id} qualification {field}={item.get(field)!r}; "
                    f"expected {expected!r}"
                )
    manifest_hash = qualification.get("manifest_sha256")
    if manifest_hash is not None and str(manifest_hash).upper() != sha256(STRUCTURE_MANIFEST):
        failures.append("qualification manifest_sha256 does not match current structure manifest")


def validate_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    required = (
        CONTRACT,
        CONFIG,
        MEMORY_MAP,
        INPUT_MANIFEST,
        SCHEDULE,
        VECTOR_MANIFEST,
        QUALIFICATION,
        STRUCTURE_MANIFEST,
        YOSYS,
        Path(__file__),
    )
    missing = [display_path(path) for path in required if not path.exists()]
    if missing:
        raise GateFailure(
            "input_validation",
            "missing required PFFT-RES-V3-001 input evidence",
            details=missing,
        )

    config = load_json(CONFIG)
    memory_map = load_json(MEMORY_MAP)
    input_manifest = load_json(INPUT_MANIFEST)
    schedule = load_json(SCHEDULE)
    vector_manifest = load_json(VECTOR_MANIFEST)
    qualification = load_json(QUALIFICATION)
    structure_manifest = load_json(STRUCTURE_MANIFEST)

    failures: list[str] = []
    validate_config(config, failures)
    if schedule.get("status") != "PASS_STATIC_FEASIBILITY_SINGLE_CHECK_PAIR":
        failures.append("P1 Stage 8 static schedule gate is not PASS")
    if vector_manifest.get("status") != "VERIFIED":
        failures.append("V3 vector manifest is not VERIFIED")
    if input_manifest.get("experiment_id") not in {None, "PFFT-RES-V3-001"}:
        failures.append("input manifest belongs to a different experiment")
    if memory_map.get("experiment_id") not in {None, "PFFT-RES-V3-001"}:
        failures.append("memory map belongs to a different experiment")

    sources = structure_sources(structure_manifest, failures)
    validate_qualification(qualification, structure_manifest, failures)

    indexed = indexed_input_manifest(input_manifest)
    validate_all_manifest_records(indexed, failures)
    required_manifest_paths = {
        CONTRACT,
        CONFIG,
        MEMORY_MAP,
        Path(__file__),
        QUALIFICATION_RUNNER,
        YOSYS,
        SCHEDULE,
    }
    required_manifest_paths.update(EXPERIMENT / item for item in TB_SOURCES.values())
    for architecture_sources in EXPECTED_SOURCES.values():
        required_manifest_paths.update(EXPERIMENT / item for item in architecture_sources)
    frozen_vector_records = (
        vector_manifest.get("input", {}),
        vector_manifest.get("P1_unchanged_exchange_vector", {}),
        vector_manifest.get("outputs", {}).get("P0", {}),
        vector_manifest.get("outputs", {}).get("P2", {}),
    )
    for record in frozen_vector_records:
        raw_path = record_path(record) if isinstance(record, dict) else None
        if raw_path is None:
            failures.append("vector manifest lacks a required input/expected-vector path")
        else:
            required_manifest_paths.add(resolve_record_path(raw_path))
    for path in sorted(required_manifest_paths, key=lambda item: str(item).lower()):
        require_manifest_record(indexed, path, failures)

    version = yosys_version()
    if failures:
        raise GateFailure(
            "input_validation",
            "PFFT-RES-V3-001 input validation failed",
            details=failures,
        )

    fingerprint = {
        "contract_sha256": sha256(CONTRACT),
        "config_sha256": sha256(CONFIG),
        "memory_map_sha256": sha256(MEMORY_MAP),
        "input_manifest_sha256": sha256(INPUT_MANIFEST),
        "schedule_sha256": sha256(SCHEDULE),
        "vector_manifest_sha256": sha256(VECTOR_MANIFEST),
        "qualification_sha256": sha256(QUALIFICATION),
        "structure_manifest_sha256": sha256(STRUCTURE_MANIFEST),
        "runner_sha256": sha256(Path(__file__)),
        "yosys_executable_sha256": sha256(YOSYS),
        "source_sha256_by_architecture": {
            architecture_id: {
                item["relative_path"]: item["sha256"] for item in sources[architecture_id]
            }
            for architecture_id in ARCH_ORDER
        },
    }
    validation = {
        "schema": "pfft-resource-v3-001-yosys-input-validation-v1",
        "status": "VERIFIED",
        "timestamp_utc": utc_now(),
        "experiment_id": "PFFT-RES-V3-001",
        "evidence_class": "input_identity_and_qualification_gate_not_synthesis_measurement",
        "fingerprint": fingerprint,
        "sources_by_architecture": sources,
        "tops": config["tops"],
        "yosys": {
            "specified_executable": str(YOSYS),
            "version": version,
            "sha256": sha256(YOSYS),
            "flow": "synth_xilinx -family xc7",
        },
        "python": {
            "executable": sys.executable,
            "sha256": sha256(Path(sys.executable)),
        },
        "qualification_gate": {
            "status": qualification["status"],
            "qualification": display_path(QUALIFICATION),
            "qualification_sha256": sha256(QUALIFICATION),
            "structure_manifest": display_path(STRUCTURE_MANIFEST),
            "structure_manifest_sha256": sha256(STRUCTURE_MANIFEST),
            "schedule": display_path(SCHEDULE),
            "schedule_sha256": sha256(SCHEDULE),
        },
        "input_manifest": {
            "path": display_path(INPUT_MANIFEST),
            "sha256": sha256(INPUT_MANIFEST),
            "hashed_record_count": len(indexed),
        },
        "policy": {
            "independent_source_top_per_architecture": True,
            "stop_on_first_failure": True,
            "no_automatic_retry": True,
            "no_backfill": True,
        },
    }
    return config, validation


def require_prior_validation(config: dict[str, Any], fresh: dict[str, Any]) -> dict[str, Any]:
    del config
    if not VALIDATION_RESULT.exists():
        raise GateFailure(
            "prior_validation",
            f"run --validate-only first; missing {display_path(VALIDATION_RESULT)}",
        )
    prior = load_json(VALIDATION_RESULT)
    if prior.get("status") != "VERIFIED":
        raise GateFailure("prior_validation", "stored input validation is not VERIFIED")
    if prior.get("fingerprint") != fresh.get("fingerprint"):
        raise GateFailure(
            "prior_validation",
            "inputs changed after --validate-only",
            details={
                "stored_fingerprint": prior.get("fingerprint"),
                "current_fingerprint": fresh.get("fingerprint"),
            },
        )
    return prior


def require_prior_preflight(fingerprint: dict[str, Any]) -> dict[str, Any]:
    if not PREFLIGHT_RESULT.exists():
        raise GateFailure(
            "prior_preflight",
            f"run --preflight first; missing {display_path(PREFLIGHT_RESULT)}",
        )
    prior = load_json(PREFLIGHT_RESULT)
    if prior.get("status") != "VERIFIED":
        raise GateFailure("prior_preflight", "stored Yosys preflight is not VERIFIED")
    if prior.get("input_fingerprint") != fingerprint:
        raise GateFailure(
            "prior_preflight",
            "inputs changed after --preflight",
            details={
                "preflight_fingerprint": prior.get("input_fingerprint"),
                "current_fingerprint": fingerprint,
            },
        )
    return prior


def write_script(
    config: dict[str, Any],
    validation: dict[str, Any],
    architecture_id: str,
    mode: str,
    directory: Path,
) -> Path:
    top = config["tops"][architecture_id]
    source_files = [
        item["relative_path"]
        for item in validation["sources_by_architecture"][architecture_id]
    ]
    path = directory / f"{architecture_id}_{mode}.ys"
    lines = [
        "read_verilog -sv " + " ".join(source_files),
        f"hierarchy -check -top {top}",
    ]
    if mode == "preflight":
        lines.extend(("proc", "check"))
    elif mode == "synth":
        hierarchy_name = f"{architecture_id}_hierarchy.json"
        netlist_name = f"{architecture_id}_netlist.json"
        lines.extend(
            (
                "proc",
                "opt_clean",
                f"write_json {hierarchy_name}",
                f"synth_xilinx -family xc7 -top {top}",
                "stat -tech xilinx",
                f"write_json {netlist_name}",
            )
        )
    else:
        raise ValueError(mode)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path


def run_yosys(
    validation: dict[str, Any],
    architecture_id: str,
    mode: str,
    script: Path,
    log: Path,
    output_directory: Path,
) -> subprocess.CompletedProcess[str]:
    temporary_root = Path(tempfile.gettempdir()).resolve()
    stage = temporary_root / ("PV3" + uuid.uuid4().hex[:8].upper())
    stage.mkdir()
    command: list[str] = []
    result: subprocess.CompletedProcess[str] | None = None
    staged_outputs = (
        ()
        if mode == "preflight"
        else (
            f"{architecture_id}_hierarchy.json",
            f"{architecture_id}_netlist.json",
        )
    )
    try:
        script_text = script.read_text(encoding="utf-8")
        source_records = validation["sources_by_architecture"][architecture_id]
        for index, record in enumerate(source_records):
            relative = record["relative_path"]
            original = EXPERIMENT / relative
            staged = stage / f"s{index}_{original.name}"
            shutil.copy2(original, staged)
            script_text = script_text.replace(relative, staged.name)
        staged_script = stage / "flow.ys"
        staged_log = stage / "yosys.log"
        staged_script.write_text(script_text, encoding="utf-8", newline="\n")
        command = [str(YOSYS), "-l", str(staged_log), str(staged_script)]
        result = subprocess.run(
            command,
            cwd=stage,
            env=yosys_environment(),
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=7200,
            check=False,
        )
        log.parent.mkdir(parents=True, exist_ok=True)
        if staged_log.exists():
            shutil.copy2(staged_log, log)
        else:
            log.write_text(result.stdout, encoding="utf-8", newline="\n")
        for name in staged_outputs:
            source = stage / name
            if source.exists():
                shutil.copy2(source, output_directory / name)
    finally:
        resolved = stage.resolve()
        if (
            resolved.parent == temporary_root
            and re.fullmatch(r"PV3[0-9A-F]{8}", resolved.name)
        ):
            shutil.rmtree(resolved)

    if result is None:
        raise GateFailure(
            "runner",
            "Yosys subprocess did not start",
            architecture_id=architecture_id,
        )
    if not log.exists():
        raise GateFailure(
            mode,
            "Yosys did not produce a log",
            architecture_id=architecture_id,
        )
    sidecar = log.with_suffix(".command.json")
    write_json(
        sidecar,
        {
            "schema": "pfft-resource-v3-001-yosys-command-v1",
            "timestamp_utc": utc_now(),
            "experiment_id": "PFFT-RES-V3-001",
            "architecture_id": architecture_id,
            "mode": mode,
            "command": command,
            "specified_executable": str(YOSYS),
            "specified_executable_sha256": sha256(YOSYS),
            "yosys_version": validation["yosys"]["version"],
            "official_script": display_path(script),
            "official_script_sha256": sha256(script),
            "execution_mode": "hash_identical_sources_staged_in_unique_ascii_temporary_directory",
            "source_hashes": {
                item["relative_path"]: item["sha256"]
                for item in validation["sources_by_architecture"][architecture_id]
            },
            "exit_code": result.returncode,
            "console_output_tail": result.stdout[-4000:],
            "log": display_path(log),
            "log_sha256": sha256(log),
        },
    )
    return result


def is_blackbox(module: dict[str, Any]) -> bool:
    value = str(module.get("attributes", {}).get("blackbox", "0"))
    return value in {"1", "00000000000000000000000000000001"}


def clean_name(value: str) -> str:
    return str(value).lstrip("\\")


def hdlname(module_name: str, module: dict[str, Any]) -> str:
    return clean_name(str(module.get("attributes", {}).get("hdlname", module_name)))


def cell_label(cell_name: str, cell: dict[str, Any]) -> str:
    attribute = cell.get("attributes", {}).get("hdlname")
    if isinstance(attribute, str) and attribute:
        return clean_name(attribute)
    return clean_name(cell_name)


def stage_number(*labels: str) -> int | None:
    for label in labels:
        match = STAGE_PATTERN.search(clean_name(label).replace("\\", "/"))
        if match:
            return int(match.group(1))
    return None


def inferred_stage(
    architecture_id: str,
    current: int | None,
    instance_label: str,
    module_label: str,
) -> int | None:
    explicit = stage_number(instance_label)
    if explicit is not None:
        return explicit
    if current is not None:
        return current
    combined = f"{instance_label} {module_label}".lower()
    if architecture_id == "P1" and (
        "stage8" in combined
        or "check_pair" in combined
        or re.search(r"(^|[./])pair($|[./])", instance_label.lower())
    ):
        return 8
    return None


def is_distributed_memory(cell_type: str) -> bool:
    name = clean_name(cell_type)
    return (name.startswith("RAM") and not name.startswith("RAMB")) or name.startswith("SRL")


def hierarchy_audit(
    netlist: dict[str, Any],
    top: str,
    architecture_id: str,
) -> dict[str, Any]:
    modules = netlist.get("modules", {})
    if top not in modules:
        raise GateFailure(
            "netlist_audit",
            f"top {top} absent from JSON hierarchy",
            architecture_id,
        )

    leaf_counts: Counter[str] = Counter()
    leaf_by_stage: dict[int, Counter[str]] = defaultdict(Counter)
    leaf_by_ancestor_module: dict[str, Counter[str]] = defaultdict(Counter)
    module_counts: Counter[str] = Counter()
    generic_by_stage: Counter[int] = Counter()
    unassigned_generic = 0
    stage_roots: dict[int, list[dict[str, str]]] = defaultdict(list)
    active: set[str] = set()

    def walk(
        module_name: str,
        path: str,
        current_stage: int | None,
        ancestor_modules: tuple[str, ...],
    ) -> None:
        nonlocal unassigned_generic
        if module_name in active:
            raise GateFailure(
                "netlist_audit",
                f"recursive module hierarchy at {module_name}",
                architecture_id,
            )
        active.add(module_name)
        module = modules[module_name]
        module_label = hdlname(module_name, module)
        current_ancestors = (*ancestor_modules, module_label)
        for local_name, cell in module.get("cells", {}).items():
            cell_type = cell["type"]
            instance = cell_label(local_name, cell)
            child_path = f"{path}/{instance}" if path else instance
            child_module = modules.get(cell_type)
            child_module_label = (
                hdlname(cell_type, child_module)
                if child_module is not None
                else clean_name(cell_type)
            )
            child_stage = inferred_stage(
                architecture_id,
                current_stage,
                instance,
                child_module_label,
            )
            explicit_stage = stage_number(instance)
            if explicit_stage is not None and current_stage is None:
                stage_roots[explicit_stage].append(
                    {
                        "path": child_path,
                        "module_key": cell_type,
                        "module_hdlname": child_module_label,
                        "instance": instance,
                    }
                )
            if child_module is not None and not is_blackbox(child_module):
                module_counts[child_module_label] += 1
                if child_module_label == "fft_complex_mul_q28":
                    if child_stage is None:
                        unassigned_generic += 1
                    else:
                        generic_by_stage[child_stage] += 1
                walk(cell_type, child_path, child_stage, current_ancestors)
            else:
                leaf = clean_name(cell_type)
                leaf_counts[leaf] += 1
                if child_stage is not None:
                    leaf_by_stage[child_stage][leaf] += 1
                for ancestor_module in current_ancestors:
                    leaf_by_ancestor_module[ancestor_module][leaf] += 1
        active.remove(module_name)

    walk(top, top, None, ())
    return {
        "leaf_counts": leaf_counts,
        "leaf_by_stage": leaf_by_stage,
        "leaf_by_ancestor_module": leaf_by_ancestor_module,
        "module_counts": module_counts,
        "generic_by_stage": generic_by_stage,
        "unassigned_generic": unassigned_generic,
        "stage_roots": stage_roots,
        "modules": modules,
    }


def replica_audit(
    hierarchy: dict[str, Any],
    architecture_id: str,
) -> dict[str, Any]:
    modules = hierarchy["modules"]
    stage_roots = hierarchy["stage_roots"]
    expected_stages = set(EXPECTED_TMR_STAGES[architecture_id])
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    for stage in range(1, 11):
        roots = stage_roots.get(stage, [])
        if len(roots) != 1:
            failures.append(f"Stage {stage} has {len(roots)} live stage roots; expected 1")
            checks.append(
                {
                    "stage": stage,
                    "expected_tmr": stage in expected_stages,
                    "stage_root_count": len(roots),
                    "status": "FAILED",
                }
            )
            continue
        root = roots[0]
        module_label = root["module_hdlname"]
        expects_tmr = stage in expected_stages
        contains_tmr = "tmr" in module_label.lower()
        replica_children: list[dict[str, str]] = []
        voter_children: list[dict[str, str]] = []
        root_module = modules[root["module_key"]]
        for child_name, cell in root_module.get("cells", {}).items():
            child_type = cell["type"]
            child_module = modules.get(child_type)
            if child_module is None or is_blackbox(child_module):
                continue
            child_instance = cell_label(child_name, cell)
            child_hdlname = hdlname(child_type, child_module)
            record = {
                "instance": child_instance,
                "module": child_hdlname,
            }
            if re.search(
                r"(^|[./])rep(?:lica|licas)?(?:\[\d+\])?([./]|$)",
                child_instance,
            ):
                replica_children.append(record)
            if "vote" in child_hdlname.lower() or "voter" in child_hdlname.lower():
                voter_children.append(record)

        check_failures: list[str] = []
        if expects_tmr:
            if not contains_tmr:
                check_failures.append("stage root is not a TMR wrapper")
            if len(replica_children) != 3:
                check_failures.append(
                    f"live TMR replica count is {len(replica_children)}, expected 3"
                )
            # Voters may be inlined into primitives; the wrapper identity and
            # three live replica children are the hard preservation checks.
        elif contains_tmr:
            check_failures.append("unexpected TMR wrapper")
        if check_failures:
            failures.extend(f"Stage {stage}: {item}" for item in check_failures)
        checks.append(
            {
                "stage": stage,
                "expected_tmr": expects_tmr,
                "stage_root": root,
                "stage_root_is_tmr": contains_tmr,
                "replica_children": replica_children,
                "replica_count": len(replica_children),
                "explicit_voter_module_children": voter_children,
                "status": "VERIFIED" if not check_failures else "FAILED",
            }
        )

    live_protection_modules = {
        name: count
        for name, count in sorted(hierarchy["module_counts"].items())
        if count and any(token in name.lower() for token in ("tmr", "voter", "vote35"))
    }
    if architecture_id == "P0" and live_protection_modules:
        failures.append(f"P0 contains live TMR/voter modules: {live_protection_modules}")
    return {
        "status": "VERIFIED" if not failures else "FAILED",
        "expected_tmr_stages": sorted(expected_stages),
        "checks": checks,
        "live_tmr_or_voter_modules": live_protection_modules,
        "failures": failures,
    }


def warning_audit(log_text: str) -> dict[str, Any]:
    warnings = [
        line.strip()
        for line in log_text.splitlines()
        if re.search(r"\bwarning\b", line, flags=re.IGNORECASE)
    ]
    critical = [line for line in warnings if CRITICAL_WARNING_PATTERN.search(line)]
    return {
        "status": "VERIFIED" if not critical else "FAILED",
        "warnings": warnings,
        "critical_warnings": critical,
    }


def blackbox_audit(
    modules: dict[str, Any],
    counts: Counter[str],
) -> dict[str, Any]:
    primitive: list[str] = []
    critical: list[str] = []
    for cell_type in sorted(counts):
        if cell_type.startswith("$scopeinfo"):
            continue
        module = modules.get(cell_type)
        if module is None:
            if cell_type.startswith("$__ABC9_"):
                primitive.append(cell_type)
            else:
                critical.append(cell_type)
            continue
        if is_blackbox(module):
            source = (
                str(module.get("attributes", {}).get("src", ""))
                .replace("\\", "/")
                .lower()
            )
            if "/share/yosys/xilinx/" in source or cell_type.startswith("$__ABC9_"):
                primitive.append(cell_type)
            else:
                critical.append(cell_type)
    return {
        "status": "VERIFIED" if not critical else "FAILED",
        "primitive_blackboxes": primitive,
        "critical_blackboxes": critical,
    }


def stage_vector(counter: Counter[int]) -> list[int]:
    return [int(counter[stage]) for stage in range(1, 11)]


def parse_synthesis(
    config: dict[str, Any],
    validation: dict[str, Any],
    architecture_id: str,
    script: Path,
    log: Path,
    hierarchy_path: Path,
    netlist_path: Path,
) -> dict[str, Any]:
    top = config["tops"][architecture_id]
    log_text = log.read_text(encoding="utf-8", errors="replace")
    hierarchy_json = load_json(hierarchy_path)
    netlist_json = load_json(netlist_path)
    pre = hierarchy_audit(hierarchy_json, top, architecture_id)
    post = hierarchy_audit(netlist_json, top, architecture_id)

    generic_measured = stage_vector(pre["generic_by_stage"])
    generic_expected = EXPECTED_GENERIC_BY_STAGE[architecture_id]
    generic_total = sum(generic_measured) + pre["unassigned_generic"]
    generic_target_total = sum(generic_expected)

    dsp_by_stage_counter = Counter(
        {
            stage: post["leaf_by_stage"][stage]["DSP48E1"]
            for stage in range(1, 11)
        }
    )
    dsp_measured = stage_vector(dsp_by_stage_counter)
    dsp_expected = EXPECTED_DSP_BY_STAGE[architecture_id]
    dsp_total = post["leaf_counts"]["DSP48E1"]
    dsp_assigned = sum(dsp_measured)
    dsp_unassigned = dsp_total - dsp_assigned

    lc_matches = re.findall(r"Estimated number of LCs:\s*(\d+)", log_text)
    distributed = {
        name: count
        for name, count in sorted(post["leaf_counts"].items())
        if count and is_distributed_memory(name)
    }
    warnings = warning_audit(log_text)
    blackboxes = blackbox_audit(post["modules"], post["leaf_counts"])
    replicas = replica_audit(pre, architecture_id)
    memory_mapping = {
        "status": "NOT_APPLICABLE",
        "scope": "P1_stage8_single_check_pair_scheduler",
    }
    if architecture_id == "P1":
        scheduler_leaf_counts = post["leaf_by_ancestor_module"].get(
            "p1_stage8_single_check_pair_scheduler_v3",
            Counter(),
        )
        scheduler_ramb18 = int(scheduler_leaf_counts["RAMB18E1"])
        scheduler_ramb36 = int(scheduler_leaf_counts["RAMB36E1"])
        scheduler_logical_block_bits = (
            12 * 512 * 78
            + 128 * (23 + 12 * 78)
            + 2 * 512 * 312
        )
        scheduler_mapped_block_capacity_bits = (
            scheduler_ramb18 * 18_432
            + scheduler_ramb36 * 36_864
        )
        scheduler_bram36_equivalent = (
            scheduler_ramb36 + 0.5 * scheduler_ramb18
        )
        memory_mapping = {
            "status": (
                "VERIFIED"
                if scheduler_mapped_block_capacity_bits
                >= scheduler_logical_block_bits
                else "FAILED"
            ),
            "scope": "P1_stage8_single_check_pair_scheduler",
            "RAMB18E1": scheduler_ramb18,
            "RAMB36E1": scheduler_ramb36,
            "BRAM36_equivalent": scheduler_bram36_equivalent,
            "minimum_BRAM36_equivalent": 25,
            "declared_block_array_count": 15,
            "declared_logical_capacity_bits": scheduler_logical_block_bits,
            "mapped_nominal_block_capacity_bits": (
                scheduler_mapped_block_capacity_bits
            ),
            "requirement": (
                "aggregate_RAMB_capacity_under_the_live_scheduler_must_cover_"
                "the_921472_declared_history_FIFO_and_result_bits"
            ),
            "scheduler_leaf_cell_counts": dict(
                sorted(scheduler_leaf_counts.items())
            ),
        }
    missing_metrics = [] if lc_matches else ["Estimated number of LCs"]

    target_checks = {
        "generic_complex_multipliers_by_stage": {
            "expected": generic_expected,
            "measured": generic_measured,
            "pass": generic_measured == generic_expected
            and pre["unassigned_generic"] == 0,
            "unassigned": pre["unassigned_generic"],
        },
        "generic_complex_multipliers_total": {
            "expected": generic_target_total,
            "measured": generic_total,
            "pass": generic_total == generic_target_total
            and pre["unassigned_generic"] == 0,
        },
        "DSP48E1_by_stage": {
            "expected": dsp_expected,
            "measured": dsp_measured,
            "pass": dsp_measured == dsp_expected and dsp_unassigned == 0,
            "unassigned": dsp_unassigned,
        },
        "DSP48E1_total": {
            "expected": EXPECTED_DSP_TOTAL[architecture_id],
            "measured": dsp_total,
            "pass": dsp_total == EXPECTED_DSP_TOTAL[architecture_id],
        },
        "DSP48E1_per_generic_complex_multiplier": {
            "expected": 16,
            "measured": (
                dsp_total / generic_total if generic_total else None
            ),
            "pass": generic_total > 0 and dsp_total == generic_total * 16,
        },
    }
    target_status = (
        "VERIFIED"
        if all(item["pass"] for item in target_checks.values())
        else "FAILED"
    )
    audit_status = (
        "VERIFIED"
        if not missing_metrics
        and warnings["status"] == "VERIFIED"
        and blackboxes["status"] == "VERIFIED"
        and replicas["status"] == "VERIFIED"
        and memory_mapping["status"] in {"VERIFIED", "NOT_APPLICABLE"}
        else "FAILED"
    )
    counts = post["leaf_counts"]
    return {
        "architecture_id": architecture_id,
        "top": top,
        "status": (
            "VERIFIED"
            if target_status == "VERIFIED" and audit_status == "VERIFIED"
            else "FAILED"
        ),
        "target_status": target_status,
        "post_synthesis_audit_status": audit_status,
        "resources": {
            "LC_estimate": int(lc_matches[-1]) if lc_matches else None,
            "LUT1_to_LUT6": sum(counts[f"LUT{size}"] for size in range(1, 7)),
            "FF": sum(counts[name] for name in FF_TYPES),
            "DSP48E1": dsp_total,
            "RAMB18E1": counts["RAMB18E1"],
            "RAMB36E1": counts["RAMB36E1"],
            "BRAM36_equivalent": counts["RAMB36E1"] + 0.5 * counts["RAMB18E1"],
            "distributed_memory_cells_total": sum(distributed.values()),
            "distributed_memory_cells": distributed,
        },
        "target_checks": target_checks,
        "replica_preservation_audit": replicas,
        "memory_mapping_audit": memory_mapping,
        "warning_audit": warnings,
        "blackbox_audit": blackboxes,
        "missing_metrics": missing_metrics,
        "cell_counts": dict(sorted(counts.items())),
        "script": display_path(script),
        "script_sha256": sha256(script),
        "log": display_path(log),
        "log_sha256": sha256(log),
        "command_sidecar": display_path(log.with_suffix(".command.json")),
        "command_sidecar_sha256": sha256(log.with_suffix(".command.json")),
        "pre_synthesis_hierarchy": display_path(hierarchy_path),
        "pre_synthesis_hierarchy_sha256": sha256(hierarchy_path),
        "post_synthesis_netlist": display_path(netlist_path),
        "post_synthesis_netlist_sha256": sha256(netlist_path),
        "source_hashes": {
            item["relative_path"]: item["sha256"]
            for item in validation["sources_by_architecture"][architecture_id]
        },
    }


def write_failure(
    path: Path,
    error: GateFailure,
    mode: str,
    fingerprint: dict[str, Any] | None,
    completed: list[dict[str, Any]],
) -> None:
    if path.exists():
        return
    write_json(
        path,
        {
            "schema": "pfft-resource-v3-001-yosys-failure-v1",
            "status": "FAILED",
            "timestamp_utc": utc_now(),
            "experiment_id": "PFFT-RES-V3-001",
            "mode": mode,
            "stage": error.stage,
            "architecture_id": error.architecture_id,
            "message": str(error),
            "details": error.details,
            "input_fingerprint": fingerprint,
            "completed_architectures": completed,
            "policy": "stop_no_retry_no_backfill_no_final_table",
        },
    )


def run_validate_only(config: dict[str, Any], validation: dict[str, Any]) -> int:
    del config
    if VALIDATION_RESULT.exists():
        raise GateFailure(
            "runner",
            f"validation artifact already exists; refusing rerun: "
            f"{display_path(VALIDATION_RESULT)}",
        )
    write_json(VALIDATION_RESULT, validation)
    print(
        f"INPUT VALIDATION VERIFIED {display_path(VALIDATION_RESULT)} "
        f"SHA256={sha256(VALIDATION_RESULT)}",
        flush=True,
    )
    return 0


def run_preflight(
    config: dict[str, Any],
    fresh_validation: dict[str, Any],
) -> int:
    prior = require_prior_validation(config, fresh_validation)
    directory = BUILD / "yosys" / "preflight"
    expected_logs = [
        LOGS / f"yosys_preflight_{architecture_id}.log"
        for architecture_id in ARCH_ORDER
    ]
    if (
        directory.exists()
        or PREFLIGHT_RESULT.exists()
        or any(path.exists() or path.with_suffix(".command.json").exists() for path in expected_logs)
    ):
        raise GateFailure(
            "preflight",
            "preflight artifacts already exist; refusing an implicit rerun",
        )
    directory.mkdir(parents=True)
    completed: list[dict[str, Any]] = []
    try:
        for architecture_id in ARCH_ORDER:
            print(f"PREFLIGHT START {architecture_id}", flush=True)
            script = write_script(
                config,
                prior,
                architecture_id,
                "preflight",
                directory,
            )
            log = LOGS / f"yosys_preflight_{architecture_id}.log"
            result = run_yosys(
                prior,
                architecture_id,
                "preflight",
                script,
                log,
                directory,
            )
            item = {
                "architecture_id": architecture_id,
                "top": config["tops"][architecture_id],
                "exit_code": result.returncode,
                "script": display_path(script),
                "script_sha256": sha256(script),
                "log": display_path(log),
                "log_sha256": sha256(log),
                "command_sidecar": display_path(log.with_suffix(".command.json")),
                "command_sidecar_sha256": sha256(log.with_suffix(".command.json")),
            }
            completed.append(item)
            print(
                f"PREFLIGHT END {architecture_id} exit={result.returncode}",
                flush=True,
            )
            if result.returncode != 0:
                raise GateFailure(
                    "preflight",
                    f"Yosys preflight exited {result.returncode}",
                    architecture_id,
                    item,
                )
        write_json(
            PREFLIGHT_RESULT,
            {
                "schema": "pfft-resource-v3-001-yosys-preflight-v1",
                "status": "VERIFIED",
                "timestamp_utc": utc_now(),
                "experiment_id": "PFFT-RES-V3-001",
                "input_validation": display_path(VALIDATION_RESULT),
                "input_validation_sha256": sha256(VALIDATION_RESULT),
                "input_fingerprint": prior["fingerprint"],
                "architectures": completed,
                "policy": "one_shot_stop_on_first_failure_no_retry",
            },
        )
        print(
            f"PREFLIGHT VERIFIED {display_path(PREFLIGHT_RESULT)} "
            f"SHA256={sha256(PREFLIGHT_RESULT)}",
            flush=True,
        )
        return 0
    except GateFailure as error:
        write_failure(
            PREFLIGHT_RESULT,
            error,
            "preflight",
            prior.get("fingerprint"),
            completed,
        )
        print(
            f"STOP {error.stage} architecture={error.architecture_id} "
            f"evidence={display_path(PREFLIGHT_RESULT)}",
            flush=True,
        )
        return 2


def with_p0_deltas(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    baseline = next(row for row in rows if row["architecture_id"] == "P0")
    metrics = (
        "LC_estimate",
        "LUT1_to_LUT6",
        "FF",
        "DSP48E1",
        "RAMB18E1",
        "RAMB36E1",
        "BRAM36_equivalent",
        "distributed_memory_cells_total",
    )
    output: list[dict[str, Any]] = []
    for row in rows:
        item = {
            "architecture_id": row["architecture_id"],
            "top": row["top"],
            **row["resources"],
        }
        for metric in metrics:
            value = row["resources"][metric]
            base_value = baseline["resources"][metric]
            item[f"{metric}_delta_vs_P0"] = value - base_value
            item[f"{metric}_percent_vs_P0"] = (
                None if base_value == 0 else (value - base_value) * 100.0 / base_value
            )
        output.append(item)
    return output


def write_csv(rows: list[dict[str, Any]]) -> None:
    CSV_RESULT.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0])
    with CSV_RESULT.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# PFFT-RES-V3-001 Yosys resource audit",
        "",
        f"Overall status: **{summary['status']}**",
        "",
        "- Evidence class: specified Yosys `xc7` synthesis resource estimate.",
        "- Boundary: not Vivado post-implementation utilization, timing, Fmax, power, or board measurement.",
        "- P0/P1/P2 were synthesized independently from the common six-file set plus their own top.",
        "- LUT/LC, FF, DSP48E1 and BRAM are separate metrics and are not added into one total.",
        "",
        "| ID | LC estimate | LUT1-6 | FF | DSP48E1 | RAMB18 | RAMB36 | BRAM36 equiv. | Distributed memory cells |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary["group"]:
        lines.append(
            f"| {row['architecture_id']} | {row['LC_estimate']} | "
            f"{row['LUT1_to_LUT6']} | {row['FF']} | {row['DSP48E1']} | "
            f"{row['RAMB18E1']} | {row['RAMB36E1']} | "
            f"{row['BRAM36_equivalent']} | "
            f"{row['distributed_memory_cells_total']} |"
        )
    lines.extend(("", "## D95 target audit", ""))
    for architecture_id in ARCH_ORDER:
        row = next(
            item
            for item in summary["raw_measurements"]
            if item["architecture_id"] == architecture_id
        )
        target = row["target_checks"]
        lines.append(
            f"- {architecture_id}: generic multipliers "
            f"{target['generic_complex_multipliers_by_stage']['measured']} "
            f"(target {target['generic_complex_multipliers_by_stage']['expected']}), "
            f"DSP48E1 {target['DSP48E1_by_stage']['measured']} "
            f"(target {target['DSP48E1_by_stage']['expected']})."
        )
    lines.append("")
    return "\n".join(lines)


def write_formal_outputs(
    config: dict[str, Any],
    validation: dict[str, Any],
    rows: list[dict[str, Any]],
) -> None:
    group = with_p0_deltas(rows)
    write_csv(group)
    summary = {
        "schema": "pfft-resource-v3-001-yosys-summary-v1",
        "status": "VERIFIED",
        "timestamp_utc": utc_now(),
        "experiment_id": "PFFT-RES-V3-001",
        "attempt": "attempt1",
        "evidence_class": "same_flow_independent_top_Yosys_xc7_synthesis_resource_estimate",
        "claim_boundary": config["claim_boundary"],
        "yosys": validation["yosys"],
        "input_fingerprint": validation["fingerprint"],
        "baseline": "P0",
        "group": group,
        "raw_measurements": rows,
        "artifacts": {
            "raw": display_path(RAW_RESULT),
            "raw_sha256": sha256(RAW_RESULT),
            "csv": display_path(CSV_RESULT),
            "csv_sha256": sha256(CSV_RESULT),
            "markdown": display_path(MARKDOWN_RESULT),
        },
    }
    write_json(SUMMARY_RESULT, summary)
    MARKDOWN_RESULT.write_text(
        render_markdown(summary),
        encoding="utf-8",
        newline="\n",
    )


def run_synthesis(
    config: dict[str, Any],
    fresh_validation: dict[str, Any],
    attempt: str,
) -> int:
    if attempt != "attempt1":
        raise GateFailure(
            "runner",
            "PFFT-RES-V3-001 authorizes only --attempt attempt1",
        )
    prior = require_prior_validation(config, fresh_validation)
    require_prior_preflight(prior["fingerprint"])
    directory = BUILD / "yosys" / attempt
    protected_outputs = (
        RAW_RESULT,
        SUMMARY_RESULT,
        CSV_RESULT,
        MARKDOWN_RESULT,
    )
    expected_logs = [
        LOGS / f"yosys_{attempt}_{architecture_id}.log"
        for architecture_id in ARCH_ORDER
    ]
    if (
        directory.exists()
        or any(path.exists() for path in protected_outputs)
        or any(path.exists() or path.with_suffix(".command.json").exists() for path in expected_logs)
    ):
        raise GateFailure(
            "synthesis",
            "attempt1 or final artifacts already exist; refusing an implicit rerun",
        )
    directory.mkdir(parents=True)
    rows: list[dict[str, Any]] = []
    try:
        for architecture_id in ARCH_ORDER:
            print(f"SYNTHESIS START {architecture_id}", flush=True)
            script = write_script(
                config,
                prior,
                architecture_id,
                "synth",
                directory,
            )
            log = LOGS / f"yosys_{attempt}_{architecture_id}.log"
            result = run_yosys(
                prior,
                architecture_id,
                "synth",
                script,
                log,
                directory,
            )
            if result.returncode != 0:
                raise GateFailure(
                    "synthesis",
                    f"Yosys synthesis exited {result.returncode}",
                    architecture_id,
                    {
                        "log": display_path(log),
                        "log_sha256": sha256(log),
                        "command_sidecar": display_path(log.with_suffix(".command.json")),
                        "command_sidecar_sha256": sha256(log.with_suffix(".command.json")),
                    },
                )
            hierarchy_path = directory / f"{architecture_id}_hierarchy.json"
            netlist_path = directory / f"{architecture_id}_netlist.json"
            missing = [
                display_path(path)
                for path in (hierarchy_path, netlist_path)
                if not path.exists()
            ]
            if missing:
                raise GateFailure(
                    "synthesis",
                    "Yosys omitted required hierarchy/netlist JSON",
                    architecture_id,
                    missing,
                )
            row = parse_synthesis(
                config,
                prior,
                architecture_id,
                script,
                log,
                hierarchy_path,
                netlist_path,
            )
            rows.append(row)
            resources = row["resources"]
            print(
                f"SYNTHESIS END {architecture_id} status={row['status']} "
                f"LC={resources['LC_estimate']} FF={resources['FF']} "
                f"DSP={resources['DSP48E1']} "
                f"BRAM36eq={resources['BRAM36_equivalent']}",
                flush=True,
            )
            if row["post_synthesis_audit_status"] != "VERIFIED":
                raise GateFailure(
                    "post_synthesis_audit",
                    "critical warning/blackbox/metric/TMR-preservation audit failed",
                    architecture_id,
                    row,
                )
            if row["target_status"] != "VERIFIED":
                target_failure = {
                    "architecture_id": row["architecture_id"],
                    "target_checks": {
                        name: item
                        for name, item in row["target_checks"].items()
                        if not item["pass"]
                    },
                }
                write_json(
                    RAW_RESULT,
                    {
                        "schema": "pfft-resource-v3-001-yosys-raw-measurements-v1",
                        "status": "BLOCKED_D95_THEORY_MISMATCH",
                        "result_class": "FAILED",
                        "timestamp_utc": utc_now(),
                        "experiment_id": "PFFT-RES-V3-001",
                        "attempt": attempt,
                        "evidence_class": "raw_Yosys_xc7_synthesis_measurements",
                        "input_fingerprint": prior["fingerprint"],
                        "architectures": rows,
                        "target_failures": [target_failure],
                        "stopped_after_architecture": architecture_id,
                        "unexecuted_architectures": list(
                            ARCH_ORDER[ARCH_ORDER.index(architecture_id) + 1 :]
                        ),
                        "failure_policy": (
                            "preserve_first_mismatch_and_stop_no_final_table_"
                            "no_retry_no_backfill"
                        ),
                    },
                )
                print(
                    f"STOP BLOCKED_D95_THEORY_MISMATCH "
                    f"architecture={architecture_id} "
                    f"evidence={display_path(RAW_RESULT)} "
                    f"SHA256={sha256(RAW_RESULT)}",
                    flush=True,
                )
                return 3

        write_json(
            RAW_RESULT,
            {
                "schema": "pfft-resource-v3-001-yosys-raw-measurements-v1",
                "status": "VERIFIED",
                "result_class": "VERIFIED",
                "timestamp_utc": utc_now(),
                "experiment_id": "PFFT-RES-V3-001",
                "attempt": attempt,
                "evidence_class": "raw_Yosys_xc7_synthesis_measurements",
                "input_fingerprint": prior["fingerprint"],
                "architectures": rows,
                "target_failures": [],
                "failure_policy": (
                    "single_attempt_stop_on_first_failure_no_retry_no_backfill"
                ),
            },
        )

        write_formal_outputs(config, prior, rows)
        print(
            json.dumps(
                {
                    "status": "VERIFIED",
                    "raw": display_path(RAW_RESULT),
                    "raw_sha256": sha256(RAW_RESULT),
                    "summary": display_path(SUMMARY_RESULT),
                    "summary_sha256": sha256(SUMMARY_RESULT),
                    "csv": display_path(CSV_RESULT),
                    "csv_sha256": sha256(CSV_RESULT),
                    "markdown": display_path(MARKDOWN_RESULT),
                    "markdown_sha256": sha256(MARKDOWN_RESULT),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        return 0
    except Exception as unexpected:
        error = (
            unexpected
            if isinstance(unexpected, GateFailure)
            else GateFailure(
                "runner_internal",
                repr(unexpected),
                details={"exception_type": type(unexpected).__name__},
            )
        )
        if not RAW_RESULT.exists():
            write_failure(
                RAW_RESULT,
                error,
                "synthesis",
                prior.get("fingerprint"),
                rows,
            )
        print(
            f"STOP {error.stage} architecture={error.architecture_id} "
            f"evidence={display_path(RAW_RESULT)}",
            flush=True,
        )
        return 2


def main() -> int:
    parser = argparse.ArgumentParser(
        description="One-shot PFFT-RES-V3-001 Yosys xc7 evidence runner."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--validate-only", action="store_true")
    action.add_argument("--preflight", action="store_true")
    action.add_argument("--synthesize", action="store_true")
    parser.add_argument("--attempt", default="attempt1")
    args = parser.parse_args()

    if args.attempt != "attempt1":
        print("STOP runner: only --attempt attempt1 is authorized", flush=True)
        return 2
    try:
        config, validation = validate_inputs()
        if args.validate_only:
            return run_validate_only(config, validation)
        if args.preflight:
            return run_preflight(config, validation)
        return run_synthesis(config, validation, args.attempt)
    except GateFailure as error:
        print(
            f"STOP {error.stage} architecture={error.architecture_id}: {error}",
            flush=True,
        )
        if error.details is not None:
            print(
                json.dumps(error.details, ensure_ascii=False, indent=2),
                flush=True,
            )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
