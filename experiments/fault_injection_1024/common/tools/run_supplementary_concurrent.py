#!/usr/bin/env python3
"""SUPP-CONC-V1-001: multi-stage concurrent in-model fault experiment.

Contract: experiments/fault_injection_1024/SUPPLEMENTARY_FAULT_EXPERIMENTS_V1.md
(FROZEN / AUTHOR_APPROVED_2026-07-26).

Scenarios (1,096 rows total):
  S3   : 45 stage pairs x4 variants + {3,5,8} x4 + all-10 x4      = 188
  P1   : same structure over its stage map                          = 188
  S1   : same-path double (45x4) + cross-path double (45x4)         = 360
  S2   : 45 stage pairs x4, one replica effect per stage            = 180
  P2   : same as S2                                                 = 180

No frozen artifact is modified; results are written only to
results/supp_concurrent_v1_001/.
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
    ZERO,
    classic_r2sdf_fft,
    generate_frame,
    pfft_1024,
    pfft_no_exchange_1024,
    subfft_1024,
)
from common.python.protection import (  # noqa: E402
    arithmetic_643_decode,
    flip_component_bit,
    gao_743_capture_residual,
    gao_743_decode,
    gao_743_encode,
    tmr_vote,
)
from projects.S3.run_s3 import build_operator_groups as s3_groups  # noqa: E402
from projects.P1.run_p1 import (  # noqa: E402
    direct_operator_groups as p1_direct_groups,
    stage10_operator_groups as p1_stage10_groups,
)

EXPERIMENT_ID = "SUPP-CONC-V1-001"
CONFIG_DIR = EXPERIMENT_DIR / "config"
LEGACY_PATH = CONFIG_DIR / "legacy_protected_trial_set.json"
RESULTS_DIR = EXPERIMENT_DIR / "results" / "supp_concurrent_v1_001"
RAW_PATH = RESULTS_DIR / "supp_concurrent_raw.csv"
SUMMARY_PATH = RESULTS_DIR / "supp_concurrent_summary.json"

VARIANTS = ((0, "real"), (0, "imag"), (34, "real"), (34, "imag"))
FIELDS = [
    "experiment_id", "architecture", "scenario", "stages", "variant_bit",
    "variant_component", "per_stage_outcome", "expected_class",
    "final_match", "pass_fail",
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


def inject_ecc_group(group, stage: int, bit: int, component: str) -> tuple[bool, str]:
    """Single in-model symbol effect at this stage's decoder input."""
    symbol = stage % 4  # deterministic functional-symbol choice
    received = list(group.outputs)
    received[symbol] = flip_component_bit(received[symbol], component, bit)
    decoded = arithmetic_643_decode(received, group.expected_residual)
    ok = (
        decoded.detected
        and decoded.corrected
        and decoded.location == symbol
        and decoded.functional == group.functional
    )
    return ok, f"ecc:sym{symbol}:{'ok' if ok else 'FAIL'}"


def inject_tmr_stage(golden, stage: int, bit: int, component: str) -> tuple[bool, str]:
    replica = stage % 3
    copies = [golden, golden, golden]
    copies[replica] = flip_component_bit(golden, component, bit)
    voted, detected = tmr_vote(copies)
    ok = detected and voted == golden
    return ok, f"tmr:rep{replica}:{'ok' if ok else 'FAIL'}"


def rows_for_map(architecture, stage_effect, scenarios, writer, counter):
    """stage_effect(stage, bit, comp) -> (ok, note)."""
    for scenario_name, stage_sets in scenarios:
        for stages in stage_sets:
            for bit, comp in VARIANTS:
                outcomes = [stage_effect(s, bit, comp) for s in stages]
                all_ok = all(ok for ok, _ in outcomes)
                writer.writerow({
                    "experiment_id": EXPERIMENT_ID,
                    "architecture": architecture,
                    "scenario": scenario_name,
                    "stages": "+".join(str(s) for s in stages),
                    "variant_bit": bit,
                    "variant_component": comp,
                    "per_stage_outcome": ";".join(note for _, note in outcomes),
                    "expected_class": "concurrent_in_model_all_recovered",
                    "final_match": int(all_ok),
                    "pass_fail": "PASS" if all_ok else "FAIL",
                })
                counter["total"] += 1
                counter["pass" if all_ok else "fail"] += 1


def build_s1_paths(frame):
    lanes = [[frame[4 * sample + lane] for sample in range(256)] for lane in range(4)]
    coded = [[ZERO for _ in range(256)] for _ in range(7)]
    for sample in range(256):
        word = gao_743_encode([lanes[lane][sample] for lane in range(4)])
        for path in range(7):
            coded[path][sample] = word[path]
    outputs = [classic_r2sdf_fft(path)[0].output for path in coded]
    sample = 0
    codeword = tuple(outputs[path][sample] for path in range(7))
    residual = gao_743_capture_residual(codeword)
    expected = tuple(outputs[index][sample] for index in (2, 4, 5, 6))
    return codeword, residual, expected


def s1_bits(stage_a: int, stage_b: int, offset: int) -> tuple[int, int]:
    bit1 = (2 * stage_a + offset) % 35
    bit2 = (2 * stage_b + 1 + offset) % 35
    if bit2 == bit1:
        bit2 = (bit2 + 1) % 35
    return bit1, bit2


def run_campaign(writer):
    counter = {"total": 0, "pass": 0, "fail": 0}
    frame_id, frame = load_frame()

    pair_sets = list(itertools.combinations(range(1, 11), 2))
    scenarios = [
        ("stage_pair", pair_sets),
        ("paper_example_3_5_8", [(3, 5, 8)]),
        ("all_ten_stages", [tuple(range(1, 11))]),
    ]

    # ---- S3: stages 1-8 ECC groups (position 0), stages 9-10 TMR ----
    sub_result = subfft_1024(frame)
    s3g = s3_groups(frame, [0])

    def s3_effect(stage, bit, comp):
        if stage <= 8:
            return inject_ecc_group(s3g[stage][0], stage, bit, comp)
        return inject_tmr_stage(sub_result.stages[stage - 1].values[0], stage, bit, comp)

    rows_for_map("S3", s3_effect, scenarios, writer, counter)

    # ---- P1: stages 1-7 ECC, 8-9 TMR, 10 two-beat ECC (group 0 upper) ----
    p_result = pfft_1024(frame)
    p1g = p1_direct_groups(frame, range(1, 8), [0])
    stage10_upper, _ = p1_stage10_groups(frame)[0]

    def p1_effect(stage, bit, comp):
        if stage <= 7:
            return inject_ecc_group(p1g[stage][0], stage, bit, comp)
        if stage <= 9:
            return inject_tmr_stage(p_result.stages[stage - 1].values[0], stage, bit, comp)
        return inject_ecc_group(stage10_upper, stage, bit, comp)

    rows_for_map("P1", p1_effect, scenarios, writer, counter)

    # ---- S1: Gao path ECC at the stage-8 path boundary ----
    codeword, residual, expected = build_s1_paths(frame)

    for stage_a, stage_b in pair_sets:
        for offset, comp in ((0, "real"), (0, "imag"), (17, "real"), (17, "imag")):
            bit1, bit2 = s1_bits(stage_a, stage_b, offset)

            # same-path double: both upstream effects confined to path 2
            received = list(codeword)
            received[2] = flip_component_bit(received[2], comp, bit1)
            received[2] = flip_component_bit(received[2], comp, bit2)
            decoded = gao_743_decode(received, residual)
            ok = decoded.detected and decoded.corrected and decoded.functional == expected
            writer.writerow({
                "experiment_id": EXPERIMENT_ID,
                "architecture": "S1",
                "scenario": "same_path_double",
                "stages": f"{stage_a}+{stage_b}",
                "variant_bit": f"{bit1}+{bit2}",
                "variant_component": comp,
                "per_stage_outcome": f"path2:{'corrected' if ok else 'FAIL'}",
                "expected_class": "single_path_confined_correctable",
                "final_match": int(ok),
                "pass_fail": "PASS" if ok else "FAIL",
            })
            counter["total"] += 1
            counter["pass" if ok else "fail"] += 1

            # cross-path double: effects on functional paths 2 and 4
            received = list(codeword)
            received[2] = flip_component_bit(received[2], comp, bit1)
            received[4] = flip_component_bit(received[4], comp, bit2)
            decoded = gao_743_decode(received, residual)
            honest = decoded.detected and not decoded.corrected
            writer.writerow({
                "experiment_id": EXPERIMENT_ID,
                "architecture": "S1",
                "scenario": "cross_path_double",
                "stages": f"{stage_a}+{stage_b}",
                "variant_bit": f"{bit1}+{bit2}",
                "variant_component": comp,
                "per_stage_outcome": (
                    "detected_uncorrectable" if honest else
                    ("miscorrected" if decoded.corrected else "silent")
                ),
                "expected_class": "beyond_path_level_capability",
                "final_match": int(decoded.functional == expected),
                "pass_fail": "PASS" if honest else "FAIL",
            })
            counter["total"] += 1
            counter["pass" if honest else "fail"] += 1

    # ---- S2 / P2: full-stage TMR, one replica effect per stage ----
    p2_result = pfft_no_exchange_1024(frame)
    for architecture, result in (("S2", sub_result), ("P2", p2_result)):
        def tmr_effect(stage, bit, comp, _result=result):
            return inject_tmr_stage(_result.stages[stage - 1].values[0], stage, bit, comp)

        rows_for_map(architecture, tmr_effect, [("stage_pair", pair_sets)], writer, counter)

    return frame_id, counter


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
        frame_id, counter = run_campaign(writer)
    raw_hash = sha256_file(RAW_PATH)

    sink = HashWriter()
    replay_writer = csv.DictWriter(sink, fieldnames=FIELDS, lineterminator="\n")
    replay_writer.writeheader()
    _, replay_counter = run_campaign(replay_writer)
    replay_hash = sink.digest.hexdigest().upper()

    expected_total = 188 + 188 + 360 + 180 + 180
    deterministic = raw_hash == replay_hash and counter == replay_counter
    status = (
        "VERIFIED"
        if deterministic and counter["total"] == expected_total and counter["fail"] == 0
        else "COMPLETED_WITH_FINDINGS" if deterministic and counter["total"] == expected_total
        else "FAILED"
    )
    summary = {
        "experiment_id": EXPERIMENT_ID,
        "contract": "SUPPLEMENTARY_FAULT_EXPERIMENTS_V1.md",
        "status": status,
        "fault_frame": frame_id,
        "expected_total": expected_total,
        "counts": counter,
        "determinism": {
            "raw_sha256": raw_hash,
            "replay_sha256": replay_hash,
            "pass": deterministic,
        },
        "scenario_design": {
            "S3": "45 pairs + {3,5,8} + all-10, x4 variants (bits 0/34, re/im)",
            "P1": "same as S3 over stages 1-7 ECC / 8-9 TMR / 10 two-beat ECC",
            "S1_same_path": "double effect confined to path 2 -> correctable",
            "S1_cross_path": "effects on paths 2 and 4 -> must reject, never misclaim",
            "S2_P2": "one replica effect per stage, 45 pairs x4",
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
        "total": counter["total"],
        "pass": counter["pass"],
        "fail": counter["fail"],
        "raw_sha256": raw_hash[:16],
        "deterministic": deterministic,
    }, sort_keys=True))
    return 0 if status == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
