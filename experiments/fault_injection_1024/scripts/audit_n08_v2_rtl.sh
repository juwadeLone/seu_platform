#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/xdu/☆☆☆☆☆☆☆☆☆☆☆☆☆☆☆朱奥科研/hermes/tcas"
BASE="$ROOT/experiments/fault_injection_1024/results"

for arch in s3 p1; do
  for k in 2 5 8; do
    if [[ "$k" == 2 ]]; then trials=500; else trials=200; fi
    v1="$BASE/n08_multi_k${k}_${arch}_v1_001"
    v2="$BASE/n08_multi_k${k}_${arch}_v2_001"
    log="$v2/run_k${k}.log"
    site_v1="$v1/sites_k${k}.csv"
    site_v2="$v2/sites_k${k}_v1.csv"
    total=$(grep -c '^TRIAL ' "$log")
    bad_injected=$(grep '^TRIAL ' "$log" | grep -vc "injected=${k} " || true)
    timeouts=$(grep -c 'category=TIMEOUT' "$log" || true)
    miscorr=$(grep -c 'category=MISCORRECTION' "$log" || true)
    evidence=$(grep -c '^MISCORR_EVIDENCE ' "$log" || true)
    summary_line=$(grep '^SUMMARY ' "$log" | tail -1)
    site_hash_v1=$(sha256sum "$site_v1" | awk '{print $1}')
    site_hash_v2=$(sha256sum "$site_v2" | awk '{print $1}')
    [[ "$site_hash_v1" == "$site_hash_v2" ]]
    [[ "$total" == "$trials" && "$bad_injected" == 0 && "$timeouts" == 0 && "$miscorr" == "$evidence" ]]

    v1_ids=$(mktemp)
    v2_ids=$(mktemp)
    awk '/^TRIAL /&&/category=MISCORRECTION/{for(i=1;i<=NF;i++)if($i~/^trial=/){sub(/^trial=/,"",$i);print $i}}' "$v1/run_k${k}.log" | sort -n > "$v1_ids"
    awk '/^TRIAL /&&/category=detected_only/{for(i=1;i<=NF;i++)if($i~/^trial=/){sub(/^trial=/,"",$i);print $i}}' "$log" | sort -n > "$v2_ids"
    if cmp -s "$v1_ids" "$v2_ids"; then reclass_exact=yes; else reclass_exact=no; fi
    [[ "$reclass_exact" == yes ]]

    {
      echo "arch=$arch k=$k expected_trials=$trials actual_trials=$total bad_injected=$bad_injected timeouts=$timeouts"
      echo "site_v1_sha256=$site_hash_v1"
      echo "site_v2_sha256=$site_hash_v2"
      echo "v1_miscorr_to_v2_detected_only_exact=$reclass_exact"
      echo "miscorr_evidence_count=$evidence"
      echo "$summary_line"
    } > "$v2/combined_summary.txt"
    {
      echo "# N08 V2 audit: ${arch^^} k=$k"
      echo
      echo "- trials: $total/$trials"
      echo "- bad injected count: $bad_injected"
      echo "- timeout: $timeouts"
      echo "- V1/V2 site SHA identical: yes ($site_hash_v2)"
      echo "- V1 miscorr trial IDs exactly equal V2 detected_only IDs: $reclass_exact"
      echo "- V2 miscorr/evidence: $miscorr/$evidence"
      echo "- summary: \`$summary_line\`"
    } > "$v2/AUDIT.md"
    sha256sum "$site_v2" "$log" "$v2/combined_summary.txt" "$v2/AUDIT.md" "$v2/compile.log" > "$v2/sha256sums.txt"
    rm -f "$v1_ids" "$v2_ids"
    echo "$arch k=$k trials=$total injected_bad=$bad_injected timeout=$timeouts miscorr=$miscorr evidence=$evidence reclass_exact=$reclass_exact"
    echo "$summary_line"
  done
done

for arch in s3 p1; do
  d="$BASE/n08_regress_${arch}_v2_001"
  bad=$(awk -F, 'NR==FNR{if(NR>1)expected[$1]=$6;next}/^TRIAL /{t="";c="";for(i=1;i<=NF;i++){if(match($i,/trial=[0-9]+/))t=substr($i,RSTART+6,RLENGTH-6);if(match($i,/category=[A-Za-z_]+/))c=substr($i,RSTART+9,RLENGTH-9)}if(t!=""&&expected[t]!=c)bad++;seen++}END{if(seen!=36)bad+=1000;print bad+0}' "$d/expected_from_n07.csv" "$d/run_k1_legacy_n07_hold.log")
  [[ "$bad" == 0 ]]
  one_cycle=$(grep '^SUMMARY ' "$d/run_k1.log" | tail -1)
  legacy=$(grep '^SUMMARY ' "$d/run_k1_legacy_n07_hold.log" | tail -1)
  {
    echo "# N08 V2 k=1 regression: ${arch^^}"
    echo
    echo "- N07-compatible shared/held mode point mismatches: $bad/36"
    echo "- one-cycle stage-local result: \`$one_cycle\`"
    echo "- N07-compatible shared/held result: \`$legacy\`"
    echo "- interpretation: N07 silent-unbounded points require the legacy shared injection hook held high through the input frame."
  } > "$d/AUDIT.md"
  sha256sum "$d/sites_k1_from_n07.csv" "$d/expected_from_n07.csv" "$d/run_k1.log" "$d/run_k1_legacy_n07_hold.log" "$d/AUDIT.md" > "$d/sha256sums.txt"
  echo "$arch regression point_mismatch=$bad"
done
