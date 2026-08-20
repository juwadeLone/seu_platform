# P0-NO-FRAMEBUF-V1-001

Status: `AUTHORIZED / NOT_EXECUTED`

## Objective

Measure the functional and Yosys `xc7` resource effect of removing only the
terminal `pfft_frame_pair_buffer_v5` from P0.

## Frozen baseline

- Baseline top: `projects/P0/top_p0_pfft_unprotected.sv`
- Input: `common/vectors/qualification_input_10frames.hex`
- Expected output: `projects/P0/vectors/qualification_p0_no_exchange_expected_8frames.hex`
- Historical resource evidence is read-only and must not be overwritten.

## Allowed RTL delta

The isolated top directly instantiates
`p0_pfft_no_exchange_pipeline_v3`. The FFT pipeline, stages, twiddle factors,
common RTL and historical P0 top remain unchanged. The only removed reachable
instance is the terminal `pfft_frame_pair_buffer_v5`.

## RTL qualification acceptance criteria

Fixed latency is measured for information only and is not a PASS/FAIL
criterion.

1. Eight frames (2048 four-lane beats) match the frozen expected vector.
2. `out_valid` has no gap after the first accepted output until beat 2048.
3. Every frame contains exactly 256 valid four-lane beats.
4. `out_last` is asserted exactly on the final valid beat of every frame.
5. Eight consecutive frame boundaries are correct, with no loss, duplicate,
   reordering, or extra output before completion.

If qualification fails, Yosys must not run.

## Yosys boundary

After qualification PASS, synthesize only the isolated P0 top with
`C:\Users\pc\Downloads\oss-cad-suite\bin\yosys.exe`,
`synth_xilinx -family xc7`, an explicit controlled environment and an
independent ASCII working directory. Report the result only as a Yosys xc7
resource estimate and compare it with historical P0:

- LC estimate 22689
- LUT1--LUT6 31010
- FF 4166
- DSP48E1 464
- RAMB18E1 16
- RAMB36E1 0
- BRAM36 equivalent 8.0

All new inputs, logs, scripts and results are isolated under
`p0_no_framebuf_v1_001/attempt1`.
