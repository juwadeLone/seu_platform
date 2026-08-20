#!/usr/bin/env bash
# ============================================================================
# SC-01 P1 RTL Gao-threshold fault-injection: compile + run
# Usage:
#   ./sc01_p1_rtl_compile.sh [threshold] [stage_mode]
#   defaults: 0 0
#   stage_mode: 0 = full (3360), 1 = stages 1-7 only (2940), 2 = stage 10 only (420)
# ============================================================================
set -e
TCAS_ROOT="/home/xdu/☆☆☆☆☆☆☆☆☆☆☆☆☆☆☆朱奥科研/hermes/tcas"
RTL_DIR="$TCAS_ROOT/experiments/fault_injection_1024/common/rtl"
P1_DIR="$TCAS_ROOT/experiments/fault_injection_1024/projects/P1"
OUT_DIR="$TCAS_ROOT/experiments/fault_injection_1024/results/sc01_p1_rtl_v1_001"
THRESHOLD="${1:-0}"
STAGE_MODE="${2:-0}"
SIM="/tmp/sc01_p1_sim_tau${THRESHOLD}_m${STAGE_MODE}.vvp"

echo "=== SC-01 P1 RTL compile: threshold=$THRESHOLD stage_mode=$STAGE_MODE ==="
iverilog -g2012 -Wall -o "$SIM" \
  -P sc01_p1_fault_injection_tb.THRESHOLD="$THRESHOLD" \
  -P sc01_p1_fault_injection_tb.STAGE_MODE="$STAGE_MODE" \
  -I "$RTL_DIR" \
  "$RTL_DIR/twiddle_rom_1024.sv" \
  "$RTL_DIR/fft_common.sv" \
  "$RTL_DIR/datapath_v5.sv" \
  "$RTL_DIR/protection_rtl.sv" \
  "$RTL_DIR/protection_primitives_v5.sv" \
  "$RTL_DIR/protected_stages_v5.sv" \
  "$RTL_DIR/p1_thresholded_stages.sv" \
  "$P1_DIR/top_p1_pfft_ecc.sv" \
  "$OUT_DIR/sc01_p1_rtl_tb.sv"

echo "=== run: vvp $SIM ==="
cd "$TCAS_ROOT"
vvp "$SIM"
