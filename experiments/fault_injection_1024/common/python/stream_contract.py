"""Shared cycle/stream contract for the two unprotected FFT dataflows."""

from __future__ import annotations

from dataclasses import replace
from typing import Sequence

from common.python.fixed_fft import (
    ComplexWord,
    SDFStageCycleTrace,
    StreamBeat,
    StreamTrace,
    bit_reverse,
    classic_r2sdf_fft,
    pfft_1024,
    subfft_1024,
)


PHYSICAL_DELAY_DEPTHS = (128, 64, 32, 16, 8, 4, 2, 1, 1, 1)
STAGE_FIRST_TOKEN_LATENCIES = (130, 65, 33, 17, 9, 5, 3, 2, 2, 2)
STAGE_FIRST_VALID_CYCLES = tuple(
    sum(STAGE_FIRST_TOKEN_LATENCIES[: index + 1])
    for index in range(len(STAGE_FIRST_TOKEN_LATENCIES))
)
SUBFFT_LATENCY_CYCLES = sum(STAGE_FIRST_TOKEN_LATENCIES)
PFFT_PAIR_WAIT_AND_SYNC_READ_CYCLES = 257
PFFT_LATENCY_CYCLES = (
    SUBFFT_LATENCY_CYCLES + PFFT_PAIR_WAIT_AND_SYNC_READ_CYCLES
)


def _shift_child_cycles(
    children: Sequence[Sequence[SDFStageCycleTrace]],
) -> tuple[tuple[SDFStageCycleTrace, ...], ...]:
    adjusted: list[tuple[SDFStageCycleTrace, ...]] = []
    for child in children:
        stages: list[SDFStageCycleTrace] = []
        for index, stage in enumerate(child):
            stages.append(
                replace(
                    stage,
                    input_first_cycle=stage.input_first_cycle
                    + (0 if index == 0 else 1),
                    output_first_cycle=stage.output_first_cycle + 1,
                    output_last_cycle=stage.output_last_cycle + 1,
                    last_cycle=stage.last_cycle + 1,
                )
            )
        adjusted.append(tuple(stages))
    return tuple(adjusted)


def subfft_stream_trace(
    frames: Sequence[tuple[str, Sequence[ComplexWord]]],
) -> StreamTrace:
    output_beats: list[StreamBeat] = []
    child_stages: tuple[tuple[SDFStageCycleTrace, ...], ...] = ()
    for frame_number, (frame_id, values) in enumerate(frames):
        if len(values) != 1024:
            raise ValueError("SubFFT stream frame must contain 1024 samples")
        lanes = [
            [values[4 * beat + lane] for beat in range(256)]
            for lane in range(4)
        ]
        if not child_stages:
            child_stages = _shift_child_cycles(
                [classic_r2sdf_fft(lane)[1] for lane in lanes]
            )
        result = subfft_1024(values)
        frame_start = frame_number * 256
        for beat in range(256):
            k = bit_reverse(beat, 8)
            indices = tuple(k + 256 * quarter for quarter in range(4))
            output_beats.append(
                StreamBeat(
                    cycle=frame_start + SUBFFT_LATENCY_CYCLES + beat,
                    frame_id=frame_id,
                    beat_index=beat,
                    valid=True,
                    last=beat == 255,
                    sample_indices=indices,
                    lanes=tuple(result.output[index] for index in indices),
                )
            )
    return StreamTrace(
        group="SubFFT",
        frame_latency_cycles=SUBFFT_LATENCY_CYCLES,
        stage_first_valid_cycles=STAGE_FIRST_VALID_CYCLES,
        output_beats=tuple(output_beats),
        subfft_child_stages=child_stages,
    )


def pfft_stream_trace(
    frames: Sequence[tuple[str, Sequence[ComplexWord]]],
) -> StreamTrace:
    if len(frames) % 2:
        raise ValueError("PFFT stream contract requires complete frame pairs")
    output_beats: list[StreamBeat] = []
    for frame_number, (frame_id, values) in enumerate(frames):
        if len(values) != 1024:
            raise ValueError("PFFT stream frame must contain 1024 samples")
        result = pfft_1024(values)
        frame_start = frame_number * 256
        for beat in range(256):
            physical = tuple(4 * beat + lane for lane in range(4))
            indices = tuple(bit_reverse(index, 10) for index in physical)
            output_beats.append(
                StreamBeat(
                    cycle=frame_start + PFFT_LATENCY_CYCLES + beat,
                    frame_id=frame_id,
                    beat_index=beat,
                    valid=True,
                    last=beat == 255,
                    sample_indices=indices,
                    lanes=tuple(result.output[index] for index in indices),
                )
            )
    return StreamTrace(
        group="PFFT",
        frame_latency_cycles=PFFT_LATENCY_CYCLES,
        stage_first_valid_cycles=STAGE_FIRST_VALID_CYCLES,
        output_beats=tuple(output_beats),
    )


__all__ = [
    "PFFT_LATENCY_CYCLES",
    "PFFT_PAIR_WAIT_AND_SYNC_READ_CYCLES",
    "PHYSICAL_DELAY_DEPTHS",
    "STAGE_FIRST_TOKEN_LATENCIES",
    "STAGE_FIRST_VALID_CYCLES",
    "SUBFFT_LATENCY_CYCLES",
    "pfft_stream_trace",
    "subfft_stream_trace",
]
