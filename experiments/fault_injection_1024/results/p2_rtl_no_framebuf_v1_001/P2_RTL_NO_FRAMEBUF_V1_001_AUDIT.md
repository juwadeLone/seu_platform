# P2-RTL-NO-FRAMEBUF-V1-001 audit

Status: **VERIFIED**

- Historical P2 RTL and evidence were not modified.
- The isolated core reuses the historical P2 TMR wrappers for Stages 1--10.
- Stage-10 voted data, valid and last connect directly to the isolated top.
- No terminal `pfft_frame_pair_buffer_v5` instance is reachable.
- Eight frames / 2048 four-lane beats matched the frozen P2 vector.
- `out_valid` gaps: 0.
- Frame length: 256 valid beats for each of eight frames.
- `out_last` errors: 0.
- Frame loss, duplication and reordering: 0.
- Measured latency: 268 cycles; informational only.
- Yosys and Vivado were not run.

The result establishes bit-exact RTL functionality and stream-control behavior
for the isolated no-frame-buffer P2 version. It does not establish a new
resource estimate.
