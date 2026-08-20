#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/xdu/☆☆☆☆☆☆☆☆☆☆☆☆☆☆☆朱奥科研/hermes/tcas"
BASE="$ROOT/experiments/fault_injection_1024"

for arch in s3 p1; do
  for k in 2 5 8; do
    if [[ "$k" == 2 ]]; then trials=500; else trials=200; fi
    dir="$BASE/results/n08_multi_k${k}_${arch}_v1_001"
    log="$dir/run_k${k}.log"
    site="$dir/sites_k${k}.csv"
    summary="$dir/combined_summary.txt"
    problems="$dir/problem_sites.csv"
    total=$(grep -c '^TRIAL ' "$log")
    bad_injected=$(grep '^TRIAL ' "$log" | grep -vc "injected=${k} " || true)
    timeouts=$(grep -c 'category=TIMEOUT' "$log" || true)
    summary_line=$(grep '^SUMMARY ' "$log" | tail -1)
    {
      echo "arch=$arch k=$k expected_trials=$trials actual_trials=$total bad_injected=$bad_injected timeouts=$timeouts"
      echo "$summary_line"
      echo "site_sha256=$(sha256sum "$site" | awk '{print $1}')"
      echo "log_sha256=$(sha256sum "$log" | awk '{print $1}')"
    } > "$summary"
    {
      echo 'trial,k,category,site_row'
      awk -F, '
        NR==FNR { if (FNR > 1) sites[$1]=$0; next }
        /^TRIAL / && /category=MISCORRECTION/ {
          t=""; if (match($0,/trial=[0-9]+/)) t=substr($0,RSTART+6,RLENGTH-6)
          if (t != "") { row=sites[t]; sub(/^[^,]*,/,"",row); print t "," k ",MISCORRECTION," row }
        }
      ' k="$k" "$site" "$log"
    } > "$problems"
    sha256sum "$site" "$log" "$summary" "$problems" "$dir/compile.log" > "$dir/sha256sums.txt"
    echo "$arch k=$k trials=$total bad_injected=$bad_injected timeouts=$timeouts"
    echo "$summary_line"
  done
done
