# N07-P1-GAO2023-V1

状态：`PASS / COMPLETE`  
日期：2026-08-14  
作者本轮：与 S3 相同，先 3σ 再注入。标定 `p1_gao2023_threshold_v1_001`：ceil(3σ)=**3**（M=6，σ_max=0.769）。K_P1 现网 THRESHOLD=8 仅作对照。

## 冻结输入

- TB：本目录 `sc01_p1_rtl_tb.sv`（FRAME_BEATS=512，SYMBOL 可切）
- DUT：`../../common/rtl/p1_thresholded_stages.sv` 的 `top_p1_pfft_ecc_thresholded`
- 清洁对照：`projects/P1/top_p1_pfft_ecc.sv`
- 仿真器：iverilog/vvp 11.0，不开 Vivado

## 命令

首次：

```bash
bash experiments/fault_injection_1024/results/n07_p1_gao2023_v1_001/run_inject.sh 3
```

2026-08-13 20:13 后后台被中断（仅 symbol 0 完成）。2026-08-14 从 symbol 1 续跑，不覆盖 symbol 0 日志：

```bash
bash experiments/fault_injection_1024/results/n07_p1_gao2023_v1_001/run_inject_resume.sh 3 1
```

τ=3，Stage 1–7 + 10，symbol 0–5，每 symbol 560，合计 3360。TMR 8–9 不跑。

## PASS / FAIL

1. 六个 symbol 均有 `SUMMARY threshold=3 total=560`
2. TRIAL 合计 3360
3. 四分类原样记录；允许虚警（τ=3 < M=6）
4. 中途失败保留 log，不改 RTL 静默重试

## 不做

改论文；开 Vivado；TMR 8–9；把 3360 写成 700 分母。
