#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/xdu/☆☆☆☆☆☆☆☆☆☆☆☆☆☆☆朱奥科研/hermes/tcas"
BASE="$ROOT/experiments/fault_injection_1024/results"

build_one() {
  local arch="$1" source_dir="$2" out_dir="$3"
  local site="$out_dir/sites_k1_from_n07.csv"
  local expected="$out_dir/expected_from_n07.csv"
  mkdir -p "$out_dir"
  printf '%s\n' 'trial,sites(stage:symbol:component:bit;...)' > "$site"
  printf '%s\n' 'trial,stage,symbol,component,bit,category' > "$expected"
  awk -v site="$site" -v expected="$expected" '
    BEGIN { total=0 }
    function value(prefix,   i,a) {
      for (i=1;i<=NF;i++) if (index($i,prefix)==1) {split($i,a,"="); return a[2]}
      return ""
    }
    /^TRIAL / {
      cat=value("category=")
      if ((cat=="corrected" || cat=="silent_bounded_residual" || cat=="silent_unbounded") && count[cat]<12) {
        stage=value("stage="); symbol=value("symbol="); component=value("component="); bit=value("bit=")
        comp=(component=="imag")?1:0
        print total "," stage ":" symbol ":" comp ":" bit >> site
        print total "," stage "," symbol "," comp "," bit "," cat >> expected
        count[cat]++; total++
      }
    }
    END {
      if (total!=36 || count["corrected"]!=12 || count["silent_bounded_residual"]!=12 || count["silent_unbounded"]!=12) exit 2
    }
  ' "$source_dir"/run_sym0.log "$source_dir"/run_sym1.log "$source_dir"/run_sym2.log \
    "$source_dir"/run_sym3.log "$source_dir"/run_sym4.log "$source_dir"/run_sym5.log
  echo "$arch regression_sites=36 corrected=12 bounded=12 unbounded=12"
  sha256sum "$site" "$expected" > "$out_dir/input_sha256sums.txt"
}

build_one s3 "$BASE/n07_tau2_s3_v1_001" "$BASE/n08_regress_s3_v2_001"
build_one p1 "$BASE/n07_p1_gao2023_v1_001" "$BASE/n08_regress_p1_v2_001"
