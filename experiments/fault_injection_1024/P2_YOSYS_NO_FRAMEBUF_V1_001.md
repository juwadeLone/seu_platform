# P2-YOSYS-NO-FRAMEBUF-V1-001

Status: `AUTHORIZED / NOT_EXECUTED`

## Input

- Qualified isolated RTL:
  `projects/P2/top_p2_pfft_tmr_no_framebuf_v1.sv`
- Historical P2 module definitions:
  `projects/P2/top_p2_pfft_tmr.sv`
- Qualification:
  `results/p2_rtl_no_framebuf_v1_001/attempt1/qualification.json`
- Common six-file RTL source set used by the historical PFFT resource flow.

The selected top is `top_p2_pfft_tmr_no_framebuf_v1`. The historical
`top_p2_pfft_tmr` is parsed only to provide the unchanged TMR wrapper module
definitions and is not reachable from the selected top.

## Flow

1. Explicit controlled OSS CAD Suite environment and unique ASCII directory.
2. `yosys -V`.
3. `read_verilog -sv`.
4. `hierarchy -check`.
5. `check`.
6. `proc`.
7. `opt_clean`.
8. `write_json` preflight.
9. `synth_xilinx -family xc7`.
10. `stat` and post-synthesis JSON.

Any failure stops the attempt. The result is a Yosys xc7 resource estimate,
not Vivado post-implementation utilization, timing, Fmax or power.

## Historical comparison

- LC estimate: 69464
- LUT1--LUT6: 95826
- FF: 12474
- DSP48E1: 1392
- RAMB18E1: 0
- RAMB36E1: 16
- BRAM36 equivalent: 16.0
- Distributed RAM cells: 1116

All new artifacts use
`results|logs|build/p2_yosys_no_framebuf_v1_001/attempt1`.
