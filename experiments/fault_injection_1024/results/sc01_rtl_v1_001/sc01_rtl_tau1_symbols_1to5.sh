#!/usr/bin/env bash
# N-07: tau=1, stages 1..8, symbols 1..5 (symbol 0 already in sc01_rtl_run_tau1.log)
set -euo pipefail
OUT="$(cd "$(dirname "$0")" && pwd)"
cd "$OUT"
for s in 1 2 3 4 5; do
  echo "===== $(date -Iseconds) start symbol=$s ====="
  bash "$OUT/sc01_rtl_compile.sh" 1 1 8 "$s" "$s" \
    > "$OUT/sc01_rtl_run_tau1_sym${s}.log" 2>&1
  echo "===== $(date -Iseconds) done symbol=$s : $(grep 'SUMMARY recovery_rate' "$OUT/sc01_rtl_run_tau1_sym${s}.log" | tail -1) ====="
done
echo ALL_DONE
