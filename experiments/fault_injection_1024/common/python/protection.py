#!/usr/bin/env python3
"""Bit-level protection primitives used by all five Python objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .fixed_fft import (
    DATA_WIDTH,
    ComplexWord,
    ZERO,
    add,
    cw,
    neg,
    rotate_j,
    sub,
    unsigned,
)


MEMORY_DATA_BITS = DATA_WIDTH * 2
MEMORY_HAMMING_PARITY_BITS = 7
MEMORY_HAMMING_BITS = MEMORY_DATA_BITS + MEMORY_HAMMING_PARITY_BITS
MEMORY_CODEWORD_BITS = MEMORY_HAMMING_BITS + 1
CHECK_DOMAIN_WIDTH = 39
CHECK_DOMAIN_MIN = -(1 << (CHECK_DOMAIN_WIDTH - 1))
CHECK_DOMAIN_MAX = (1 << (CHECK_DOMAIN_WIDTH - 1)) - 1


@dataclass(frozen=True)
class WideComplex:
    """Complex integer in the non-wrapping ECC check domain."""

    real: int
    imag: int

    def as_pair(self) -> tuple[int, int]:
        return self.real, self.imag


WIDE_ZERO = WideComplex(0, 0)


def _check_wide(value: WideComplex) -> WideComplex:
    if not (CHECK_DOMAIN_MIN <= value.real <= CHECK_DOMAIN_MAX):
        raise OverflowError(f"real check-domain overflow: {value.real}")
    if not (CHECK_DOMAIN_MIN <= value.imag <= CHECK_DOMAIN_MAX):
        raise OverflowError(f"imag check-domain overflow: {value.imag}")
    return value


def _wide(value: ComplexWord | WideComplex) -> WideComplex:
    return value if isinstance(value, WideComplex) else WideComplex(value.real, value.imag)


def _wide_add(a: ComplexWord | WideComplex, b: ComplexWord | WideComplex) -> WideComplex:
    lhs, rhs = _wide(a), _wide(b)
    return _check_wide(WideComplex(lhs.real + rhs.real, lhs.imag + rhs.imag))


def _wide_sub(a: ComplexWord | WideComplex, b: ComplexWord | WideComplex) -> WideComplex:
    lhs, rhs = _wide(a), _wide(b)
    return _check_wide(WideComplex(lhs.real - rhs.real, lhs.imag - rhs.imag))


def _wide_neg(value: ComplexWord | WideComplex) -> WideComplex:
    item = _wide(value)
    return _check_wide(WideComplex(-item.real, -item.imag))


def _wide_rotate_j(value: ComplexWord | WideComplex, quarter_turns: int) -> WideComplex:
    item = _wide(value)
    turns = quarter_turns % 4
    if turns == 0:
        return item
    if turns == 1:
        return _check_wide(WideComplex(-item.imag, item.real))
    if turns == 2:
        return _check_wide(WideComplex(-item.real, -item.imag))
    return _check_wide(WideComplex(item.imag, -item.real))


def _wide_sum(values: Sequence[ComplexWord | WideComplex]) -> WideComplex:
    total = WIDE_ZERO
    for value in values:
        total = _wide_add(total, value)
    return total


def serialize_wide(values: Sequence[WideComplex]) -> list[list[int]]:
    return [[value.real, value.imag] for value in values]


def pack_complex(value: ComplexWord) -> int:
    return (unsigned(value.real) << DATA_WIDTH) | unsigned(value.imag)


def unpack_complex(value: int) -> ComplexWord:
    return cw(value >> DATA_WIDTH, value)


def flip_component_bit(value: ComplexWord, component: str, bit: int) -> ComplexWord:
    if not 0 <= bit < DATA_WIDTH:
        raise ValueError("component bit outside data width")
    if component == "real":
        return cw(unsigned(value.real) ^ (1 << bit), value.imag)
    if component == "imag":
        return cw(value.real, unsigned(value.imag) ^ (1 << bit))
    raise ValueError("component must be real or imag")


def secded_encode_payload(payload: int) -> int:
    if payload >> MEMORY_DATA_BITS:
        raise ValueError("payload exceeds 70 bits")
    bits = [0] * (MEMORY_HAMMING_BITS + 1)  # positions are 1-based
    payload_index = 0
    for position in range(1, MEMORY_HAMMING_BITS + 1):
        if position & (position - 1):
            bits[position] = (payload >> payload_index) & 1
            payload_index += 1
    for parity_position in (1, 2, 4, 8, 16, 32, 64):
        parity = 0
        for position in range(1, MEMORY_HAMMING_BITS + 1):
            if position & parity_position:
                parity ^= bits[position]
        bits[parity_position] = parity
    hamming = 0
    overall = 0
    for position in range(1, MEMORY_HAMMING_BITS + 1):
        hamming |= bits[position] << (position - 1)
        overall ^= bits[position]
    return hamming | (overall << MEMORY_HAMMING_BITS)


def secded_encode_complex(value: ComplexWord) -> int:
    return secded_encode_payload(pack_complex(value))


@dataclass(frozen=True)
class SECDEDResult:
    payload: int
    corrected_codeword: int
    status: str
    detected: bool
    corrected: bool
    syndrome: int

    @property
    def complex_word(self) -> ComplexWord:
        return unpack_complex(self.payload)


def secded_decode(codeword: int) -> SECDEDResult:
    codeword &= (1 << MEMORY_CODEWORD_BITS) - 1
    syndrome = 0
    for parity_position in (1, 2, 4, 8, 16, 32, 64):
        parity = 0
        for position in range(1, MEMORY_HAMMING_BITS + 1):
            if position & parity_position:
                parity ^= (codeword >> (position - 1)) & 1
        if parity:
            syndrome |= parity_position
    overall = 0
    for bit in range(MEMORY_CODEWORD_BITS):
        overall ^= (codeword >> bit) & 1

    corrected_codeword = codeword
    if syndrome == 0 and overall == 0:
        status = "clean"
        detected = False
        corrected = False
    elif syndrome != 0 and overall == 1 and syndrome <= MEMORY_HAMMING_BITS:
        corrected_codeword ^= 1 << (syndrome - 1)
        status = "single_corrected"
        detected = True
        corrected = True
    elif syndrome == 0 and overall == 1:
        corrected_codeword ^= 1 << MEMORY_HAMMING_BITS
        status = "overall_parity_corrected"
        detected = True
        corrected = True
    else:
        status = "double_detected"
        detected = True
        corrected = False

    payload = 0
    payload_index = 0
    for position in range(1, MEMORY_HAMMING_BITS + 1):
        if position & (position - 1):
            payload |= ((corrected_codeword >> (position - 1)) & 1) << payload_index
            payload_index += 1
    return SECDEDResult(payload, corrected_codeword, status, detected, corrected, syndrome)


ARITHMETIC_WEIGHTS = (0, 1, 2, 3)  # 1, +j, -1, -j


def _sum_words(values: Sequence[ComplexWord]) -> ComplexWord:
    total = ZERO
    for value in values:
        total = add(total, value)
    return total


def arithmetic_643_encode(functional: Sequence[ComplexWord]) -> list[ComplexWord]:
    if len(functional) != 4:
        raise ValueError("[6,4,3] requires four functional symbols")
    p0 = _sum_words(functional)
    p1 = _sum_words([rotate_j(value, weight) for value, weight in zip(functional, ARITHMETIC_WEIGHTS)])
    return [*functional, p0, p1]


def arithmetic_643_raw_syndrome(received: Sequence[ComplexWord]) -> tuple[WideComplex, WideComplex]:
    if len(received) != 6:
        raise ValueError("[6,4,3] requires six symbols")
    expected_p0 = _wide_sum(received[:4])
    expected_p1 = _wide_sum(
        [_wide_rotate_j(value, weight) for value, weight in zip(received[:4], ARITHMETIC_WEIGHTS)]
    )
    return _wide_sub(received[4], expected_p0), _wide_sub(received[5], expected_p1)


def arithmetic_643_capture_residual(received_before_fault: Sequence[ComplexWord]) -> tuple[WideComplex, WideComplex]:
    """Capture the expected fixed-point closure residual before injection.

    In RTL this value must be reconstructed from carry/wrap/shift/twiddle
    truncation metadata before the protected result boundary.  Recomputing it
    from post-fault received symbols is forbidden by the frozen contract.
    """

    return arithmetic_643_raw_syndrome(received_before_fault)


def arithmetic_643_syndrome(
    received: Sequence[ComplexWord], expected_residual: Sequence[WideComplex]
) -> tuple[WideComplex, WideComplex]:
    if len(expected_residual) != 2:
        raise ValueError("[6,4,3] residual requires two complex components")
    raw = arithmetic_643_raw_syndrome(received)
    return _wide_sub(raw[0], expected_residual[0]), _wide_sub(raw[1], expected_residual[1])


@dataclass(frozen=True)
class SymbolECCResult:
    codeword: tuple[ComplexWord, ...]
    functional: tuple[ComplexWord, ...]
    syndrome: tuple[WideComplex, ...]
    detected: bool
    corrected: bool
    location: int | None
    uncorrectable: bool


def arithmetic_643_decode(
    received: Sequence[ComplexWord], expected_residual: Sequence[WideComplex]
) -> SymbolECCResult:
    syndrome = arithmetic_643_syndrome(received, expected_residual)
    detected = syndrome != (WIDE_ZERO, WIDE_ZERO)
    if not detected:
        return SymbolECCResult(tuple(received), tuple(received[:4]), syndrome, False, False, None, False)

    candidates: list[tuple[int, list[ComplexWord]]] = []
    for location in range(6):
        if location < 4:
            error = _wide_neg(syndrome[0])
        elif location == 4:
            error = syndrome[0]
        else:
            error = syndrome[1]
        candidate = list(received)
        candidate[location] = cw(
            candidate[location].real - error.real,
            candidate[location].imag - error.imag,
        )
        if arithmetic_643_syndrome(candidate, expected_residual) == (WIDE_ZERO, WIDE_ZERO):
            candidates.append((location, candidate))
    if len(candidates) != 1:
        return SymbolECCResult(tuple(received), tuple(received[:4]), syndrome, True, False, None, True)
    location, corrected = candidates[0]
    return SymbolECCResult(tuple(corrected), tuple(corrected[:4]), syndrome, True, True, location, False)


GAO_COLUMNS = (
    (1, 0, 0),
    (0, 1, 0),
    (1, 1, 0),
    (0, 0, 1),
    (1, 0, 1),
    (0, 1, 1),
    (1, 1, 1),
)


def gao_743_encode(functional: Sequence[ComplexWord]) -> list[ComplexWord]:
    if len(functional) != 4:
        raise ValueError("Gao [7,4,3] requires four functional symbols")
    d0, d1, d2, d3 = functional
    p1 = neg(_sum_words([d0, d1, d3]))
    p2 = neg(_sum_words([d0, d2, d3]))
    p3 = neg(_sum_words([d1, d2, d3]))
    return [p1, p2, d0, p3, d1, d2, d3]


def gao_743_raw_syndrome(received: Sequence[ComplexWord]) -> tuple[WideComplex, WideComplex, WideComplex]:
    if len(received) != 7:
        raise ValueError("Gao [7,4,3] requires seven symbols")
    return (
        _wide_sum([received[index] for index in (0, 2, 4, 6)]),
        _wide_sum([received[index] for index in (1, 2, 5, 6)]),
        _wide_sum([received[index] for index in (3, 4, 5, 6)]),
    )


def gao_743_capture_residual(
    received_before_fault: Sequence[ComplexWord],
) -> tuple[WideComplex, WideComplex, WideComplex]:
    return gao_743_raw_syndrome(received_before_fault)


def gao_743_syndrome(
    received: Sequence[ComplexWord], expected_residual: Sequence[WideComplex]
) -> tuple[WideComplex, WideComplex, WideComplex]:
    if len(expected_residual) != 3:
        raise ValueError("Gao [7,4,3] residual requires three complex components")
    raw = gao_743_raw_syndrome(received)
    return tuple(_wide_sub(value, residual) for value, residual in zip(raw, expected_residual))  # type: ignore[return-value]


def gao_743_decode(
    received: Sequence[ComplexWord], expected_residual: Sequence[WideComplex]
) -> SymbolECCResult:
    syndrome3 = gao_743_syndrome(received, expected_residual)
    detected = syndrome3 != (WIDE_ZERO, WIDE_ZERO, WIDE_ZERO)
    functional_indices = (2, 4, 5, 6)
    if not detected:
        return SymbolECCResult(tuple(received), tuple(received[index] for index in functional_indices), syndrome3, False, False, None, False)
    candidates: list[tuple[int, list[ComplexWord]]] = []
    for location, column in enumerate(GAO_COLUMNS):
        active = [syndrome3[index] for index, enabled in enumerate(column) if enabled]
        inactive = [syndrome3[index] for index, enabled in enumerate(column) if not enabled]
        if active and active[0] != WIDE_ZERO and all(value == active[0] for value in active) and all(value == WIDE_ZERO for value in inactive):
            candidate = list(received)
            candidate[location] = cw(
                candidate[location].real - active[0].real,
                candidate[location].imag - active[0].imag,
            )
            if gao_743_syndrome(candidate, expected_residual) == (WIDE_ZERO, WIDE_ZERO, WIDE_ZERO):
                candidates.append((location, candidate))
    if len(candidates) != 1:
        return SymbolECCResult(tuple(received), tuple(received[index] for index in functional_indices), syndrome3, True, False, None, True)
    location, corrected = candidates[0]
    return SymbolECCResult(tuple(corrected), tuple(corrected[index] for index in functional_indices), syndrome3, True, True, location, False)


def _within_threshold(s: WideComplex, threshold: int) -> bool:
    """Gao-style threshold check: syndrome component is 'zero' if |real| <= τ and |imag| <= τ."""
    return abs(s.real) <= threshold and abs(s.imag) <= threshold


def arithmetic_643_decode_thresholded(
    received: Sequence[ComplexWord],
    expected_residual: Sequence[WideComplex],
    threshold: int = 0,
) -> SymbolECCResult:
    """Gao-style threshold-based [6,4,3] decoder.

    Detection: syndrome components with |value| <= threshold are treated as zero.
    Correction: after applying the correction, the post-correction syndrome must
    also be within threshold. Mode matching uses threshold-tolerant comparison
    instead of exact equality.

    With threshold=0 this reduces to exact matching (same as arithmetic_643_decode).
    """
    syndrome = arithmetic_643_syndrome(received, expected_residual)

    # Gao threshold detection: all components within threshold → no error
    if _within_threshold(syndrome[0], threshold) and _within_threshold(syndrome[1], threshold):
        return SymbolECCResult(
            tuple(received), tuple(received[:4]), syndrome,
            False, False, None, False,
        )

    # Detected: try to correct each candidate location
    candidates: list[tuple[int, list[ComplexWord], int]] = []  # (location, corrected_words, residual_norm)
    for location in range(6):
        if location < 4:
            error = _wide_neg(syndrome[0])
        elif location == 4:
            error = syndrome[0]
        else:
            error = syndrome[1]
        candidate = list(received)
        candidate[location] = cw(
            candidate[location].real - error.real,
            candidate[location].imag - error.imag,
        )
        post_syndrome = arithmetic_643_syndrome(candidate, expected_residual)
        if _within_threshold(post_syndrome[0], threshold) and _within_threshold(post_syndrome[1], threshold):
            residual_norm = abs(post_syndrome[0].real) + abs(post_syndrome[0].imag) + \
                           abs(post_syndrome[1].real) + abs(post_syndrome[1].imag)
            candidates.append((location, candidate, residual_norm))

    if len(candidates) == 0:
        # Detected but uncorrectable
        return SymbolECCResult(
            tuple(received), tuple(received[:4]), syndrome,
            True, False, None, True,
        )
    if len(candidates) == 1:
        location, corrected, _ = candidates[0]
        return SymbolECCResult(
            tuple(corrected), tuple(corrected[:4]), syndrome,
            True, True, location, False,
        )
    # Multiple candidates: pick the one with smallest residual (best match)
    candidates.sort(key=lambda c: c[2])
    location, corrected, _ = candidates[0]
    return SymbolECCResult(
        tuple(corrected), tuple(corrected[:4]), syndrome,
        True, True, location, False,
    )


def majority3(a: int, b: int, c: int) -> int:
    return (a & b) | (a & c) | (b & c)


def tmr_vote(replicas: Sequence[ComplexWord]) -> tuple[ComplexWord, bool]:
    if len(replicas) != 3:
        raise ValueError("TMR requires three replicas")
    packed = [pack_complex(value) for value in replicas]
    voted = unpack_complex(majority3(*packed))
    return voted, len(set(packed)) != 1
