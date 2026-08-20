# P2-YOSYS-NO-FRAMEBUF-V1-001 execution audit

Overall status: **VERIFIED**

## Attempt history

- Attempt1 stopped inside the runner before `yosys -V`. The P2 qualification
  was `VERIFIED` but did not contain the P0-specific optional
  `synthesis_authorized` field. No Yosys subprocess was started.
- Attempt2 used independent result, log and build directories. The gate was
  corrected to accept a `VERIFIED` qualification unless it explicitly sets
  `synthesis_authorized` to false.
- Attempt1 evidence was not overwritten.

## Attempt2 execution

- Yosys version gate: VERIFIED.
- `read_verilog`: completed.
- `hierarchy -check`: completed.
- `check`: completed.
- `proc`, `opt_clean`, preflight JSON: completed.
- Formal `synth_xilinx -family xc7`: completed.
- Selected top: `top_p2_pfft_tmr_no_framebuf_v1`.
- Reachable complete-stage TMR wrappers: 10.
- Reachable terminal frame-pair buffer instances: 0.

## Resource comparison

These values are Yosys xc7 synthesis estimates, not Vivado implementation
utilization, timing, Fmax or power.

| Metric | Historical P2 | P2 without terminal frame buffer | Delta |
|---|---:|---:|---:|
| LC estimate | 69464 | 69420 | -44 |
| LUT1--LUT6 | 95826 | 95466 | -360 |
| FF | 12474 | 12462 | -12 |
| DSP48E1 | 1392 | 1392 | 0 |
| RAMB18E1 | 0 | 0 | 0 |
| RAMB36E1 | 16 | 12 | -4 |
| BRAM36 equivalent | 16.0 | 12.0 | -4.0 |
| Distributed RAM cells | 1116 | 1116 | 0 |

The measured result confirms that the unprotected, post-voter terminal
two-frame delay consumed four RAMB36E1 blocks. The remaining twelve RAMB36E1
blocks belong to the triplicated FFT-core storage.

The authoritative machine-readable result is:

`attempt2/p2_resource_result.json`
