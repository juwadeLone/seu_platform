#!/usr/bin/env python3
"""Bit-accurate fixed-point FFT kernels for the five-architecture study.

This file is the authoritative Python-first definition of two independent
radix-2 DIF dataflow models.  It is not derived from any existing RTL:

* ``subfft_1024``: four independent single-lane classic 256-point,
  eight-stage R2SDF sub-FFTs,
  followed by the cross twiddle and two radix-2 combining stages.
* ``pfft_no_exchange_1024``: one four-parallel ten-stage P-SDF transform
  using the canonical radix-2 DIF lower-branch twiddle placement.  This is
  the functional schedule used by the P0 and P2 comparison baselines.
* ``pfft_1024``: one four-parallel ten-stage P-SDF transform using the
  frozen ``dit_latest`` triangular-matrix twiddle placement.  This exchanged
  schedule is reserved for P1.

The implementation never calls numpy/scipy FFT.  The floating reference at
the bottom is a separate radix-2 implementation used only for a numerical
sanity check.  All protected objects use the integer kernels above.
"""

from __future__ import annotations

import cmath
import math
import random
from dataclasses import dataclass
from typing import Iterable, Sequence


DATA_WIDTH = 35
TWIDDLE_WIDTH = 30
TWIDDLE_FRAC = 28
DATA_MASK = (1 << DATA_WIDTH) - 1
DATA_SIGN = 1 << (DATA_WIDTH - 1)
TWIDDLE_MIN = -(1 << (TWIDDLE_WIDTH - 1))
TWIDDLE_MAX = (1 << (TWIDDLE_WIDTH - 1)) - 1
PHYSICAL_DELAY_DEPTHS = (128, 64, 32, 16, 8, 4, 2, 1, 1, 1)
STAGE_FIRST_TOKEN_LATENCIES = tuple(depth + 1 for depth in PHYSICAL_DELAY_DEPTHS)
BASE_PIPELINE_LATENCY = sum(STAGE_FIRST_TOKEN_LATENCIES)
PFFT_PAIR_WAIT_CYCLES = 256
PFFT_FRAME_LATENCY = BASE_PIPELINE_LATENCY + PFFT_PAIR_WAIT_CYCLES


@dataclass(frozen=True)
class ComplexWord:
    real: int
    imag: int

    def as_pair(self) -> tuple[int, int]:
        return self.real, self.imag


@dataclass(frozen=True)
class StageTrace:
    stage: int
    logical_length: int
    physical_delay_depth: int
    values: tuple[ComplexWord, ...]
    twiddle_exponents: tuple[int, ...]


@dataclass(frozen=True)
class FFTResult:
    output: tuple[ComplexWord, ...]
    stages: tuple[StageTrace, ...]


@dataclass(frozen=True)
class SDFStageCycleTrace:
    """Cycle-visible trace of one single-lane classic radix-2 DIF SDF stage."""

    stage: int
    physical_delay_depth: int
    input_first_cycle: int
    output_first_cycle: int
    output_last_cycle: int
    valid_count: int
    last_cycle: int
    initial_fill_inputs: int
    butterfly_outputs: int
    feedback_outputs: int
    drain_outputs: int
    values: tuple[ComplexWord, ...]
    twiddle_exponents: tuple[int, ...]


@dataclass(frozen=True)
class StreamBeat:
    cycle: int
    frame_id: str
    beat_index: int
    valid: bool
    last: bool
    sample_indices: tuple[int, int, int, int]
    lanes: tuple[ComplexWord, ComplexWord, ComplexWord, ComplexWord]


@dataclass(frozen=True)
class StreamTrace:
    group: str
    frame_latency_cycles: int
    stage_first_valid_cycles: tuple[int, ...]
    output_beats: tuple[StreamBeat, ...]
    subfft_child_stages: tuple[tuple[SDFStageCycleTrace, ...], ...] = ()


def wrap_signed(value: int, width: int = DATA_WIDTH) -> int:
    mask = (1 << width) - 1
    value &= mask
    sign = 1 << (width - 1)
    return value - (1 << width) if value & sign else value


def unsigned(value: int, width: int = DATA_WIDTH) -> int:
    return value & ((1 << width) - 1)


def cw(real: int, imag: int) -> ComplexWord:
    return ComplexWord(wrap_signed(real), wrap_signed(imag))


ZERO = cw(0, 0)


def add(a: ComplexWord, b: ComplexWord) -> ComplexWord:
    return cw(a.real + b.real, a.imag + b.imag)


def sub(a: ComplexWord, b: ComplexWord) -> ComplexWord:
    return cw(a.real - b.real, a.imag - b.imag)


def neg(a: ComplexWord) -> ComplexWord:
    return cw(-a.real, -a.imag)


def rotate_j(a: ComplexWord, quarter_turns: int) -> ComplexWord:
    turns = quarter_turns % 4
    if turns == 0:
        return a
    if turns == 1:
        return cw(-a.imag, a.real)
    if turns == 2:
        return cw(-a.real, -a.imag)
    return cw(a.imag, -a.real)


def half(value: ComplexWord) -> ComplexWord:
    """Arithmetic divide by two, matching a signed RTL ``>>> 1``."""
    return cw(value.real >> 1, value.imag >> 1)


def butterfly_scaled(a: ComplexWord, b: ComplexWord) -> tuple[ComplexWord, ComplexWord]:
    return half(add(a, b)), half(sub(a, b))


def _round_ties_away(value: float) -> int:
    if value >= 0.0:
        return int(math.floor(value + 0.5))
    return int(math.ceil(value - 0.5))


def quantize_twiddle(value: float) -> int:
    scaled = _round_ties_away(value * (1 << TWIDDLE_FRAC))
    return min(TWIDDLE_MAX, max(TWIDDLE_MIN, scaled))


def twiddle_coeff(n_points: int, exponent: int) -> tuple[int, int]:
    angle = -2.0 * math.pi * (exponent % n_points) / n_points
    return quantize_twiddle(math.cos(angle)), quantize_twiddle(math.sin(angle))


def complex_multiply_q2_28(value: ComplexWord, coefficient: tuple[int, int]) -> ComplexWord:
    wr, wi = coefficient
    real_wide = value.real * wr - value.imag * wi
    imag_wide = value.real * wi + value.imag * wr
    return cw(real_wide >> TWIDDLE_FRAC, imag_wide >> TWIDDLE_FRAC)


def multiply_twiddle(value: ComplexWord, n_points: int, exponent: int) -> ComplexWord:
    return complex_multiply_q2_28(value, twiddle_coeff(n_points, exponent))


def bit_reverse(value: int, bits: int) -> int:
    result = 0
    for _ in range(bits):
        result = (result << 1) | (value & 1)
        value >>= 1
    return result


def bit_reverse_order(values: Sequence[ComplexWord]) -> list[ComplexWord]:
    bits = int(math.log2(len(values)))
    return [values[bit_reverse(index, bits)] for index in range(len(values))]


def canonical_dif_stage(values: Sequence[ComplexWord], stage: int) -> StageTrace:
    """One scaled radix-2 DIF stage with the canonical lower-branch twiddle."""
    n_points = len(values)
    nbits = int(math.log2(n_points))
    if 1 << nbits != n_points or not 1 <= stage <= nbits:
        raise ValueError("invalid power-of-two stage")
    length = 1 << (nbits - stage + 1)
    depth = length // 2
    result = list(values)
    exponents = [0] * n_points
    stride = n_points // length
    for base in range(0, n_points, length):
        for offset in range(depth):
            upper, lower = butterfly_scaled(values[base + offset], values[base + depth + offset])
            exponent = offset * stride
            result[base + offset] = upper
            result[base + depth + offset] = multiply_twiddle(lower, n_points, exponent)
            exponents[base + depth + offset] = exponent
    return StageTrace(stage, length, depth, tuple(result), tuple(exponents))


def classic_r2sdf_stage(
    values: Sequence[ComplexWord], stage: int, input_first_cycle: int = 0
) -> tuple[StageTrace, SDFStageCycleTrace]:
    """Execute one explicit single-lane R2SDF feedback stage cycle by cycle.

    During the first half-block inputs fill the feedback memory.  During the
    second half, each input is combined with the delayed word: the upper result
    is emitted and the twiddled lower result replaces the delay word.  The next
    half-block emits those stored lower results while accepting the next block.
    A single output register accounts for the ``depth + 1`` first-token rule.
    """

    n_points = len(values)
    nbits = int(math.log2(n_points))
    if 1 << nbits != n_points or not 1 <= stage <= nbits:
        raise ValueError("invalid power-of-two stage")
    length = 1 << (nbits - stage + 1)
    depth = length // 2
    stride = n_points // length
    delay_values = [ZERO] * depth
    delay_exponents = [0] * depth
    delay_valid = [False] * depth
    outputs: list[ComplexWord] = []
    output_exponents: list[int] = []
    initial_fill_inputs = 0
    butterfly_outputs = 0
    feedback_outputs = 0

    for token_index, value in enumerate(values):
        position = token_index % length
        address = position % depth
        if position < depth:
            if delay_valid[address]:
                outputs.append(delay_values[address])
                output_exponents.append(delay_exponents[address])
                feedback_outputs += 1
            else:
                initial_fill_inputs += 1
            delay_values[address] = value
            delay_exponents[address] = 0
            delay_valid[address] = True
        else:
            if not delay_valid[address]:
                raise RuntimeError("R2SDF feedback memory read before fill")
            upper, lower = butterfly_scaled(delay_values[address], value)
            exponent = address * stride
            outputs.append(upper)
            output_exponents.append(0)
            butterfly_outputs += 1
            delay_values[address] = multiply_twiddle(lower, n_points, exponent)
            delay_exponents[address] = exponent

    drain_outputs = 0
    for address in range(depth):
        if not delay_valid[address]:
            raise RuntimeError("R2SDF feedback memory invalid during drain")
        outputs.append(delay_values[address])
        output_exponents.append(delay_exponents[address])
        drain_outputs += 1

    if len(outputs) != n_points:
        raise RuntimeError(f"R2SDF stage emitted {len(outputs)} tokens, expected {n_points}")
    first_cycle = input_first_cycle + depth + 1
    last_cycle = first_cycle + n_points - 1
    stage_trace = StageTrace(stage, length, depth, tuple(outputs), tuple(output_exponents))
    cycle_trace = SDFStageCycleTrace(
        stage=stage,
        physical_delay_depth=depth,
        input_first_cycle=input_first_cycle,
        output_first_cycle=first_cycle,
        output_last_cycle=last_cycle,
        valid_count=n_points,
        last_cycle=last_cycle,
        initial_fill_inputs=initial_fill_inputs,
        butterfly_outputs=butterfly_outputs,
        feedback_outputs=feedback_outputs,
        drain_outputs=drain_outputs,
        values=tuple(outputs),
        twiddle_exponents=tuple(output_exponents),
    )
    return stage_trace, cycle_trace


def classic_r2sdf_fft(
    values: Sequence[ComplexWord], input_first_cycle: int = 0
) -> tuple[FFTResult, tuple[SDFStageCycleTrace, ...]]:
    """Run every stage as an explicit single-lane classic R2SDF machine."""

    n_points = len(values)
    nbits = int(math.log2(n_points))
    if 1 << nbits != n_points:
        raise ValueError("R2SDF length must be a power of two")
    state = list(values)
    stage_traces: list[StageTrace] = []
    cycle_traces: list[SDFStageCycleTrace] = []
    first_cycle = input_first_cycle
    for stage in range(1, nbits + 1):
        stage_trace, cycle_trace = classic_r2sdf_stage(state, stage, first_cycle)
        state = list(stage_trace.values)
        stage_traces.append(stage_trace)
        cycle_traces.append(cycle_trace)
        first_cycle = cycle_trace.output_first_cycle
    return FFTResult(tuple(bit_reverse_order(state)), tuple(stage_traces)), tuple(cycle_traces)


def canonical_dif_fft(values: Sequence[ComplexWord]) -> FFTResult:
    n_points = len(values)
    nbits = int(math.log2(n_points))
    state = list(values)
    traces: list[StageTrace] = []
    for stage in range(1, nbits + 1):
        trace = canonical_dif_stage(state, stage)
        state = list(trace.values)
        traces.append(trace)
    return FFTResult(tuple(bit_reverse_order(state)), tuple(traces))


def pfft_no_exchange_1024(values: Sequence[ComplexWord]) -> FFTResult:
    """Canonical 1024-point DIF schedule for the four-lane PFFT baselines.

    The arithmetic is identical to :func:`canonical_dif_fft`; only the trace
    metadata records the physical four-lane delay depth used by the P-SDF
    implementation.  No exchanged ``phi`` schedule is evaluated here.
    """

    if len(values) != 1024:
        raise ValueError("PFFT requires exactly 1024 complex samples")
    state = list(values)
    traces: list[StageTrace] = []
    for stage in range(1, 11):
        canonical_trace = canonical_dif_stage(state, stage)
        state = list(canonical_trace.values)
        physical_depth = max(1, canonical_trace.physical_delay_depth // 4)
        traces.append(
            StageTrace(
                stage=canonical_trace.stage,
                logical_length=canonical_trace.logical_length,
                physical_delay_depth=physical_depth,
                values=canonical_trace.values,
                twiddle_exponents=canonical_trace.twiddle_exponents,
            )
        )
    return FFTResult(tuple(bit_reverse_order(state)), tuple(traces))


def exchange_phi(n_points: int) -> list[list[int]]:
    """Frozen ``dit_latest`` triangular-matrix exponent placement."""
    nbits = int(math.log2(n_points))
    if 1 << nbits != n_points:
        raise ValueError("n_points must be a power of two")
    phi = [[0 for _ in range(n_points)] for _ in range(nbits - 1)]
    for high in range(1, nbits):
        for low in range(high):
            latest_stage = nbits - low - 1
            term = 1 << (nbits - 1 - high + low)
            target = phi[latest_stage - 1]
            for index in range(n_points):
                if ((index >> high) & 1) and ((index >> low) & 1):
                    target[index] += term
    return phi


def exchanged_dif_stage(
    values: Sequence[ComplexWord], stage: int, phi: Sequence[Sequence[int]]
) -> StageTrace:
    """One P-SDF stage using the verified exchanged per-output rotations."""
    n_points = len(values)
    nbits = int(math.log2(n_points))
    length = 1 << (nbits - stage + 1)
    depth_global = length // 2
    result = list(values)
    exponents = [0] * n_points
    for base in range(0, n_points, length):
        for offset in range(depth_global):
            upper_index = base + offset
            lower_index = base + depth_global + offset
            upper, lower = butterfly_scaled(values[upper_index], values[lower_index])
            if stage <= nbits - 1:
                upper_exp = phi[stage - 1][upper_index] % n_points
                lower_exp = phi[stage - 1][lower_index] % n_points
                upper = multiply_twiddle(upper, n_points, upper_exp)
                lower = multiply_twiddle(lower, n_points, lower_exp)
                exponents[upper_index] = upper_exp
                exponents[lower_index] = lower_exp
            result[upper_index] = upper
            result[lower_index] = lower
    # Four physical lanes divide the global delay by four for Stages 1--8.
    physical_depth = max(1, depth_global // 4)
    return StageTrace(stage, length, physical_depth, tuple(result), tuple(exponents))


def pfft_1024(values: Sequence[ComplexWord]) -> FFTResult:
    if len(values) != 1024:
        raise ValueError("PFFT requires exactly 1024 complex samples")
    phi = exchange_phi(1024)
    state = list(values)
    traces: list[StageTrace] = []
    for stage in range(1, 11):
        trace = exchanged_dif_stage(state, stage, phi)
        state = list(trace.values)
        traces.append(trace)
    return FFTResult(tuple(bit_reverse_order(state)), tuple(traces))


def subfft_1024(values: Sequence[ComplexWord]) -> FFTResult:
    """Four independent single-lane classic R2SDFs, then cross twiddle/FFT4."""
    if len(values) != 1024:
        raise ValueError("SubFFT requires exactly 1024 complex samples")

    lanes = [[values[4 * sample + lane] for sample in range(256)] for lane in range(4)]
    lane_results = [classic_r2sdf_fft(lane)[0] for lane in lanes]
    stage_traces: list[StageTrace] = []
    for stage in range(1, 9):
        packed: list[ComplexWord] = []
        packed_exponents: list[int] = []
        for sample in range(256):
            for lane in range(4):
                packed.append(lane_results[lane].stages[stage - 1].values[sample])
                packed_exponents.append(lane_results[lane].stages[stage - 1].twiddle_exponents[sample])
        stage_traces.append(
            StageTrace(stage, 1 << (9 - stage), 1 << (8 - stage), tuple(packed), tuple(packed_exponents))
        )

    natural_subffts = [list(result.output) for result in lane_results]
    after_stage9: list[ComplexWord] = [ZERO] * 1024
    final_output: list[ComplexWord] = [ZERO] * 1024
    stage9_exponents: list[int] = [0] * 1024
    for k in range(256):
        crossed = [multiply_twiddle(natural_subffts[lane][k], 1024, lane * k) for lane in range(4)]
        # First radix-2 layer of the 4-point combine.
        a0, a2 = butterfly_scaled(crossed[0], crossed[2])
        a1, a3 = butterfly_scaled(crossed[1], crossed[3])
        a3 = rotate_j(a3, 3)  # multiply by -j
        stage9 = [a0, a1, a2, a3]
        for lane, word in enumerate(stage9):
            after_stage9[4 * k + lane] = word
            stage9_exponents[4 * k + lane] = lane * k

        # Second radix-2 layer.  Natural q order is X[k+256*q].
        q0 = add(a0, a1)
        q2 = sub(a0, a1)
        q1 = add(a2, a3)
        q3 = sub(a2, a3)
        combined = [half(q0), half(q1), half(q2), half(q3)]
        for q, word in enumerate(combined):
            final_output[k + 256 * q] = word

    stage_traces.append(StageTrace(9, 4, 1, tuple(after_stage9), tuple(stage9_exponents)))
    stage_traces.append(StageTrace(10, 2, 1, tuple(final_output), tuple([0] * 1024)))
    return FFTResult(tuple(final_output), tuple(stage_traces))


def _stage_first_valid_cycles() -> tuple[int, ...]:
    total = 0
    starts = []
    for latency in STAGE_FIRST_TOKEN_LATENCIES:
        total += latency
        starts.append(total)
    return tuple(starts)


def subfft_stream_trace(
    frames: Sequence[tuple[str, Sequence[ComplexWord]]]
) -> StreamTrace:
    """Build the frozen 267-cycle four-lane SubFFT valid/last trace."""

    output_beats: list[StreamBeat] = []
    child_stages: tuple[tuple[SDFStageCycleTrace, ...], ...] = ()
    for frame_number, (frame_id, values) in enumerate(frames):
        if len(values) != 1024:
            raise ValueError("SubFFT stream frame must contain 1024 samples")
        lanes = [[values[4 * beat + lane] for beat in range(256)] for lane in range(4)]
        lane_cycle_traces = tuple(classic_r2sdf_fft(lane)[1] for lane in lanes)
        if not child_stages:
            child_stages = lane_cycle_traces
        result = subfft_1024(values)
        frame_start = frame_number * 256
        for beat in range(256):
            k = bit_reverse(beat, 8)
            indices = tuple(k + 256 * quarter for quarter in range(4))
            words = tuple(result.output[index] for index in indices)
            output_beats.append(StreamBeat(
                cycle=frame_start + BASE_PIPELINE_LATENCY + beat,
                frame_id=frame_id,
                beat_index=beat,
                valid=True,
                last=beat == 255,
                sample_indices=indices,
                lanes=words,
            ))
    return StreamTrace(
        group="SubFFT",
        frame_latency_cycles=BASE_PIPELINE_LATENCY,
        stage_first_valid_cycles=_stage_first_valid_cycles(),
        output_beats=tuple(output_beats),
        subfft_child_stages=child_stages,
    )


def pfft_stream_trace(
    frames: Sequence[tuple[str, Sequence[ComplexWord]]]
) -> StreamTrace:
    """Build the frozen paired-frame PFFT trace with fixed 523-cycle latency."""

    if len(frames) % 2:
        raise ValueError("PFFT stream contract requires complete adjacent frame pairs")
    output_beats: list[StreamBeat] = []
    for frame_number, (frame_id, values) in enumerate(frames):
        if len(values) != 1024:
            raise ValueError("PFFT stream frame must contain 1024 samples")
        result = pfft_1024(values)
        frame_start = frame_number * 256
        for beat in range(256):
            physical_indices = tuple(4 * beat + lane for lane in range(4))
            indices = tuple(bit_reverse(index, 10) for index in physical_indices)
            words = tuple(result.output[index] for index in indices)
            output_beats.append(StreamBeat(
                cycle=frame_start + PFFT_FRAME_LATENCY + beat,
                frame_id=frame_id,
                beat_index=beat,
                valid=True,
                last=beat == 255,
                sample_indices=indices,
                lanes=words,
            ))
    return StreamTrace(
        group="PFFT",
        frame_latency_cycles=PFFT_FRAME_LATENCY,
        stage_first_valid_cycles=_stage_first_valid_cycles(),
        output_beats=tuple(output_beats),
    )


def reference_fft(values: Sequence[ComplexWord]) -> list[complex]:
    """Independent floating radix-2 reference, normalized by N."""
    data = [complex(value.real, value.imag) for value in values]

    def recurse(items: Sequence[complex]) -> list[complex]:
        if len(items) == 1:
            return [items[0]]
        even = recurse(items[0::2])
        odd = recurse(items[1::2])
        half_n = len(items) // 2
        result = [0j] * len(items)
        for k in range(half_n):
            rotated = cmath.exp(-2j * math.pi * k / len(items)) * odd[k]
            result[k] = even[k] + rotated
            result[k + half_n] = even[k] - rotated
        return result

    raw = recurse(data)
    return [value / len(values) for value in raw]


def error_metrics(actual: Sequence[ComplexWord], expected: Sequence[complex]) -> dict[str, float]:
    errors = [complex(word.real, word.imag) - ref for word, ref in zip(actual, expected)]
    signal = sum(abs(value) ** 2 for value in expected)
    noise = sum(abs(value) ** 2 for value in errors)
    return {
        "max_abs_error": max(abs(value) for value in errors),
        "rmse": math.sqrt(noise / len(errors)),
        "relative_l2": math.sqrt(noise / signal) if signal else 0.0,
    }


def generate_frame(spec: dict) -> list[ComplexWord]:
    frame = [ZERO for _ in range(1024)]
    generator = spec["generator"]
    if generator == "constant":
        return [cw(spec["real"], spec["imag"]) for _ in frame]
    if generator == "impulse":
        frame[spec["index"]] = cw(spec["real"], spec["imag"])
        return frame
    if generator == "lane_impulses":
        for index, real, imag in zip(spec["indices"], spec["real_values"], spec["imag_values"]):
            frame[index] = cw(real, imag)
        return frame
    if generator == "alternating":
        amplitude = spec["amplitude"]
        return [cw(amplitude if index % 2 == 0 else -amplitude, -amplitude if index % 4 < 2 else amplitude) for index in range(1024)]
    if generator == "signed_ramp":
        shift = spec["left_shift"]
        return [cw((index - 512) << shift, (511 - index) << shift) for index in range(1024)]
    if generator == "uniform_random":
        rng = random.Random(spec["seed"])
        return [cw(rng.randint(spec["min"], spec["max"]), rng.randint(spec["min"], spec["max"])) for _ in range(1024)]
    raise ValueError(f"unknown frame generator: {generator}")


def serialize_words(values: Iterable[ComplexWord]) -> list[list[int]]:
    return [[value.real, value.imag] for value in values]
