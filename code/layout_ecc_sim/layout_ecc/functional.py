"""WP2 wrapper around the frozen P1 Python injector.

Does not modify ``experiments/fault_injection_1024``. Imports that tree
read-only and records golden hashes under ``data/golden/``.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PKG = _HERE.parent
_GOLDEN_DIR = _PKG / "data" / "golden"
_EXP = _PKG.parents[1] / "experiments" / "fault_injection_1024"
if str(_EXP) not in sys.path:
    sys.path.insert(0, str(_EXP))

from common.python.fixed_fft import (  # noqa: E402
    bit_reverse_order,
    exchange_phi,
    exchanged_dif_stage,
    generate_frame,
    pfft_1024,
    serialize_words,
)
from common.python.protection import (  # noqa: E402
    arithmetic_643_decode,
    flip_component_bit,
    secded_decode,
    secded_encode_complex,
    tmr_vote,
)
from projects.P1.run_p1 import (  # noqa: E402
    independent_operator_group,
    operator_input,
    pfft_stage_inputs,
    stage10_operator_groups,
)
from .lifetime import map_cycle, masked_by_lifetime

FRAME_SPEC = {
    "id": "random_seeded",
    "generator": "uniform_random",
    "min": -1048576,
    "max": 1048575,
    "seed": 20260721,
}
THRESHOLD_LO, THRESHOLD_HI = 2, 3


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest().upper()


def ensure_golden(directory=None):
    """Write (or reuse) the frozen golden frame + FFT output."""
    directory = Path(directory or _GOLDEN_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    frame = generate_frame(FRAME_SPEC)
    result = pfft_1024(frame)
    payload = {
        "spec": FRAME_SPEC,
        "n_points": 1024,
        "input": serialize_words(frame),
        "output": serialize_words(result.output),
        "stage_outputs": [
            serialize_words(tr.values) for tr in result.stages
        ],
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    digest = _sha256_bytes(raw)
    json_path = directory / "p1_random_seeded.json"
    sha_path = directory / "SHA256.txt"
    if json_path.is_file():
        old = json_path.read_bytes()
        if _sha256_bytes(old) != digest:
            raise RuntimeError("golden file changed; freeze a new name")
    else:
        json_path.write_bytes(raw)
        sha_path.write_text(
            f"{digest}  {json_path.name}\nseed={FRAME_SPEC['seed']}\n",
            encoding="utf-8",
        )
    # zero-fault must match stored output
    stored = json.loads(json_path.read_text(encoding="utf-8"))
    assert serialize_words(result.output) == stored["output"]
    return {
        "path": str(json_path),
        "sha256": digest,
        "frame": frame,
        "result": result,
    }


def _linf(a, b):
    m = 0
    for x, y in zip(a, b):
        m = max(m, abs(x.real - y.real), abs(x.imag - y.imag))
    return m


def _open_loop_from(stage_id, corrupted_after_stage, golden_out):
    """Continue PFFT from stage_id+1 with no ECC (sensitivity proxy)."""
    phi = exchange_phi(1024)
    state = list(corrupted_after_stage)
    for stage in range(stage_id + 1, 11):
        state = list(exchanged_dif_stage(state, stage, phi).values)
    observed = bit_reverse_order(state)
    n = len(observed)
    over_lo = over_hi = 0
    m = 0
    for x, y in zip(observed, golden_out):
        d = max(abs(x.real - y.real), abs(x.imag - y.imag))
        m = max(m, d)
        if d > THRESHOLD_LO:
            over_lo += 1
        if d > THRESHOLD_HI:
            over_hi += 1
    return m, over_lo / n, over_hi / n


def _outcome(detected, corrected, match, uncorrectable=False):
    if match and not detected:
        return "MASKED"
    if match and detected and corrected:
        return "CORRECTED"
    if detected and (uncorrectable or not match):
        return "DUE"
    if (not detected) and (not match):
        return "SDC"
    return "DUE"


def inject_and_classify(fault, golden=None):
    """fault: dict(stage_id, module_role, domain, bit, cycle, ...).

    cycle / address / lane map to (frame, sample) via WP6 SDF depths.
    If the delay-line slot is overwritten before the pairing read,
    outcome is MASKED regardless of the ECC decoder.
    """
    golden = golden or ensure_golden()
    frame = golden["frame"]
    result = golden["result"]
    stage = int(fault.get("stage_id") or 1)
    domain = fault.get("domain") or "FF_STATE"
    role = fault.get("module_role") or "butterfly"
    bit = int(fault.get("bit") or 0)
    component = fault.get("component") or "real"
    symbol = int(fault.get("symbol") or 0)
    n_faults = int(fault.get("n_faults") or 1)
    protection = fault.get("protection", "on")
    ident = map_cycle(
        stage, int(fault.get("cycle") or 0),
        address=fault.get("address"),
        lane=int(fault.get("lane") or 0),
        component=component,
    )
    life = masked_by_lifetime(ident, role=role)

    # open-loop sensitivity: flip one sample after this stage, continue
    pos = int(fault.get("physical_index") or 0)
    after = list(result.stages[stage - 1].values)
    flipped_word = flip_component_bit(after[pos], component, bit)
    corrupted = list(after)
    corrupted[pos] = flipped_word
    dev, p_lo, p_hi = _open_loop_from(stage, corrupted, result.output)

    outcome = None
    detected = corrected = match = False
    uncorrectable = False
    note = ""

    if protection == "off":
        match = dev == 0
        detected = False
        outcome = _outcome(False, False, match)
        note = "open-loop continuation, ECC not applied"
    elif stage in (8, 9) or role == "replica":
        copies = [result.stages[stage - 1].values[pos]] * 3
        copies[int(fault.get("replica") or 0)] = flipped_word
        voted, detected = tmr_vote(copies)
        match = voted == result.stages[stage - 1].values[pos]
        corrected = False
        outcome = _outcome(detected, True, match) if match else _outcome(
            detected, False, match)
        if match:
            outcome = "MASKED"
        note = "TMR vote on one replica"
    elif domain == "BRAM_STATE" or role == "delay":
        src = result.stages[stage - 2].values[pos] if stage > 1 else frame[pos]
        encoded = secded_encode_complex(src)
        received = encoded ^ (1 << (bit % 78))
        if n_faults >= 2:
            received ^= 1 << ((bit + 17) % 78)
        decoded = secded_decode(received)
        match = decoded.complex_word == src
        detected = decoded.detected
        corrected = decoded.corrected
        uncorrectable = detected and not corrected
        outcome = _outcome(detected, corrected, match, uncorrectable)
        note = "memory SECDED on delay-line sample"
        golden_w = src
    else:
        # arithmetic ECC on one operator group (s1–7 or s10)
        phi = exchange_phi(1024)
        if stage == 10:
            groups = stage10_operator_groups(frame)
            group = groups[0][0]  # first two-beat upper
        else:
            states = pfft_stage_inputs(frame)
            ins = [
                operator_input(states[stage - 1], stage, i, phi)
                for i in range(4)
            ]
            group = independent_operator_group(ins)
        received = list(group.outputs)
        received[symbol] = flip_component_bit(
            received[symbol], component, bit)
        if n_faults >= 2:
            other = (symbol + 1) % 6
            received[other] = flip_component_bit(
                received[other], component, (bit + 3) % 35)
        decoded = arithmetic_643_decode(received, group.expected_residual)
        match = decoded.functional == group.functional
        detected = decoded.detected
        corrected = decoded.corrected
        uncorrectable = decoded.uncorrectable
        outcome = _outcome(detected, corrected, match, uncorrectable)
        note = "arithmetic [6,4,3] on one operator group"

    if life["lifetime_class"] == "MASKED" and protection != "off":
        outcome = "MASKED"
        note = life["reason"]

    return {
        "outcome": outcome,
        "detected": detected,
        "corrected": corrected,
        "uncorrectable": uncorrectable,
        "match": match,
        "max_output_deviation": int(dev),
        "frac_over_threshold_2": p_lo,
        "frac_over_threshold_3": p_hi,
        "stage_id": stage,
        "module_role": role,
        "domain": domain,
        "bit": bit,
        "note": note,
        "frame": ident["frame"],
        "sample": ident["sample"],
        "cycle": ident["cycle"],
        "lifetime_class": life["lifetime_class"],
        "lifetime_reason": life["reason"],
        "source_model": "proxy",
        "confidence": "wrapper_of_frozen_p1_injector",
    }


def scan_one_bit_per_stage(golden=None):
    """Handbook WP2.4: one representative FF flip per stage."""
    golden = golden or ensure_golden()
    rows = []
    for stage in range(1, 11):
        role = "replica" if stage in (8, 9) else "butterfly"
        rows.append(inject_and_classify(
            {"stage_id": stage, "module_role": role, "domain": "FF_STATE",
             "bit": 0, "component": "real", "symbol": 0,
             "physical_index": 0},
            golden=golden,
        ))
    return rows
