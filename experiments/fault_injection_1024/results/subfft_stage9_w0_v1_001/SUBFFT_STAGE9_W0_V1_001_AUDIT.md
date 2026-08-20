# SUBFFT-STAGE9-W0-V1-001 audit

Status: `RECORDED_VERIFIED`.

The experiment record manifest covers the complete evidence directory and is
stored as `experiment_record_manifest.json`.

## RTL scope

Only `common/rtl/fft_common.sv::subfft_stage9` changed. The lane-0 operation
`x * W_1024^0` was replaced by direct real/imaginary connections. All Python
files, twiddle tables, data ordering, interfaces, ECC, Gao, and TMR structures
remain unchanged.

S0 directly instantiates `subfft_stage9`. S1, S2, and S3 share it through the
three replicas in `tmr_subfft_stage9_v5`.

## Qualification

S0, S1, S2, and S3 each passed 2048 output beats / eight frames against the
frozen SubFFT vector at the unchanged 268-cycle latency. Valid, last, and frame
boundaries passed. S1 Gao, S2 TMR, and S3 SECDED, upper/lower arithmetic ECC,
and Stage-9 TMR connectivity injections remained masked.

Qualification JSON SHA-256:
`756820C0CD0E700A1C143EC4989125C05AC0D824F9D73B7B51948F09C36F8C5C`.

## Yosys

The first S0 preflight attempt stopped before hierarchy because PowerShell
attached a semicolon to the top source filename. It is retained unchanged.
Independent attempt2 used the same commands in `.ys` files. Version gates,
preflights, and formal `synth_xilinx -family xc7` runs passed for all four
architectures.

| ID | LC before | LC after | LUT1--6 before | LUT1--6 after | FF after | DSP before | DSP after | BRAM36eq after |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S0 | 26,330 | 25,764 | 35,663 | 34,937 | 4,162 | 576 | 560 | 4.0 |
| S1 | 52,788 | 51,114 | 71,432 | 69,241 | 8,666 | 1,088 | 1,040 | 7.0 |
| S2 | 80,399 | 78,701 | 109,809 | 107,631 | 12,486 | 1,728 | 1,680 | 12.0 |
| S3 | 97,719 | 96,021 | 120,686 | 118,505 | 5,972 | 960 | 912 | 6.0 |

S0 removes one Stage-9 multiplier. S1/S2/S3 each remove one multiplier from
each of the three Stage-9 TMR replicas. No FF, BRAM, or distributed-memory
count changed.

Resource summary SHA-256:
`6CF20747EC540998BFCC37F1843AFB00F366E59A5D2B10FFFA2A8C27C506129E`.

All numbers are Yosys `xc7` synthesis estimates, not Vivado
post-implementation utilization, timing, Fmax, or power.
