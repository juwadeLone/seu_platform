#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/xdu/☆☆☆☆☆☆☆☆☆☆☆☆☆☆☆朱奥科研/hermes/tcas"
BASE="$ROOT/experiments/fault_injection_1024/results"
total_trials=0
total_injects=0

for arch in s3 p1; do
  for k in 2 5 8; do
    if [[ "$k" == 2 ]]; then trials=500; else trials=200; fi
    first="$BASE/n08_multi_k${k}_${arch}_v2_001"
    repeat="$BASE/n08_multi_k${k}_${arch}_v2_002"
    first_log="$first/run_k${k}.log"
    repeat_log="$repeat/run_k${k}.log"
    first_site="$first/sites_k${k}_v1.csv"
    repeat_site="$repeat/sites_k${k}_v1.csv"

    actual_trials=$(grep -c '^TRIAL ' "$repeat_log")
    actual_injects=$(grep -c '^INJECT ' "$repeat_log")
    expected_injects=$((trials * k))
    bad_injected=$(grep '^TRIAL ' "$repeat_log" | grep -vc "injected=${k} " || true)
    timeouts=$(grep -c 'category=TIMEOUT' "$repeat_log" || true)
    miscorr=$(grep -c 'category=MISCORRECTION' "$repeat_log" || true)
    evidence=$(grep -c '^MISCORR_EVIDENCE ' "$repeat_log" || true)
    first_summary=$(grep '^SUMMARY ' "$first_log" | tail -1)
    repeat_summary=$(grep '^SUMMARY ' "$repeat_log" | tail -1)
    first_site_hash=$(sha256sum "$first_site" | awk '{print $1}')
    repeat_site_hash=$(sha256sum "$repeat_site" | awk '{print $1}')

    [[ "$actual_trials" == "$trials" ]]
    [[ "$actual_injects" == "$expected_injects" ]]
    [[ "$bad_injected" == 0 ]]
    [[ "$timeouts" == 0 ]]
    [[ "$miscorr" == 0 ]]
    [[ "$evidence" == 0 ]]
    [[ "$first_site_hash" == "$repeat_site_hash" ]]
    [[ "$first_summary" == "$repeat_summary" ]]

    first_trials=$(mktemp)
    repeat_trials=$(mktemp)
    first_injects=$(mktemp)
    repeat_injects=$(mktemp)
    first_evidence=$(mktemp)
    repeat_evidence=$(mktemp)
    trap 'rm -f "$first_trials" "$repeat_trials" "$first_injects" "$repeat_injects" "$first_evidence" "$repeat_evidence"' EXIT
    grep '^TRIAL ' "$first_log" > "$first_trials"
    grep '^TRIAL ' "$repeat_log" > "$repeat_trials"
    grep '^INJECT ' "$first_log" > "$first_injects"
    grep '^INJECT ' "$repeat_log" > "$repeat_injects"
    grep '^MISCORR_EVIDENCE ' "$first_log" > "$first_evidence" || true
    grep '^MISCORR_EVIDENCE ' "$repeat_log" > "$repeat_evidence" || true
    cmp -s "$first_trials" "$repeat_trials"
    cmp -s "$first_injects" "$repeat_injects"
    cmp -s "$first_evidence" "$repeat_evidence"

    {
      echo "arch=$arch k=$k expected_trials=$trials actual_trials=$actual_trials expected_injects=$expected_injects actual_injects=$actual_injects"
      echo "bad_injected=$bad_injected timeouts=$timeouts miscorr=$miscorr miscorr_evidence=$evidence"
      echo "site_sha256=$repeat_site_hash"
      echo "first_repeat_site_identical=yes"
      echo "first_repeat_summary_identical=yes"
      echo "first_repeat_trial_lines_identical=yes"
      echo "first_repeat_inject_lines_identical=yes"
      echo "$repeat_summary"
    } > "$repeat/combined_summary.txt"

    {
      echo "# N08 V2 repeat audit: ${arch^^} k=$k"
      echo
      echo "- trials: $actual_trials/$trials"
      echo "- injection events: $actual_injects/$expected_injects"
      echo "- bad injected count / timeout / miscorr / evidence: $bad_injected / $timeouts / $miscorr / $evidence"
      echo "- V2_001/V2_002 site SHA identical: yes ($repeat_site_hash)"
      echo "- V2_001/V2_002 summary identical: yes"
      echo "- V2_001/V2_002 per-trial lines identical: yes"
      echo "- V2_001/V2_002 per-injection lines identical: yes"
      echo "- summary: \`$repeat_summary\`"
    } > "$repeat/AUDIT.md"

    sha256sum "$repeat_site" "$repeat_log" "$repeat/combined_summary.txt" \
      "$repeat/AUDIT.md" "$repeat/compile.log" "$repeat/progress.txt" > "$repeat/sha256sums.txt"

    rm -f "$first_trials" "$repeat_trials" "$first_injects" "$repeat_injects" "$first_evidence" "$repeat_evidence"
    trap - EXIT
    total_trials=$((total_trials + actual_trials))
    total_injects=$((total_injects + actual_injects))
    echo "PASS arch=$arch k=$k trials=$actual_trials injects=$actual_injects summary_identical=yes trial_lines_identical=yes inject_lines_identical=yes"
    echo "$repeat_summary"
  done
done

[[ "$total_trials" == 1800 ]]
[[ "$total_injects" == 7200 ]]
echo "PASS all_groups=6 total_trials=$total_trials total_injects=$total_injects"
