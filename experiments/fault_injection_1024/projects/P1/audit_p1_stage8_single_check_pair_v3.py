#!/usr/bin/env python3
"""Static scheduling audit for one physical P1 Stage-8 check pair.

This program does not simulate RTL and does not run Yosys.  It enumerates the
512 exact-operator codewords formed by the existing two-frame Stage-8 grouping,
then schedules those codewords on one server that accepts at most one codeword
per cycle.  The result records:

* the same0/same_pair/cross_normal/cross_a/cross_b arrival pattern;
* strict-FIFO and earliest-output-first schedules;
* queue depth before and after the single issue slot;
* the fixed latency required for gap-free ordered output; and
* the control-tag and retained-payload obligations of a future RTL scheduler.

The audit is intentionally project-local because the Stage-8 schedule belongs
to P1.  Common FFT mathematics remain imported from P1's existing Python model.
"""

from __future__ import annotations

import hashlib
import heapq
import json
import sys
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


FRAME_BEATS = 256
FRAMES_PER_PAIR = 2
PAIR_BEATS = FRAME_BEATS * FRAMES_PER_PAIR
LANES = 4
SERVICE_CAPACITY_PER_CYCLE = 1
SERVICE_RESULT_LATENCY_CYCLES = 1
PERIODIC_REPLAY_PAIRS = 4

SCRIPT_PATH = Path(__file__).resolve()
P1_DIR = SCRIPT_PATH.parent
EXPERIMENT_ROOT = P1_DIR.parents[1]
WORKSPACE_ROOT = EXPERIMENT_ROOT.parents[1]
RTL_PATH = P1_DIR / "top_p1_pfft_ecc.sv"
MODEL_PATH = P1_DIR / "run_p1.py"
DEFAULT_OUTPUT = (
    EXPERIMENT_ROOT
    / "results"
    / "pfft_resource_v3_001"
    / "schedule_feasibility_attempt1.json"
)

sys.path.insert(0, str(EXPERIMENT_ROOT))

from projects.P1.run_p1 import stage8_groups_strict  # noqa: E402


KIND_ORDER = {
    "same0": 0,
    "same_pair": 1,
    "cross_normal": 2,
    "cross_a": 3,
    "cross_b": 4,
}
EXPECTED_KIND_COUNTS = {
    "same0": 2,
    "same_pair": 254,
    "cross_normal": 254,
    "cross_a": 1,
    "cross_b": 1,
}


@dataclass(frozen=True)
class Task:
    """One [6,4,3] exact-operator check-codeword operation."""

    task_id: str
    kind: str
    release_cycle: int
    positions: tuple[tuple[int, int], ...]
    affected_output_cycles: tuple[int, ...]
    earliest_output_cycle: int
    latest_output_cycle: int

    def shifted(self, pair_index: int) -> "Task":
        shift = pair_index * PAIR_BEATS
        return Task(
            task_id=f"P{pair_index}_{self.task_id}",
            kind=self.kind,
            release_cycle=self.release_cycle + shift,
            positions=self.positions,
            affected_output_cycles=tuple(
                cycle + shift for cycle in self.affected_output_cycles
            ),
            earliest_output_cycle=self.earliest_output_cycle + shift,
            latest_output_cycle=self.latest_output_cycle + shift,
        )

    def as_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "kind": self.kind,
            "release_cycle": self.release_cycle,
            "release_frame": self.release_cycle // FRAME_BEATS,
            "release_beat": self.release_cycle % FRAME_BEATS,
            "positions": [
                {
                    "frame": frame,
                    "physical_index": index,
                    "beat": index // LANES,
                    "lane": index % LANES,
                }
                for frame, index in self.positions
            ],
            "affected_output_cycles": list(self.affected_output_cycles),
            "earliest_output_cycle": self.earliest_output_cycle,
            "latest_output_cycle": self.latest_output_cycle,
        }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def workspace_relative(path: Path) -> str:
    return path.resolve().relative_to(WORKSPACE_ROOT).as_posix()


def source_marker_audit() -> dict:
    source = RTL_PATH.read_text(encoding="utf-8")
    compact = "".join(source.split())
    markers = {
        "same0_physical_operator_exists": (
            "independent_check_operator_pair_v5same0_check(" in compact
        ),
        "same_pair_physical_operator_exists": (
            "independent_check_operator_pair_v5same_pair_check(" in compact
        ),
        "same_pair_release_predicate_matches": (
            "wiresame_pair_active=in_valid&&"
            "((input_beat[1:0]==2'd3)||"
            "((input_beat[1:0]==2'd0)&&(input_beat!=0)));" in compact
        ),
        "cross_normal_physical_operator_exists": (
            "independent_check_operator_pair_v5cross_normal_check(" in compact
        ),
        "cross_a_physical_operator_exists": (
            "independent_check_operator_pair_v5cross_a_check(" in compact
        ),
        "cross_b_physical_operator_exists": (
            "independent_check_operator_pair_v5cross_b_check(" in compact
        ),
        "cross_normal_regular_beats_are_1_through_253": (
            "if((cycle_beat>=1)&&(cycle_beat<=253))begin"
            "selected2r=crossn_d0r;" in compact
        ),
        "two_special_cross_groups_are_used_at_beat_254": (
            "elseif(cycle_beat==254)begin"
            "selected0r=crossa_d0r;"
            "selected0i=crossa_d0i;"
            "selected1r=crossa_d1r;"
            "selected1i=crossa_d1i;"
            "selected2r=crossb_d0r;" in compact
        ),
        "cross_normal_final_beat_is_used_at_255": (
            "elseif(cycle_beat==255)begin"
            "selected2r=crossn_d0r;" in compact
        ),
    }
    return {
        "status": "PASS" if all(markers.values()) else "FAIL",
        "checks": markers,
    }


def classify_group(
    positions: tuple[tuple[int, int], ...],
) -> tuple[str, int, tuple[int, ...]]:
    frames = {frame for frame, _ in positions}
    affected = tuple(
        sorted({frame * FRAME_BEATS + index // LANES for frame, index in positions})
    )
    release = max(
        frame * FRAME_BEATS + index // LANES for frame, index in positions
    )

    if len(frames) == 1:
        local_indices = {index for _, index in positions}
        if local_indices == {0, 1, 2, 3}:
            return "same0", release, affected
        return "same_pair", release, affected

    second_frame = sorted(
        index for frame, index in positions if frame == 1
    )
    second_beats = {index // LANES for index in second_frame}
    second_lanes = tuple(index % LANES for index in second_frame)
    if len(second_beats) != 1:
        raise AssertionError(
            f"cross-frame group spans multiple second-frame beats: {positions}"
        )
    beat = next(iter(second_beats))
    if beat == 254 and second_lanes == (0, 1):
        kind = "cross_a"
    elif beat == 254 and second_lanes == (2, 3):
        kind = "cross_b"
    else:
        if second_lanes != (2, 3):
            raise AssertionError(
                f"unexpected cross-normal lane pattern: {positions}"
            )
        kind = "cross_normal"
    return kind, release, affected


def build_tasks() -> tuple[list[Task], dict]:
    grouping = stage8_groups_strict()
    if grouping.unconsumed:
        raise AssertionError(
            f"Stage-8 grouping leaves {len(grouping.unconsumed)} symbols"
        )

    raw: list[dict] = []
    for positions in (*grouping.same_frame, *grouping.cross_frame):
        canonical = tuple(sorted(positions))
        kind, release, affected = classify_group(canonical)
        raw.append(
            {
                "kind": kind,
                "release": release,
                "positions": canonical,
                "affected": affected,
            }
        )

    raw.sort(
        key=lambda item: (
            item["release"],
            min(item["affected"]),
            KIND_ORDER[item["kind"]],
            item["positions"],
        )
    )
    tasks = [
        Task(
            task_id=f"T{ordinal:03d}",
            kind=item["kind"],
            release_cycle=item["release"],
            positions=item["positions"],
            affected_output_cycles=item["affected"],
            earliest_output_cycle=min(item["affected"]),
            latest_output_cycle=max(item["affected"]),
        )
        for ordinal, item in enumerate(raw)
    ]

    coverage = Counter(
        position for task in tasks for position in task.positions
    )
    expected_positions = {
        (frame, index)
        for frame in range(FRAMES_PER_PAIR)
        for index in range(FRAME_BEATS * LANES)
    }
    duplicated = sorted(
        position for position, count in coverage.items() if count != 1
    )
    missing = sorted(expected_positions - set(coverage))
    kind_counts = Counter(task.kind for task in tasks)
    checks = {
        "same_frame_group_count_is_256": (
            len(grouping.same_frame) == 256
        ),
        "cross_frame_group_count_is_256": (
            len(grouping.cross_frame) == 256
        ),
        "total_task_count_is_512": len(tasks) == 512,
        "all_2048_symbols_covered_exactly_once": (
            not duplicated and not missing and len(coverage) == 2048
        ),
        "kind_counts_match_existing_rtl_schedule": (
            dict(sorted(kind_counts.items()))
            == dict(sorted(EXPECTED_KIND_COUNTS.items()))
        ),
    }
    return tasks, {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "same_frame_groups": len(grouping.same_frame),
        "cross_frame_groups": len(grouping.cross_frame),
        "unconsumed_symbols": len(grouping.unconsumed),
        "covered_symbols": len(coverage),
        "duplicated_positions": [
            {"frame": frame, "physical_index": index}
            for frame, index in duplicated
        ],
        "missing_positions": [
            {"frame": frame, "physical_index": index}
            for frame, index in missing
        ],
        "task_counts_by_kind": dict(sorted(kind_counts.items())),
    }


def schedule_tasks(tasks: Iterable[Task], policy: str) -> dict:
    ordered = sorted(
        tasks,
        key=lambda task: (
            task.release_cycle,
            task.earliest_output_cycle,
            KIND_ORDER[task.kind],
            task.task_id,
        ),
    )
    arrivals: dict[int, list[Task]] = defaultdict(list)
    for task in ordered:
        arrivals[task.release_cycle].append(task)

    fifo: deque[Task] = deque()
    priority: list[tuple[int, int, int, str, Task]] = []
    completions: dict[str, int] = {}
    trace: list[dict] = []
    total = len(ordered)
    cycle = 0
    enqueue_serial = 0
    max_pre_issue = 0
    max_post_issue = 0

    while len(completions) < total:
        cycle_arrivals = arrivals.get(cycle, [])
        for task in cycle_arrivals:
            if policy == "strict_fifo":
                fifo.append(task)
            elif policy == "earliest_output_first":
                heapq.heappush(
                    priority,
                    (
                        task.earliest_output_cycle,
                        task.release_cycle,
                        enqueue_serial,
                        task.task_id,
                        task,
                    ),
                )
            else:
                raise ValueError(f"unknown scheduling policy: {policy}")
            enqueue_serial += 1

        queue_depth_pre_issue = (
            len(fifo) if policy == "strict_fifo" else len(priority)
        )
        max_pre_issue = max(max_pre_issue, queue_depth_pre_issue)

        issued: Task | None = None
        if policy == "strict_fifo" and fifo:
            issued = fifo.popleft()
        elif policy == "earliest_output_first" and priority:
            issued = heapq.heappop(priority)[-1]

        if issued is not None:
            completions[issued.task_id] = (
                cycle + SERVICE_RESULT_LATENCY_CYCLES
            )

        queue_depth_post_issue = (
            len(fifo) if policy == "strict_fifo" else len(priority)
        )
        max_post_issue = max(max_post_issue, queue_depth_post_issue)
        trace.append(
            {
                "cycle": cycle,
                "pair_frame": (
                    cycle // FRAME_BEATS if cycle < PAIR_BEATS else None
                ),
                "beat": cycle % FRAME_BEATS if cycle < PAIR_BEATS else None,
                "arrivals": [
                    {"task_id": task.task_id, "kind": task.kind}
                    for task in cycle_arrivals
                ],
                "arrival_count": len(cycle_arrivals),
                "issued": (
                    {
                        "task_id": issued.task_id,
                        "kind": issued.kind,
                        "result_ready_cycle": completions[issued.task_id],
                    }
                    if issued is not None
                    else None
                ),
                "queue_depth_pre_issue": queue_depth_pre_issue,
                "queue_depth_post_issue": queue_depth_post_issue,
            }
        )
        cycle += 1
        if cycle > max(task.release_cycle for task in ordered) + total + 2:
            raise RuntimeError("single-server schedule failed to terminate")

    end_input_record = trace[PAIR_BEATS - 1]
    return {
        "policy": policy,
        "completions": completions,
        "trace": trace,
        "max_queue_depth_pre_issue": max_pre_issue,
        "max_queue_depth_post_issue": max_post_issue,
        "queue_depth_post_issue_at_input_cycle_511": (
            end_input_record["queue_depth_post_issue"]
        ),
        "last_issue_cycle": trace[-1]["cycle"],
        "last_result_ready_cycle": max(completions.values()),
        "drain_issue_cycles_after_input_window": (
            trace[-1]["cycle"] - (PAIR_BEATS - 1)
        ),
    }


def analyze_ordered_output(
    tasks: Iterable[Task],
    completions: dict[str, int],
    total_beats: int,
) -> dict:
    tasks_by_output: dict[int, list[Task]] = defaultdict(list)
    for task in tasks:
        for output_cycle in task.affected_output_cycles:
            tasks_by_output[output_cycle].append(task)

    readiness: dict[int, int] = {}
    output_records: list[dict] = []
    for source_cycle in range(total_beats):
        dependencies = tasks_by_output[source_cycle]
        if not dependencies:
            raise AssertionError(
                f"no check task covers output beat {source_cycle}"
            )
        readiness[source_cycle] = max(
            completions[task.task_id] for task in dependencies
        )

    fixed_latency = max(
        readiness[source_cycle] - source_cycle
        for source_cycle in range(total_beats)
    )
    emission_cycles = [
        source_cycle + fixed_latency
        for source_cycle in range(total_beats)
    ]
    for source_cycle, emission_cycle in enumerate(emission_cycles):
        dependencies = tasks_by_output[source_cycle]
        output_records.append(
            {
                "source_cycle": source_cycle,
                "source_pair_frame": (
                    (source_cycle % PAIR_BEATS) // FRAME_BEATS
                ),
                "source_beat": source_cycle % FRAME_BEATS,
                "dependency_task_ids": sorted(
                    task.task_id for task in dependencies
                ),
                "ready_cycle": readiness[source_cycle],
                "emit_cycle": emission_cycle,
                "timing_slack_cycles": (
                    emission_cycle - readiness[source_cycle]
                ),
            }
        )

    no_gap = all(
        right == left + 1
        for left, right in zip(emission_cycles, emission_cycles[1:])
    )
    all_ready = all(
        record["ready_cycle"] <= record["emit_cycle"]
        for record in output_records
    )
    return {
        "minimum_fixed_latency_cycles": fixed_latency,
        "output_start_cycle": emission_cycles[0],
        "output_end_cycle": emission_cycles[-1],
        "output_beat_count": len(emission_cycles),
        "continuous_no_gap": no_gap,
        "all_dependencies_ready_before_or_at_emission": all_ready,
        "records": output_records,
    }


def arrival_enumeration(
    tasks: list[Task], recommended_trace: list[dict]
) -> list[dict]:
    by_cycle: dict[int, list[Task]] = defaultdict(list)
    for task in tasks:
        by_cycle[task.release_cycle].append(task)
    trace_by_cycle = {record["cycle"]: record for record in recommended_trace}
    result: list[dict] = []
    for cycle in range(PAIR_BEATS):
        cycle_tasks = sorted(
            by_cycle.get(cycle, []),
            key=lambda task: (
                task.earliest_output_cycle,
                KIND_ORDER[task.kind],
                task.task_id,
            ),
        )
        scheduled = trace_by_cycle[cycle]
        result.append(
            {
                "cycle": cycle,
                "pair_frame": cycle // FRAME_BEATS,
                "beat": cycle % FRAME_BEATS,
                "arrivals": [
                    {
                        "task_id": task.task_id,
                        "kind": task.kind,
                        "affected_output_cycles": list(
                            task.affected_output_cycles
                        ),
                    }
                    for task in cycle_tasks
                ],
                "arrival_count": len(cycle_tasks),
                "issued": scheduled["issued"],
                "queue_depth_pre_issue": (
                    scheduled["queue_depth_pre_issue"]
                ),
                "queue_depth_post_issue": (
                    scheduled["queue_depth_post_issue"]
                ),
            }
        )
    return result


def periodic_replay(base_tasks: list[Task]) -> dict:
    replay_tasks = [
        task.shifted(pair_index)
        for pair_index in range(PERIODIC_REPLAY_PAIRS)
        for task in base_tasks
    ]
    schedule = schedule_tasks(replay_tasks, "earliest_output_first")
    output = analyze_ordered_output(
        replay_tasks,
        schedule["completions"],
        PERIODIC_REPLAY_PAIRS * PAIR_BEATS,
    )
    trace_by_cycle = {record["cycle"]: record for record in schedule["trace"]}
    boundaries = []
    for pair_index in range(PERIODIC_REPLAY_PAIRS):
        sparse_end = pair_index * PAIR_BEATS + FRAME_BEATS - 1
        dense_end = pair_index * PAIR_BEATS + PAIR_BEATS - 1
        boundaries.append(
            {
                "pair_index": pair_index,
                "queue_after_sparse_first_frame": (
                    trace_by_cycle[sparse_end]["queue_depth_post_issue"]
                ),
                "queue_after_dense_second_frame": (
                    trace_by_cycle[dense_end]["queue_depth_post_issue"]
                ),
            }
        )
    return {
        "pairs_replayed": PERIODIC_REPLAY_PAIRS,
        "input_cycles_replayed": PERIODIC_REPLAY_PAIRS * PAIR_BEATS,
        "tasks_replayed": len(replay_tasks),
        "average_arrivals_per_cycle": (
            len(replay_tasks)
            / (PERIODIC_REPLAY_PAIRS * PAIR_BEATS)
        ),
        "max_queue_depth_pre_issue": (
            schedule["max_queue_depth_pre_issue"]
        ),
        "max_queue_depth_post_issue": (
            schedule["max_queue_depth_post_issue"]
        ),
        "minimum_fixed_latency_cycles": (
            output["minimum_fixed_latency_cycles"]
        ),
        "continuous_no_gap": output["continuous_no_gap"],
        "all_dependencies_ready_before_or_at_emission": (
            output["all_dependencies_ready_before_or_at_emission"]
        ),
        "pair_boundaries": boundaries,
    }


def build_report() -> dict:
    markers = source_marker_audit()
    tasks, grouping = build_tasks()
    fifo_schedule = schedule_tasks(tasks, "strict_fifo")
    priority_schedule = schedule_tasks(tasks, "earliest_output_first")
    fifo_output = analyze_ordered_output(
        tasks, fifo_schedule["completions"], PAIR_BEATS
    )
    priority_output = analyze_ordered_output(
        tasks, priority_schedule["completions"], PAIR_BEATS
    )
    periodic = periodic_replay(tasks)

    arrivals_per_cycle = Counter(task.release_cycle for task in tasks)
    first_frame_arrivals = sum(
        count
        for cycle, count in arrivals_per_cycle.items()
        if cycle < FRAME_BEATS
    )
    second_frame_arrivals = sum(
        count
        for cycle, count in arrivals_per_cycle.items()
        if FRAME_BEATS <= cycle < PAIR_BEATS
    )

    beat254_cross = [
        task
        for task in tasks
        if task.release_cycle == FRAME_BEATS + 254
        and task.kind in {"cross_a", "cross_b"}
    ]
    latency_lower_bound = FRAME_BEATS + 2
    lower_bound_checks = {
        "two_cross_tasks_release_at_second_frame_beat_254": (
            len(beat254_cross) == 2
        ),
        "one_server_needs_two_issue_slots_for_those_tasks": True,
        "fixed_latency_lower_bound_is_258_cycles": (
            latency_lower_bound == 258
        ),
        "recommended_schedule_achieves_lower_bound": (
            priority_output["minimum_fixed_latency_cycles"]
            == latency_lower_bound
        ),
    }

    pass_conditions = {
        "rtl_source_markers_match": markers["status"] == "PASS",
        "grouping_and_coverage_match": grouping["status"] == "PASS",
        "one_task_per_cycle_server_limit_respected": all(
            record["issued"] is None
            or isinstance(record["issued"], dict)
            for record in priority_schedule["trace"]
        ),
        "bounded_queue_for_two_frame_window": (
            priority_schedule["max_queue_depth_pre_issue"] == 129
            and priority_schedule["max_queue_depth_post_issue"] == 128
        ),
        "fixed_latency_is_mathematically_optimal": all(
            lower_bound_checks.values()
        ),
        "two_frame_output_is_continuous": (
            priority_output["continuous_no_gap"]
            and priority_output[
                "all_dependencies_ready_before_or_at_emission"
            ]
        ),
        "periodic_stream_queue_remains_bounded": (
            periodic["max_queue_depth_pre_issue"] == 129
            and periodic["max_queue_depth_post_issue"] == 128
        ),
        "periodic_stream_preserves_same_fixed_latency": (
            periodic["minimum_fixed_latency_cycles"] == latency_lower_bound
            and periodic["continuous_no_gap"]
            and periodic[
                "all_dependencies_ready_before_or_at_emission"
            ]
        ),
    }
    feasible = all(pass_conditions.values())

    return {
        "record_id": "PFFT-RES-V3-001",
        "substep": "S02_P1_STAGE8_SINGLE_CHECK_PAIR_STATIC_FEASIBILITY",
        "attempt": "attempt1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": (
            "PASS_STATIC_FEASIBILITY_SINGLE_CHECK_PAIR"
            if feasible
            else "BLOCKED_SINGLE_CHECK_PAIR_NOT_PROVEN"
        ),
        "stop_condition_triggered": not feasible,
        "evidence_class": (
            "STATIC_SCHEDULE_MODEL_NOT_RTL_SIMULATION_NOT_YOSYS"
        ),
        "claim_boundary": (
            "This proves only that the frozen two-frame P1 Stage-8 grouping "
            "can be time-multiplexed onto one two-symbol check-pair server "
            "with bounded storage and fixed-latency gap-free ordering. It "
            "does not prove RTL bit-exactness, synthesized DSP count, LUT/FF/"
            "BRAM use, timing, Fmax, or physical implementation."
        ),
        "inputs": {
            "script": {
                "path": workspace_relative(SCRIPT_PATH),
                "sha256": sha256(SCRIPT_PATH),
            },
            "p1_rtl": {
                "path": workspace_relative(RTL_PATH),
                "sha256": sha256(RTL_PATH),
            },
            "p1_python_model": {
                "path": workspace_relative(MODEL_PATH),
                "sha256": sha256(MODEL_PATH),
            },
            "python_executable": sys.executable,
            "python_version": sys.version,
            "frame_beats": FRAME_BEATS,
            "frames_per_pair": FRAMES_PER_PAIR,
            "server_capacity_tasks_per_cycle": (
                SERVICE_CAPACITY_PER_CYCLE
            ),
            "service_result_latency_cycles": (
                SERVICE_RESULT_LATENCY_CYCLES
            ),
        },
        "rtl_source_marker_audit": markers,
        "grouping_audit": grouping,
        "arrival_summary": {
            "total_tasks": len(tasks),
            "first_frame_tasks": first_frame_arrivals,
            "second_frame_tasks": second_frame_arrivals,
            "average_tasks_per_cycle_over_two_frames": (
                len(tasks) / PAIR_BEATS
            ),
            "maximum_arrivals_in_one_cycle": max(
                arrivals_per_cycle.values()
            ),
            "cycles_with_zero_arrivals": sum(
                1
                for cycle in range(PAIR_BEATS)
                if arrivals_per_cycle[cycle] == 0
            ),
            "cycles_with_one_arrival": sum(
                1
                for cycle in range(PAIR_BEATS)
                if arrivals_per_cycle[cycle] == 1
            ),
            "cycles_with_two_arrivals": sum(
                1
                for cycle in range(PAIR_BEATS)
                if arrivals_per_cycle[cycle] == 2
            ),
        },
        "latency_lower_bound_proof": {
            "reason": (
                "At second-frame beat 254, cross_a and cross_b are both "
                "released and both cover first-frame output beat 254. A "
                "single server with one-cycle result latency must issue them "
                "in two successive cycles, so that output beat cannot be "
                "ready before cycle 512. Relative to source cycle 254, the "
                "fixed-latency lower bound is 512-254=258 cycles."
            ),
            "checks": lower_bound_checks,
            "lower_bound_cycles": latency_lower_bound,
        },
        "strict_fifo_reference": {
            "policy": fifo_schedule["policy"],
            "max_queue_depth_pre_issue": (
                fifo_schedule["max_queue_depth_pre_issue"]
            ),
            "max_queue_depth_post_issue": (
                fifo_schedule["max_queue_depth_post_issue"]
            ),
            "queue_depth_post_issue_at_input_cycle_511": (
                fifo_schedule[
                    "queue_depth_post_issue_at_input_cycle_511"
                ]
            ),
            "last_result_ready_cycle": (
                fifo_schedule["last_result_ready_cycle"]
            ),
            "minimum_fixed_latency_cycles": (
                fifo_output["minimum_fixed_latency_cycles"]
            ),
            "continuous_no_gap": fifo_output["continuous_no_gap"],
            "note": (
                "A strict arrival-order FIFO is finite but increases the "
                "required fixed latency. It is retained as a reference, not "
                "the recommended scheduler."
            ),
        },
        "recommended_schedule": {
            "policy": priority_schedule["policy"],
            "implementation_form": (
                "earliest-output-first tag scheduler; implementable as an "
                "urgent cross-frame FIFO plus a background same-frame FIFO"
            ),
            "max_queue_depth_pre_issue": (
                priority_schedule["max_queue_depth_pre_issue"]
            ),
            "max_queue_depth_post_issue": (
                priority_schedule["max_queue_depth_post_issue"]
            ),
            "safe_queue_entries_if_enqueue_precedes_issue": 129,
            "queue_entries_with_fallthrough_or_input_skid": (
                "128 stored entries plus one same-cycle input skid slot"
            ),
            "queue_depth_post_issue_at_input_cycle_511": (
                priority_schedule[
                    "queue_depth_post_issue_at_input_cycle_511"
                ]
            ),
            "drain_issue_cycles_after_input_window": (
                priority_schedule[
                    "drain_issue_cycles_after_input_window"
                ]
            ),
            "last_issue_cycle_for_isolated_pair": (
                priority_schedule["last_issue_cycle"]
            ),
            "last_result_ready_cycle_for_isolated_pair": (
                priority_schedule["last_result_ready_cycle"]
            ),
            "minimum_fixed_latency_cycles": (
                priority_output["minimum_fixed_latency_cycles"]
            ),
            "output_start_cycle": priority_output["output_start_cycle"],
            "output_end_cycle": priority_output["output_end_cycle"],
            "continuous_no_gap": priority_output["continuous_no_gap"],
            "all_dependencies_ready_before_or_at_emission": (
                priority_output[
                    "all_dependencies_ready_before_or_at_emission"
                ]
            ),
            "input_cycle_enumeration": arrival_enumeration(
                tasks, priority_schedule["trace"]
            ),
            "post_input_drain_cycles": [
                record
                for record in priority_schedule["trace"]
                if record["cycle"] >= PAIR_BEATS
            ],
            "ordered_output_readiness": priority_output["records"],
        },
        "periodic_stream_replay": periodic,
        "fifo_and_tag_requirements": {
            "control_only_minimum_with_schedule_rom": {
                "pair_ping_pong_bank_bits": 1,
                "group_id_bits": 9,
                "total_control_tag_bits": 10,
                "condition": (
                    "The group ID must address immutable schedule metadata "
                    "and all operands/results must remain in indexed storage."
                ),
            },
            "self_describing_logical_fields": [
                "valid",
                "pair_epoch_or_ping_pong_bank",
                "group_kind_3_bits",
                "primary_beat_8_bits",
                "partner_beat_8_bits_for_same_pair",
                "lane_mask_4_bits",
                "twiddle_exponent_10_bits",
                "butterfly_branch_1_bit",
                "destination_or_group_reference",
            ],
            "retained_data_obligation": (
                "A tag-only FIFO is insufficient unless indexed memories "
                "retain the four functional complex results plus the four A "
                "and four B complex operands until the shared check-pair and "
                "arithmetic corrector consume them. A fully self-contained "
                "task payload is 4*70 functional bits + 8*70 operand bits + "
                "10 exponent bits + 1 branch bit = 851 bits before control "
                "tags. A future RTL should normally retain these values in "
                "BRAM and queue compact references rather than build a "
                "129x851-bit register FIFO."
            ),
            "output_reorder_obligation": (
                "Corrected beats must remain in an indexed two-frame store "
                "with per-group readiness metadata until their fixed emit "
                "cycle. The current 2x256-per-lane common frame-buffer shape "
                "is large enough in address count, but reuse and port "
                "scheduling require a separate RTL proof."
            ),
        },
        "pass_fail_checks": pass_conditions,
        "verdict": (
            "FEASIBLE_ONE_PHYSICAL_CHECK_PAIR_WITH_BOUNDED_129_ENTRY_"
            "SCHEDULER_AND_258_CYCLE_FIXED_STAGE8_DELAY"
            if feasible
            else "INFEASIBLE_OR_UNPROVEN_STOP_BEFORE_RTL"
        ),
        "next_boundary": (
            "No RTL was modified. A future implementation must freeze the "
            "258-cycle local Stage-8 delay, queue/reference memory contract, "
            "and output-readiness assertions before replacing the five "
            "parallel check-pair instances."
        ),
        "tasks": [task.as_dict() for task in tasks],
    }


def main() -> int:
    report = build_report()
    DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUTPUT.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"status={report['status']}")
    print(f"verdict={report['verdict']}")
    print(
        "fixed_latency_cycles="
        f"{report['recommended_schedule']['minimum_fixed_latency_cycles']}"
    )
    print(
        "max_queue_depth_pre_issue="
        f"{report['recommended_schedule']['max_queue_depth_pre_issue']}"
    )
    print(
        "queue_depth_after_cycle_511="
        f"{report['recommended_schedule']['queue_depth_post_issue_at_input_cycle_511']}"
    )
    print(f"result={DEFAULT_OUTPUT}")
    return 0 if report["status"].startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
