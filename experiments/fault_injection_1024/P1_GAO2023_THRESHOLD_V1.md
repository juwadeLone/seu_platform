# P1-GAO2023-TH-V1-001 — K_P1 无故障综合征 3σ 标定后注入

状态：`PASS / CALIBRATE_AND_INJECT_COMPLETE`  
记录：D161  
日期：2026-08-13

## 范围

与 S3（D159+D160）同一方案：先 Gao 2023 无故障检查量 3σ 得全局整数 τ，再用该 τ 在 thresholded P1 iverilog DUT 上注入。本轮作者已授权两步都做。不改 `manuscript/`、不改 K_P1 源 RTL、不启动 Vivado/XSim。

## 冻结输入（标定）

| 项 | 路径 |
|---|---|
| DUT | `/home/xdu/JuWade_research/fft1024_ft_exp/vivado/K_P1_pfft/hdl/rtl/top_p1_kernel.sv` 中 `top_p1_pfft_ecc` |
| 激励 | `.../kernels/P1/vectors/qualification_input_10frames.hex` |
| 功能对照 | `.../kernels/P1/vectors/qualification_pfft_expected_8frames.hex` |
| 采样 | Stage 1–7 `syn_v` 时的 `sy0r,sy0i,sy1r,sy1i`；Stage 10 `go_syn` 时的 upper `sy0_ur,...` |

仿真器：`iverilog` + `vvp` only。

## 注入（标定 PASS 且 Th>0 后立即开）

- DUT：`common/rtl/p1_thresholded_stages.sv` 的 `top_p1_pfft_ecc_thresholded`
- 一个全局 τ=`ceil(3σ)`；每枪两帧；ECC Stage 1–7 + Stage 10；6 个 `[6,4,3]` 符号；TMR 8–9 不跑
- 合计 3360 枪（与 S3 同计数）
- 输出：`results/n07_p1_gao2023_v1_001/`（不覆盖 `sc01_p1_rtl_v1_001`）

## PASS / FAIL（标定）

1. 编译退出 0；2048 输出 beat；bit-exact mismatch=0，否则停止不给 τ。
2. 有效综合征样本 Stage 1–7 均 >0。
3. 报告 Th=`ceil(3σ_max)`。若 Th=0：停止询问。
4. 不把 τ 写回 K_P1 源文件。

## 不做

改论文；开 Vivado；跑 TMR 8–9；把 3360 写成论文 700 分母。
