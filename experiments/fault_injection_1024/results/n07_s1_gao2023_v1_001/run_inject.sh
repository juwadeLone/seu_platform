#!/usr/bin/env bash
# N07 S1 Gao-2023 inject. Usage: bash run_inject.sh <THRESHOLD>
set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
hash -r
TAU="${1:?threshold integer required}"
TCAS_ROOT="/home/xdu/☆☆☆☆☆☆☆☆☆☆☆☆☆☆☆朱奥科研/hermes/tcas"
RTL_DIR="$TCAS_ROOT/experiments/fault_injection_1024/common/rtl"
S1_DIR="$TCAS_ROOT/experiments/fault_injection_1024/projects/S1"
OUT="$(cd "$(dirname "$0")" && pwd)"
TB="$OUT/sc01_s1_rtl_tb.sv"
DUT="$OUT/top_s1_gao_subfft_ecc_thresholded.sv"
PROGRESS="$OUT/progress.txt"
LOG="$OUT/run_all.log"
: > "$PROGRESS"
echo "$(date -Iseconds) START N07 S1 tau=$TAU paths=0-6 two-frames 490 trials" | tee -a "$PROGRESS"
SIM="/tmp/n07_s1_tau${TAU}.vvp"
iverilog -g2012 -Wall -o "$SIM" \
  -P sc01_s1_fault_injection_tb.THRESHOLD="$TAU" \
  -P sc01_s1_fault_injection_tb.SYMBOL_MIN=0 \
  -P sc01_s1_fault_injection_tb.SYMBOL_MAX=6 \
  -I "$RTL_DIR" \
  "$RTL_DIR/twiddle_rom_1024.sv" \
  "$RTL_DIR/fft_common.sv" \
  "$RTL_DIR/datapath_v5.sv" \
  "$RTL_DIR/protection_rtl.sv" \
  "$RTL_DIR/protection_primitives_v5.sv" \
  "$RTL_DIR/protected_stages_v5.sv" \
  "$S1_DIR/top_s1_gao_subfft_ecc.sv" \
  "$DUT" \
  "$TB" > "$OUT/compile.log" 2>&1

: > "$LOG"
(
  cd "$TCAS_ROOT"
  stdbuf -oL -eL /usr/bin/vvp "$SIM"
) > "$LOG" 2>&1 &
sim=$!
while kill -0 "$sim" 2>/dev/null; do
  n=$(grep -c '^TRIAL' "$LOG" 2>/dev/null || true)
  last=$(grep '^TRIAL' "$LOG" 2>/dev/null | tail -1 | tr -d '\r' || true)
  printf '%s trials=%s/490 last=%s\n' "$(date '+%H:%M:%S')" "${n:-0}" "${last:-none}" | tee -a "$PROGRESS"
  sleep 15
done
wait "$sim" || {
  echo "$(date -Iseconds) FAIL vvp S1 exit=$?" | tee -a "$PROGRESS"
  exit 1
}
sum=$(grep '^SUMMARY' "$LOG" | tr -d '\r' || true)
echo "$(date -Iseconds) ALL_DONE S1 tau=$TAU $sum" | tee -a "$PROGRESS"
echo "$sum" > "$OUT/combined_summary.txt"
