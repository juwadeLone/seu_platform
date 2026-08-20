# Seven-architecture Yosys resource audit

Overall status: **VERIFIED**

- Tool: `Yosys 0.66+181 (git sha1 afe6b18f2, Release, GNU /usr/bin/x86_64-w64-mingw32-g++ 13.2.1)`
- Flow: `synth_xilinx -family xc7` on the same frozen eight-file RTL-v5 source set.
- Boundary: synthesis resource estimates only; not Vivado post-implementation utilization, timing, Fmax, or power.
- Hard gates: live replica multiplicity, critical blackboxes/warnings, per-memory primitive class, cross-architecture mapping consistency, and P1 pending-memory output reachability.

## SubFFT group

| ID | LUT (est. LC) | FF | DSP48E1 | RAMB18 | RAMB36 | BRAM36 equiv. |
|---|---:|---:|---:|---:|---:|---:|
| S0 | 26330 | 4162 | 576 | 0 | 4 | 4.0 |
| S1 | 52788 | 8666 | 1088 | 0 | 7 | 7.0 |
| S2 | 80399 | 12486 | 1728 | 0 | 12 | 12.0 |
| S3 | 175749 | 5972 | 2496 | 12 | 0 | 6.0 |

## PFFT group

| ID | LUT (est. LC) | FF | DSP48E1 | RAMB18 | RAMB36 | BRAM36 equiv. |
|---|---:|---:|---:|---:|---:|---:|
| P0 | 25159 | 4188 | 576 | 0 | 8 | 8.0 |
| P1 | 186813 | 10918 | 2432 | 30 | 4 | 19.0 |
| P2 | 76873 | 12540 | 1728 | 0 | 16 | 16.0 |
