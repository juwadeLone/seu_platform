#!/usr/bin/env bash
# ============================================================================
# SC-01 RTL Gao-threshold fault-injection simulation: compile + run
# Usage:
#   ./sc01_rtl_compile.sh [threshold] [stage_min] [stage_max] [sym_min] [sym_max]
#   defaults: 0 1 1 0 0   (stage 1, symbol 0, tau=0)
# ============================================================================
set -e
TCAS_ROOT="/home/xdu/☆☆☆☆☆☆☆☆☆☆☆☆☆☆☆朱奥科研/hermes/tcas"
RTL_DIR="$TCAS_ROOT/experiments/fault_injection_1024/common/rtl"
OUT_DIR="$TCAS_ROOT/experiments/fault_injection_1024/results/sc01_rtl_v1_001"
THRESHOLD="${1:-0}"
STAGE_MIN="${2:-1}"
STAGE_MAX="${3:-1}"
SYMBOL_MIN="${4:-0}"
SYMBOL_MAX="${5:-0}"
SIM="/tmp/sc01_sim_${THRESHOLD}_${STAGE_MIN}_${STAGE_MAX}_${SYMBOL_MIN}_${SYMBOL_MAX}.vvp"

echo "=== SC-01 RTL compile: threshold=$THRESHOLD stages=$STAGE_MIN..$STAGE_MAX symbols=$SYMBOL_MIN..$SYMBOL_MAX ==="
iverilog -g2012 -Wall -o "$SIM" \
  -P sc01_fault_injection_tb.THRESHOLD="$THRESHOLD" \
  -P sc01_fault_injection_tb.STAGE_MIN="$STAGE_MIN" \
  -P sc01_fault_injection_tb.STAGE_MAX="$STAGE_MAX" \
  -P sc01_fault_injection_tb.SYMBOL_MIN="$SYMBOL_MIN" \
  -P sc01_fault_injection_tb.SYMBOL_MAX="$SYMBOL_MAX" \
  -I "$RTL_DIR" \
  "$RTL_DIR/twiddle_rom_1024.sv" \
  "$RTL_DIR/fft_common.sv" \
  "$RTL_DIR/datapath_v5.sv" \
  "$RTL_DIR/protection_rtl.sv" \
  "$RTL_DIR/protection_primitives_v5.sv" \
  "$RTL_DIR/protected_stages_v5.sv" \
  "$RTL_DIR/top_s3_subfft_ecc_thresholded.sv" \
  "$OUT_DIR/sc01_rtl_tb.sv"

echo "=== run: vvp $SIM ==="
cd "$TCAS_ROOT"
vvp "$SIM"
