# N07-S3-TAU2-GAO2023-V1

状态：`PASS / COMPLETE`  
日期：2026-08-13  
作者本轮：τ=2（Gao 2023 ceil(3σ)），虚警先跑；一个全局 τ；每枪两帧；Stage 1–8；6 符号；TMR 不跑。

## 冻结输入

- TB：`../sc01_rtl_v1_001/sc01_rtl_tb.sv`（FRAME_BEATS=512）
- DUT：`../../common/rtl/top_s3_subfft_ecc_thresholded.sv` 及同目录依赖
- 激励：`../../common/vectors/qualification_input_10frames.hex`
- 仿真器：`/usr/bin/iverilog` + `/usr/bin/vvp`（不用 Vivado）

## 命令

```bash
bash experiments/fault_injection_1024/results/n07_tau2_s3_v1_001/run_tau2.sh
```

等价：对 symbol s=0..5 执行 `THRESHOLD=2 STAGE=1..8 SYMBOL=s..s`（每 symbol 560 枪）。

## 输出（本目录，不覆盖 sc01_rtl_v1_001）

- `progress.txt`：心跳（约每 15 s）
- `run_sym{0-5}.log`：该 symbol 全 TRIAL + SUMMARY
- `combined_summary.txt`：六段 SUMMARY 汇总
- `silent_sites.csv`：192 个 silent 位点
- `AUDIT.md`：PASS 审计
- `实验记录.md`：本次实验行为与结果说明

## PASS / FAIL

1. 六个 symbol 均出现 `SUMMARY threshold=2 total=560` — **PASS**
2. TRIAL 合计 3360 — **PASS**
3. 四分类原样记录；允许虚警（τ=2 对 M=3 本底）— **PASS**（miscorrection=0；unbounded=86）
4. 中途失败：保留已有 log，不改 TB/RTL 重试 — 未触发

合计：corrected=3168，silent_bounded=106，silent_unbounded=86。Gao (corr+bounded)=3274/3360=97.44%。

## 不做

改论文；开 Vivado；跑 Stage 9–10 TMR；跑 S1/P1；把 3360 直接写成 700 分母。
