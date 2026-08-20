#!/usr/bin/env bash
# S1-GAO2023-TH-V1-001: fault-free Gao [7,4,3] syndrome dump on K_S1.
set -euo pipefail
OUT_DIR="$(cd "$(dirname "$0")" && pwd)"
K_RTL="/home/xdu/JuWade_research/fft1024_ft_exp/vivado/K_S1_subfft/hdl/rtl"
IN_HEX="/home/xdu/JuWade_research/fft1024_ft_exp/kernels/S1/vectors/qualification_input_10frames.hex"
EXP_HEX="/home/xdu/JuWade_research/fft1024_ft_exp/kernels/S1/vectors/qualification_subfft_expected_8frames.hex"
SIM="$OUT_DIR/s1_gao2023_nf.vvp"
ASCII_DIR="/tmp/s1_gao2023_threshold_v1_001"
mkdir -p "$ASCII_DIR"
CSV="$ASCII_DIR/syndrome_faultfree.csv"

{
  echo "record=S1-GAO2023-TH-V1-001"
  echo "iverilog=$(iverilog -V 2>&1 | head -n 1)"
  echo "date=$(date -Iseconds)"
  sha256sum \
    "$K_RTL/top_s1_kernel.sv" \
    "$K_RTL/twiddle_rom_1024.sv" \
    "$K_RTL/fft_common.sv" \
    "$K_RTL/datapath_v5.sv" \
    "$K_RTL/protection_rtl.sv" \
    "$K_RTL/protection_primitives_v5.sv" \
    "$IN_HEX" "$EXP_HEX" \
    "$OUT_DIR/tb_s1_gao2023_noise_floor.sv"
} | tee "$OUT_DIR/input_hashes.txt"

iverilog -g2012 -Wall -o "$SIM" -s tb_s1_gao2023_noise_floor \
  "$K_RTL/twiddle_rom_1024.sv" \
  "$K_RTL/fft_common.sv" \
  "$K_RTL/datapath_v5.sv" \
  "$K_RTL/protection_rtl.sv" \
  "$K_RTL/protection_primitives_v5.sv" \
  "$K_RTL/top_s1_kernel.sv" \
  "$OUT_DIR/tb_s1_gao2023_noise_floor.sv" \
  2>&1 | tee "$OUT_DIR/compile.log"

vvp "$SIM" +CSV="$CSV" +INPUT_HEX="$IN_HEX" +EXPECTED_HEX="$EXP_HEX" \
  2>&1 | tee "$OUT_DIR/sim.log"
cp -f "$CSV" "$OUT_DIR/syndrome_faultfree.csv"
