# S3-SINGLE-ROT-V1-001 execution contract

## Scope

- Keep `results/seven_arch_v1/` and every pre-existing result immutable.
- Keep the 1024-point, four-lane, ten-stage radix-2 SubFFT algorithm,
  twiddle exponents, `[6,4,3]` arithmetic ECC rule, and Yosys `xc7` flow
  unchanged.
- In S3 Stage 1--8, retain one required lower/difference-branch rotation per
  encoded stream and leave the upper/sum branch unrotated.
- Do not instantiate `independent_rotation_ecc_v5` when `PFFT_MODE=0`.
  Preserve its existing behavior when `PFFT_MODE!=0`.
- Keep Stage 9--10 TMR unchanged.

## Frozen inputs and independent outputs

- Pre-edit snapshot:
  `archive/migration/2026-07-24/pre_edit/S3-SINGLE-ROT-V1-001_authorized/`.
- Qualification output:
  `experiments/fault_injection_1024/results/s3_single_rotation_v1_001/qualification_attempt1/`.
- Yosys output:
  `experiments/fault_injection_1024/results/s3_single_rotation_v1_001/yosys_attempt1/`.

## Qualification gates

1. Source audit finds exactly six generic complex multipliers in each
   `independent_butterfly_ecc_v5` instance selected for SubFFT: no generic
   upper rotation and one lower rotation for each of six encoded streams.
2. The SubFFT elaborated hierarchy contains no
   `independent_rotation_ecc_v5`.
3. Eight output frames (2048 four-lane beats) remain bit-exact against the
   frozen SubFFT vector, with unchanged latency, `out_valid`, `out_last`, and
   frame boundaries.
4. The existing S3 SECDED-memory, upper arithmetic ECC, and Stage-9 TMR
   connectivity injections remain masked.
5. A new lower arithmetic ECC injection is masked and produces the same
   data/control stream as a clean instance.

Yosys may run only after every qualification gate passes.  The formal flow
remains `read_verilog -sv`, `hierarchy -check`, `synth_xilinx -family xc7`,
`stat -tech xilinx`, and `write_json`.

