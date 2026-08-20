# P2-RTL-NO-FRAMEBUF-V1-001

Status: `AUTHORIZED / NOT_EXECUTED`

## Frozen baseline

- Historical source: `projects/P2/top_p2_pfft_tmr.sv`
- Frozen input vector:
  `common/vectors/qualification_input_10frames.hex`
- Frozen expected vector:
  `projects/P2/vectors/qualification_p2_no_exchange_expected_8frames.hex`
- Existing P2 RTL, vectors, logs, qualification and Yosys results are read-only.

## Authorized RTL delta

Create an isolated P2 top that reuses the historical P2 complete-stage TMR
wrappers for Stages 1--10. Connect the voted Stage-10 outputs directly to the
new top outputs. Do not instantiate the terminal single-copy
`pfft_frame_pair_buffer_v5`.

No FFT stage, TMR replica, voter, twiddle factor, numerical width or scaling
logic may change.

## Qualification

Fixed latency is measured for information only and is not an acceptance
criterion.

1. Eight frames / 2048 four-lane beats match the frozen P2 expected vector.
2. `out_valid` is continuous after the first output.
3. Each frame has 256 valid beats.
4. `out_last` is asserted only on each frame's final valid beat.
5. Consecutive frame boundaries show no loss, duplicate or reordering.

This authorization does not include Yosys or Vivado.
