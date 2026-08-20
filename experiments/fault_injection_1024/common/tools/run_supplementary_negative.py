#!/usr/bin/env python3
"""SUPP-NEG-V1-001: systematic out-of-model negative enumeration.

Contract: experiments/fault_injection_1024/SUPPLEMENTARY_FAULT_EXPERIMENTS_V1.md
(FROZEN / AUTHOR_APPROVED_2026-07-26).

Row classes (7,666 rows total):
  ecc_double_symbol : 8 groups x 15 symbol pairs x 4 bit patterns x 2 comps = 960
  secded_double_bit : C(78,2)=3,003 pairs x 2 protected words               = 6,006
  tmr_double_replica: 70 bits x 10 (arch,stage) combos                      = 700

Outcome taxonomy (reported, not gated except where theory guarantees):
  detected_uncorrectable / miscorrected / corrected_benign / silent /
  wrong_output_disagreement_flag (TMR).
PASS gates: count closure, deterministic replay, SECDED zero miscorrection
and zero silence. The ECC distribution itself is a reported result.
Author decision 2026-07-26: ECC miscorrection counts stay out of the
manuscript for now (internal evidence only).
"""

from __future__ import annotations

import csv
import hashlib
import itertools
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
EXPERIMENT_DIR = SCRIPT_DIR.parents[1]
if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

from common.python.fixed_fft import (  # noqa: E402
    generate_frame,
    pfft_1024,
    pfft_no_exchange_1024,
    subfft_1024,
)
from common.python.protection import (  # noqa: E402
    MEMORY_CODEWORD_BITS,
    arithmetic_643_decode,
    flip_component_bit,
    secded_decode,
    secded_encode_complex,
    tmr_vote,
)
from projects.S3.run_s3 import build_operator_groups as s3_groups  # noqa: E402
from projects.P1.run_p1 import (  # noqa: E402
    direct_operator_groups as p1_direct_groups,
    stage10_operator_groups as p1_stage10_groups,
)

EXPERIMENT_ID = "SUPP-NEG-V1-001"
CONFIG_DIR = EXPERIMENT_DIR / "config"
LEGACY_PATH = CONFIG_DIR / "legacy_protected_trial_set.json"
RESULTS_DIR = EXPERIMENT_DIR / "results" / "supp_negative_v1_001"
RAW_PATH = RESULTS_DIR / "supp_negative_raw.csv"
SUMMARY_PATH = RESULTS_DIR / "supp_negative_summary.json"

BIT_PATTERNS = ((0, 0), (0, 34), (17, 17), (34, 34))
FIELDS = [
    "experiment_id", "category", "architecture", "object", "symbols_or_bits",
    "bit_pattern", "component", "cross_beat_tag", "detected", "corrected",
    "functional_match", "classification",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_frame():
    legacy = json.loads(LEGACY_PATH.read_text(encoding="utf-8"))
    specs = {item["id"]: item for item in legacy["no_fault_frames"]}
    frame_id = legacy["fault_frames"][0]
    return frame_id, generate_frame(specs[frame_id])


def classify_ecc(decoded, golden_functional):
    functional_match = decoded.functional == golden_functional
    if not decoded.detected:
        return "silent_benign" if functional_match else "silent"
    if decoded.corrected:
        return "corrected_benign" if functional_match else "miscorrected"
    return "detected_uncorrectable"


def run_campaign(writer):
    counts: dict[str, dict[str, int]] = {}

    def bump(category: str, classification: str):
        bucket = counts.setdefault(category, {})
        bucket[classification] = bucket.get(classification, 0) + 1
        bucket["_total"] = bucket.get("_total", 0) + 1

    frame_id, frame = load_frame()

    # ---- category 1: ECC double-symbol -------------------------------
    sub_g = s3_groups(frame, [0])
    p1_g = p1_direct_groups(frame, range(1, 8), [0])
    st10_upper, st10_lower = p1_stage10_groups(frame)[0]
    ecc_objects = (
        [("S3", f"stage{stage}_pos0", sub_g[stage][0], False) for stage in (1, 4, 8)]
        + [("P1", f"stage{stage}_beat0", p1_g[stage][0], False) for stage in (1, 4, 7)]
        + [("P1", "stage10_pair0_upper", st10_upper, True),
           ("P1", "stage10_pair0_lower", st10_lower, True)]
    )
    for architecture, obj_name, group, is_stage10 in ecc_objects:
        for sym_a, sym_b in itertools.combinations(range(6), 2):
            for bit_a, bit_b in BIT_PATTERNS:
                for comp in ("real", "imag"):
                    received = list(group.outputs)
                    received[sym_a] = flip_component_bit(received[sym_a], comp, bit_a)
                    received[sym_b] = flip_component_bit(received[sym_b], comp, bit_b)
                    decoded = arithmetic_643_decode(received, group.expected_residual)
                    cls = classify_ecc(decoded, group.functional)
                    cross = is_stage10 and sym_a < 4 and sym_b < 4
                    writer.writerow({
                        "experiment_id": EXPERIMENT_ID,
                        "category": "ecc_double_symbol",
                        "architecture": architecture,
                        "object": obj_name,
                        "symbols_or_bits": f"{sym_a}+{sym_b}",
                        "bit_pattern": f"{bit_a}+{bit_b}",
                        "component": comp,
                        "cross_beat_tag": int(cross),
                        "detected": int(decoded.detected),
                        "corrected": int(decoded.corrected),
                        "functional_match": int(decoded.functional == group.functional),
                        "classification": cls,
                    })
                    bump("ecc_double_symbol", cls)
                    if cross:
                        bump("stage10_cross_beat_subset", cls)

    # ---- category 2: SECDED double-bit full enumeration ---------------
    sub_result = subfft_1024(frame)
    p_result = pfft_1024(frame)
    secded_objects = (
        ("S3", "stage1_word_pos0", sub_result.stages[0].values[0]),
        ("P1", "stage1_word_pos0", p_result.stages[0].values[0]),
    )
    for architecture, obj_name, golden in secded_objects:
        encoded = secded_encode_complex(golden)
        for bit_a, bit_b in itertools.combinations(range(MEMORY_CODEWORD_BITS), 2):
            decoded = secded_decode(encoded ^ (1 << bit_a) ^ (1 << bit_b))
            match = decoded.complex_word == golden
            if not decoded.detected:
                cls = "silent_benign" if match else "silent"
            elif decoded.corrected:
                cls = "corrected_benign" if match else "miscorrected"
            else:
                cls = "detected_uncorrectable"
            writer.writerow({
                "experiment_id": EXPERIMENT_ID,
                "category": "secded_double_bit",
                "architecture": architecture,
                "object": obj_name,
                "symbols_or_bits": f"{bit_a}+{bit_b}",
                "bit_pattern": "codeword_bits",
                "component": "",
                "cross_beat_tag": 0,
                "detected": int(decoded.detected),
                "corrected": int(decoded.corrected),
                "functional_match": int(match),
                "classification": cls,
            })
            bump("secded_double_bit", cls)

    # ---- category 3: TMR double-replica same-bit ----------------------
    p2_result = pfft_no_exchange_1024(frame)
    tmr_objects = (
        [("S2", stage, sub_result) for stage in (1, 5, 10)]
        + [("P2", stage, p2_result) for stage in (1, 5, 10)]
        + [("S3", stage, sub_result) for stage in (9, 10)]
        + [("P1", stage, p_result) for stage in (8, 9)]
    )
    for architecture, stage, result in tmr_objects:
        golden = result.stages[stage - 1].values[0]
        for comp in ("real", "imag"):
            for bit in range(35):
                flipped = flip_component_bit(golden, comp, bit)
                voted, detected = tmr_vote([flipped, flipped, golden])
                match = voted == golden
                if match:
                    cls = "masked_unexpectedly"
                else:
                    cls = (
                        "wrong_output_disagreement_flag"
                        if detected else "silent"
                    )
                writer.writerow({
                    "experiment_id": EXPERIMENT_ID,
                    "category": "tmr_double_replica",
                    "architecture": architecture,
                    "object": f"stage{stage}_pos0",
                    "symbols_or_bits": "replica0+replica1",
                    "bit_pattern": str(bit),
                    "component": comp,
                    "cross_beat_tag": 0,
                    "detected": int(detected),
                    "corrected": 0,
                    "functional_match": int(match),
                    "classification": cls,
                })
                bump("tmr_double_replica", cls)

    return frame_id, counts


class HashWriter:
    def __init__(self):
        self.digest = hashlib.sha256()

    def write(self, text: str) -> int:
        self.digest.update(text.encode("utf-8"))
        return len(text)


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with RAW_PATH.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        frame_id, counts = run_campaign(writer)
    raw_hash = sha256_file(RAW_PATH)

    sink = HashWriter()
    replay_writer = csv.DictWriter(sink, fieldnames=FIELDS, lineterminator="\n")
    replay_writer.writeheader()
    _, replay_counts = run_campaign(replay_writer)
    replay_hash = sink.digest.hexdigest().upper()

    expected = {"ecc_double_symbol": 960, "secded_double_bit": 6006, "tmr_double_replica": 700}
    deterministic = raw_hash == replay_hash and counts == replay_counts
    count_ok = all(
        counts.get(category, {}).get("_total", 0) == total
        for category, total in expected.items()
    )
    secded_bucket = counts.get("secded_double_bit", {})
    secded_ok = (
        secded_bucket.get("miscorrected", 0) == 0
        and secded_bucket.get("silent", 0) == 0
        and secded_bucket.get("silent_benign", 0) == 0
    )
    status = (
        "VERIFIED"
        if deterministic and count_ok and secded_ok
        else "FAILED"
    )
    summary = {
        "experiment_id": EXPERIMENT_ID,
        "contract": "SUPPLEMENTARY_FAULT_EXPERIMENTS_V1.md",
        "status": status,
        "fault_frame": frame_id,
        "expected_counts": expected,
        "outcome_distribution": counts,
        "pass_gates": {
            "count_closure": count_ok,
            "secded_zero_miscorrection_zero_silence": secded_ok,
            "deterministic_replay": deterministic,
        },
        "reporting_note": (
            "ECC double-symbol distribution is a reported result, not a pass "
            "gate; per author decision 2026-07-26 it stays out of the "
            "manuscript for now (internal evidence)."
        ),
        "determinism": {
            "raw_sha256": raw_hash,
            "replay_sha256": replay_hash,
            "pass": deterministic,
        },
        "script_sha256": sha256_file(Path(__file__).resolve()),
        "legacy_matrix_sha256": sha256_file(LEGACY_PATH),
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({
        "status": status,
        "counts": {k: v.get("_total") for k, v in counts.items()},
        "distribution": {
            k: {c: n for c, n in v.items() if c != "_total"}
            for k, v in counts.items()
        },
        "deterministic": deterministic,
    }, sort_keys=True))
    return 0 if status == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
