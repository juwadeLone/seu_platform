# N07-S1-GAO2023-V1

状态：`PASS / COMPLETE`  
日期：2026-08-13  
作者本轮：高镇路径 ECC，与 S3 相同先 3σ 再注入。标定 `s1_gao2023_threshold_v1_001`：ceil(3σ)=**5**（M=11，σ_max=1.461）。K_S1 现网经验门限 16 仅作对照。

## 冻结输入

- TB：本目录 `sc01_s1_rtl_tb.sv`
- DUT：本目录 `top_s1_gao_subfft_ecc_thresholded.sv`
- 清洁对照：`projects/S1/top_s1_gao_subfft_ecc.sv`
- 仿真器：iverilog/vvp

## 命令

```bash
bash experiments/fault_injection_1024/results/n07_s1_gao2023_v1_001/run_inject.sh 5
```

τ=5，7 条 received 路径 × 2 × 35 = 490。TMR 9–10 不注入。每枪两帧。

## PASS / FAIL

1. `SUMMARY threshold=5 total=490`
2. 四分类原样记录
3. 中途失败保留 log

## 不做

改论文；开 Vivado；TMR 9–10；把 490 写成 700 分母。
