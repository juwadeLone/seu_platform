#!/usr/bin/env python3
"""Frozen seven-architecture Yosys xc7 resource flow.

The runner refuses stale/reused formal attempts.  It preserves a complete
command/log/netlist chain, expands the live hierarchy for resource counting,
and treats the frozen BRAM/distributed-RAM policy and replica multiplicity as
hard gates before writing either comparison table.
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
import tempfile
import uuid
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
CONFIG = EXPERIMENT / "config" / "yosys_resource_contract_v2.json"
MEMORY_MAP = EXPERIMENT / "config" / "seven_architecture_memory_map.json"
QUALIFICATION = EXPERIMENT / "results" / "seven_arch_v2" / "rtl_qualification.json"
MANIFEST = EXPERIMENT / "results" / "seven_arch_v2" / "rtl_structure_manifest.json"
RESULTS = EXPERIMENT / "results" / "seven_arch_v2"
LOGS = EXPERIMENT / "logs" / "seven_arch_v2"
BUILD = EXPERIMENT / "build" / "yosys_seven_arch_v2"

YOSYS = Path(r"C:\Users\pc\Downloads\oss-cad-suite\bin\yosys.exe")
YOSYS_RUNTIME = Path(r"C:\Users\pc\DOWNLO~1\OSS-CA~1\bin\yosys.exe")
OSS_ROOT_RUNTIME = Path(r"C:\Users\pc\DOWNLO~1\OSS-CA~1")

ARCH_ORDER = ("S0", "S1", "S2", "S3", "P0", "P1", "P2")
ARCH_NAMES = {
    "S0": "Unprotected SubFFT baseline",
    "S1": "Gao SubFFT ECC",
    "S2": "SubFFT per-stage full TMR",
    "S3": "Proposed SubFFT per-stage ECC",
    "P0": "Unprotected PFFT baseline",
    "P1": "PFFT per-stage ECC",
    "P2": "PFFT per-stage full TMR",
}
EXPECTED_SOURCES = (
    "common/rtl/twiddle_rom_1024.sv",
    "common/rtl/fft_common.sv",
    "common/rtl/protection_rtl.sv",
    "common/rtl/datapath_v5.sv",
    "common/rtl/protection_primitives_v5.sv",
    "common/rtl/protected_stages_v5.sv",
    "projects/S0/top_s0_subfft_unprotected.sv",
    "projects/S1/top_s1_gao_subfft_ecc.sv",
    "projects/S2/top_s2_subfft_tmr.sv",
    "projects/S3/top_s3_subfft_ecc.sv",
    "projects/P0/top_p0_pfft_unprotected.sv",
    "projects/P1/top_p1_pfft_ecc.sv",
    "projects/P2/top_p2_pfft_tmr.sv",
)
MEMORY_TEMPLATES = {
    "fft_memory_v5": None,
    "pfft_frame_buffer_lane_v5": (70, 512),
    "p1_pending_bram_v5": (78, 256),
}
TMR_CHILD = {
    "tmr_subfft_stage4_v5": "subfft_stage4_sdf_v5",
    "tmr_pfft_stage4_v5": "pfft_stage4_sdf_v5",
    "tmr_subfft_stage9_v5": "subfft_stage9",
    "tmr_subfft_stage10_v5": "subfft_stage10",
    "tmr_pfft_stage9_v5": "pfft_stage9",
    "tmr_pfft_stage10_v5": "pfft_stage10",
}
FF_TYPES = ("FDCE", "FDPE", "FDRE", "FDSE")
P1_PENDING_NAMES = (
    "pending_functional0",
    "pending_functional1",
    "pending_operand_a0",
    "pending_operand_a1",
    "pending_operand_b0",
    "pending_operand_b1",
)


class GateFailure(RuntimeError):
    def __init__(self, stage: str, message: str, architecture_id: str | None = None, details: Any = None):
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


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def yosys_environment() -> dict[str, str]:
    env = os.environ.copy()
    env["YOSYSHQ_ROOT"] = str(OSS_ROOT_RUNTIME) + "\\"
    env["PATH"] = str(OSS_ROOT_RUNTIME / "bin") + os.pathsep + str(OSS_ROOT_RUNTIME / "lib") + os.pathsep + env.get("PATH", "")
    env["PYTHON_EXECUTABLE"] = str(OSS_ROOT_RUNTIME / "lib" / "python3.exe")
    return env


def tool_version() -> str:
    result = subprocess.run(
        [str(YOSYS_RUNTIME), "-V"],
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
        raise GateFailure("tool_validation", f"Yosys -V exited {result.returncode}", details=result.stdout)
    return result.stdout.strip()


def source_paths(config: dict[str, Any]) -> list[Path]:
    return [EXPERIMENT / relative for relative in config["source_files"]]


def validate_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    required = (CONFIG, MEMORY_MAP, QUALIFICATION, MANIFEST, YOSYS, YOSYS_RUNTIME)
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise GateFailure("input_validation", "missing frozen inputs", details=missing)

    config = load(CONFIG)
    memory_map = load(MEMORY_MAP)
    qualification = load(QUALIFICATION)
    manifest = load(MANIFEST)
    failures: list[str] = []
    if config.get("status") != "FROZEN":
        failures.append("Yosys contract is not FROZEN")
    if memory_map.get("status") != "FROZEN":
        failures.append("memory map is not FROZEN")
    if qualification.get("status") != "VERIFIED":
        failures.append("RTL qualification is not VERIFIED")
    if manifest.get("status") != "VERIFIED":
        failures.append("RTL structure manifest is not VERIFIED")
    if tuple(config.get("source_files", ())) != EXPECTED_SOURCES:
        failures.append("source_files do not equal the frozen RTL-v5 eight-file set")
    if tuple(config.get("tops", {}).keys()) != ARCH_ORDER:
        failures.append("top ordering is not S0,S1,S2,S3,P0,P1,P2")
    if set(qualification.get("bit_exact", {})) != set(ARCH_ORDER):
        failures.append("RTL qualification does not contain all seven bit-exact tops")
    if qualification.get("manifest_sha256", "").upper() != sha256(MANIFEST):
        failures.append("qualification manifest hash does not match current manifest")
    if config.get("target_evidence", {}).get("synth_xilinx_family") != "xc7":
        failures.append("synth_xilinx family is not xc7")
    missing_sources = [str(path) for path in source_paths(config) if not path.exists()]
    if missing_sources:
        failures.append("missing source files: " + ", ".join(missing_sources))
    referenced_profiles = {
        profile
        for profiles in config.get("architecture_memory_profiles", {}).values()
        for profile in profiles
    }
    if not referenced_profiles.issubset(config.get("memory_profiles", {})):
        failures.append("architecture references an undefined memory profile")

    long_hash = sha256(YOSYS)
    runtime_hash = sha256(YOSYS_RUNTIME)
    if long_hash != runtime_hash:
        failures.append("long-path and runtime-short-path Yosys hashes differ")
    version = tool_version()
    if version != config.get("version"):
        failures.append(f"Yosys version mismatch: {version!r}")
    if failures:
        raise GateFailure("input_validation", "frozen input validation failed", details=failures)

    validation = {
        "schema": "yosys-seven-architecture-input-validation-v1",
        "status": "VERIFIED",
        "timestamp_utc": utc_now(),
        "config": str(CONFIG),
        "config_sha256": sha256(CONFIG),
        "memory_map": str(MEMORY_MAP),
        "memory_map_sha256": sha256(MEMORY_MAP),
        "qualification": str(QUALIFICATION),
        "qualification_sha256": sha256(QUALIFICATION),
        "manifest": str(MANIFEST),
        "manifest_sha256": sha256(MANIFEST),
        "yosys_specified_executable": str(YOSYS),
        "yosys_runtime_alias": str(YOSYS_RUNTIME),
        "yosys_executable_sha256": long_hash,
        "yosys_version": version,
        "sources": [
            {"relative_path": relative, "absolute_path": str(EXPERIMENT / relative), "sha256": sha256(EXPERIMENT / relative)}
            for relative in config["source_files"]
        ],
        "tops": config["tops"],
    }
    return config, validation


def write_script(config: dict[str, Any], architecture_id: str, mode: str, directory: Path) -> Path:
    top = config["tops"][architecture_id]
    path = directory / f"{architecture_id}_{mode}.ys"
    lines = [
        "read_verilog -sv " + " ".join(config["source_files"]),
        f"hierarchy -check -top {top}",
    ]
    if mode == "preflight":
        lines.extend(("proc", "check"))
    elif mode == "synth":
        output = (directory / f"{architecture_id}_netlist.json").relative_to(EXPERIMENT).as_posix()
        lines.extend((
            f"synth_xilinx -family xc7 -top {top}",
            "stat -tech xilinx",
            f"write_json {output}",
        ))
    else:
        raise ValueError(mode)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path


def run_yosys(
    config: dict[str, Any],
    architecture_id: str,
    mode: str,
    script: Path,
    log: Path,
    output_directory: Path,
) -> subprocess.CompletedProcess[str]:
    temporary_root = Path(tempfile.gettempdir()).resolve()
    stage = temporary_root / ("Y7" + uuid.uuid4().hex[:8].upper())
    stage.mkdir()
    command: list[str] = []
    result: subprocess.CompletedProcess[str] | None = None
    try:
        script_text = script.read_text(encoding="utf-8")
        for index, relative in enumerate(config["source_files"]):
            original = EXPERIMENT / relative
            staged = stage / f"s{index}_{original.name}"
            shutil.copy2(original, staged)
            script_text = script_text.replace(relative, staged.name)
        netlist_name = f"{architecture_id}_netlist.json"
        if mode == "synth":
            script_text = re.sub(rf"write_json\s+\S+/{re.escape(netlist_name)}", f"write_json {netlist_name}", script_text)
        staged_script = stage / "flow.ys"
        staged_log = stage / "yosys.log"
        staged_script.write_text(script_text, encoding="utf-8", newline="\n")
        command = [str(YOSYS_RUNTIME), "-l", str(staged_log), str(staged_script)]
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
        if mode == "synth":
            staged_netlist = stage / netlist_name
            if staged_netlist.exists():
                shutil.copy2(staged_netlist, output_directory / netlist_name)
    finally:
        resolved = stage.resolve()
        if resolved.parent == temporary_root and re.fullmatch(r"Y7[0-9A-F]{8}", resolved.name):
            shutil.rmtree(resolved)

    if result is None:
        raise GateFailure("runner", "Yosys subprocess did not start", architecture_id)
    sidecar = log.with_suffix(".command.json")
    write_json(sidecar, {
        "architecture_id": architecture_id,
        "mode": mode,
        "command": command,
        "specified_executable": str(YOSYS),
        "runtime_short_path_alias": str(YOSYS_RUNTIME),
        "specified_and_runtime_sha256": sha256(YOSYS),
        "official_script": str(script),
        "official_script_sha256": sha256(script),
        "execution_mode": "hash_identical_sources_staged_in_unique_ascii_temporary_directory",
        "source_hashes": {relative: sha256(EXPERIMENT / relative) for relative in config["source_files"]},
        "exit_code": result.returncode,
        "console_output_tail": result.stdout[-4000:],
        "log": str(log),
        "log_sha256": sha256(log),
    })
    return result


def is_blackbox(module: dict[str, Any]) -> bool:
    value = str(module.get("attributes", {}).get("blackbox", "0"))
    return value in {"1", "00000000000000000000000000000001"}


def hdlname(module_name: str, module: dict[str, Any]) -> str:
    value = str(module.get("attributes", {}).get("hdlname", module_name))
    return value.lstrip("\\")


def clean_name(value: str) -> str:
    return value.lstrip("\\")


def binary_parameter(value: Any) -> int:
    if isinstance(value, int):
        return value
    text = str(value)
    if re.fullmatch(r"[01]+", text):
        return int(text, 2)
    return int(text, 0)


def is_bram(cell_type: str) -> bool:
    return clean_name(cell_type).startswith("RAMB")


def is_distributed_memory(cell_type: str) -> bool:
    name = clean_name(cell_type)
    return (name.startswith("RAM") and not name.startswith("RAMB")) or name.startswith("SRL")


def expanded_counter(modules: dict[str, Any], root: str) -> Counter[str]:
    cache: dict[str, Counter[str]] = {}
    active: set[str] = set()

    def expand(module_name: str) -> Counter[str]:
        if module_name in cache:
            return cache[module_name].copy()
        if module_name in active:
            raise GateFailure("netlist_audit", f"recursive module hierarchy at {module_name}")
        active.add(module_name)
        counts: Counter[str] = Counter()
        for cell in modules[module_name].get("cells", {}).values():
            cell_type = cell["type"]
            if cell_type in modules and not is_blackbox(modules[cell_type]):
                counts.update(expand(cell_type))
            else:
                counts[clean_name(cell_type)] += 1
        active.remove(module_name)
        cache[module_name] = counts.copy()
        return counts

    return expand(root)


def memory_implementation(template: str, depth: int) -> str:
    if template == "fft_memory_v5":
        return "block" if depth == 128 else "distributed"
    return "block"


def primitive_fingerprint(counts: Counter[str]) -> dict[str, int]:
    return {
        name: count
        for name, count in sorted(counts.items())
        if count and (is_bram(name) or is_distributed_memory(name))
    }


def collect_hierarchy(modules: dict[str, Any], top: str) -> tuple[list[dict[str, Any]], Counter[str], list[dict[str, Any]]]:
    memories: list[dict[str, Any]] = []
    module_instances: Counter[str] = Counter()
    wrappers: list[dict[str, Any]] = []
    expand_cache: dict[str, Counter[str]] = {}

    def expand(module_name: str) -> Counter[str]:
        if module_name not in expand_cache:
            expand_cache[module_name] = expanded_counter(modules, module_name)
        return expand_cache[module_name].copy()

    def walk(module_name: str, path: str) -> None:
        module = modules[module_name]
        for raw_cell_name, cell in module.get("cells", {}).items():
            cell_type = cell["type"]
            cell_path = path + "/" + clean_name(raw_cell_name)
            if cell_type not in modules or is_blackbox(modules[cell_type]):
                continue
            child_module = modules[cell_type]
            base = hdlname(cell_type, child_module)
            module_instances[base] += 1
            if base in MEMORY_TEMPLATES:
                fixed = MEMORY_TEMPLATES[base]
                if fixed is None:
                    parameters = child_module.get("parameter_default_values", {})
                    width = binary_parameter(parameters["WIDTH"])
                    depth = binary_parameter(parameters["DEPTH"])
                else:
                    width, depth = fixed
                counts = expand(cell_type)
                bram = {name: count for name, count in sorted(counts.items()) if count and is_bram(name)}
                distributed = {name: count for name, count in sorted(counts.items()) if count and is_distributed_memory(name)}
                if bram and not distributed:
                    actual = "block"
                elif distributed and not bram:
                    actual = "distributed"
                elif bram and distributed:
                    actual = "mixed"
                else:
                    actual = "registers_or_logic"
                expected = memory_implementation(base, depth)
                memories.append({
                    "path": cell_path,
                    "template": base,
                    "width": width,
                    "depth": depth,
                    "expected_implementation": expected,
                    "actual_implementation": actual,
                    "mapping_pass": actual == expected,
                    "bram_primitives": bram,
                    "distributed_primitives": distributed,
                    "ff_cells_inside_template": sum(counts[name] for name in FF_TYPES),
                    "primitive_fingerprint": primitive_fingerprint(counts),
                })
            if base in TMR_CHILD:
                expected_child = TMR_CHILD[base]
                child_count = 0
                for grandchild in child_module.get("cells", {}).values():
                    grandchild_type = grandchild["type"]
                    if grandchild_type in modules and not is_blackbox(modules[grandchild_type]):
                        if hdlname(grandchild_type, modules[grandchild_type]) == expected_child:
                            child_count += 1
                wrappers.append({
                    "path": cell_path,
                    "wrapper": base,
                    "replica_module": expected_child,
                    "replicas": child_count,
                    "pass": child_count == 3,
                })
            walk(cell_type, cell_path)

    walk(top, top)
    return memories, module_instances, wrappers


def expected_memory_entries(config: dict[str, Any], architecture_id: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for profile_name in config["architecture_memory_profiles"][architecture_id]:
        profile = config["memory_profiles"][profile_name]
        for depth in profile["depths"]:
            entries.append({
                "profile": profile_name,
                "template": profile["template"],
                "width": int(profile["width"]),
                "depth": int(depth),
                "count": int(profile["instances_per_depth"]),
                "implementation": memory_implementation(profile["template"], int(depth)),
                "required_instance_name_counts": profile.get("required_instance_name_counts", {}),
            })
    return entries


def audit_memories(config: dict[str, Any], architecture_id: str, memories: list[dict[str, Any]]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    expected_entries = expected_memory_entries(config, architecture_id)
    expected_keys = {(item["template"], item["width"], item["depth"]) for item in expected_entries}
    observed_keys = {(item["template"], item["width"], item["depth"]) for item in memories}
    for expected in expected_entries:
        matching = [
            item for item in memories
            if (item["template"], item["width"], item["depth"])
            == (expected["template"], expected["width"], expected["depth"])
        ]
        checks.append({
            "check": "instance_count",
            "profile": expected["profile"],
            "geometry": f"{expected['width']}x{expected['depth']}",
            "expected": expected["count"],
            "observed": len(matching),
            "pass": len(matching) == expected["count"],
        })
        mapping_failures = [item["path"] for item in matching if not item["mapping_pass"]]
        checks.append({
            "check": "primitive_class",
            "profile": expected["profile"],
            "geometry": f"{expected['width']}x{expected['depth']}",
            "expected": expected["implementation"],
            "failures": mapping_failures,
            "pass": not mapping_failures and len(matching) == expected["count"],
        })
        for token, required_count in expected.get("required_instance_name_counts", {}).items():
            observed_count = sum(token in item["path"] for item in matching)
            checks.append({
                "check": "instance_name_count",
                "profile": expected["profile"],
                "token": token,
                "expected": required_count,
                "observed": observed_count,
                "pass": observed_count == required_count,
            })
    unexpected = sorted(observed_keys - expected_keys)
    checks.append({"check": "no_unexpected_memory_geometry", "unexpected": unexpected, "pass": not unexpected})
    return {
        "status": "VERIFIED" if all(item["pass"] for item in checks) else "BLOCKED",
        "checks": checks,
        "instances": memories,
    }


def audit_preservation(
    config: dict[str, Any], architecture_id: str, module_instances: Counter[str], wrappers: list[dict[str, Any]]
) -> dict[str, Any]:
    policy = config["synthesis_preservation"]
    checks: list[dict[str, Any]] = []
    expected_wrappers = policy["architecture_tmr_wrapper_expectations"][architecture_id]
    all_wrapper_names = set(TMR_CHILD)
    for name in sorted(all_wrapper_names):
        expected = int(expected_wrappers.get(name, 0))
        observed = module_instances[name]
        checks.append({"check": "tmr_wrapper_count", "module": name, "expected": expected, "observed": observed, "pass": observed == expected})
    checks.append({
        "check": "each_live_tmr_wrapper_contains_three_kept_complete_replicas",
        "failures": [item for item in wrappers if not item["pass"]],
        "pass": all(item["pass"] for item in wrappers),
    })
    for name, expected in policy.get("architecture_protection_module_expectations", {}).get(architecture_id, {}).items():
        observed = module_instances[name]
        checks.append({"check": "protection_module_count", "module": name, "expected": expected, "observed": observed, "pass": observed == expected})
    if architecture_id in {"S0", "P0"}:
        forbidden = {
            name: count
            for name, count in module_instances.items()
            if count and any(name.startswith(prefix) for prefix in policy["baseline_forbidden_module_prefixes"])
        }
        checks.append({"check": "baseline_has_no_protection_modules", "forbidden_instances": forbidden, "pass": not forbidden})
    return {
        "status": "VERIFIED" if all(item["pass"] for item in checks) else "BLOCKED",
        "checks": checks,
        "tmr_wrappers": wrappers,
        "live_module_instance_counts": dict(sorted(module_instances.items())),
    }


def p1_pending_output_paths(netlist: dict[str, Any], top: str) -> dict[str, Any]:
    modules = netlist["modules"]
    adjacency: dict[Any, list[Any]] = defaultdict(list)
    pending_sources: dict[str, set[Any]] = {name: set() for name in P1_PENDING_NAMES}

    def local_node(path: str, bit: Any, port_map: dict[int, Any]) -> Any:
        if isinstance(bit, int):
            return port_map.get(bit, (path, bit))
        return ("const", str(bit))

    def instantiate(module_name: str, path: str, inherited_port_map: dict[int, Any]) -> None:
        module = modules[module_name]
        for raw_cell_name, cell in module.get("cells", {}).items():
            cell_name = clean_name(raw_cell_name)
            cell_path = path + "/" + cell_name
            cell_type = cell["type"]
            if cell_type in modules and not is_blackbox(modules[cell_type]):
                child = modules[cell_type]
                child_map: dict[int, Any] = {}
                for port_name, child_port in child.get("ports", {}).items():
                    parent_bits = cell.get("connections", {}).get(port_name, [])
                    for child_bit, parent_bit in zip(child_port.get("bits", []), parent_bits):
                        if isinstance(child_bit, int):
                            child_map[child_bit] = local_node(path, parent_bit, inherited_port_map)
                instantiate(cell_type, cell_path, child_map)
                continue

            inputs: set[Any] = set()
            outputs: set[Any] = set()
            directions = cell.get("port_directions", {})
            for port_name, bits in cell.get("connections", {}).items():
                nodes = {local_node(path, bit, inherited_port_map) for bit in bits}
                direction = directions.get(port_name)
                if direction in {"input", "inout"}:
                    inputs.update(nodes)
                if direction in {"output", "inout"}:
                    outputs.update(nodes)
            cell_node = ("cell", cell_path)
            for node in inputs:
                adjacency[node].append(cell_node)
            adjacency[cell_node].extend(outputs)
            if is_bram(cell_type):
                for pending_name in P1_PENDING_NAMES:
                    if pending_name in cell_path:
                        pending_sources[pending_name].update(outputs)

    top_module = modules[top]
    top_map: dict[int, Any] = {}
    for port in top_module.get("ports", {}).values():
        for bit in port.get("bits", []):
            if isinstance(bit, int):
                top_map[bit] = (top, bit)
    instantiate(top, top, top_map)
    target_bits = {
        (top, bit)
        for name, port in top_module.get("ports", {}).items()
        if port.get("direction") == "output" and name not in {"out_valid", "out_last"}
        for bit in port.get("bits", [])
        if isinstance(bit, int)
    }

    checks: list[dict[str, Any]] = []
    for pending_name, starts in pending_sources.items():
        queue = deque(starts)
        visited = set(starts)
        reaches = bool(visited & target_bits)
        while queue and not reaches:
            node = queue.popleft()
            for successor in adjacency.get(node, ()):
                if successor not in visited:
                    visited.add(successor)
                    if successor in target_bits:
                        reaches = True
                        break
                    queue.append(successor)
        checks.append({
            "pending_instance": pending_name,
            "mapped_bram_output_bits": len(starts),
            "reaches_top_data_output": reaches,
            "pass": bool(starts) and reaches,
        })
    return {"status": "VERIFIED" if all(item["pass"] for item in checks) else "BLOCKED", "checks": checks}


def warning_audit(log_text: str) -> dict[str, Any]:
    warnings = [line.strip() for line in log_text.splitlines() if re.search(r"\bwarning\b", line, flags=re.I)]
    critical_pattern = re.compile(
        r"blackbox|unresolved|not found|multiple conflicting drivers|has no driver|unsupported|failed to map|cannot map",
        flags=re.I,
    )
    critical = [line for line in warnings if critical_pattern.search(line)]
    return {"warnings": warnings, "critical_warnings": critical, "status": "VERIFIED" if not critical else "BLOCKED"}


def blackbox_audit(modules: dict[str, Any], counts: Counter[str]) -> dict[str, Any]:
    primitive: list[str] = []
    critical: list[str] = []
    for cell_type in sorted(counts):
        if cell_type.startswith("$scopeinfo"):
            continue
        module = modules.get(cell_type)
        if module is None:
            critical.append(cell_type)
            continue
        if is_blackbox(module):
            source = str(module.get("attributes", {}).get("src", "")).replace("\\", "/").lower()
            if "/share/yosys/xilinx/" in source or cell_type.startswith("$__ABC9_"):
                primitive.append(cell_type)
            else:
                critical.append(cell_type)
    return {"primitive_blackboxes": primitive, "critical_blackboxes": critical, "status": "VERIFIED" if not critical else "BLOCKED"}


def parse_synthesis(config: dict[str, Any], architecture_id: str, script: Path, log: Path, netlist_path: Path) -> dict[str, Any]:
    top = config["tops"][architecture_id]
    log_text = log.read_text(encoding="utf-8", errors="replace")
    netlist = load(netlist_path)
    modules = netlist["modules"]
    if top not in modules:
        raise GateFailure("netlist_audit", f"top {top} absent from JSON netlist", architecture_id)
    counts = expanded_counter(modules, top)
    lc_matches = re.findall(r"Estimated number of LCs:\s*(\d+)", log_text)
    warnings = warning_audit(log_text)
    blackboxes = blackbox_audit(modules, counts)
    memories, module_instances, wrappers = collect_hierarchy(modules, top)
    memory_audit = audit_memories(config, architecture_id, memories)
    preservation = audit_preservation(config, architecture_id, module_instances, wrappers)
    p1_paths = p1_pending_output_paths(netlist, top) if architecture_id == "P1" else {"status": "NOT_APPLICABLE", "checks": []}
    missing_metrics = [] if lc_matches else ["Estimated number of LCs"]
    statuses = (warnings["status"], blackboxes["status"], memory_audit["status"], preservation["status"], p1_paths["status"])
    status = "VERIFIED" if not missing_metrics and all(value in {"VERIFIED", "NOT_APPLICABLE"} for value in statuses) else "BLOCKED"
    distributed = {name: count for name, count in sorted(counts.items()) if count and is_distributed_memory(name)}
    row = {
        "architecture_id": architecture_id,
        "architecture": ARCH_NAMES[architecture_id],
        "group": "SubFFT" if architecture_id.startswith("S") else "PFFT",
        "top": top,
        "status": status,
        "lut": int(lc_matches[-1]) if lc_matches else None,
        "raw_lut_cells": sum(counts[f"LUT{size}"] for size in range(1, 7)),
        "ff": sum(counts[name] for name in FF_TYPES),
        "dsp": counts["DSP48E1"],
        "bram18": counts["RAMB18E1"],
        "bram36": counts["RAMB36E1"],
        "bram36_equivalent": counts["RAMB36E1"] + 0.5 * counts["RAMB18E1"],
        "distributed_memory_cells_total": sum(distributed.values()),
        "distributed_memory_cells": distributed,
        "warning_audit": warnings,
        "blackbox_audit": blackboxes,
        "memory_mapping_audit": memory_audit,
        "replica_preservation_audit": preservation,
        "p1_pending_transitive_path_audit": p1_paths,
        "missing_metrics": missing_metrics,
        "cell_counts": dict(sorted(counts.items())),
        "script": str(script),
        "script_sha256": sha256(script),
        "log": str(log),
        "log_sha256": sha256(log),
        "netlist": str(netlist_path),
        "netlist_sha256": sha256(netlist_path),
    }
    return row


def cross_architecture_mapping(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[tuple[str, int, int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        for memory in row["memory_mapping_audit"]["instances"]:
            key = (memory["template"], memory["width"], memory["depth"], memory["expected_implementation"])
            groups[key].append({
                "architecture_id": row["architecture_id"],
                "path": memory["path"],
                "fingerprint": memory["primitive_fingerprint"],
            })
    checks: list[dict[str, Any]] = []
    for key, instances in sorted(groups.items()):
        fingerprints = {json.dumps(item["fingerprint"], sort_keys=True) for item in instances}
        checks.append({
            "template": key[0],
            "width": key[1],
            "depth": key[2],
            "expected_implementation": key[3],
            "architectures": sorted({item["architecture_id"] for item in instances}),
            "fingerprints": [json.loads(item) for item in sorted(fingerprints)],
            "pass": len(fingerprints) == 1,
        })
    return {"status": "VERIFIED" if all(item["pass"] for item in checks) else "BLOCKED", "checks": checks}


def with_baseline_deltas(rows: list[dict[str, Any]], baseline_id: str) -> list[dict[str, Any]]:
    baseline = next(row for row in rows if row["architecture_id"] == baseline_id)
    metrics = ("lut", "ff", "dsp", "bram18", "bram36", "bram36_equivalent")
    output: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["baseline_id"] = baseline_id
        item["baseline_deltas"] = {}
        for metric in metrics:
            value = row[metric]
            base = baseline[metric]
            delta = value - base
            item["baseline_deltas"][metric] = {
                "absolute": delta,
                "relative_percent": (100.0 * delta / base) if base else (0.0 if delta == 0 else None),
            }
        output.append(item)
    return output


def write_group_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    metrics = ("lut", "ff", "dsp", "bram18", "bram36", "bram36_equivalent")
    fields = ["architecture_id", "architecture", "top", "status", "baseline_id"]
    for metric in metrics:
        fields.extend((metric, f"{metric}_delta", f"{metric}_delta_percent"))
    fields.extend(("raw_lut_cells", "distributed_memory_cells_total", "script_sha256", "log_sha256", "netlist_sha256"))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            flat = {field: row.get(field) for field in fields}
            for metric in metrics:
                flat[f"{metric}_delta"] = row["baseline_deltas"][metric]["absolute"]
                flat[f"{metric}_delta_percent"] = row["baseline_deltas"][metric]["relative_percent"]
            writer.writerow(flat)


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Seven-architecture Yosys resource audit",
        "",
        f"Overall status: **{summary['status']}**",
        "",
        f"- Tool: `{summary['yosys_version']}`",
        "- Flow: `synth_xilinx -family xc7` on the same frozen eight-file RTL-v5 source set.",
        "- Boundary: synthesis resource estimates only; not Vivado post-implementation utilization, timing, Fmax, or power.",
        "- Hard gates: live replica multiplicity, critical blackboxes/warnings, per-memory primitive class, cross-architecture mapping consistency, and P1 pending-memory output reachability.",
    ]
    for group_name in ("SubFFT", "PFFT"):
        lines.extend((
            "",
            f"## {group_name} group",
            "",
            "| ID | LUT (est. LC) | FF | DSP48E1 | RAMB18 | RAMB36 | BRAM36 equiv. |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ))
        for row in summary["groups"][group_name]:
            lines.append(
                f"| {row['architecture_id']} | {row['lut']} | {row['ff']} | {row['dsp']} | "
                f"{row['bram18']} | {row['bram36']} | {row['bram36_equivalent']} |"
            )
    lines.append("")
    return "\n".join(lines)


def failure_payload(error: GateFailure, validation: dict[str, Any] | None, rows: list[dict[str, Any]], attempt: str) -> dict[str, Any]:
    return {
        "schema": "yosys-seven-architecture-failure-v1",
        "status": "FAILED" if error.stage in {"preflight", "synthesis"} else "BLOCKED",
        "timestamp_utc": utc_now(),
        "attempt": attempt,
        "stage": error.stage,
        "architecture_id": error.architecture_id,
        "message": str(error),
        "details": error.details,
        "validation": validation,
        "completed_architectures": rows,
        "policy": "no_silent_retry_no_final_tables_on_any_failure",
    }


def run_preflight(config: dict[str, Any], validation: dict[str, Any]) -> int:
    directory = BUILD / "preflight"
    output = RESULTS / "yosys_preflight.json"
    if directory.exists() or output.exists():
        raise GateFailure("preflight", "preflight artifacts already exist; refusing an implicit rerun")
    directory.mkdir(parents=True)
    statuses: dict[str, Any] = {}
    for architecture_id in ARCH_ORDER:
        print(f"PREFLIGHT START {architecture_id}", flush=True)
        script = write_script(config, architecture_id, "preflight", directory)
        log = LOGS / f"yosys_preflight_{architecture_id}.log"
        result = run_yosys(config, architecture_id, "preflight", script, log, directory)
        statuses[architecture_id] = {
            "exit_code": result.returncode,
            "script": str(script),
            "script_sha256": sha256(script),
            "log": str(log),
            "log_sha256": sha256(log),
        }
        print(f"PREFLIGHT END {architecture_id} exit={result.returncode}", flush=True)
        if result.returncode != 0:
            payload = {"schema": "yosys-seven-architecture-preflight-v1", "status": "FAILED", "validation": validation, "tops": statuses}
            write_json(output, payload)
            return 2
    payload = {"schema": "yosys-seven-architecture-preflight-v1", "status": "VERIFIED", "validation": validation, "tops": statuses}
    write_json(output, payload)
    print(f"PREFLIGHT VERIFIED {output} SHA256={sha256(output)}", flush=True)
    return 0


def run_formal(config: dict[str, Any], validation: dict[str, Any], attempt: str) -> int:
    if not re.fullmatch(r"attempt[1-9][0-9]*", attempt):
        raise GateFailure("runner", "attempt label must match attemptN")
    directory = BUILD / attempt
    failure_path = RESULTS / f"yosys_{attempt}_failure.json"
    final_paths = (
        RESULTS / "yosys_seven_arch_summary.json",
        RESULTS / "yosys_subfft_group.csv",
        RESULTS / "yosys_pfft_group.csv",
        RESULTS / "yosys_memory_mapping_audit.json",
        RESULTS / "yosys_resource_audit.md",
    )
    if directory.exists() or failure_path.exists() or any(path.exists() for path in final_paths):
        raise GateFailure("runner", "formal attempt or final artifacts already exist; refusing an implicit rerun")
    directory.mkdir(parents=True)
    rows: list[dict[str, Any]] = []
    try:
        for architecture_id in ARCH_ORDER:
            print(f"SYNTHESIS START {architecture_id}", flush=True)
            script = write_script(config, architecture_id, "synth", directory)
            log = LOGS / f"yosys_{attempt}_{architecture_id}.log"
            result = run_yosys(config, architecture_id, "synth", script, log, directory)
            if result.returncode != 0:
                raise GateFailure("synthesis", f"Yosys exited {result.returncode}", architecture_id, {"log": str(log), "log_sha256": sha256(log)})
            netlist = directory / f"{architecture_id}_netlist.json"
            if not netlist.exists():
                raise GateFailure("synthesis", "Yosys did not produce JSON netlist", architecture_id)
            row = parse_synthesis(config, architecture_id, script, log, netlist)
            rows.append(row)
            print(
                f"SYNTHESIS END {architecture_id} status={row['status']} LUT={row['lut']} FF={row['ff']} "
                f"DSP={row['dsp']} BRAM36eq={row['bram36_equivalent']}",
                flush=True,
            )
            if row["status"] != "VERIFIED":
                raise GateFailure("post_synthesis_audit", "architecture failed a frozen post-synthesis gate", architecture_id, row)

        consistency = cross_architecture_mapping(rows)
        if consistency["status"] != "VERIFIED":
            raise GateFailure("cross_architecture_mapping", "same-geometry memory primitive fingerprints differ", details=consistency)

        subfft = with_baseline_deltas([row for row in rows if row["group"] == "SubFFT"], "S0")
        pfft = with_baseline_deltas([row for row in rows if row["group"] == "PFFT"], "P0")
        subfft_csv = RESULTS / "yosys_subfft_group.csv"
        pfft_csv = RESULTS / "yosys_pfft_group.csv"
        mapping_json = RESULTS / "yosys_memory_mapping_audit.json"
        summary_path = RESULTS / "yosys_seven_arch_summary.json"
        markdown_path = RESULTS / "yosys_resource_audit.md"
        write_group_csv(subfft_csv, subfft)
        write_group_csv(pfft_csv, pfft)
        write_json(mapping_json, {
            "schema": "yosys-seven-architecture-memory-audit-v1",
            "status": "VERIFIED",
            "per_architecture": {row["architecture_id"]: row["memory_mapping_audit"] for row in rows},
            "cross_architecture_consistency": consistency,
        })
        summary = {
            "schema": "yosys-seven-architecture-resource-summary-v1",
            "status": "VERIFIED",
            "timestamp_utc": utc_now(),
            "attempt": attempt,
            "evidence_class": "same-flow complete-RTL Yosys xc7 synthesis resource estimate",
            "yosys_executable": str(YOSYS),
            "yosys_executable_sha256": sha256(YOSYS),
            "yosys_version": config["version"],
            "family": "xc7",
            "target_device_context": config["target_evidence"]["device"],
            "validation": validation,
            "runner": str(Path(__file__)),
            "runner_sha256": sha256(Path(__file__)),
            "groups": {"SubFFT": subfft, "PFFT": pfft},
            "cross_architecture_memory_consistency": consistency,
            "artifacts": {
                "subfft_csv": str(subfft_csv),
                "pfft_csv": str(pfft_csv),
                "memory_audit": str(mapping_json),
                "markdown_audit": str(markdown_path),
            },
            "claim_boundary": config["claim_boundary"],
        }
        write_json(summary_path, summary)
        markdown_path.write_text(render_markdown(summary), encoding="utf-8", newline="\n")
        print(json.dumps({
            "status": "VERIFIED",
            "summary": str(summary_path),
            "summary_sha256": sha256(summary_path),
            "subfft_csv_sha256": sha256(subfft_csv),
            "pfft_csv_sha256": sha256(pfft_csv),
            "memory_audit_sha256": sha256(mapping_json),
            "markdown_audit_sha256": sha256(markdown_path),
        }, ensure_ascii=False), flush=True)
        return 0
    except Exception as unexpected:
        error = unexpected if isinstance(unexpected, GateFailure) else GateFailure(
            "runner_internal", repr(unexpected), details={"exception_type": type(unexpected).__name__}
        )
        write_json(failure_path, failure_payload(error, validation, rows, attempt))
        print(f"STOP {error.stage} architecture={error.architecture_id} evidence={failure_path} SHA256={sha256(failure_path)}", flush=True)
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
    validation_path = RESULTS / "yosys_runner_validation.json"
    try:
        config, validation = validate_inputs()
        write_json(validation_path, validation)
        print(f"INPUT VALIDATION VERIFIED {validation_path} SHA256={sha256(validation_path)}", flush=True)
        if args.validate_only:
            return 0
        if args.preflight:
            return run_preflight(config, validation)
        return run_formal(config, validation, args.attempt)
    except GateFailure as error:
        payload = failure_payload(error, None, [], args.attempt)
        if error.stage in {"input_validation", "tool_validation"}:
            write_json(validation_path, payload)
        print(f"STOP {error.stage}: {error}", flush=True)
        if error.details is not None:
            print(json.dumps(error.details, ensure_ascii=False, indent=2), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
