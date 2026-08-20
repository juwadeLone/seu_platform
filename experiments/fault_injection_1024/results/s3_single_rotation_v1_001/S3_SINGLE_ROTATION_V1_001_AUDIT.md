# S3-SINGLE-ROT-V1-001 audit

Status: `VERIFIED`.

The frozen S3 evidence remains unchanged. Pre-edit inputs are under
`archive/migration/2026-07-24/pre_edit/S3-SINGLE-ROT-V1-001_authorized/`.

## Qualification

- 2048 output beats / eight frames are bit-exact against the frozen vector.
- Latency remains 268 cycles; valid, last, and frame boundaries are unchanged.
- SECDED, upper arithmetic ECC, Stage-9 TMR, and the added lower arithmetic ECC
  injections are all masked.
- Attempt1 retains a runner-argument failure after bit-exact passed; independent
  qualification attempt2 is the complete verified attempt.

## Yosys xc7 estimate

| Metric | Frozen S3 | Corrected S3 | Delta |
|---|---:|---:|---:|
| Estimated LC | 175,749 | 97,719 | -78,030 |
| LUT1--LUT6 | 218,338 | 120,686 | -97,652 |
| FF | 5,972 | 5,972 | 0 |
| DSP48E1 | 2,496 | 960 | -1,536 |
| RAMB18E1 | 12 | 12 | 0 |
| BRAM36 equivalent | 6.0 | 6.0 | 0 |
| Distributed-memory cells | 404 | 404 | 0 |

Preflight contains no active `independent_rotation_ecc_v5`. The 960 DSP48E1
correspond to 60 generic complex multipliers: 48 required lower rotations in
Stages 1--8 plus 12 Stage-9 TMR rotations.

Resource result SHA-256:
`918DD903D464F1364538322C599361B596EFA5F24973E97A3E715BA408184C07`.

These are Yosys `synth_xilinx -family xc7` estimates, not Vivado
post-implementation utilization, timing, Fmax, or power.
