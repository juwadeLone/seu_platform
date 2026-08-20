#!/usr/bin/env python3
"""Isolated RTL qualification for P1-RTL-V4-001.

This runner performs the frozen V4 source-structure checks, compiles the P1
top with Icarus, and executes the 8-frame bit-exact testbench.  It does not
invoke Yosys, Vivado, or XSim and never writes into PFFT-RES-V3-001.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
WORKSPACE = HERE.parents[3]
RTL = EXPERIMENT / "common" / "rtl"
P1 = EXPERIMENT / "projects" / "P1"
ATTEMPT = "qualification_attempt1"
RESULTS = EXPERIMENT / "results" / "p1_rtl_v4_001" / ATTEMPT
LOGS = EXPERIMENT / "logs" / "p1_rtl_v4_001" / ATTEMPT
BUILD = EXPERIMENT / "build" / "p1_rtl_v4_001" / ATTEMPT
IVERILOG = Path(r"C:\iverilog\bin\iverilog.exe")
VVP = Path(r"C:\iverilog\bin\vvp.exe")

SOURCES = (
    RTL / "twiddle_rom_1024.sv",
    RTL / "fft_common.sv",
    RTL / "protection_rtl.sv",
    RTL / "datapath_v5.sv",
    RTL / "protection_primitives_v5.sv",
    RTL / "protected_stages_v5.sv",
    P1 / "top_p1_pfft_ecc.sv",
    P1 / "tb_p1.sv",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def rel(path: Path) -> str:
    return path.relative_to(WORKSPACE).as_posix()


def record(path: Path) -> dict[str, object]:
    return {"path": rel(path), "sha256": sha256(path), "size_bytes": path.stat().st_size}


def module_text(source: str, name: str) -> str:
    match = re.search(
        rf"\bmodule\s+{re.escape(name)}\b(.*?)\bendmodule\b", source, flags=re.S
    )
    if not match:
        raise RuntimeError(f"module not found: {name}")
    return match.group(0)


def check(label: str, condition: bool, detail: object) -> dict[str, object]:
    return {"name": label, "passed": bool(condition), "detail": detail}


def run(command: list[str], log_path: Path) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=WORKSPACE,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    log_path.write_text(completed.stdout, encoding="utf-8", newline="\n")
    return completed


def main() -> int:
    for path in (RESULTS, LOGS, BUILD):
        if path.exists():
            raise RuntimeError(f"isolated attempt already exists: {path}")
        path.mkdir(parents=True)

    top_text = (P1 / "top_p1_pfft_ecc.sv").read_text(encoding="utf-8")
    primitive_text = (RTL / "protection_primitives_v5.sv").read_text(encoding="utf-8")
    core = module_text(top_text, "p1_pfft_ecc_core_v4")
    stage8 = module_text(top_text, "p1_tmr_pfft_stage8_v4")
    stage9 = module_text(top_text, "p1_tmr_pfft_stage9_v3")
    stage10 = module_text(top_text, "p1_stage10_two_beat_ecc_v4")
    butterfly_ecc = module_text(primitive_text, "independent_butterfly_ecc_v5")

    checks = [
        check("core_uses_stage8_tmr_v4", core.count("p1_tmr_pfft_stage8_v4") == 1, core.count("p1_tmr_pfft_stage8_v4")),
        check("core_uses_stage9_tmr", core.count("p1_tmr_pfft_stage9_v3") == 1, core.count("p1_tmr_pfft_stage9_v3")),
        check("core_uses_stage10_two_beat_ecc", core.count("p1_stage10_two_beat_ecc_v4") == 1, core.count("p1_stage10_two_beat_ecc_v4")),
        check("legacy_stage8_scheduler_unreachable", "p1_stage8_single_check_pair_scheduler_v3" not in core, "absent" if "p1_stage8_single_check_pair_scheduler_v3" not in core else "present"),
        check("legacy_stage10_tmr_unreachable", "p1_tmr_pfft_stage10_v3" not in core, "absent" if "p1_tmr_pfft_stage10_v3" not in core else "present"),
        check("stage8_three_complete_replicas", bool(re.search(r"g8\s*<\s*3", stage8)) and stage8.count("p1_stage8_functional_v3") == 1, {"generate_bound": 3, "generated_module": "p1_stage8_functional_v3"}),
        check("stage8_eight_data_voters", stage8.count("vote35") == 8, stage8.count("vote35")),
        check("stage9_three_complete_replicas", bool(re.search(r"g9\s*<\s*3", stage9)) and stage9.count("p1_pfft_stage9_exchange_v3") == 1, {"generate_bound": 3, "generated_module": "p1_pfft_stage9_exchange_v3"}),
        check("stage9_eight_data_voters", stage9.count("vote35") == 8, stage9.count("vote35")),
        check("stage10_one_643_codeword", stage10.count("independent_butterfly_ecc_v5") == 1, stage10.count("independent_butterfly_ecc_v5")),
        check("stage10_six_complete_operators", bool(re.search(r"g\s*<\s*6", butterfly_ecc)), "generate operators[0:5]"),
        check("stage10_separate_upper_lower_boundaries", butterfly_ecc.count("arithmetic_boundary_from_clean_v5") == 2, butterfly_ecc.count("arithmetic_boundary_from_clean_v5")),
        check("stage10_input_pair_state", all(token in stage10 for token in ("pair_phase", "a0r", "b0r", "a1r", "b1r")), "present"),
        check("stage10_output_alignment_state", all(token in stage10 for token in ("pending_valid", "pending0_re", "pending3_im")), "present"),
        check("tb_expected_latency_v4", "`define PROJECT_EXPECTED_LATENCY 267" in (P1 / "tb_p1.sv").read_text(encoding="utf-8"), 267),
    ]

    if not all(item["passed"] for item in checks):
        status = {
            "record_id": "P1-RTL-V4-001",
            "status": "FAILED_STATIC_STRUCTURE",
            "checks": checks,
            "inputs": [record(path) for path in SOURCES],
        }
        result_path = RESULTS / "qualification.json"
        result_path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
        print("FAIL_P1_RTL_V4_STATIC")
        return 1

    vvp_path = BUILD / "tb_p1.vvp"
    compile_command = [
        str(IVERILOG), "-g2012", "-s", "tb_p1", "-o", str(vvp_path),
        *(str(path) for path in SOURCES),
    ]
    compile_result = run(compile_command, LOGS / "compile.log")
    simulation_result = None
    if compile_result.returncode == 0:
        simulation_result = run([str(VVP), str(vvp_path)], LOGS / "simulation.log")

    simulation_log = (
        (LOGS / "simulation.log").read_text(encoding="utf-8")
        if (LOGS / "simulation.log").exists()
        else ""
    )
    marker = re.search(
        r"PASS_V3 architecture=P1 beats=(\d+) latency=(\d+) gaps=(\d+) last_errors=(\d+) data_errors=(\d+)",
        simulation_log,
    )
    passed = (
        compile_result.returncode == 0
        and simulation_result is not None
        and simulation_result.returncode == 0
        and marker is not None
        and tuple(int(value) for value in marker.groups()) == (2048, 267, 0, 0, 0)
    )

    payload = {
        "record_id": "P1-RTL-V4-001",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "VERIFIED" if passed else "FAILED_RTL_QUALIFICATION",
        "scope": "P1 RTL structure and Icarus bit-exact qualification only; no Yosys/Vivado/XSim",
        "checks": checks,
        "inputs": [record(path) for path in SOURCES],
        "compile": {
            "command": compile_command,
            "exit_code": compile_result.returncode,
            "log": record(LOGS / "compile.log"),
        },
        "simulation": {
            "command": [str(VVP), str(vvp_path)],
            "exit_code": simulation_result.returncode if simulation_result else None,
            "pass_marker": marker.group(0) if marker else None,
            "log": record(LOGS / "simulation.log") if (LOGS / "simulation.log").exists() else None,
        },
    }
    result_path = RESULTS / "qualification.json"
    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(("PASS_P1_RTL_V4 " if passed else "FAIL_P1_RTL_V4 ") + sha256(result_path))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
