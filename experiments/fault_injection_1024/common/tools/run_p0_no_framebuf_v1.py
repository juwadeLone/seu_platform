#!/usr/bin/env python3
"""Isolated qualification and Yosys run for P0-NO-FRAMEBUF-V1-001."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
WORKSPACE = HERE.parents[3]
RTL = EXPERIMENT / "common" / "rtl"
PROJECT = EXPERIMENT / "projects" / "P0"
RECORD = "P0-NO-FRAMEBUF-V1-001"
TOP = "top_p0_pfft_no_framebuf_v1"
TB_TOP = "tb_p0_no_framebuf_v1"
YOSYS = Path(r"C:\Users\pc\Downloads\oss-cad-suite\bin\yosys.exe")
OSS_ROOT = YOSYS.parents[1]
IVERILOG = Path(r"C:\iverilog\bin\iverilog.exe")
VVP = Path(r"C:\iverilog\bin\vvp.exe")

RESULTS = EXPERIMENT / "results" / "p0_no_framebuf_v1_001" / "attempt1"
LOGS = EXPERIMENT / "logs" / "p0_no_framebuf_v1_001" / "attempt1"
BUILD = EXPERIMENT / "build" / "p0_no_framebuf_v1_001" / "attempt1"

COMMON = (
    RTL / "twiddle_rom_1024.sv",
    RTL / "fft_common.sv",
    RTL / "protection_rtl.sv",
    RTL / "datapath_v5.sv",
    RTL / "protection_primitives_v5.sv",
    RTL / "protected_stages_v5.sv",
)
BASELINE_TOP = PROJECT / "top_p0_pfft_unprotected.sv"
ISOLATED_TOP = PROJECT / "top_p0_pfft_no_framebuf_v1.sv"
TB = PROJECT / "tb_p0_no_framebuf_v1.sv"
CONTRACT = EXPERIMENT / "P0_NO_FRAME_BUFFER_V1_001.md"
INPUT_VECTOR = EXPERIMENT / "common" / "vectors" / "qualification_input_10frames.hex"
EXPECTED_VECTOR = (
    PROJECT / "vectors" / "qualification_p0_no_exchange_expected_8frames.hex"
)
SOURCES = COMMON + (BASELINE_TOP, ISOLATED_TOP)
INPUTS = SOURCES + (TB, CONTRACT, INPUT_VECTOR, EXPECTED_VECTOR)

HISTORICAL = {
    "LC_estimate": 22689,
    "LUT1_to_LUT6": 31010,
    "FF": 4166,
    "DSP48E1": 464,
    "RAMB18E1": 16,
    "RAMB36E1": 0,
    "BRAM36_equivalent": 8.0,
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def record(path: Path) -> dict[str, object]:
    return {"path": rel(path), "sha256": sha256(path), "size_bytes": path.stat().st_size}


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def require_inputs() -> None:
    missing = [rel(path) for path in INPUTS if not path.is_file()]
    if missing:
        raise RuntimeError("missing input: " + ", ".join(missing))
    if not IVERILOG.is_file() or not VVP.is_file():
        raise RuntimeError("Icarus executable missing")
    text = ISOLATED_TOP.read_text(encoding="utf-8")
    if "pfft_frame_pair_buffer_v5" in re.sub(r"//.*", "", text):
        raise RuntimeError("isolated top still reaches pfft_frame_pair_buffer_v5")
    if text.count("p0_pfft_no_exchange_pipeline_v3") != 1:
        raise RuntimeError("isolated top must instantiate exactly one frozen P0 pipeline")


def controlled_environment(temp: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["YOSYSHQ_ROOT"] = str(OSS_ROOT) + "\\"
    env["OSS_ROOT"] = str(OSS_ROOT)
    env["PATH"] = (
        str(OSS_ROOT / "bin")
        + os.pathsep
        + str(OSS_ROOT / "lib")
        + os.pathsep
        + env.get("PATH", "")
    )
    env["PYTHON_EXECUTABLE"] = str(OSS_ROOT / "lib" / "python3.exe")
    env["TMP"] = str(temp)
    env["TEMP"] = str(temp)
    env["TMPDIR"] = str(temp)
    return env


def run_logged(command: list[str], cwd: Path, log: Path, env: dict[str, str] | None = None) -> int:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(result.stdout, encoding="utf-8", newline="\n")
    write_json(
        log.with_suffix(".command.json"),
        {"command": command, "cwd": str(cwd), "exit_code": result.returncode},
    )
    return result.returncode


def qualify() -> int:
    require_inputs()
    result_path = RESULTS / "qualification.json"
    if RESULTS.exists() or LOGS.exists() or BUILD.exists():
        raise RuntimeError("attempt1 artifact directory already exists; refusing overwrite")
    RESULTS.mkdir(parents=True)
    LOGS.mkdir(parents=True)
    BUILD.mkdir(parents=True)
    manifest = {
        "schema": "p0-no-framebuf-v1-001-input-manifest-v1",
        "status": "FROZEN_FOR_ATTEMPT1",
        "timestamp_utc": now(),
        "record_id": RECORD,
        "inputs": [record(path) for path in INPUTS],
    }
    write_json(RESULTS / "input_manifest.json", manifest)

    vvp_image = BUILD / "qualification.vvp"
    compile_log = LOGS / "iverilog_compile.log"
    compile_command = [
        str(IVERILOG), "-g2012", "-s", TB_TOP, "-o", str(vvp_image),
        *(str(path) for path in SOURCES), str(TB),
    ]
    compile_code = run_logged(compile_command, WORKSPACE, compile_log)
    if compile_code != 0:
        write_json(result_path, {
            "status": "FAILED_COMPILE", "record_id": RECORD,
            "compile_exit_code": compile_code, "synthesis_authorized": False,
        })
        return 2

    sim_log = LOGS / "rtl_qualification.log"
    sim_code = run_logged([str(VVP), str(vvp_image)], WORKSPACE, sim_log)
    text = sim_log.read_text(encoding="utf-8")
    marker = re.search(
        r"PASS_NO_FRAMEBUF beats=(\d+) frames=(\d+) measured_latency=(-?\d+) "
        r"gaps=0 last_errors=0 data_errors=0",
        text,
    )
    passed = sim_code == 0 and marker is not None
    payload = {
        "schema": "p0-no-framebuf-v1-001-qualification-v1",
        "status": "VERIFIED" if passed else "FAILED_SIMULATION",
        "timestamp_utc": now(),
        "record_id": RECORD,
        "fixed_latency_is_acceptance_criterion": False,
        "measured_latency": int(marker.group(3)) if marker else None,
        "checks": {
            "eight_frames_2048_beats_bit_exact": bool(marker and marker.group(1) == "2048"),
            "out_valid_continuous": bool(marker),
            "each_frame_256_beats": bool(marker and marker.group(2) == "8"),
            "out_last_at_each_frame_end": bool(marker),
            "continuous_frame_boundaries": bool(marker),
        },
        "compile_exit_code": compile_code,
        "simulation_exit_code": sim_code,
        "input_manifest": record(RESULTS / "input_manifest.json"),
        "compile_log": record(compile_log),
        "simulation_log": record(sim_log),
        "synthesis_authorized": passed,
    }
    write_json(result_path, payload)
    return 0 if passed else 2


def top_cell_counts(netlist: Path) -> Counter[str]:
    data = json.loads(netlist.read_text(encoding="utf-8"))
    modules = data.get("modules", {})
    if TOP not in modules:
        raise RuntimeError(f"post-synthesis top missing: {TOP}")
    counts: Counter[str] = Counter()
    active: set[str] = set()

    def descend(module_name: str, multiplier: int = 1) -> None:
        if module_name in active:
            raise RuntimeError(f"recursive module hierarchy at {module_name}")
        active.add(module_name)
        for cell in modules[module_name].get("cells", {}).values():
            cell_type = cell["type"]
            is_xilinx_leaf = (
                cell_type.startswith("LUT")
                or cell_type.startswith("FD")
                or cell_type.startswith("RAM")
                or cell_type in {
                    "DSP48E1", "BUFG", "IBUF", "OBUF", "CARRY4",
                    "MUXF7", "MUXF8", "INV",
                }
            )
            if is_xilinx_leaf:
                counts[cell_type] += multiplier
                continue
            child = modules.get(cell_type)
            attributes = child.get("attributes", {}) if child else {}
            is_blackbox = str(attributes.get("blackbox", "0")) == "1"
            if child is not None and not is_blackbox and child.get("cells"):
                descend(cell_type, multiplier)
            else:
                counts[cell_type] += multiplier
        active.remove(module_name)

    descend(TOP)
    return counts


def synthesize() -> int:
    qualification = RESULTS / "qualification.json"
    if not qualification.is_file():
        raise RuntimeError("qualification evidence missing; Yosys blocked")
    qualified = json.loads(qualification.read_text(encoding="utf-8"))
    if (
        qualified.get("status") != "VERIFIED"
        or qualified.get("synthesis_authorized") is False
    ):
        raise RuntimeError("qualification is not VERIFIED; Yosys blocked")
    resource_path = RESULTS / "resource_result.json"
    if resource_path.exists() or (BUILD / "yosys").exists():
        raise RuntimeError("Yosys attempt1 artifacts exist; refusing overwrite")
    if not YOSYS.is_file():
        raise RuntimeError(f"Yosys missing: {YOSYS}")

    stage = BUILD / "yosys"
    temp = BUILD / "ascii_tmp_P0NFBA1"
    stage.mkdir(parents=True)
    temp.mkdir()
    if not str(temp).isascii():
        raise RuntimeError("temporary path is not ASCII")
    env = controlled_environment(temp)
    write_json(RESULTS / "startup_environment.json", {
        "schema": "p0-no-framebuf-v1-001-startup-environment-v1",
        "timestamp_utc": now(), "record_id": RECORD,
        "yosys": record(YOSYS), "cwd": str(stage),
        "environment": dict(sorted(env.items())),
    })

    version_log = LOGS / "yosys_version.log"
    version_code = run_logged([str(YOSYS), "-V"], stage, version_log, env)
    write_json(RESULTS / "yosys_version_gate.json", {
        "status": "VERIFIED" if version_code == 0 else "FAILED",
        "exit_code": version_code, "log": record(version_log),
    })
    if version_code != 0:
        return 2

    source_commands = "\n".join(
        f'read_verilog -sv "{path.as_posix()}"' for path in SOURCES
    )
    hierarchy_json = stage / "preflight_hierarchy.json"
    preflight_script = stage / "preflight.ys"
    preflight_script.write_text(
        source_commands + "\n"
        f"hierarchy -check -top {TOP}\n"
        "check\nproc\nopt_clean\n"
        f'write_json "{hierarchy_json.as_posix()}"\n',
        encoding="ascii", newline="\n",
    )
    preflight_log = LOGS / "yosys_preflight.log"
    preflight_code = run_logged(
        [str(YOSYS), "-s", str(preflight_script)], stage, preflight_log, env
    )
    write_json(RESULTS / "preflight.json", {
        "status": "VERIFIED" if preflight_code == 0 else "FAILED",
        "exit_code": preflight_code, "script": record(preflight_script),
        "log": record(preflight_log),
    })
    if preflight_code != 0:
        return 2

    netlist = stage / "post_synthesis_netlist.json"
    synth_script = stage / "synthesis.ys"
    synth_script.write_text(
        source_commands + "\n"
        f"hierarchy -check -top {TOP}\n"
        f"synth_xilinx -family xc7 -top {TOP}\n"
        "stat\n"
        f'write_json "{netlist.as_posix()}"\n',
        encoding="ascii", newline="\n",
    )
    synth_log = LOGS / "yosys_synthesis.log"
    synth_code = run_logged(
        [str(YOSYS), "-s", str(synth_script)], stage, synth_log, env
    )
    if synth_code != 0 or not netlist.is_file():
        write_json(resource_path, {
            "status": "FAILED_SYNTHESIS", "exit_code": synth_code,
            "script": record(synth_script), "log": record(synth_log),
        })
        return 2

    counts = top_cell_counts(netlist)
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
            count for name, count in counts.items() if name.startswith("RAM") and name not in {"RAMB18E1", "RAMB36E1"}
        ),
    }
    deltas = {
        name: resources[name] - value
        for name, value in HISTORICAL.items()
    }
    write_json(resource_path, {
        "schema": "p0-no-framebuf-v1-001-resource-result-v1",
        "status": "VERIFIED",
        "timestamp_utc": now(),
        "record_id": RECORD,
        "scope": "Yosys synth_xilinx -family xc7 estimate; not Vivado implementation",
        "qualification": record(qualification),
        "yosys_version": version_log.read_text(encoding="utf-8").strip(),
        "resources": resources,
        "historical_p0": HISTORICAL,
        "delta_vs_historical_p0": deltas,
        "cell_counts": dict(sorted(counts.items())),
        "script": record(synth_script),
        "log": record(synth_log),
        "netlist": record(netlist),
    })
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("qualify", "synthesize"))
    args = parser.parse_args()
    try:
        return qualify() if args.phase == "qualify" else synthesize()
    except Exception as exc:
        print(f"STOP {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
