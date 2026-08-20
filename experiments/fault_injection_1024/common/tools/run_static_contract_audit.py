from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
WORKSPACE = EXPERIMENT_DIR.parents[1]
CONFIG_DIR = EXPERIMENT_DIR / "config"
CONTRACT = CONFIG_DIR / "seven_architecture_contract.json"
MATRIX = CONFIG_DIR / "seven_architecture_fault_matrix.json"
MEMORY = CONFIG_DIR / "seven_architecture_memory_map.json"
YOSYS = CONFIG_DIR / "yosys_resource_contract_v2.json"
LEGACY_MATRIX = CONFIG_DIR / "legacy_protected_trial_set.json"
MATRIX_MD = EXPERIMENT_DIR / "SEVEN_ARCHITECTURE_MATRIX_V1.md"
TASK_CARD = WORKSPACE / "当前实验任务卡.md"
DECISIONS = WORKSPACE / "实验决策记录.md"
OUTPUT_DIR = EXPERIMENT_DIR / "results" / "seven_arch_v2"

ARCHITECTURES = ["S0", "S1", "S2", "S3", "P0", "P1", "P2"]
SUBFFT = ["S0", "S1", "S2", "S3"]
PFFT = ["P0", "P1", "P2"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-frozen", action="store_true")
    parser.add_argument("--output-stem", default="static_contract_audit")
    args = parser.parse_args()
    if not args.output_stem.replace("_", "").isalnum():
        raise ValueError("output stem must be alphanumeric with underscores")
    output_json = OUTPUT_DIR / f"{args.output_stem}.json"
    output_md = OUTPUT_DIR / f"{args.output_stem}.md"

    files = [CONTRACT, MATRIX, MEMORY, YOSYS, LEGACY_MATRIX, MATRIX_MD, TASK_CARD, DECISIONS]
    checks: list[dict[str, object]] = []

    def check(name: str, condition: bool, evidence: object) -> None:
        checks.append({"name": name, "status": "PASS" if condition else "FAIL", "evidence": evidence})

    check("all_files_exist", all(path.is_file() for path in files), [str(path) for path in files])
    contract = load(CONTRACT)
    matrix = load(MATRIX)
    memory = load(MEMORY)
    yosys = load(YOSYS)

    expected_status = "FROZEN" if args.require_frozen else "WORKING_COPY_NOT_EXECUTED"
    statuses = {path.name: load(path)["status"] for path in [CONTRACT, MATRIX, MEMORY, YOSYS]}
    check("contract_status", all(value == expected_status for value in statuses.values()), statuses)
    check(
        "experiment_id",
        {contract["experiment_id"], matrix["experiment_id"], memory["experiment_id"], yosys["experiment_id"]}
        == {"FFT1024-SEVEN-ARCH-V2"},
        [contract["experiment_id"], matrix["experiment_id"], memory["experiment_id"], yosys["experiment_id"]],
    )
    check("architecture_order", contract["scope"]["architectures"] == ARCHITECTURES, contract["scope"]["architectures"])
    check("architecture_keys", list(contract["architectures"]) == ARCHITECTURES, list(contract["architectures"]))
    check("fault_domains", list(matrix["architecture_domains"]) == ARCHITECTURES, list(matrix["architecture_domains"]))
    check("yosys_tops", list(yosys["tops"]) == ARCHITECTURES, list(yosys["tops"]))
    check("subfft_group", yosys["comparison_groups"]["SubFFT"] == SUBFFT, yosys["comparison_groups"]["SubFFT"])
    check("pfft_group", yosys["comparison_groups"]["PFFT"] == PFFT, yosys["comparison_groups"]["PFFT"])
    check("baselines", yosys["baselines"] == {"SubFFT": "S0", "PFFT": "P0"}, yosys["baselines"])
    check(
        "latencies",
        contract["stream_contract"]["subfft_latency_cycles"] == 268
        and contract["stream_contract"]["pfft_latency_cycles"] == 525
        and contract["stream_contract"]["stage_first_token_latencies"] == [130, 65, 33, 17, 9, 5, 3, 2, 2, 2],
        contract["stream_contract"],
    )
    feedback = memory["feedback_memories"]
    check(
        "memory_policy",
        feedback[0]["depth"] == 128
        and feedback[0]["implementation"] == "block"
        and feedback[1]["depths"] == [64, 32, 16, 8, 4, 2, 1]
        and feedback[1]["implementation"] == "distributed",
        feedback,
    )
    large = memory["large_buffers"]
    check(
        "large_buffers",
        large["pfft_common_frame_reorder"]["architectures"] == PFFT
        and large["pfft_common_frame_reorder"]["implementation"] == "block"
        and large["p1_stage8_pending_symbols"]["logical_capacity_complex_words"] == 512
        and large["p1_stage8_pending_symbols"]["payload_width_bits"] == 70
        and large["p1_stage8_pending_symbols"]["secded_codeword_width_bits"] == 78
        and large["p1_stage8_pending_symbols"]["must_be_in_functional_correction_path"] is True,
        large,
    )
    check(
        "p1_stage8_exact_operator_key",
        matrix["p1_stage8_grouping_key"] == ["twiddle_exponent", "butterfly_branch"]
        and "grouped_by_twiddle_and_butterfly_branch" in contract["architectures"]["P1"]["stage_8"],
        matrix["p1_stage8_grouping_key"],
    )
    check(
        "legacy_trial_hash",
        sha256(LEGACY_MATRIX) == matrix["protected_campaign_inheritance"]["sha256"],
        {"actual": sha256(LEGACY_MATRIX), "expected": matrix["protected_campaign_inheritance"]["sha256"]},
    )
    check(
        "baseline_no_fault_only",
        matrix["architecture_domains"]["S0"]["no_fault_only"] is True
        and matrix["architecture_domains"]["P0"]["no_fault_only"] is True,
        {"S0": matrix["architecture_domains"]["S0"], "P0": matrix["architecture_domains"]["P0"]},
    )
    check(
        "p0_common_buffer",
        contract["architectures"]["P0"]["common_frame_reorder"] is True
        and contract["architectures"]["P0"]["stage8_protection_buffer"] is False,
        contract["architectures"]["P0"],
    )
    outputs = matrix["frozen_outputs"]
    check("frozen_outputs_unique", len(outputs) == len(set(outputs)) and len(outputs) == 9, outputs)

    matrix_text = MATRIX_MD.read_text(encoding="utf-8")
    task_text = TASK_CARD.read_text(encoding="utf-8")
    decision_text = DECISIONS.read_text(encoding="utf-8")
    check("matrix_markdown_ids", all(f"| {item} |" in matrix_text for item in ARCHITECTURES), ARCHITECTURES)
    task_card_markers = [
        "用户已于2026-07-21确认七对象与存储政策",
        "旧五对象资源结果只保留失败溯源",
    ]
    check(
        "task_card_gate",
        all(marker in task_text for marker in task_card_markers),
        task_card_markers,
    )
    check("decision_gate", all(f"D{number}" in decision_text for number in range(43, 48)), "D43-D47")
    check(
        "hard_failure_guards",
        set(contract["hard_failures"])
        >= {
            "check_symbols_reencoded_from_received_functional_outputs",
            "expected_residual_recomputed_from_post_fault_received_symbols",
            "p1_stage8_buffer_removed_or_not_in_corrected_data_path",
            "memory_primitive_class_differs_for_same_declared_geometry",
        },
        contract["hard_failures"],
    )

    passed = all(item["status"] == "PASS" for item in checks)
    result = {
        "experiment_id": "FFT1024-SEVEN-ARCH-V2",
        "status": "VERIFIED" if passed else "FAILED",
        "mode": "require_frozen" if args.require_frozen else "pending_freeze",
        "checks": checks,
        "files": {str(path.relative_to(EXPERIMENT_DIR)): sha256(path) for path in files if path.is_relative_to(EXPERIMENT_DIR)},
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    lines = ["# Seven-architecture static contract audit", "", f"Status: **{result['status']}**", "", "| Check | Status |", "|---|---|"]
    lines.extend(f"| {item['name']} | {item['status']} |" for item in checks)
    output_md.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": result["status"], "checks": len(checks), "json": str(output_json), "sha256": sha256(output_json)}, ensure_ascii=False))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
