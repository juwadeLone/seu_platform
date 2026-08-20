#!/usr/bin/env bash
# N07-S3-TAU2-GAO2023-V1: one global tau=2, two frames/trial, stages 1-8, 6 symbols.
set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
hash -r

TCAS_ROOT="/home/xdu/☆☆☆☆☆☆☆☆☆☆☆☆☆☆☆朱奥科研/hermes/tcas"
RTL_DIR="$TCAS_ROOT/experiments/fault_injection_1024/common/rtl"
TB="$TCAS_ROOT/experiments/fault_injection_1024/results/sc01_rtl_v1_001/sc01_rtl_tb.sv"
OUT="$(cd "$(dirname "$0")" && pwd)"
PROGRESS="$OUT/progress.txt"
COMBINED="$OUT/combined_summary.txt"

: > "$PROGRESS"
: > "$COMBINED"
echo "$(date -Iseconds) START N07 tau=2 stages=1-8 symbols=0-5 two-frames" | tee -a "$PROGRESS"

heartbeat() {
  local log="$1" s="$2"
  local n last done
  n=$(grep -c '^TRIAL' "$log" 2>/dev/null || true)
  n=${n:-0}
  last=$(grep '^TRIAL' "$log" 2>/dev/null | tail -1 | tr -d '\r' || true)
  done=$((s * 560 + n))
  printf '%s symbol=%s trials=%s/560 done=%s/3360 last=%s\n' \
    "$(date '+%H:%M:%S')" "$s" "$n" "$done" "${last:-none}"
}

for s in 0 1 2 3 4 5; do
  LOG="$OUT/run_sym${s}.log"
  SIM="/tmp/n07_tau2_1_8_${s}_${s}.vvp"
  echo "===== $(date -Iseconds) COMPILE tau=2 stages=1..8 symbol=$s =====" | tee -a "$PROGRESS"
  iverilog -g2012 -Wall -o "$SIM" \
    -P sc01_fault_injection_tb.THRESHOLD=2 \
    -P sc01_fault_injection_tb.STAGE_MIN=1 \
    -P sc01_fault_injection_tb.STAGE_MAX=8 \
    -P sc01_fault_injection_tb.SYMBOL_MIN="$s" \
    -P sc01_fault_injection_tb.SYMBOL_MAX="$s" \
    -I "$RTL_DIR" \
    "$RTL_DIR/twiddle_rom_1024.sv" \
    "$RTL_DIR/fft_common.sv" \
    "$RTL_DIR/datapath_v5.sv" \
    "$RTL_DIR/protection_rtl.sv" \
    "$RTL_DIR/protection_primitives_v5.sv" \
    "$RTL_DIR/protected_stages_v5.sv" \
    "$RTL_DIR/top_s3_subfft_ecc_thresholded.sv" \
    "$TB" > "$OUT/compile_sym${s}.log" 2>&1

  echo "===== $(date -Iseconds) RUN vvp symbol=$s =====" | tee -a "$PROGRESS"
  : > "$LOG"
  (
    cd "$TCAS_ROOT"
    stdbuf -oL -eL /usr/bin/vvp "$SIM"
  ) > "$LOG" 2>&1 &
  sim=$!

  while kill -0 "$sim" 2>/dev/null; do
    line=$(heartbeat "$LOG" "$s")
    echo "$line" | tee -a "$PROGRESS"
    sleep 15
  done
  wait "$sim" || {
    echo "$(date -Iseconds) FAIL vvp symbol=$s exit=$?" | tee -a "$PROGRESS"
    heartbeat "$LOG" "$s" | tee -a "$PROGRESS"
    exit 1
  }

  sum=$(grep '^SUMMARY' "$LOG" | tr -d '\r' || true)
  echo "$(date -Iseconds) DONE symbol=$s $sum" | tee -a "$PROGRESS"
  echo "symbol=$s $sum" >> "$COMBINED"
done

echo "$(date -Iseconds) ALL_DONE tau=2 3360 trials" | tee -a "$PROGRESS"
grep -h '^SUMMARY ' "$OUT"/run_sym*.log | tee -a "$COMBINED"
