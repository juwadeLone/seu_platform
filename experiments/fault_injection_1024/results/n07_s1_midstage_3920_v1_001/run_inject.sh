#!/usr/bin/env bash
# N07 S1 mid-stage 3920 inject. Usage: bash run_inject.sh <THRESHOLD> [START_STAGE]
set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
hash -r
TAU="${1:?threshold integer required}"
START_STAGE="${2:-1}"
TCAS_ROOT="/home/xdu/☆☆☆☆☆☆☆☆☆☆☆☆☆☆☆朱奥科研/hermes/tcas"
RTL_DIR="$TCAS_ROOT/experiments/fault_injection_1024/common/rtl"
S1_DIR="$TCAS_ROOT/experiments/fault_injection_1024/projects/S1"
OUT="$(cd "$(dirname "$0")" && pwd)"
TB="$OUT/sc01_s1_midstage_tb.sv"
DUT="$OUT/top_s1_midstage_thresholded.sv"
PROGRESS="$OUT/progress.txt"
COMBINED="$OUT/combined_summary.txt"
if [ "$START_STAGE" -eq 1 ]; then
  : > "$PROGRESS"
  : > "$COMBINED"
fi
echo "$(date -Iseconds) START N07 S1 midstage tau=$TAU stages=${START_STAGE}-8 paths=0-6 two-frames 3920" | tee -a "$PROGRESS"

heartbeat() {
  local log="$1" st="$2"
  local n last
  n=$(grep -c '^TRIAL' "$log" 2>/dev/null || true)
  n=${n:-0}
  last=$(grep '^TRIAL' "$log" 2>/dev/null | tail -1 | tr -d '\r' || true)
  printf '%s stage=%s trials=%s/490 last=%s\n' "$(date '+%H:%M:%S')" "$st" "$n" "${last:-none}"
}

for st in 1 2 3 4 5 6 7 8; do
  if [ "$st" -lt "$START_STAGE" ]; then
    continue
  fi
  LOG="$OUT/run_st${st}.log"
  SIM="/tmp/n07_s1_mid_tau${TAU}_st${st}.vvp"
  echo "===== $(date -Iseconds) COMPILE S1 midstage tau=$TAU stage=$st =====" | tee -a "$PROGRESS"
  iverilog -g2012 -Wall -o "$SIM" \
    -P sc01_s1_midstage_tb.THRESHOLD="$TAU" \
    -P sc01_s1_midstage_tb.STAGE_MIN="$st" \
    -P sc01_s1_midstage_tb.STAGE_MAX="$st" \
    -P sc01_s1_midstage_tb.PATH_MIN=0 \
    -P sc01_s1_midstage_tb.PATH_MAX=6 \
    -I "$RTL_DIR" \
    "$RTL_DIR/twiddle_rom_1024.sv" \
    "$RTL_DIR/fft_common.sv" \
    "$RTL_DIR/datapath_v5.sv" \
    "$RTL_DIR/protection_rtl.sv" \
    "$RTL_DIR/protection_primitives_v5.sv" \
    "$RTL_DIR/protected_stages_v5.sv" \
    "$S1_DIR/top_s1_gao_subfft_ecc.sv" \
    "$DUT" \
    "$TB" > "$OUT/compile_st${st}.log" 2>&1

  echo "===== $(date -Iseconds) RUN vvp S1 midstage stage=$st =====" | tee -a "$PROGRESS"
  : > "$LOG"
  (
    cd "$TCAS_ROOT"
    stdbuf -oL -eL /usr/bin/vvp "$SIM"
  ) > "$LOG" 2>&1 &
  sim=$!
  while kill -0 "$sim" 2>/dev/null; do
    heartbeat "$LOG" "$st" | tee -a "$PROGRESS"
    sleep 15
  done
  wait "$sim" || {
    echo "$(date -Iseconds) FAIL vvp S1 midstage stage=$st exit=$?" | tee -a "$PROGRESS"
    exit 1
  }
  sum=$(grep '^SUMMARY' "$LOG" | tr -d '\r' || true)
  echo "$(date -Iseconds) DONE S1 midstage stage=$st $sum" | tee -a "$PROGRESS"
  echo "stage=$st $sum" >> "$COMBINED"
done
echo "$(date -Iseconds) ALL_DONE S1 midstage tau=$TAU 3920 trials" | tee -a "$PROGRESS"
grep -h '^SUMMARY ' "$OUT"/run_st*.log | tee -a "$COMBINED"
