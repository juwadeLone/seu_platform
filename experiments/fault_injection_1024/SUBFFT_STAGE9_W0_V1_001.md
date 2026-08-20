# SUBFFT-STAGE9-W0-V1-001

Status before execution: `AUTHORIZED / INPUTS_SNAPSHOTTED`.

## Scope

- Preserve all pre-existing RTL and experiment evidence through the pre-edit
  snapshot and independent result directories.
- Do not modify any Python numerical model.
- In the shared `subfft_stage9` only, replace the lane-0 generic multiplication
  by the constant twiddle `W_1024^0 = 1` with a direct connection.
- Do not change the FFT algorithm, twiddle table, data ordering, fixed-point
  widths, interfaces, ECC, Gao, or TMR protection.

## Qualification gates

S0, S1, S2, and S3 must each pass the frozen 2048-beat SubFFT expected vector,
including valid, last, frame boundaries, and the existing 268-cycle latency.
S1 Gao, S2 TMR, and S3 SECDED/arithmetic-ECC/TMR connectivity injections must
remain masked. S3 also retains the lower-arithmetic ECC injection introduced by
`S3-SINGLE-ROT-V1-001`.

Yosys may run only if all four qualification targets and all protection
connectivity cases pass.

## Yosys boundary

Each architecture uses an independent attempt directory with the unchanged
`synth_xilinx -family xc7` flow. Resources are measured results, not theoretical
targets, and are not Vivado post-implementation utilization, timing, Fmax, or
power.
