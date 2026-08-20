#!/usr/bin/env python3
"""Schema-v5 seven-top RTL qualification.

One invocation performs exactly one pass over the frozen seven bit-exact tops
and five top-connected protection cases.  There is no retry/resume path.
"""

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
RESULTS = EXPERIMENT / "results" / "seven_arch_v2"
LOGS = EXPERIMENT / "logs" / "seven_arch_v2"
BUILD = EXPERIMENT / "build" / "rtl_seven_projects_v2"
IVERILOG = Path(r"C:\iverilog\bin\iverilog.exe")
VVP = Path(r"C:\iverilog\bin\vvp.exe")

SOURCES = (
    SHARED_RTL / "twiddle_rom_1024.sv",
    SHARED_RTL / "fft_common.sv",
    SHARED_RTL / "protection_rtl.sv",
    SHARED_RTL / "datapath_v5.sv",
    SHARED_RTL / "protection_primitives_v5.sv",
    SHARED_RTL / "protected_stages_v5.sv",
    EXPERIMENT / "projects" / "S0" / "top_s0_subfft_unprotected.sv",
    EXPERIMENT / "projects" / "S1" / "top_s1_gao_subfft_ecc.sv",
    EXPERIMENT / "projects" / "S2" / "top_s2_subfft_tmr.sv",
    EXPERIMENT / "projects" / "S3" / "top_s3_subfft_ecc.sv",
    EXPERIMENT / "projects" / "P0" / "top_p0_pfft_unprotected.sv",
    EXPERIMENT / "projects" / "P1" / "top_p1_pfft_ecc.sv",
    EXPERIMENT / "projects" / "P2" / "top_p2_pfft_tmr.sv",
)

TOPS = (
    (0, "S0", "top_s0_subfft_unprotected", "SubFFT", 268),
    (1, "S1", "top_s1_gao_subfft_ecc", "SubFFT", 268),
    (2, "S2", "top_s2_subfft_tmr", "SubFFT", 268),
    (3, "S3", "top_s3_subfft_ecc", "SubFFT", 268),
    (4, "P0", "top_p0_pfft_unprotected", "PFFT", 525),
    (5, "P1", "top_p1_pfft_ecc", "PFFT", 525),
    (6, "P2", "top_p2_pfft_tmr", "PFFT", 525),
)

PROJECT_TESTBENCHES = {
    "S0": (EXPERIMENT / "projects" / "S0" / "tb_s0.sv", "tb_s0"),
    "S1": (EXPERIMENT / "projects" / "S1" / "tb_s1.sv", "tb_s1"),
    "S2": (EXPERIMENT / "projects" / "S2" / "tb_s2.sv", "tb_s2"),
    "S3": (EXPERIMENT / "projects" / "S3" / "tb_s3.sv", "tb_s3"),
    "P0": (EXPERIMENT / "projects" / "P0" / "tb_p0.sv", "tb_p0"),
    "P1": (EXPERIMENT / "projects" / "P1" / "tb_p1.sv", "tb_p1"),
    "P2": (EXPERIMENT / "projects" / "P2" / "tb_p2.sv", "tb_p2"),
}

CONNECTIVITY = (
    (0, "S1", 768, 1, ("gao_stage8_received_path",)),
    (1, "S2", 768, 1, ("stage1_full_replica_before_voter",)),
    (2, "S3", 768, 3, ("stage1_secded_read", "stage1_arithmetic_received", "stage9_full_replica_before_voter")),
    (3, "P1", 1024, 6, (
        "stage1_secded_read", "stage1_direct_arithmetic_received", "stage8_same_frame_arithmetic_received",
        "stage8_pending_bram_codeword", "stage8_cross_frame_arithmetic_received", "stage9_full_replica_before_voter",
    )),
    (4, "P2", 1024, 1, ("stage1_full_replica_before_voter",)),
)

VECTORS = (
    SHARED_VECTORS / "qualification_input_10frames.hex",
    SHARED_VECTORS / "qualification_subfft_expected_8frames.hex",
    SHARED_VECTORS / "qualification_pfft_expected_8frames.hex",
)
CONTRACTS = (
    EXPERIMENT / "config" / "seven_architecture_contract.json",
    EXPERIMENT / "config" / "seven_architecture_fault_matrix.json",
    EXPERIMENT / "config" / "seven_architecture_memory_map.json",
    EXPERIMENT / "config" / "yosys_resource_contract_v2.json",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def module_text(text: str, name: str) -> str:
    match = re.search(rf"\bmodule\s+{re.escape(name)}\b.*?\bendmodule\b", text, flags=re.S)
    if not match:
        raise RuntimeError(f"module not found: {name}")
    return match.group(0)


def structural_audit() -> dict[str, object]:
    texts = {path.name: path.read_text(encoding="utf-8") for path in SOURCES}
    tops = "\n".join(texts[path.name] for path in SOURCES)
    data = texts["datapath_v5.sv"]
    protected = texts["protected_stages_v5.sv"]
    p1 = texts["top_p1_pfft_ecc.sv"]
    primitives = texts["protection_primitives_v5.sv"]
    sub_lane = module_text(tops, "subfft_lane8_v5")
    sub_tmr = module_text(tops, "subfft_tmr_core_v5")
    sub_ecc = module_text(tops, "subfft_ecc_core_v5")
    p_tmr = module_text(tops, "pfft_tmr_core_v5")
    p_ecc = module_text(tops, "pfft_ecc_core_v5")
    s1 = module_text(tops, "top_s1_gao_subfft_ecc")
    checks = {
        "seven_named_synthesis_tops": all(f"module {top}" in tops for _, _, top, _, _ in TOPS),
        "subfft_child_has_eight_explicit_r2sdf_stages": sub_lane.count("r2sdf_lane_subfft_v5") == 8
        and all(f".DEPTH({depth})" in sub_lane for depth in (128, 64, 32, 16, 8, 4, 2, 1)),
        "s1_has_seven_complete_child_paths": "x<7" in s1 and "subfft_lane8_v5" in s1
        and '(* keep = "true" *) subfft_lane8_v5' in s1
        and "gao_boundary_from_clean_v5" in s1 and "tmr_subfft_stage9_v5" in s1 and "tmr_subfft_stage10_v5" in s1,
        "s2_tmr_all_ten_stages": sub_tmr.count("tmr_subfft_stage4_v5") == 8
        and "tmr_subfft_stage9_v5" in sub_tmr and "tmr_subfft_stage10_v5" in sub_tmr,
        "s3_ecc_eight_then_tmr_two": sub_ecc.count("ecc_stage4_v5") == 8
        and "tmr_subfft_stage9_v5" in sub_ecc and "tmr_subfft_stage10_v5" in sub_ecc,
        "p2_tmr_all_ten_stages": p_tmr.count("tmr_pfft_stage4_v5") == 8
        and "tmr_pfft_stage9_v5" in p_tmr and "tmr_pfft_stage10_v5" in p_tmr,
        "p1_ecc_1_7_dedicated_stage8_then_tmr": p_ecc.count("ecc_stage4_v5") == 7
        and "p1_ecc_stage8_v5" in p_ecc and "p1_stage8_pair_protector_v5" in p_ecc
        and "tmr_pfft_stage9_v5" in p_ecc and "tmr_pfft_stage10_v5" in p_ecc,
        "tmr_wrapper_triplicates_complete_stage": "for(g=0;g<3" in protected
        and "subfft_stage4_sdf_v5" in module_text(protected, "tmr_subfft_stage4_v5")
        and "pfft_stage4_sdf_v5" in module_text(protected, "tmr_pfft_stage4_v5")
        and all('(* keep = "true" *)' in module_text(protected, name) for name in (
            "tmr_subfft_stage4_v5", "tmr_pfft_stage4_v5", "tmr_subfft_stage9_v5",
            "tmr_subfft_stage10_v5", "tmr_pfft_stage9_v5", "tmr_pfft_stage10_v5",
        )),
        "ecc_feedback_is_78_bit_secded": "fft_memory_v5 #(.WIDTH(78)" in module_text(protected, "ecc_stage4_v5")
        and module_text(protected, "ecc_stage4_v5").count("secded_decode70") == 4,
        "independent_check_streams_encode_before_operator": "independent_check_operator_pair_v5" in primitives
        and "adds exactly" in primitives and "functional results" in primitives,
        "p1_stage8_has_same_and_cross_boundaries": all(marker in p1 for marker in (
            "same0_boundary", "same_pair_boundary", "cross_normal_boundary", "cross_a_boundary", "cross_b_boundary"
        )),
        "p1_pending_functional_capacity_two_by_256x78": p1.count("p1_pending_bram_v5 pending_functional") == 2
        and "reg[77:0]memory[0:255]" in p1,
        "p1_check_metadata_is_operand_not_post_result": p1.count("p1_pending_bram_v5 pending_operand_") == 4
        and "independent_check_operator_pair_v5 cross_normal_check" in p1,
        "pfft_common_buffer_exact_shared_template": p1.count("pfft_frame_buffer_lane_v5 common") == 4
        and data.count("pfft_frame_buffer_lane_v5 lane") == 4 and "p1_common_lane_v5" not in p1,
        "depth128_block_sync_smaller_distributed_async": 'if (DEPTH == 128)' in data
        and 'ram_style = "block"' in data and 'ram_style = "distributed"' in data,
        "explicit_clean_received_boundaries": "received_path_r" in s1
        and "upper_received_r" in primitives and "samep_r0r" in p1 and "crossn_r0r" in p1,
        "baselines_are_independent_complete_tops": "subfft_functional_core_v5 u" in module_text(tops, "top_s0_subfft_unprotected")
        and "pfft_functional_core_v5 u" in module_text(tops, "top_p0_pfft_unprotected"),
        "no_proxy_in_source_set": all("rtl_proxy" not in str(path) for path in SOURCES),
    }
    return {
        "status": "VERIFIED" if all(checks.values()) else "FAILED",
        "checks": [{"name": key, "pass": value} for key, value in checks.items()],
        "passed": sum(checks.values()),
        "total": len(checks),
    }


def run_logged(command: list[str], log_path: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    print("RUN", " ".join(command), flush=True)
    result = subprocess.run(
        command, cwd=WORKSPACE, text=True, encoding=locale.getpreferredencoding(False), errors="backslashreplace",
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False,
    )
    log_path.write_text(result.stdout, encoding="utf-8")
    if result.stdout:
        print(result.stdout.rstrip(), flush=True)
    print(f"EXIT {result.returncode} LOG {log_path}", flush=True)
    return result


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    required = (
        IVERILOG, VVP, *SOURCES, *VECTORS, *CONTRACTS,
        *(path for path, _ in PROJECT_TESTBENCHES.values()),
    )
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("missing frozen inputs: " + ", ".join(missing))

    structure = structural_audit()
    manifest = {
        "schema": "rtl-seven-architecture-manifest-v1",
        "status": structure["status"],
        "target": "1024-point four-lane ten-stage radix-2 FFT",
        "sources": [{"path": str(path.relative_to(WORKSPACE)), "sha256": sha256(path)} for path in SOURCES],
        "vectors": [{"path": str(path.relative_to(WORKSPACE)), "sha256": sha256(path)} for path in VECTORS],
        "contracts": [{"path": str(path.relative_to(WORKSPACE)), "sha256": sha256(path)} for path in CONTRACTS],
        "tops": {
            "S0": {"top": "top_s0_subfft_unprotected", "stages_1_8": "four independent complete eight-stage R2SDF children", "stages_9_10": "single functional stages"},
            "S1": {"top": "top_s1_gao_subfft_ecc", "stages_1_8": "seven complete eight-stage R2SDF paths and Gao 7-4-3 boundary", "stages_9_10": "full-stage TMR"},
            "S2": {"top": "top_s2_subfft_tmr", "stages_1_10": "three complete stage replicas and voter per stage"},
            "S3": {"top": "top_s3_subfft_ecc", "stages_1_8": "four SECDED functional memories plus four functional and two independent check operators", "stages_9_10": "full-stage TMR"},
            "P0": {"top": "top_p0_pfft_unprotected", "stages_1_10": "single functional P-SDF", "common_frame_bram": "four shared-template 512x70 synchronous memories"},
            "P1": {"top": "top_p1_pfft_ecc", "stages_1_7": "SECDED plus direct independent-check arithmetic ECC", "stage_8": "SECDED plus 256 same-frame and 256 adjacent-frame exact-operator groups", "pending_functional_bram": "two 256x78 SECDED banks", "check_operand_metadata_bram": "four 256x78 SECDED banks", "stages_9_10": "full-stage TMR", "common_frame_bram": "four shared-template 512x70 synchronous memories"},
            "P2": {"top": "top_p2_pfft_tmr", "stages_1_10": "three complete stage replicas and voter per stage", "common_frame_bram": "four shared-template 512x70 synchronous memories"},
        },
        "memory_policy": {
            "feedback_depth_128": "fft_memory_v5 block synchronous read",
            "feedback_depth_64_32_16_8_4_2_1": "fft_memory_v5 distributed asynchronous read",
            "pfft_common": "pfft_frame_buffer_lane_v5 block synchronous 1R1W",
            "p1_pending": "p1_pending_bram_v5 block synchronous 1R1W",
        },
        "structural_audit": structure,
    }
    manifest_path = RESULTS / "rtl_structure_manifest.json"
    write_json(manifest_path, manifest)
    if structure["status"] != "VERIFIED":
        print("FAILED structural audit", flush=True)
        return 1

    bit_exact: dict[str, object] = {}
    connectivity: dict[str, object] = {}
    failure: dict[str, object] | None = None
    for top_id, arch, top, group, latency in TOPS:
        image = BUILD / f"official_{arch.lower()}_bit_exact.vvp"
        compile_log = LOGS / f"rtl_{arch.lower()}_bit_exact_compile.log"
        sim_log = LOGS / f"rtl_{arch.lower()}_bit_exact_sim.log"
        tb_top, tb_module = PROJECT_TESTBENCHES[arch]
        compile_cmd = [str(IVERILOG), "-g2012", "-s", tb_module, "-o", str(image), *map(str, SOURCES), str(tb_top)]
        compiled = run_logged(compile_cmd, compile_log, 120)
        if compiled.returncode != 0:
            failure = {"phase": "bit_exact_compile", "architecture": arch, "returncode": compiled.returncode}
            bit_exact[arch] = {"status": "FAILED", "compile_log": str(compile_log), "compile_log_sha256": sha256(compile_log)}
            break
        simulated = run_logged([str(VVP), str(image)], sim_log, 240)
        marker = f"PASS top={top_id} beats=2048 latency={latency}"
        passed = simulated.returncode == 0 and marker in simulated.stdout
        bit_exact[arch] = {
            "status": "VERIFIED" if passed else "FAILED", "top": top, "group": group,
            "beats": 2048, "latency": latency, "compile_command": compile_cmd,
            "compile_log": str(compile_log), "compile_log_sha256": sha256(compile_log),
            "simulation_command": [str(VVP), str(image)], "simulation_log": str(sim_log), "simulation_log_sha256": sha256(sim_log),
        }
        if not passed:
            failure = {"phase": "bit_exact_simulation", "architecture": arch, "returncode": simulated.returncode, "required_marker": marker}
            break

    if failure is None:
        tb_conn = SHARED_RTL / "connectivity_spot_tb_v2.sv"
        for case_id, arch, beats, injection_count, boundaries in CONNECTIVITY:
            image = BUILD / f"official_{arch.lower()}_connectivity.vvp"
            compile_log = LOGS / f"rtl_{arch.lower()}_connectivity_compile.log"
            sim_log = LOGS / f"rtl_{arch.lower()}_connectivity_sim.log"
            compile_cmd = [str(IVERILOG), "-g2012", "-s", "tb_top_connectivity_v5", f"-Ptb_top_connectivity_v5.CASE_ID={case_id}", "-o", str(image), *map(str, SOURCES), str(tb_conn)]
            compiled = run_logged(compile_cmd, compile_log, 120)
            if compiled.returncode != 0:
                failure = {"phase": "connectivity_compile", "architecture": arch, "returncode": compiled.returncode}
                connectivity[arch] = {"status": "FAILED", "compile_log": str(compile_log), "compile_log_sha256": sha256(compile_log)}
                break
            simulated = run_logged([str(VVP), str(image)], sim_log, 300)
            marker = f"PASS connectivity case={case_id} beats={beats} injections={injection_count}"
            passed = simulated.returncode == 0 and marker in simulated.stdout and "WARNING:" not in simulated.stdout
            connectivity[arch] = {
                "status": "VERIFIED" if passed else "FAILED", "case_id": case_id, "beats": beats,
                "injections": injection_count, "boundaries": list(boundaries), "compile_command": compile_cmd,
                "compile_log": str(compile_log), "compile_log_sha256": sha256(compile_log),
                "simulation_command": [str(VVP), str(image)], "simulation_log": str(sim_log), "simulation_log_sha256": sha256(sim_log),
            }
            if not passed:
                failure = {"phase": "connectivity_simulation", "architecture": arch, "returncode": simulated.returncode, "required_marker": marker}
                break

    overall = "VERIFIED" if failure is None and len(bit_exact) == 7 and len(connectivity) == 5 else "FAILED"
    summary = {
        "schema": "rtl-seven-architecture-qualification-v1", "status": overall,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "tool": {"iverilog": str(IVERILOG), "vvp": str(VVP)},
        "policy": {"single_pass_no_retry": True, "bit_exact_before_connectivity": True, "yosys_allowed_only_if_verified": True},
        "manifest": str(manifest_path), "manifest_sha256": sha256(manifest_path),
        "bit_exact": bit_exact, "connectivity": connectivity, "failure": failure,
    }
    summary_path = RESULTS / "rtl_qualification.json"
    write_json(summary_path, summary)
    print(f"QUALIFICATION {overall} {summary_path}", flush=True)
    print(f"SHA256 {sha256(summary_path)}", flush=True)
    return 0 if overall == "VERIFIED" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.TimeoutExpired as exc:
        print(f"TIMEOUT command={exc.cmd} seconds={exc.timeout}", file=sys.stderr, flush=True)
        raise SystemExit(1)
