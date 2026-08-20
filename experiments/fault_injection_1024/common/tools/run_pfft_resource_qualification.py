#!/usr/bin/env python3
"""Single-pass P0/P1/P2 qualification for PFFT-RES-V2-001."""

from __future__ import annotations

import hashlib
import json
import locale
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
WORKSPACE = HERE.parents[3]
SHARED_RTL = EXPERIMENT / "common" / "rtl"
SHARED_VECTORS = EXPERIMENT / "common" / "vectors"
RESULTS = EXPERIMENT / "results" / "pfft_resource_v2_001" / "qualification_attempt2"
LOGS = EXPERIMENT / "logs" / "pfft_resource_v2_001" / "qualification_attempt2"
BUILD = EXPERIMENT / "build" / "pfft_resource_v2_001" / "rtl_attempt2"
IVERILOG = Path(r"C:\iverilog\bin\iverilog.exe")
VVP = Path(r"C:\iverilog\bin\vvp.exe")

SOURCES = (
    SHARED_RTL / "twiddle_rom_1024.sv",
    SHARED_RTL / "fft_common.sv",
    SHARED_RTL / "protection_rtl.sv",
    SHARED_RTL / "datapath_v5.sv",
    SHARED_RTL / "protection_primitives_v5.sv",
    SHARED_RTL / "protected_stages_v5.sv",
    EXPERIMENT / "projects" / "P0" / "top_p0_pfft_unprotected.sv",
    EXPERIMENT / "projects" / "P1" / "top_p1_pfft_ecc.sv",
    EXPERIMENT / "projects" / "P2" / "top_p2_pfft_tmr.sv",
)
TOPS = (
    ("P0", "top_p0_pfft_unprotected", EXPERIMENT / "projects" / "P0" / "tb_p0.sv", "tb_p0"),
    ("P1", "top_p1_pfft_ecc", EXPERIMENT / "projects" / "P1" / "tb_p1.sv", "tb_p1"),
    ("P2", "top_p2_pfft_tmr", EXPERIMENT / "projects" / "P2" / "tb_p2.sv", "tb_p2"),
)
VECTORS = (
    SHARED_VECTORS / "qualification_input_10frames.hex",
    SHARED_VECTORS / "qualification_pfft_expected_8frames.hex",
)
CONTRACTS = (
    EXPERIMENT / "PFFT_RESOURCE_REEVALUATION_V2.md",
    EXPERIMENT / "config" / "pfft_resource_reevaluation_v2.json",
    EXPERIMENT / "config" / "seven_architecture_memory_map.json",
)
SNAPSHOT = (
    WORKSPACE
    / "archive"
    / "migration"
    / "2026-07-23"
    / "pre_edit"
    / "2026-07-23_PFFT-RES-V2-001_resource_reevaluation"
    / "SNAPSHOT_SHA256.md"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def module_text(text: str, name: str) -> str:
    match = re.search(rf"\bmodule\s+{re.escape(name)}\b.*?\bendmodule\b", text, flags=re.S)
    if not match:
        raise RuntimeError(f"module not found: {name}")
    return match.group(0)


def pfft_phi(stage: int, index: int) -> int:
    exponent = 0
    for high_bit in range(1, 10):
        for low_bit in range(high_bit):
            if (
                stage == 10 - low_bit - 1
                and ((index >> high_bit) & 1)
                and ((index >> low_bit) & 1)
            ):
                exponent += 1 << (9 - high_bit + low_bit)
    return exponent & 0x3FF


def structural_audit() -> dict[str, object]:
    texts = {path.name: path.read_text(encoding="utf-8") for path in SOURCES}
    common = texts["fft_common.sv"]
    data = texts["datapath_v5.sv"]
    primitives = texts["protection_primitives_v5.sv"]
    protected = texts["protected_stages_v5.sv"]
    p0 = texts["top_p0_pfft_unprotected.sv"]
    p1 = texts["top_p1_pfft_ecc.sv"]
    p2 = texts["top_p2_pfft_tmr.sv"]
    trivial = module_text(common, "fft_complex_rotate_trivial_1024")
    lane = module_text(data, "r2sdf_lane_pfft_v5")
    butterfly = module_text(primitives, "independent_butterfly_ecc_v5")
    feedback = module_text(primitives, "independent_rotation_ecc_v5")
    ecc_stage = module_text(protected, "ecc_stage4_v5")
    p0_pipeline = module_text(p0, "pfft_functional_pipeline_v5")
    p1_core = module_text(p1, "pfft_ecc_core_v5")
    p2_core = module_text(p2, "pfft_tmr_core_v5")

    stage1_exponents = {pfft_phi(1, index) for index in range(1024)}
    homogeneous_groups = all(
        len({pfft_phi(1, (beat << 2) | lane_id) for lane_id in range(4)}) == 1
        for beat in range(256)
    )
    checks = {
        "stage1_phi_set_is_exactly_1_and_minus_j": stage1_exponents == {0, 256},
        "stage1_four_lane_groups_are_homogeneous": homogeneous_groups,
        "trivial_rotator_implements_all_four_exact_cases": all(
            f"10'd{value}" in trivial for value in (0, 256, 512, 768)
        )
        and "fft_complex_mul_q28" not in trivial,
        "p0_and_p2_share_stage1_specialized_functional_lane": "if (STAGE == 1)" in lane
        and "fft_complex_rotate_trivial_1024 u_rotation" in lane
        and "fft_complex_mul_q28 u_rotation" in lane,
        "p1_butterfly_has_trivial_upper_and_lower_bypass": "TRIVIAL_UPPER" in butterfly
        and "BYPASS_LOWER" in butterfly
        and "fft_complex_rotate_trivial_1024 upper_rotation" in butterfly
        and "assign lower_clean_r[g]=lower_pre_r[g]" in butterfly,
        "p1_feedback_has_stage1_trivial_rotation": "TRIVIAL_ROTATION" in feedback
        and "fft_complex_rotate_trivial_1024 u" in feedback,
        "p1_stage_parameters_enable_only_frozen_specializations": ".TRIVIAL_UPPER((PFFT_MODE!=0)&&(STAGE==1))" in ecc_stage
        and ".BYPASS_LOWER(PFFT_MODE!=0)" in ecc_stage
        and ".TRIVIAL_ROTATION((PFFT_MODE!=0)&&(STAGE==1))" in ecc_stage,
        "p0_is_complete_unprotected_baseline": p0_pipeline.count("pfft_stage4_sdf_v5") == 8
        and "pfft_stage9" in p0_pipeline
        and "pfft_stage10" in p0_pipeline
        and not any(token in p0_pipeline for token in ("tmr_", "ecc_", "independent_", "p1_")),
        "p1_protection_partition_is_unchanged": p1_core.count("ecc_stage4_v5") == 7
        and "p1_ecc_stage8_v5" in p1_core
        and "p1_stage8_pair_protector_v5" in p1_core
        and "tmr_pfft_stage9_v5" in p1_core
        and "tmr_pfft_stage10_v5" in p1_core,
        "p2_tmr_partition_is_unchanged": p2_core.count("tmr_pfft_stage4_v5") == 8
        and "tmr_pfft_stage9_v5" in p2_core
        and "tmr_pfft_stage10_v5" in p2_core,
    }
    return {
        "status": "VERIFIED" if all(checks.values()) else "FAILED",
        "stage1_exponents": sorted(stage1_exponents),
        "checks": [{"name": name, "pass": passed} for name, passed in checks.items()],
        "passed": sum(checks.values()),
        "total": len(checks),
    }


def run_logged(command: list[str], log_path: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=WORKSPACE,
        text=True,
        encoding=locale.getpreferredencoding(False),
        errors="backslashreplace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(result.stdout, encoding="utf-8", newline="\n")
    print(f"EXIT {result.returncode} LOG {log_path}", flush=True)
    if result.returncode != 0 and result.stdout:
        print(result.stdout[-4000:], flush=True)
    return result


def main() -> int:
    final_path = RESULTS / "rtl_qualification.json"
    manifest_path = RESULTS / "rtl_structure_manifest.json"
    if final_path.exists() or manifest_path.exists() or BUILD.exists():
        raise RuntimeError("PFFT qualification artifacts already exist; refusing an implicit rerun")
    required = (
        IVERILOG,
        VVP,
        *SOURCES,
        *VECTORS,
        *CONTRACTS,
        SNAPSHOT,
        *(tb for _, _, tb, _ in TOPS),
    )
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("missing frozen input: " + ", ".join(missing))

    RESULTS.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True)
    structure = structural_audit()
    manifest = {
        "schema": "pfft-resource-v2-001-rtl-manifest-v1",
        "status": structure["status"],
        "target": "1024-point four-lane ten-stage radix-2 PFFT",
        "sources": [
            {"path": str(path.relative_to(WORKSPACE)), "sha256": sha256(path)}
            for path in SOURCES
        ],
        "testbenches": [
            {"architecture_id": arch, "path": str(tb.relative_to(WORKSPACE)), "sha256": sha256(tb)}
            for arch, _, tb, _ in TOPS
        ],
        "vectors": [
            {"path": str(path.relative_to(WORKSPACE)), "sha256": sha256(path)}
            for path in VECTORS
        ],
        "contracts": [
            {"path": str(path.relative_to(WORKSPACE)), "sha256": sha256(path)}
            for path in CONTRACTS
        ],
        "snapshot": {"path": str(SNAPSHOT.relative_to(WORKSPACE)), "sha256": sha256(SNAPSHOT)},
        "structural_audit": structure,
    }
    write_json(manifest_path, manifest)
    if structure["status"] != "VERIFIED":
        print(f"STRUCTURE FAILED {manifest_path}", flush=True)
        return 1

    bit_exact: dict[str, object] = {}
    failure: dict[str, object] | None = None
    for arch, top, tb, tb_module in TOPS:
        image = BUILD / f"{arch.lower()}_bit_exact.vvp"
        compile_log = LOGS / f"rtl_{arch.lower()}_compile.log"
        simulation_log = LOGS / f"rtl_{arch.lower()}_simulation.log"
        compile_command = [
            str(IVERILOG),
            "-g2012",
            "-s",
            tb_module,
            "-o",
            str(image),
            *map(str, SOURCES),
            str(tb),
        ]
        print(f"COMPILE START {arch}", flush=True)
        compiled = run_logged(compile_command, compile_log, 120)
        if compiled.returncode != 0:
            failure = {"phase": "compile", "architecture_id": arch, "returncode": compiled.returncode}
            bit_exact[arch] = {"status": "FAILED", "compile_log": str(compile_log)}
            break

        simulation_command = [str(VVP), str(image)]
        print(f"SIMULATION START {arch}", flush=True)
        simulated = run_logged(simulation_command, simulation_log, 300)
        marker = f"PASS architecture={arch} beats=2048 latency=525"
        passed = simulated.returncode == 0 and marker in simulated.stdout
        bit_exact[arch] = {
            "status": "VERIFIED" if passed else "FAILED",
            "top": top,
            "beats": 2048,
            "latency": 525,
            "compile_command": compile_command,
            "compile_log": str(compile_log),
            "compile_log_sha256": sha256(compile_log),
            "simulation_command": simulation_command,
            "simulation_log": str(simulation_log),
            "simulation_log_sha256": sha256(simulation_log),
            "required_marker": marker,
        }
        if not passed:
            failure = {
                "phase": "simulation",
                "architecture_id": arch,
                "returncode": simulated.returncode,
                "required_marker": marker,
            }
            break

    status = "VERIFIED" if failure is None and len(bit_exact) == 3 else "FAILED"
    summary = {
        "schema": "pfft-resource-v2-001-rtl-qualification-v1",
        "status": status,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "tool": {
            "python": sys.executable,
            "python_sha256": sha256(Path(sys.executable)),
            "iverilog": str(IVERILOG),
            "iverilog_sha256": sha256(IVERILOG),
            "vvp": str(VVP),
            "vvp_sha256": sha256(VVP),
        },
        "policy": {
            "single_pass_no_retry": True,
            "bit_exact_before_yosys": True,
            "resource_only_no_new_fault_campaign": True,
        },
        "manifest": str(manifest_path),
        "manifest_sha256": sha256(manifest_path),
        "bit_exact": bit_exact,
        "failure": failure,
    }
    write_json(final_path, summary)
    print(f"QUALIFICATION {status} {final_path} SHA256={sha256(final_path)}", flush=True)
    return 0 if status == "VERIFIED" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.TimeoutExpired as exc:
        print(f"TIMEOUT command={exc.cmd} seconds={exc.timeout}", file=sys.stderr, flush=True)
        raise SystemExit(1)
