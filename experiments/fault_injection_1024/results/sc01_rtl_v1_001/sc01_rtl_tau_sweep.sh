#!/usr/bin/env bash
# SC-01 RTL tau sweep: run stage 1..8 symbol 0 for each tau in {0,1,2,4,8}
# Logs go to sc01_rtl_run_tau<tau>.log in the results dir.
TCAS_ROOT="/home/xdu/☆☆☆☆☆☆☆☆☆☆☆☆☆☆☆朱奥科研/hermes/tcas"
OUT_DIR="$TCAS_ROOT/experiments/fault_injection_1024/results/sc01_rtl_v1_001"
cd "$TCAS_ROOT"
for tau in 0 1 2 4 8; do
  echo "===== tau=$tau ====="
  bash "$OUT_DIR/sc01_rtl_compile.sh" "$tau" 1 8 0 0 > "$OUT_DIR/sc01_rtl_run_tau${tau}.log" 2>&1
  echo "tau=$tau done: $(grep 'SUMMARY recovery_rate' "$OUT_DIR/sc01_rtl_run_tau${tau}.log" | tail -1)"
done
echo "ALL_DONE"
