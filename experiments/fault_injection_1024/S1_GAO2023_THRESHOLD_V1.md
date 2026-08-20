# S1-GAO2023-TH-V1-001 — K_S1 Gao `[7,4,3]` 无故障综合征 3σ 标定后注入

状态：`AUTHORIZED / CALIBRATE_THEN_INJECT`  
记录：D162  
日期：2026-08-13

## 范围

高镇路径 ECC（S1）按与 S3 相同的 Gao 2023 方案：先对无故障检查量做 3σ，再注入。S1 的检查量是 Stage-8 边界的 `[7,4,3]` 路径综合征 `syn0,syn1,syn2`（不是逐级 `[6,4,3]`）。本轮作者已授权两步都做。不改 `manuscript/`、不改 K_S1 源 RTL、不启动 Vivado。

## 冻结输入（标定）

| 项 | 路径 |
|---|---|
| DUT | `/home/xdu/JuWade_research/fft1024_ft_exp/vivado/K_S1_subfft/hdl/rtl/top_s1_kernel.sv` 中 `top_s1_gao_subfft_ecc` |
| 激励 | `.../kernels/S1/vectors/qualification_input_10frames.hex` |
| 功能对照 | `.../kernels/S1/vectors/qualification_subfft_expected_8frames.hex` |
| 采样 | `pv_d3==1` 时的 `syn0r,syn0i,syn1r,syn1i,syn2r,syn2i` |

对照：K_S1 现网经验门限为 16（不是 3σ）。本步按 3σ 重算。

## 注入（标定 PASS 且 Th>0 后立即开）

- DUT：隔离文件 `results/n07_s1_gao2023_v1_001/top_s1_gao_subfft_ecc_thresholded.sv`
- 一个全局 τ；每枪两帧；在 7 条 received 路径进入 Gao 译码器之前翻 1 bit
- TMR Stage 9–10 不注入
- 合计 7 路径 × 2 分量 × 35 bit = **490** 枪（S1 只有一处路径译码器，不是 S3 的 8 级 × 6 符号）
- 输出：`results/n07_s1_gao2023_v1_001/`

## PASS / FAIL（标定）

1. 编译退出 0；2048 beat bit-exact，否则停止。
2. 综合征样本 >0。
3. Th=`ceil(3σ_max)`。若 Th=0：停止询问。

## 不做

改论文；开 Vivado；跑 TMR 9–10；把 490 写成论文 700 分母。
