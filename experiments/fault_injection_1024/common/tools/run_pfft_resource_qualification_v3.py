#!/usr/bin/env python3
"""Single-attempt RTL qualification for PFFT-RES-V3-001.

This runner is intentionally fail-fast.  It performs source-contract checks,
executes the dedicated connectivity spot test, then compiles and simulates
P0, P1, and P2 in that order.  The elaborated Icarus VVP scope graph is used
to count active ``fft_complex_mul_q28`` instances, so parameter-specialized
and generated-away branches are not mistaken for physical multiplier units.

No artifact produced by a previous attempt is overwritten.  A first failure
is serialized with the completed evidence and the remaining phases are not
run.
"""

from __future__ import annotations

import hashlib
import json
import locale
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
WORKSPACE = HERE.parents[3]
SHARED_RTL = EXPERIMENT / "common" / "rtl"
RESULTS = EXPERIMENT / "results" / "pfft_resource_v3_001" / "qualification_attempt1"
LOGS = EXPERIMENT / "logs" / "pfft_resource_v3_001" / "qualification_attempt1"
BUILD = EXPERIMENT / "build" / "pfft_resource_v3_001" / "qualification_attempt1"
IVERILOG = Path(r"C:\iverilog\bin\iverilog.exe")
VVP = Path(r"C:\iverilog\bin\vvp.exe")

CONTRACT = EXPERIMENT / "PFFT_RESOURCE_REEVALUATION_V3.md"
CONFIG = EXPERIMENT / "config" / "pfft_resource_reevaluation_v3.json"
MEMORY_MAP = EXPERIMENT / "config" / "pfft_resource_memory_map_v3.json"
INPUT_MANIFEST = EXPERIMENT / "config" / "pfft_resource_v3_input_manifest.json"
VECTOR_MANIFEST = EXPERIMENT / "results" / "pfft_resource_v3_001" / "vector_manifest.json"
SCHEDULE_FEASIBILITY = (
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
        "tb_module": "tb_p0",
        "top_source": EXPERIMENT / "projects" / "P0" / "top_p0_pfft_unprotected.sv",
        "tb": EXPERIMENT / "projects" / "P0" / "tb_p0.sv",
        "expected_vector": (
            EXPERIMENT
            / "projects"
            / "P0"
            / "vectors"
            / "qualification_p0_no_exchange_expected_8frames.hex"
        ),
        "expected_active_complex_multipliers": 29,
    },
    "P1": {
        "top": "top_p1_pfft_ecc",
        "tb_module": "tb_p1",
        "top_source": EXPERIMENT / "projects" / "P1" / "top_p1_pfft_ecc.sv",
        "tb": EXPERIMENT / "projects" / "P1" / "tb_p1.sv",
        "expected_vector": (
            EXPERIMENT
            / "common"
            / "vectors"
            / "qualification_pfft_expected_8frames.hex"
        ),
        "expected_active_complex_multipliers": 46,
    },
    "P2": {
        "top": "top_p2_pfft_tmr",
        "tb_module": "tb_p2",
        "top_source": EXPERIMENT / "projects" / "P2" / "top_p2_pfft_tmr.sv",
        "tb": EXPERIMENT / "projects" / "P2" / "tb_p2.sv",
        "expected_vector": (
            EXPERIMENT
            / "projects"
            / "P2"
            / "vectors"
            / "qualification_p2_no_exchange_expected_8frames.hex"
        ),
        "expected_active_complex_multipliers": 87,
    },
}

CONNECTIVITY = {
    "top": "pfft_connectivity_spot_tb_v3",
    "tb": SHARED_RTL / "pfft_connectivity_spot_tb_v3.sv",
    "required_marker": "PASS_V3_CONNECTIVITY",
}

# This is the only configuration block that should need adjustment if the
# final P1 implementation chooses different explicit V3 module names.  The
# qualification logic below must not be weakened when updating these names.
P1_REQUIRED_MARKERS = {
    "core_module": "p1_pfft_ecc_core_v3",
    "stage1_to7_module": "p1_ecc_stage4_v3",
    "stage8_functional_module": "p1_stage8_functional_v3",
    "stage8_scheduler_module": "p1_stage8_single_check_pair_scheduler_v3",
    "check_pair_module": "independent_check_operator_pair_v5",
    "stage9_replica_module": "p1_pfft_stage9_exchange_v3",
    "stage9_tmr_module": "p1_tmr_pfft_stage9_v3",
    "stage10_tmr_module": "p1_tmr_pfft_stage10_v3",
    "scheduler_source_check_pair_instances": 1,
    "check_pair_source_multiplier_instances": 2,
    "scheduler_elaborated_instances": 1,
    "scheduler_descendant_multiplier_instances": 2,
    "required_scheduler_tokens": ("FIFO", "urgent", "background", "tag"),
    "required_scheduler_fixed_latency": 258,
    "required_pre_issue_capacity": 129,
}

EXPECTED_BEATS = 2048
EXPECTED_LATENCY = 525


def relative(path: Path) -> str:
    return path.relative_to(WORKSPACE).as_posix()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def file_record(path: Path) -> dict[str, object]:
    return {
        "path": relative(path) if path.is_relative_to(WORKSPACE) else path.as_posix(),
        "sha256": sha256(path),
        "size_bytes": path.stat().st_size,
    }


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def strip_sv_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"//[^\r\n]*", " ", text)


def extract_modules(paths: Iterable[Path]) -> dict[str, str]:
    modules: dict[str, str] = {}
    for path in paths:
        text = strip_sv_comments(path.read_text(encoding="utf-8"))
        for match in re.finditer(
            r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)\b(.*?)\bendmodule\b",
            text,
            flags=re.S,
        ):
            name = match.group(1)
            if name in modules:
                raise RuntimeError(f"duplicate module definition in active source set: {name}")
            modules[name] = match.group(0)
    return modules


def count_module_instances(module_text: str, target_module: str) -> int:
    body_start = module_text.find(");")
    body = module_text[body_start + 2 :] if body_start >= 0 else module_text
    pattern = re.compile(
        rf"\b{re.escape(target_module)}\b\s*"
        rf"(?:#\s*\(.*?\)\s*)?"
        rf"[A-Za-z_][A-Za-z0-9_$]*(?:\s*\[[^\]]+\])?\s*\(",
        flags=re.S,
    )
    return len(pattern.findall(body))


def module_closure(top: str, modules: dict[str, str]) -> tuple[set[str], dict[str, dict[str, int]]]:
    if top not in modules:
        raise RuntimeError(f"top module not defined: {top}")
    closure: set[str] = set()
    edges: dict[str, dict[str, int]] = {}
    pending = [top]
    while pending:
        parent = pending.pop()
        if parent in closure:
            continue
        closure.add(parent)
        children: dict[str, int] = {}
        for candidate in modules:
            count = count_module_instances(modules[parent], candidate)
            if count:
                children[candidate] = count
                if candidate not in closure:
                    pending.append(candidate)
        edges[parent] = children
    return closure, edges


def check(name: str, passed: bool, evidence: object) -> dict[str, object]:
    return {"name": name, "pass": bool(passed), "evidence": evidence}


def source_structural_audit() -> dict[str, object]:
    all_sources = (*COMMON_SOURCES, *(entry["top_source"] for entry in PROJECTS.values()))
    modules = extract_modules(all_sources)
    closures: dict[str, list[str]] = {}
    edges_by_architecture: dict[str, object] = {}
    checks: list[dict[str, object]] = []

    for architecture, entry in PROJECTS.items():
        closure, edges = module_closure(entry["top"], modules)
        closures[architecture] = sorted(closure)
        edges_by_architecture[architecture] = edges

    p0_text = PROJECTS["P0"]["top_source"].read_text(encoding="utf-8")
    p0_pipeline = modules.get("p0_pfft_no_exchange_pipeline_v3", "")
    p0_closure = set(closures["P0"])
    checks.extend(
        (
            check(
                "P0_has_eight_canonical_no_exchange_SDF_stages",
                count_module_instances(p0_pipeline, "pfft_stage4_sdf_no_exchange_v3") == 8,
                count_module_instances(p0_pipeline, "pfft_stage4_sdf_no_exchange_v3"),
            ),
            check(
                "P0_has_canonical_no_exchange_stage9_and_stage10",
                count_module_instances(p0_pipeline, "pfft_stage9_no_exchange_v3") == 1
                and count_module_instances(p0_pipeline, "pfft_stage10") == 1,
                {
                    "stage9": count_module_instances(p0_pipeline, "pfft_stage9_no_exchange_v3"),
                    "stage10": count_module_instances(p0_pipeline, "pfft_stage10"),
                },
            ),
            check(
                "P0_active_source_has_no_exchange_phi_instance",
                "pfft_phi_calc" not in p0_closure
                and not re.search(r"\bpfft_phi_calc\b\s*(?:#\s*\()?", strip_sv_comments(p0_text)),
                {"closure_contains_pfft_phi_calc": "pfft_phi_calc" in p0_closure},
            ),
            check(
                "P0_closure_has_no_ECC_TMR_or_voter",
                not any(
                    token in name.lower()
                    for name in p0_closure
                    for token in ("ecc", "tmr", "secded", "vote35")
                ),
                sorted(
                    name
                    for name in p0_closure
                    if any(token in name.lower() for token in ("ecc", "tmr", "secded", "vote35"))
                ),
            ),
        )
    )

    p2_text = PROJECTS["P2"]["top_source"].read_text(encoding="utf-8")
    p2_core = modules.get("p2_pfft_tmr_no_exchange_core_v3", "")
    p2_stage = modules.get("p2_tmr_pfft_stage4_no_exchange_v3", "")
    p2_stage9 = modules.get("p2_tmr_pfft_stage9_no_exchange_v3", "")
    p2_stage10 = modules.get("p2_tmr_pfft_stage10_v3", "")
    p2_closure = set(closures["P2"])
    compact_p2_wrappers = re.sub(r"\s+", "", p2_stage + p2_stage9 + p2_stage10)
    checks.extend(
        (
            check(
                "P2_has_eight_TMR_SDF_stages",
                count_module_instances(p2_core, "p2_tmr_pfft_stage4_no_exchange_v3") == 8,
                count_module_instances(p2_core, "p2_tmr_pfft_stage4_no_exchange_v3"),
            ),
            check(
                "P2_has_TMR_stage9_and_stage10",
                count_module_instances(p2_core, "p2_tmr_pfft_stage9_no_exchange_v3") == 1
                and count_module_instances(p2_core, "p2_tmr_pfft_stage10_v3") == 1,
                {
                    "stage9": count_module_instances(p2_core, "p2_tmr_pfft_stage9_no_exchange_v3"),
                    "stage10": count_module_instances(p2_core, "p2_tmr_pfft_stage10_v3"),
                },
            ),
            check(
                "P2_each_wrapper_declares_three_replicas",
                compact_p2_wrappers.count("for(g=0;g<3;g=g+1)") == 3,
                compact_p2_wrappers.count("for(g=0;g<3;g=g+1)"),
            ),
            check(
                "P2_each_wrapper_has_eight_complex_component_voters",
                all(text.count("vote35 ") == 8 for text in (p2_stage, p2_stage9, p2_stage10)),
                {
                    "stage1_to8_wrapper": p2_stage.count("vote35 "),
                    "stage9_wrapper": p2_stage9.count("vote35 "),
                    "stage10_wrapper": p2_stage10.count("vote35 "),
                },
            ),
            check(
                "P2_active_source_has_no_exchange_phi_instance",
                "pfft_phi_calc" not in p2_closure
                and not re.search(r"\bpfft_phi_calc\b\s*(?:#\s*\()?", strip_sv_comments(p2_text)),
                {"closure_contains_pfft_phi_calc": "pfft_phi_calc" in p2_closure},
            ),
        )
    )

    p1_source = PROJECTS["P1"]["top_source"]
    p1_text = p1_source.read_text(encoding="utf-8")
    p1_closure = set(closures["P1"])
    configured_modules = {
        key: value
        for key, value in P1_REQUIRED_MARKERS.items()
        if key.endswith("_module")
    }
    checks.append(
        check(
            "P1_all_required_modules_are_defined_and_reachable",
            all(name in modules and name in p1_closure for name in configured_modules.values()),
            {
                key: {
                    "module": name,
                    "defined": name in modules,
                    "reachable": name in p1_closure,
                }
                for key, name in configured_modules.items()
            },
        )
    )
    scheduler_name = P1_REQUIRED_MARKERS["stage8_scheduler_module"]
    scheduler_source = modules.get(scheduler_name, "")
    scheduler_instance_count = sum(
        count_module_instances(modules[parent], scheduler_name) for parent in p1_closure
    )
    check_pair_name = P1_REQUIRED_MARKERS["check_pair_module"]
    scheduler_check_pair_source_count = count_module_instances(
        scheduler_source, check_pair_name
    )
    check_pair_multiplier_source_count = count_module_instances(
        modules.get(check_pair_name, ""), "fft_complex_mul_q28"
    )
    history_block_arrays = sorted(
        re.findall(
            r'\(\*\s*ram_style\s*=\s*"block"\s*\*\)\s*'
            r'reg\s*\[77:0\]\s*'
            r'((?:functional|operand_a|operand_b)_history[0-3])'
            r'\s*\[0:511\]\s*;',
            scheduler_source,
        )
    )
    background_block_arrays = re.findall(
        r'\(\*\s*ram_style\s*=\s*"block"\s*\*\)\s*'
        r'reg\s*\[TASK_PAYLOAD_W-1:0\]\s*background_fifo'
        r'\s*\[0:127\]\s*;',
        scheduler_source,
    )
    result_block_arrays = sorted(
        re.findall(
            r'\(\*\s*ram_style\s*=\s*"block"\s*\*\)\s*'
            r'reg\s*\[311:0\]\s*(result(?:01|23)_memory)'
            r'\s*\[0:511\]\s*;',
            scheduler_source,
        )
    )
    expected_history_block_arrays = sorted(
        [
            *(f"functional_history{index}" for index in range(4)),
            *(f"operand_a_history{index}" for index in range(4)),
            *(f"operand_b_history{index}" for index in range(4)),
        ]
    )
    checks.extend(
        (
            check(
                "P1_closure_has_exactly_one_single_check_pair_scheduler_instance",
                scheduler_instance_count
                == P1_REQUIRED_MARKERS["scheduler_elaborated_instances"],
                scheduler_instance_count,
            ),
            check(
                "P1_scheduler_directly_instantiates_exactly_one_shared_check_pair",
                scheduler_check_pair_source_count
                == P1_REQUIRED_MARKERS["scheduler_source_check_pair_instances"],
                scheduler_check_pair_source_count,
            ),
            check(
                "P1_shared_check_pair_source_has_exactly_two_complex_multipliers",
                check_pair_multiplier_source_count
                == P1_REQUIRED_MARKERS["check_pair_source_multiplier_instances"],
                check_pair_multiplier_source_count,
            ),
            check(
                "P1_scheduler_has_FIFO_urgent_background_and_tag_markers",
                all(
                    token.lower() in scheduler_source.lower()
                    for token in P1_REQUIRED_MARKERS["required_scheduler_tokens"]
                ),
                {
                    token: token.lower() in scheduler_source.lower()
                    for token in P1_REQUIRED_MARKERS["required_scheduler_tokens"]
                },
            ),
            check(
                "P1_scheduler_freezes_129_capacity_or_128_plus_skid_and_258_cycle_latency",
                (
                    bool(re.search(r"(?<!\d)129(?!\d)", scheduler_source))
                    or (
                        "background_fifo[0:127]" in re.sub(r"\s+", "", scheduler_source)
                        and "issue_urgent_direct" in scheduler_source
                    )
                )
                and bool(re.search(r"(?<!\d)258(?!\d)", scheduler_source)),
                {
                    "literal_129": bool(
                        re.search(r"(?<!\d)129(?!\d)", scheduler_source)
                    ),
                    "background_128_plus_direct_skid": (
                        "background_fifo[0:127]" in re.sub(r"\s+", "", scheduler_source)
                        and "issue_urgent_direct" in scheduler_source
                    ),
                    "fixed_latency_258": bool(
                        re.search(r"(?<!\d)258(?!\d)", scheduler_source)
                    ),
                },
            ),
            check(
                "P1_scheduler_freezes_15_block_arrays_and_921472_logical_bits",
                history_block_arrays == expected_history_block_arrays
                and len(background_block_arrays) == 1
                and result_block_arrays
                == ["result01_memory", "result23_memory"]
                and bool(
                    re.search(
                        r"localparam\s+integer\s+TASK_TAG_W\s*=\s*23\s*;",
                        scheduler_source,
                    )
                )
                and bool(
                    re.search(
                        r"localparam\s+integer\s+TASK_PAYLOAD_W\s*=\s*"
                        r"TASK_TAG_W\s*\+\s*\(\s*12\s*\*\s*78\s*\)\s*;",
                        scheduler_source,
                    )
                ),
                {
                    "history_arrays": history_block_arrays,
                    "background_array_count": len(background_block_arrays),
                    "result_arrays": result_block_arrays,
                    "declared_block_array_count": (
                        len(history_block_arrays)
                        + len(background_block_arrays)
                        + len(result_block_arrays)
                    ),
                    "logical_capacity_bits": (
                        12 * 512 * 78
                        + 128 * (23 + 12 * 78)
                        + 2 * 512 * 312
                    ),
                },
            ),
            check(
                "P1_source_uses_exchange_schedule",
                "pfft_phi_calc" in p1_closure or "pfft_phi_calc" in strip_sv_comments(p1_text),
                {"closure_contains_pfft_phi_calc": "pfft_phi_calc" in p1_closure},
            ),
        )
    )

    lane = modules.get("r2sdf_lane_pfft_no_exchange_v3", "")
    checks.extend(
        (
            check(
                "canonical_lane_has_one_time_shared_lower_rotation_slot",
                count_module_instances(lane, "fft_complex_mul_q28") == 1
                and count_module_instances(lane, "fft_complex_rotate_trivial_1024") == 1
                and "store_re = work_second ? rotated_lower_re : work_in_re" in lane
                and "candidate_re = work_second ? upper_re : memory_re" in lane,
                {
                    "generic_source_instances": count_module_instances(
                        lane, "fft_complex_mul_q28"
                    ),
                    "trivial_source_instances": count_module_instances(
                        lane, "fft_complex_rotate_trivial_1024"
                    ),
                },
            ),
            check(
                "canonical_lane_specializes_stage7_lane0_and_stage8_lanes0_2",
                all(
                    marker in lane
                    for marker in (
                        "(STAGE == 7) && (LANE == 0)",
                        "(STAGE == 8) && ((LANE == 0) || (LANE == 2))",
                    )
                ),
                "stage7_lane0_and_stage8_lanes0_2",
            ),
        )
    )

    schedule = json.loads(SCHEDULE_FEASIBILITY.read_text(encoding="utf-8"))
    schedule_checks = schedule.get("pass_fail_checks", {})
    recommendation = schedule.get("recommended_schedule", {})
    checks.extend(
        (
            check(
                "P1_stage8_static_feasibility_gate_passed",
                schedule.get("status") == "PASS_STATIC_FEASIBILITY_SINGLE_CHECK_PAIR"
                and schedule.get("stop_condition_triggered") is False
                and all(schedule_checks.values()),
                {
                    "status": schedule.get("status"),
                    "stop_condition_triggered": schedule.get("stop_condition_triggered"),
                    "all_pass_fail_checks": bool(schedule_checks)
                    and all(schedule_checks.values()),
                },
            ),
            check(
                "P1_stage8_schedule_matches_129_entry_258_cycle_contract",
                recommendation.get("safe_queue_entries_if_enqueue_precedes_issue") == 129
                and recommendation.get("minimum_fixed_latency_cycles") == 258
                and recommendation.get("continuous_no_gap") is True,
                {
                    "safe_queue_entries": recommendation.get(
                        "safe_queue_entries_if_enqueue_precedes_issue"
                    ),
                    "minimum_fixed_latency_cycles": recommendation.get(
                        "minimum_fixed_latency_cycles"
                    ),
                    "continuous_no_gap": recommendation.get("continuous_no_gap"),
                },
            ),
        )
    )

    vector_manifest = json.loads(VECTOR_MANIFEST.read_text(encoding="utf-8"))
    p0_vector = PROJECTS["P0"]["expected_vector"]
    p2_vector = PROJECTS["P2"]["expected_vector"]
    checks.extend(
        (
            check(
                "P0_P2_vectors_are_byte_identical_canonical_DIF",
                p0_vector.read_bytes() == p2_vector.read_bytes()
                and sha256(p0_vector)
                == vector_manifest["outputs"]["shared_sha256"]
                == sha256(p2_vector),
                {
                    "P0_sha256": sha256(p0_vector),
                    "P2_sha256": sha256(p2_vector),
                    "manifest_shared_sha256": vector_manifest["outputs"]["shared_sha256"],
                },
            ),
            check(
                "vector_manifest_is_verified",
                vector_manifest.get("status") == "VERIFIED"
                and vector_manifest.get("frame_contract", {}).get(
                    "output_beats_per_architecture"
                )
                == EXPECTED_BEATS,
                {
                    "status": vector_manifest.get("status"),
                    "output_beats": vector_manifest.get("frame_contract", {}).get(
                        "output_beats_per_architecture"
                    ),
                },
            ),
        )
    )

    for architecture, entry in PROJECTS.items():
        tb_text = entry["tb"].read_text(encoding="utf-8")
        checks.append(
            check(
                f"{architecture}_TB_freezes_latency_and_project_vector",
                f"`define PROJECT_EXPECTED_LATENCY {EXPECTED_LATENCY}" in tb_text
                and relative(entry["expected_vector"]) in tb_text,
                {
                    "latency_marker": f"`define PROJECT_EXPECTED_LATENCY {EXPECTED_LATENCY}"
                    in tb_text,
                    "expected_vector": relative(entry["expected_vector"]),
                    "vector_marker": relative(entry["expected_vector"]) in tb_text,
                },
            )
        )

    passed = sum(item["pass"] for item in checks)
    return {
        "status": "VERIFIED" if passed == len(checks) else "FAILED",
        "checks": checks,
        "passed": passed,
        "total": len(checks),
        "module_closure_by_architecture": closures,
        "module_edges_by_architecture": edges_by_architecture,
    }


def run_logged(
    command: list[str], log_path: Path, timeout: int
) -> subprocess.CompletedProcess[str]:
    try:
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
    except subprocess.TimeoutExpired as exc:
        partial = exc.stdout or ""
        if isinstance(partial, bytes):
            partial = partial.decode(locale.getpreferredencoding(False), errors="backslashreplace")
        partial += f"\nTIMEOUT seconds={timeout} command={command!r}\n"
        result = subprocess.CompletedProcess(command, 124, stdout=partial)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(result.stdout, encoding="utf-8", newline="\n")
    print(f"EXIT {result.returncode} LOG {relative(log_path)}", flush=True)
    if result.returncode != 0 and result.stdout:
        print(result.stdout[-4000:], flush=True)
    return result


def parse_vvp_scopes(image: Path) -> dict[str, dict[str, str | None]]:
    scopes: dict[str, dict[str, str | None]] = {}
    pattern = re.compile(
        r'^(S_[0-9A-Fa-f]+)\s+\.scope module,\s+"([^"]+)"\s+"([^"]+)"'
    )
    with image.open("r", encoding="utf-8", errors="replace") as stream:
        for line in stream:
            match = pattern.match(line)
            if not match:
                continue
            scope_id, instance_name, module_name = match.groups()
            ids = re.findall(r"S_[0-9A-Fa-f]+", line)
            parent = ids[-1] if len(ids) > 1 and ids[-1] != scope_id else None
            scopes[scope_id] = {
                "instance": instance_name,
                "module": module_name,
                "parent": parent,
            }
    if not scopes:
        raise RuntimeError(f"no elaborated module scopes found in {relative(image)}")
    return scopes


def has_ancestor_module(
    scope_id: str, target_module: str, scopes: dict[str, dict[str, str | None]]
) -> bool:
    current: str | None = scope_id
    visited: set[str] = set()
    while current is not None and current not in visited:
        visited.add(current)
        entry = scopes.get(current)
        if entry is None:
            return False
        if entry["module"] == target_module:
            return True
        current = entry["parent"]
    return False


def elaboration_audit(
    architecture: str, image: Path
) -> tuple[dict[str, object], list[dict[str, object]]]:
    scopes = parse_vvp_scopes(image)
    module_counts = Counter(
        str(entry["module"]) for entry in scopes.values() if entry["module"] is not None
    )
    expected_multipliers = PROJECTS[architecture]["expected_active_complex_multipliers"]
    active_multipliers = module_counts["fft_complex_mul_q28"]
    checks = [
        check(
            f"{architecture}_elaborated_active_complex_multiplier_count",
            active_multipliers == expected_multipliers,
            {"actual": active_multipliers, "expected": expected_multipliers},
        )
    ]
    detail: dict[str, object] = {
        "image": file_record(image),
        "scope_count": len(scopes),
        "module_instance_counts": dict(sorted(module_counts.items())),
        "active_fft_complex_mul_q28_instances": active_multipliers,
        "expected_active_fft_complex_mul_q28_instances": expected_multipliers,
    }
    if architecture == "P1":
        scheduler = P1_REQUIRED_MARKERS["stage8_scheduler_module"]
        scheduler_count = module_counts[scheduler]
        scheduler_multipliers = sum(
            1
            for scope_id, entry in scopes.items()
            if entry["module"] == "fft_complex_mul_q28"
            and has_ancestor_module(scope_id, scheduler, scopes)
        )
        checks.extend(
            (
                check(
                    "P1_elaborated_has_one_single_check_pair_scheduler",
                    scheduler_count
                    == P1_REQUIRED_MARKERS["scheduler_elaborated_instances"],
                    scheduler_count,
                ),
                check(
                    "P1_elaborated_scheduler_has_two_descendant_complex_multipliers",
                    scheduler_multipliers
                    == P1_REQUIRED_MARKERS["scheduler_descendant_multiplier_instances"],
                    scheduler_multipliers,
                ),
            )
        )
        detail["P1_stage8_single_check_pair"] = {
            "scheduler_module": scheduler,
            "scheduler_instances": scheduler_count,
            "descendant_fft_complex_mul_q28_instances": scheduler_multipliers,
        }
    detail["status"] = "VERIFIED" if all(item["pass"] for item in checks) else "FAILED"
    return detail, checks


def compile_command(top: str, output: Path, sources: Iterable[Path]) -> list[str]:
    return [
        str(IVERILOG),
        "-g2012",
        "-s",
        top,
        "-o",
        str(output),
        *map(str, sources),
    ]


def base_summary() -> dict[str, object]:
    return {
        "schema": "pfft-resource-v3-001-rtl-qualification-v1",
        "status": "IN_PROGRESS",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "PFFT-RES-V3-001",
        "evidence_class": "RTL_BIT_EXACT_QUALIFICATION_NOT_YOSYS_NOT_PHYSICAL_IMPLEMENTATION",
        "claim_boundary": (
            "Qualification establishes source structure, elaborated active multiplier "
            "instances, connectivity spots, bit-exact outputs, stream continuity, "
            "out_last cadence, and deterministic latency. It is not a synthesized "
            "resource result, timing result, Fmax, power, board, or radiation result."
        ),
        "tools": {
            "python": file_record(Path(sys.executable)),
            "iverilog": file_record(IVERILOG),
            "vvp": file_record(VVP),
        },
        "policy": {
            "single_attempt": "attempt1",
            "stop_on_first_failure": True,
            "no_automatic_retry": True,
            "qualification_before_yosys": True,
            "architecture_order": ["P0", "P1", "P2"],
        },
        "inputs": {
            "contract": file_record(CONTRACT),
            "config": file_record(CONFIG),
            "memory_map": file_record(MEMORY_MAP),
            "input_manifest": file_record(INPUT_MANIFEST),
            "vector_manifest": file_record(VECTOR_MANIFEST),
            "schedule_feasibility": file_record(SCHEDULE_FEASIBILITY),
            "snapshot_manifest": file_record(SNAPSHOT_MANIFEST),
        },
        "connectivity": None,
        "bit_exact": {},
        "failure": None,
    }


def fail(
    summary: dict[str, object],
    final_path: Path,
    phase: str,
    detail: dict[str, object],
) -> int:
    summary["status"] = "FAILED"
    summary["failure"] = {"phase": phase, **detail}
    write_json(final_path, summary)
    print(
        f"QUALIFICATION FAILED phase={phase} result={relative(final_path)} "
        f"sha256={sha256(final_path)}",
        flush=True,
    )
    return 1


def main() -> int:
    final_path = RESULTS / "rtl_qualification.json"
    structure_path = RESULTS / "rtl_structure_manifest.json"
    if RESULTS.exists() or LOGS.exists() or BUILD.exists():
        raise RuntimeError(
            "PFFT-RES-V3-001 qualification attempt1 artifact directory already exists; "
            "refusing an implicit retry or overwrite"
        )

    sources_by_architecture = {
        architecture: (*COMMON_SOURCES, entry["top_source"])
        for architecture, entry in PROJECTS.items()
    }
    required = {
        IVERILOG,
        VVP,
        CONTRACT,
        CONFIG,
        MEMORY_MAP,
        INPUT_MANIFEST,
        VECTOR_MANIFEST,
        SCHEDULE_FEASIBILITY,
        SNAPSHOT_MANIFEST,
        CONNECTIVITY["tb"],
        *COMMON_SOURCES,
        *(entry["top_source"] for entry in PROJECTS.values()),
        *(entry["tb"] for entry in PROJECTS.values()),
        *(entry["expected_vector"] for entry in PROJECTS.values()),
    }
    missing = sorted(relative(path) if path.is_relative_to(WORKSPACE) else str(path) for path in required if not path.exists())
    if missing:
        raise FileNotFoundError("missing frozen qualification input: " + ", ".join(missing))

    RESULTS.mkdir(parents=True)
    LOGS.mkdir(parents=True)
    BUILD.mkdir(parents=True)
    summary = base_summary()

    structure = source_structural_audit()
    structure_manifest: dict[str, object] = {
        "schema": "pfft-resource-v3-001-rtl-structure-manifest-v1",
        "status": structure["status"],
        "experiment_id": "PFFT-RES-V3-001",
        "target": "1024-point four-lane ten-stage radix-2 PFFT",
        "sources_by_architecture": {
            architecture: [file_record(path) for path in sources]
            for architecture, sources in sources_by_architecture.items()
        },
        "testbenches": {
            architecture: file_record(entry["tb"])
            for architecture, entry in PROJECTS.items()
        },
        "connectivity_testbench": file_record(CONNECTIVITY["tb"]),
        "expected_vectors": {
            architecture: file_record(entry["expected_vector"])
            for architecture, entry in PROJECTS.items()
        },
        "source_static_audit": structure,
        "elaboration_by_architecture": {},
        "elaboration_checks_by_architecture": {},
    }
    write_json(structure_path, structure_manifest)
    summary["structure_manifest"] = file_record(structure_path)
    if structure["status"] != "VERIFIED":
        return fail(
            summary,
            final_path,
            "source_static_audit",
            {
                "passed": structure["passed"],
                "total": structure["total"],
                "failed_checks": [
                    item["name"] for item in structure["checks"] if not item["pass"]
                ],
            },
        )

    connectivity_image = BUILD / "pfft_connectivity_spot_v3.vvp"
    connectivity_compile_log = LOGS / "connectivity_compile.log"
    connectivity_simulation_log = LOGS / "connectivity_simulation.log"
    connectivity_sources = (
        *COMMON_SOURCES,
        *(entry["top_source"] for entry in PROJECTS.values()),
        CONNECTIVITY["tb"],
    )
    connectivity_compile_command = compile_command(
        CONNECTIVITY["top"], connectivity_image, connectivity_sources
    )
    print("COMPILE START CONNECTIVITY", flush=True)
    compiled = run_logged(connectivity_compile_command, connectivity_compile_log, 180)
    connectivity_record: dict[str, object] = {
        "status": "IN_PROGRESS",
        "compile_command": connectivity_compile_command,
        "compile_log": file_record(connectivity_compile_log),
        "simulation_command": [str(VVP), str(connectivity_image)],
        "required_marker": CONNECTIVITY["required_marker"],
    }
    summary["connectivity"] = connectivity_record
    if compiled.returncode != 0:
        connectivity_record["status"] = "FAILED"
        return fail(
            summary,
            final_path,
            "connectivity_compile",
            {"returncode": compiled.returncode},
        )
    print("SIMULATION START CONNECTIVITY", flush=True)
    simulated = run_logged(
        connectivity_record["simulation_command"], connectivity_simulation_log, 300
    )
    connectivity_record["simulation_log"] = file_record(connectivity_simulation_log)
    connectivity_pass = (
        simulated.returncode == 0
        and CONNECTIVITY["required_marker"] in simulated.stdout
    )
    connectivity_record["status"] = "VERIFIED" if connectivity_pass else "FAILED"
    if not connectivity_pass:
        return fail(
            summary,
            final_path,
            "connectivity_simulation",
            {
                "returncode": simulated.returncode,
                "required_marker": CONNECTIVITY["required_marker"],
            },
        )

    for architecture, entry in PROJECTS.items():
        image = BUILD / f"{architecture.lower()}_bit_exact.vvp"
        compile_log = LOGS / f"rtl_{architecture.lower()}_compile.log"
        simulation_log = LOGS / f"rtl_{architecture.lower()}_simulation.log"
        command = compile_command(
            entry["tb_module"],
            image,
            (*sources_by_architecture[architecture], entry["tb"]),
        )
        architecture_record: dict[str, object] = {
            "status": "IN_PROGRESS",
            "top": entry["top"],
            "testbench_top": entry["tb_module"],
            "expected_beats": EXPECTED_BEATS,
            "expected_latency_cycles": EXPECTED_LATENCY,
            "compile_command": command,
            "compile_log": relative(compile_log),
            "simulation_command": [str(VVP), str(image)],
            "simulation_log": relative(simulation_log),
        }
        summary["bit_exact"][architecture] = architecture_record
        print(f"COMPILE START {architecture}", flush=True)
        compiled = run_logged(command, compile_log, 180)
        architecture_record["compile_log"] = file_record(compile_log)
        if compiled.returncode != 0:
            architecture_record["status"] = "FAILED"
            return fail(
                summary,
                final_path,
                "architecture_compile",
                {"architecture_id": architecture, "returncode": compiled.returncode},
            )

        elaboration, elaboration_checks = elaboration_audit(architecture, image)
        architecture_record["elaboration"] = elaboration
        structure_manifest["elaboration_by_architecture"][architecture] = elaboration
        structure_manifest["elaboration_checks_by_architecture"][
            architecture
        ] = elaboration_checks
        write_json(structure_path, structure_manifest)
        summary["structure_manifest"] = file_record(structure_path)
        if elaboration["status"] != "VERIFIED":
            architecture_record["status"] = "FAILED"
            structure_manifest["status"] = "FAILED"
            write_json(structure_path, structure_manifest)
            summary["structure_manifest"] = file_record(structure_path)
            return fail(
                summary,
                final_path,
                "elaboration_structure_audit",
                {
                    "architecture_id": architecture,
                    "failed_checks": [
                        item["name"] for item in elaboration_checks if not item["pass"]
                    ],
                },
            )

        print(f"SIMULATION START {architecture}", flush=True)
        simulated = run_logged(
            architecture_record["simulation_command"], simulation_log, 600
        )
        architecture_record["simulation_log"] = file_record(simulation_log)
        marker_pattern = re.compile(
            rf"PASS_V3 architecture={architecture} beats=(\d+) latency=(\d+) "
            rf"gaps=(\d+) last_errors=(\d+) data_errors=(\d+)"
        )
        marker = marker_pattern.search(simulated.stdout)
        measured = {
            "beats": int(marker.group(1)) if marker else None,
            "latency_cycles": int(marker.group(2)) if marker else None,
            "gap_errors": int(marker.group(3)) if marker else None,
            "last_errors": int(marker.group(4)) if marker else None,
            "data_errors": int(marker.group(5)) if marker else None,
        }
        architecture_record["measured"] = measured
        architecture_record["beats"] = measured["beats"]
        architecture_record["measured_latency_cycles"] = measured["latency_cycles"]
        architecture_record["gap_errors"] = measured["gap_errors"]
        architecture_record["last_errors"] = measured["last_errors"]
        architecture_record["data_errors"] = measured["data_errors"]
        architecture_record["beats"] = measured["beats"]
        architecture_record["measured_latency_cycles"] = measured["latency_cycles"]
        architecture_record["gap_errors"] = measured["gap_errors"]
        architecture_record["last_errors"] = measured["last_errors"]
        architecture_record["data_errors"] = measured["data_errors"]
        passed = (
            simulated.returncode == 0
            and marker is not None
            and measured["beats"] == EXPECTED_BEATS
            and measured["latency_cycles"] == EXPECTED_LATENCY
            and measured["gap_errors"] == 0
            and measured["last_errors"] == 0
            and measured["data_errors"] == 0
        )
        architecture_record["status"] = "VERIFIED" if passed else "FAILED"
        if not passed:
            return fail(
                summary,
                final_path,
                "architecture_simulation",
                {
                    "architecture_id": architecture,
                    "returncode": simulated.returncode,
                    "required_marker_regex": marker_pattern.pattern,
                    "measured": measured,
                },
            )

    structure_manifest["status"] = "VERIFIED"
    write_json(structure_path, structure_manifest)
    summary["structure_manifest"] = file_record(structure_path)
    summary["manifest_sha256"] = sha256(structure_path)
    summary["status"] = "VERIFIED"
    write_json(final_path, summary)
    print(
        f"QUALIFICATION VERIFIED result={relative(final_path)} "
        f"sha256={sha256(final_path)}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        exception_path = RESULTS / "runner_exception.json"
        if RESULTS.exists() and not exception_path.exists():
            write_json(
                exception_path,
                {
                    "schema": "pfft-resource-v3-001-runner-exception-v1",
                    "status": "FAILED",
                    "experiment_id": "PFFT-RES-V3-001",
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "exception_type": type(exc).__name__,
                    "message": str(exc),
                    "no_automatic_retry": True,
                },
            )
        print(
            f"QUALIFICATION FAIL type={type(exc).__name__} message={exc}",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(1)
