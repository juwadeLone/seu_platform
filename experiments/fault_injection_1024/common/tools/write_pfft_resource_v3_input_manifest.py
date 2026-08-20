#!/usr/bin/env python3
"""Freeze the pre-qualification input manifest for PFFT-RES-V3-001.

The manifest intentionally excludes the not-yet-created RTL qualification and
structure outputs.  Those downstream hashes belong to the Yosys validation
evidence, avoiding a circular dependency in the evidence chain.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
WORKSPACE = HERE.parents[3]
SHARED_RTL = EXPERIMENT / "common" / "rtl"
OUTPUT = EXPERIMENT / "config" / "pfft_resource_v3_input_manifest.json"

PYTHON = Path(r"C:\Program Files\Inkscape\bin\python.exe")
IVERILOG = Path(r"C:\iverilog\bin\iverilog.exe")
VVP = Path(r"C:\iverilog\bin\vvp.exe")
YOSYS = Path(r"C:\Users\pc\Downloads\oss-cad-suite\bin\yosys.exe")

COMMON_SOURCES = (
    SHARED_RTL / "twiddle_rom_1024.sv",
    SHARED_RTL / "fft_common.sv",
    SHARED_RTL / "protection_rtl.sv",
    SHARED_RTL / "datapath_v5.sv",
    SHARED_RTL / "protection_primitives_v5.sv",
    SHARED_RTL / "protected_stages_v5.sv",
)
PROJECTS = {
    "P0": {
        "top": "top_p0_pfft_unprotected",
        "source": EXPERIMENT / "projects" / "P0" / "top_p0_pfft_unprotected.sv",
        "tb": EXPERIMENT / "projects" / "P0" / "tb_p0.sv",
        "vector": (
            EXPERIMENT
            / "projects"
            / "P0"
            / "vectors"
            / "qualification_p0_no_exchange_expected_8frames.hex"
        ),
    },
    "P1": {
        "top": "top_p1_pfft_ecc",
        "source": EXPERIMENT / "projects" / "P1" / "top_p1_pfft_ecc.sv",
        "tb": EXPERIMENT / "projects" / "P1" / "tb_p1.sv",
        "vector": (
            EXPERIMENT
            / "common"
            / "vectors"
            / "qualification_pfft_expected_8frames.hex"
        ),
    },
    "P2": {
        "top": "top_p2_pfft_tmr",
        "source": EXPERIMENT / "projects" / "P2" / "top_p2_pfft_tmr.sv",
        "tb": EXPERIMENT / "projects" / "P2" / "tb_p2.sv",
        "vector": (
            EXPERIMENT
            / "projects"
            / "P2"
            / "vectors"
            / "qualification_p2_no_exchange_expected_8frames.hex"
        ),
    },
}

CONTRACT_FILES = (
    EXPERIMENT / "PFFT_RESOURCE_REEVALUATION_V3.md",
    EXPERIMENT / "config" / "pfft_resource_reevaluation_v3.json",
    EXPERIMENT / "config" / "pfft_resource_memory_map_v3.json",
)
VECTOR_INPUT = (
    EXPERIMENT / "common" / "vectors" / "qualification_input_10frames.hex"
)
VECTOR_MANIFEST = (
    EXPERIMENT / "results" / "pfft_resource_v3_001" / "vector_manifest.json"
)
SCHEDULE_EVIDENCE = (
    EXPERIMENT / "results" / "pfft_resource_v3_001" / "schedule_feasibility_attempt1.json"
)
SNAPSHOT_MANIFEST = (
    WORKSPACE
    / "archive"
    / "migration"
    / "2026-07-23"
    / "pre_edit"
    / "2026-07-23_PFFT-RES-V3-001_authorized"
    / "snapshot_sha256.csv"
)
INCLUDES_AND_SPOTS = (
    SHARED_RTL / "pfft_project_tb_v3.svh",
    SHARED_RTL / "pfft_connectivity_spot_tb_v3.sv",
)
SUPPORT_TOOLS = (
    HERE / "generate_pfft_no_exchange_vectors_v3.py",
    HERE / "run_pfft_resource_qualification_v3.py",
    HERE / "run_pfft_yosys_resources_v3.py",
    HERE / "write_pfft_resource_v3_input_manifest.py",
    EXPERIMENT / "projects" / "P1" / "audit_p1_stage8_single_check_pair_v3.py",
)


def label(path: Path) -> str:
    return path.relative_to(WORKSPACE).as_posix() if path.is_relative_to(WORKSPACE) else path.as_posix()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def record(path: Path) -> dict[str, object]:
    return {"path": label(path), "sha256": sha256(path), "size_bytes": path.stat().st_size}


def canonical_bytes(payload: object) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(
            "pre-qualification input manifest already exists; refusing implicit overwrite"
        )

    required = {
        PYTHON,
        IVERILOG,
        VVP,
        YOSYS,
        *CONTRACT_FILES,
        VECTOR_INPUT,
        VECTOR_MANIFEST,
        SCHEDULE_EVIDENCE,
        SNAPSHOT_MANIFEST,
        *COMMON_SOURCES,
        *INCLUDES_AND_SPOTS,
        *SUPPORT_TOOLS,
        *(entry["source"] for entry in PROJECTS.values()),
        *(entry["tb"] for entry in PROJECTS.values()),
        *(entry["vector"] for entry in PROJECTS.values()),
    }
    missing = sorted(label(path) for path in required if not path.exists())
    if missing:
        raise FileNotFoundError("missing pre-qualification input: " + ", ".join(missing))

    vector_manifest = json.loads(VECTOR_MANIFEST.read_text(encoding="utf-8"))
    if vector_manifest.get("status") != "VERIFIED":
        raise RuntimeError("V3 vector manifest is not VERIFIED")
    p0_vector = PROJECTS["P0"]["vector"]
    p2_vector = PROJECTS["P2"]["vector"]
    if p0_vector.read_bytes() != p2_vector.read_bytes():
        raise RuntimeError("P0 and P2 canonical-DIF expected vectors are not byte-identical")
    if sha256(p0_vector) != vector_manifest["outputs"]["shared_sha256"]:
        raise RuntimeError("P0/P2 vector SHA-256 does not match vector_manifest.json")

    schedule = json.loads(SCHEDULE_EVIDENCE.read_text(encoding="utf-8"))
    if (
        schedule.get("status") != "PASS_STATIC_FEASIBILITY_SINGLE_CHECK_PAIR"
        or schedule.get("stop_condition_triggered") is not False
        or not all(schedule.get("pass_fail_checks", {}).values())
    ):
        raise RuntimeError("P1 Stage-8 single-check-pair feasibility evidence is not PASS")

    architecture_sources = {
        architecture: [
            record(path) for path in (*COMMON_SOURCES, entry["source"])
        ]
        for architecture, entry in PROJECTS.items()
    }
    payload: dict[str, object] = {
        "schema": "pfft-resource-v3-001-input-manifest-v1",
        "status": "FROZEN_PRE_QUALIFICATION_INPUTS",
        "experiment_id": "PFFT-RES-V3-001",
        "scope": "pre_qualification_and_pre_yosys_inputs_only",
        "dependency_order": [
            "this_input_manifest",
            "rtl_structure_manifest_and_rtl_qualification",
            "yosys_input_validation_and_preflight",
            "yosys_measurement_attempt1",
        ],
        "excluded_downstream_outputs": {
            "paths": [
                "experiments/fault_injection_1024/results/pfft_resource_v3_001/qualification_attempt1/rtl_structure_manifest.json",
                "experiments/fault_injection_1024/results/pfft_resource_v3_001/qualification_attempt1/rtl_qualification.json",
            ],
            "reason": "not_created_until_after_this_prequalification_manifest; downstream Yosys evidence records their SHA-256",
        },
        "tool_executables": {
            "python": record(PYTHON),
            "iverilog": record(IVERILOG),
            "vvp": record(VVP),
            "yosys": record(YOSYS),
        },
        "contracts": [record(path) for path in CONTRACT_FILES],
        "snapshot_manifest": record(SNAPSHOT_MANIFEST),
        "schedule_evidence": record(SCHEDULE_EVIDENCE),
        "vector_manifest": record(VECTOR_MANIFEST),
        "vectors": {
            "input_10frames": record(VECTOR_INPUT),
            **{
                architecture: record(entry["vector"])
                for architecture, entry in PROJECTS.items()
            },
            "P0_and_P2_byte_identical": True,
        },
        "architecture_tops": {
            architecture: entry["top"] for architecture, entry in PROJECTS.items()
        },
        "shared_rtl_sources": [record(path) for path in COMMON_SOURCES],
        "architecture_sources": architecture_sources,
        "testbenches": {
            architecture: record(entry["tb"])
            for architecture, entry in PROJECTS.items()
        },
        "includes_and_connectivity_spot": [
            record(path) for path in INCLUDES_AND_SPOTS
        ],
        "support_tools": [record(path) for path in SUPPORT_TOOLS],
        "policy": {
            "stop_on_first_failure": True,
            "no_automatic_retry": True,
            "frozen_theoretical_DSP48E1_targets": {
                "P0": 464,
                "P1": 736,
                "P2": 1392,
            },
            "qualification_target": {
                "beats": 2048,
                "latency_cycles": 525,
                "continuous_after_first_valid": True,
                "out_last_every_256_beats": True,
            },
        },
    }
    payload["content_fingerprint_sha256"] = hashlib.sha256(
        canonical_bytes(payload)
    ).hexdigest().upper()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(canonical_bytes(payload))
    print(
        f"INPUT_MANIFEST PASS path={label(OUTPUT)} sha256={sha256(OUTPUT)} "
        f"fingerprint={payload['content_fingerprint_sha256']}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            f"INPUT_MANIFEST FAIL type={type(exc).__name__} message={exc}",
            file=sys.stderr,
        )
        raise SystemExit(1)
