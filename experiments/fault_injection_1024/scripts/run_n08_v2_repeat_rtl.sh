#!/usr/bin/env bash
set -euo pipefail

ARCH="${1:?arch must be s3 or p1}"
K="${2:?k must be 2, 5, or 8}"
ROOT="/home/xdu/☆☆☆☆☆☆☆☆☆☆☆☆☆☆☆朱奥科研/hermes/tcas"
RTL="$ROOT/experiments/fault_injection_1024/common/rtl"
P1="$ROOT/experiments/fault_injection_1024/projects/P1"
if [[ "$K" == 2 ]]; then TRIALS=500; else TRIALS=200; fi

if [[ "$ARCH" == s3 ]]; then
  OUT="$ROOT/experiments/fault_injection_1024/results/n08_multi_k${K}_s3_v2_002"
  TOP=n08_multi_rtl_tb_s3_v2
  TB="$ROOT/experiments/fault_injection_1024/results/n08_multi_rtl_tb_s3_v2.sv"
  WRAP="$ROOT/experiments/fault_injection_1024/results/n08_multi_k2_s3_v1_001/n08_s3_multifault_top.sv"
  EXTRA=("$RTL/top_s3_subfft_ecc_thresholded.sv" "$WRAP")
  TAU=2
elif [[ "$ARCH" == p1 ]]; then
  OUT="$ROOT/experiments/fault_injection_1024/results/n08_multi_k${K}_p1_v2_002"
  TOP=n08_multi_rtl_tb_p1_v2
  TB="$ROOT/experiments/fault_injection_1024/results/n08_multi_rtl_tb_p1_v2.sv"
  WRAP="$ROOT/experiments/fault_injection_1024/results/n08_multi_k2_p1_v1_001/n08_p1_multifault_top.sv"
  EXTRA=("$RTL/p1_thresholded_stages.sv" "$P1/top_p1_pfft_ecc.sv" "$WRAP")
  TAU=3
else
  echo "unsupported arch: $ARCH" >&2
  exit 2
fi

SITE="$OUT/sites_k${K}_v1.csv"
SITE_ARG="${SITE#$ROOT/}"
SIM="/tmp/n08_v2_repeat_${ARCH}_k${K}.vvp"
LOG="$OUT/run_k${K}.log"
PROGRESS="$OUT/progress.txt"
COMPILE="$OUT/compile.log"

echo "$(date -Iseconds) START_V2_REPEAT arch=$ARCH k=$K trials=$TRIALS tau=$TAU site=$SITE_ARG" | tee "$PROGRESS"
iverilog -g2012 -Wall -s "$TOP" -o "$SIM" \
  -P "$TOP.THRESHOLD=$TAU" -P "$TOP.K_MODE=$K" -P "$TOP.TRIALS=$TRIALS" -P "$TOP.LEGACY_N07_HOLD=0" \
  -I "$RTL" \
  "$RTL/twiddle_rom_1024.sv" "$RTL/fft_common.sv" "$RTL/datapath_v5.sv" \
  "$RTL/protection_rtl.sv" "$RTL/protection_primitives_v5.sv" "$RTL/protected_stages_v5.sv" \
  "${EXTRA[@]}" "$TB" > "$COMPILE" 2>&1
echo "$(date -Iseconds) COMPILE_OK_V2_REPEAT arch=$ARCH k=$K" | tee -a "$PROGRESS"

: > "$LOG"
(
  cd "$ROOT"
  stdbuf -oL -eL vvp "$SIM" +SITE="$SITE_ARG"
) > "$LOG" 2>&1 &
PID=$!
while kill -0 "$PID" 2>/dev/null; do
  count=$(grep -c '^TRIAL ' "$LOG" 2>/dev/null || true)
  last=$(grep '^TRIAL ' "$LOG" 2>/dev/null | tail -1 | tr -d '\r' || true)
  echo "$(date -Iseconds) RUNNING_V2_REPEAT arch=$ARCH k=$K trials=$count/$TRIALS last=${last:-none}" | tee -a "$PROGRESS"
  sleep 15
done
wait "$PID"
summary=$(grep '^SUMMARY ' "$LOG" | tail -1 || true)
echo "$(date -Iseconds) DONE_V2_REPEAT arch=$ARCH k=$K $summary" | tee -a "$PROGRESS"
