# P2-PY-NO-FRAMEBUF-V1-001

Status: `VERIFIED`

## Scope

Create an isolated P2 Python campaign version whose external output contract is
the direct Stage-10 voter stream without the terminal
`pfft_frame_pair_buffer_v5`.

The numerical FFT model and all ten complete-stage TMR injection loops remain
unchanged. The existing `projects/P2/run_p2.py`, its results, the common
seven-architecture contract and all frozen evidence remain unchanged.

## Expected Python delta

- Replace the historical no-fault evidence label
  `group_output_stream_with_common_2x1024_reorder_buffer`.
- Use
  `direct_stage10_voter_output_without_terminal_frame_pair_buffer`.
- State explicitly that the recovery boundary ends at each stage-local voter
  and that no post-voter frame memory is part of this P2 version.
- Keep `EXPECTED_TRIALS=16809` and the existing fault schedule unchanged.

## Output

The isolated run writes only to:

`results/p2_py_no_framebuf_v1_001/attempt1/`

This Python version does not modify RTL and does not produce a Yosys resource
claim.

## Result

- Trial count: 16809 / 16809.
- Failures: 0.
- SDC: 0.
- Deterministic full-row replay: PASS.
- No-fault frame digests: 8 / 8.
- Output stream contract:
  `direct_stage10_voter_output_without_terminal_frame_pair_buffer`.
- `terminal_frame_pair_buffer_modeled`: `false`.
