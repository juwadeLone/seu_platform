#!/usr/bin/env python3
"""Generate and verify the P0/P2 canonical-DIF V3 qualification vectors.

The frozen ten-frame input contains the eight declared no-fault frames followed
by two zero padding frames.  P0 and P2 share one functional schedule, so this
tool deliberately renders their expected files from one in-memory byte string
and requires the two SHA-256 digests to be identical.  The P1 exchanged-schedule
vector is read and hashed, never rewritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
WORKSPACE = HERE.parents[3]
if str(EXPERIMENT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT))

from common.python.fixed_fft import (  # noqa: E402
    DATA_WIDTH,
    ZERO,
    bit_reverse,
    generate_frame,
    pfft_no_exchange_1024,
)


INPUT = EXPERIMENT / "common" / "vectors" / "qualification_input_10frames.hex"
P1_EXPECTED = EXPERIMENT / "common" / "vectors" / "qualification_pfft_expected_8frames.hex"
TRIALS = EXPERIMENT / "config" / "legacy_protected_trial_set.json"
MATRIX = EXPERIMENT / "config" / "seven_architecture_fault_matrix.json"
MODEL = EXPERIMENT / "common" / "python" / "fixed_fft.py"
P0_EXPECTED = (
    EXPERIMENT
    / "projects"
    / "P0"
    / "vectors"
    / "qualification_p0_no_exchange_expected_8frames.hex"
)
P2_EXPECTED = (
    EXPERIMENT
    / "projects"
    / "P2"
    / "vectors"
    / "qualification_p2_no_exchange_expected_8frames.hex"
)
MANIFEST = EXPERIMENT / "results" / "pfft_resource_v3_001" / "vector_manifest.json"

LINE_HEX_DIGITS = 8 * DATA_WIDTH // 4
EXPECTED_INPUT_LINES = 10 * 256
EXPECTED_OUTPUT_LINES = 8 * 256


def relative(path: Path) -> str:
    return path.relative_to(WORKSPACE).as_posix()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def pack_words(words: object) -> str:
    value = 0
    mask = (1 << DATA_WIDTH) - 1
    for word in words:
        for component in (word.real, word.imag):
            value = (value << DATA_WIDTH) | (component & mask)
    return f"{value:0{LINE_HEX_DIGITS}x}"


def validate_hex_lines(path: Path, expected_count: int) -> list[str]:
    lines = path.read_text(encoding="ascii").splitlines()
    if len(lines) != expected_count:
        raise RuntimeError(f"{relative(path)} has {len(lines)} lines, expected {expected_count}")
    for line_number, line in enumerate(lines, 1):
        if len(line) != LINE_HEX_DIGITS:
            raise RuntimeError(
                f"{relative(path)}:{line_number} has {len(line)} hex digits, "
                f"expected {LINE_HEX_DIGITS}"
            )
        try:
            int(line, 16)
        except ValueError as exc:
            raise RuntimeError(f"{relative(path)}:{line_number} is not hexadecimal") from exc
    return lines


def load_frames() -> tuple[list[dict[str, object]], list[tuple[str, list[object]]]]:
    trials = json.loads(TRIALS.read_text(encoding="utf-8"))
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    specs = trials["no_fault_frames"]
    declared_ids = matrix["no_fault_frames"]
    actual_ids = [spec["id"] for spec in specs]
    if actual_ids != declared_ids:
        raise RuntimeError(
            "no-fault frame order drift: "
            f"legacy_protected_trial_set={actual_ids}, seven_architecture_fault_matrix={declared_ids}"
        )
    if len(specs) != 8:
        raise RuntimeError(f"V3 requires exactly eight no-fault frames, found {len(specs)}")
    frames = [(spec["id"], generate_frame(spec)) for spec in specs]
    return specs, frames


def expected_input_text(frames: list[tuple[str, list[object]]]) -> str:
    padding = [("padding0", [ZERO] * 1024), ("padding1", [ZERO] * 1024)]
    lines: list[str] = []
    for _, frame in frames + padding:
        if len(frame) != 1024:
            raise RuntimeError("qualification frame length is not 1024")
        for beat in range(256):
            lines.append(pack_words(frame[4 * beat : 4 * beat + 4]))
    return "\n".join(lines) + "\n"


def expected_output_text(frames: list[tuple[str, list[object]]]) -> str:
    lines: list[str] = []
    for _, frame in frames:
        natural_output = pfft_no_exchange_1024(frame).output
        for beat in range(256):
            physical_indices = tuple(4 * beat + lane for lane in range(4))
            natural_indices = tuple(bit_reverse(index, 10) for index in physical_indices)
            lines.append(pack_words(tuple(natural_output[index] for index in natural_indices)))
    if len(lines) != EXPECTED_OUTPUT_LINES:
        raise RuntimeError(f"rendered {len(lines)} output beats, expected {EXPECTED_OUTPUT_LINES}")
    return "\n".join(lines) + "\n"


def build_manifest(
    specs: list[dict[str, object]],
    expected_bytes: bytes,
) -> dict[str, object]:
    p0_hash = sha256(P0_EXPECTED)
    p2_hash = sha256(P2_EXPECTED)
    rendered_hash = sha256_bytes(expected_bytes)
    if p0_hash != p2_hash or p0_hash != rendered_hash:
        raise RuntimeError(
            f"P0/P2 rendered vector hash mismatch: P0={p0_hash}, P2={p2_hash}, "
            f"in_memory={rendered_hash}"
        )
    return {
        "schema": "pfft-resource-v3-001-vector-manifest-v1",
        "status": "VERIFIED",
        "experiment_id": "PFFT-RES-V3-001",
        "model": {
            "function": "common.python.fixed_fft.pfft_no_exchange_1024",
            "path": relative(MODEL),
            "sha256": sha256(MODEL),
            "schedule": "canonical_radix2_DIF_no_exchange",
        },
        "generator": {
            "path": relative(Path(__file__).resolve()),
            "sha256": sha256(Path(__file__).resolve()),
            "python": sys.executable,
            "python_sha256": sha256(Path(sys.executable)),
        },
        "frame_contract": {
            "source": relative(TRIALS),
            "source_sha256": sha256(TRIALS),
            "order_contract": relative(MATRIX),
            "order_contract_sha256": sha256(MATRIX),
            "frame_ids": [spec["id"] for spec in specs],
            "input_frames": 10,
            "checked_output_frames": 8,
            "input_beats": EXPECTED_INPUT_LINES,
            "output_beats_per_architecture": EXPECTED_OUTPUT_LINES,
            "packed_bits_per_beat": 8 * DATA_WIDTH,
            "output_order": "natural_output[bit_reverse(4*beat+lane,10)]",
        },
        "input": {
            "path": relative(INPUT),
            "sha256": sha256(INPUT),
            "line_count": EXPECTED_INPUT_LINES,
            "matches_regenerated_eight_frames_plus_two_zero_padding_frames": True,
        },
        "outputs": {
            "P0": {
                "path": relative(P0_EXPECTED),
                "sha256": p0_hash,
                "line_count": EXPECTED_OUTPUT_LINES,
            },
            "P2": {
                "path": relative(P2_EXPECTED),
                "sha256": p2_hash,
                "line_count": EXPECTED_OUTPUT_LINES,
            },
            "P0_and_P2_byte_identical": True,
            "shared_sha256": rendered_hash,
        },
        "P1_unchanged_exchange_vector": {
            "path": relative(P1_EXPECTED),
            "sha256": sha256(P1_EXPECTED),
            "line_count": EXPECTED_OUTPUT_LINES,
            "rewritten_by_this_tool": False,
        },
    }


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="verify existing P0/P2 vectors and manifest without rewriting them",
    )
    args = parser.parse_args()

    required = (INPUT, P1_EXPECTED, TRIALS, MATRIX, MODEL)
    missing = [relative(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("missing frozen vector input: " + ", ".join(missing))

    specs, frames = load_frames()
    frozen_input_bytes = expected_input_text(frames).encode("ascii")
    if INPUT.read_bytes() != frozen_input_bytes:
        raise RuntimeError(
            "frozen qualification input does not match the declared eight frames plus "
            "two zero padding frames"
        )
    validate_hex_lines(INPUT, EXPECTED_INPUT_LINES)
    validate_hex_lines(P1_EXPECTED, EXPECTED_OUTPUT_LINES)

    rendered_bytes = expected_output_text(frames).encode("ascii")
    if args.verify_only:
        required_outputs = (P0_EXPECTED, P2_EXPECTED, MANIFEST)
        missing_outputs = [relative(path) for path in required_outputs if not path.exists()]
        if missing_outputs:
            raise FileNotFoundError("missing generated V3 vector artifact: " + ", ".join(missing_outputs))
        if P0_EXPECTED.read_bytes() != rendered_bytes or P2_EXPECTED.read_bytes() != rendered_bytes:
            raise RuntimeError("existing P0/P2 V3 vector does not match the regenerated canonical-DIF data")
        validate_hex_lines(P0_EXPECTED, EXPECTED_OUTPUT_LINES)
        validate_hex_lines(P2_EXPECTED, EXPECTED_OUTPUT_LINES)
        recorded = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest = build_manifest(specs, rendered_bytes)
        if recorded != manifest:
            raise RuntimeError("existing vector manifest does not match current frozen inputs and hashes")
        print(
            f"VECTOR_VERIFY PASS beats={EXPECTED_OUTPUT_LINES} "
            f"shared_sha256={manifest['outputs']['shared_sha256']}"
        )
        return 0

    existing = [path for path in (P0_EXPECTED, P2_EXPECTED, MANIFEST) if path.exists()]
    if existing:
        raise RuntimeError(
            "V3 vector artifact already exists; refusing implicit overwrite: "
            + ", ".join(relative(path) for path in existing)
        )

    P0_EXPECTED.parent.mkdir(parents=True, exist_ok=True)
    P2_EXPECTED.parent.mkdir(parents=True, exist_ok=True)
    P0_EXPECTED.write_bytes(rendered_bytes)
    P2_EXPECTED.write_bytes(rendered_bytes)
    validate_hex_lines(P0_EXPECTED, EXPECTED_OUTPUT_LINES)
    validate_hex_lines(P2_EXPECTED, EXPECTED_OUTPUT_LINES)
    manifest = build_manifest(specs, rendered_bytes)
    write_json(MANIFEST, manifest)
    print(
        f"VECTOR_GENERATION PASS beats={EXPECTED_OUTPUT_LINES} "
        f"shared_sha256={manifest['outputs']['shared_sha256']} manifest={relative(MANIFEST)}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"VECTOR_GENERATION FAIL type={type(exc).__name__} message={exc}", file=sys.stderr)
        raise SystemExit(1)
