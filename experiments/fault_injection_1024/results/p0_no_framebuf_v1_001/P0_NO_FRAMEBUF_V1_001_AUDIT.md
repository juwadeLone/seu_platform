# P0-NO-FRAMEBUF-V1-001 execution audit

Overall status: **VERIFIED**

## RTL qualification

- Frozen ten-frame input and frozen eight-frame P0 expected output were reused.
- The historical P0 RTL, vectors, logs and resource results were not modified.
- The isolated top instantiates the unchanged
  `p0_pfft_no_exchange_pipeline_v3` directly.
- 2048 output beats formed eight consecutive 256-beat frames.
- Data mismatches: 0.
- `out_valid` gaps after first output: 0.
- `out_last` errors: 0.
- Frame loss, duplication or reordering: 0.
- Measured latency: 268 cycles; informational only.

## Yosys execution

Attempt1 passed `yosys -V` but failed before `read_verilog` with
`GetShortPathName() failed.` No synthesis was executed in attempt1.

Attempt2 used a new directory and the historical explicit OSS CAD Suite
environment outside the sandbox. Version gate, preflight and
`synth_xilinx -family xc7` completed successfully.

## Resource comparison

These numbers are Yosys xc7 synthesis estimates, not Vivado implementation
utilization, timing, Fmax or power.

| Metric | Historical P0 | P0 without terminal frame buffer | Delta |
|---|---:|---:|---:|
| LC estimate | 22689 | 22670 | -19 |
| LUT1--LUT6 | 31010 | 30882 | -128 |
| FF | 4166 | 4154 | -12 |
| DSP48E1 | 464 | 464 | 0 |
| RAMB18E1 | 16 | 0 | -16 |
| RAMB36E1 | 0 | 4 | +4 |
| BRAM36 equivalent | 8.0 | 4.0 | -4.0 |
| Distributed RAM cells | not used for the historical comparison | 372 | n/a |

Removing the terminal four-lane, two-bank frame delay reduced the total block
RAM allocation by four BRAM36 equivalents. The remaining FFT-core storage was
repacked by Yosys as four RAMB36E1 blocks, so the result did not fall to zero
BRAM.

## Parser audit

The first attempt2 JSON parser counted only the experiment top's direct cells,
while `keep_hierarchy` left the P0 pipeline below one hierarchical instance.
That file is preserved as failed parsing evidence. A first recursive audit also
descended into Xilinx simulation-model modules; it too is preserved. The
authoritative result is:

`attempt2/resource_result_corrected_recursive_leaf_audit.json`

It recursively traverses design hierarchy while treating mapped Xilinx
primitives as leaf cells. No synthesis rerun or RTL change was used to produce
the corrected audit.
