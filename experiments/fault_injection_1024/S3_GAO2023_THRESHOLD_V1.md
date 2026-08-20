# S3-GAO2023-TH-V1-001 — K_S3 无故障综合征 3σ 标定

状态：`AUTHORIZED / CALIBRATION_ONLY / INJECTION_NOT_STARTED`  
记录：D159  
日期：2026-08-13

## 范围

Gao 2023（TCAS-I channelizer）阈值标定的 S3 对应物。只测无注入 raw syndrome 的 σ，给出整数门限候选。本步**不开** 5040 注入、不改 `manuscript/`、不改 K_S3 源 RTL、不启动 Vivado/XSim。

## Gao 2023 → 本步映射

| Gao 2023 | 本步 |
|---|---|
| Matlab 浮点 vs FPGA 定点，得输出量化噪声 σ | 无注入下 K_S3 译码器所见 raw `[6,4,3]` 综合征（检查量本身） |
| 式 (17) 把噪声方差传到 Δ1/Δ2 | 不另传：综合征已是检查量 |
| \(T_{h1}=3\sigma(\Delta_1)\)，取整数 | \(T_h=\mathrm{ceil}(3\sigma_{\max})\)，硬件比较为 \(\lvert sy\rvert>T_h\) |
| 无故障虚警 | 同一 10 帧标定集上的超阈比例（不是 \(10^{11}\) 板上虚警） |
| 再做配置位 SEU + SNR | **本步不做**；5040 位级注入另授权 |

对照：2026-08-10 `uncomp_v1_001` 的 S3 τ=4 是 \(M=\max\lvert\rho\rvert=3\) 再取 2 的幂，**不是** 3σ。本步按 3σ 重算，并与 M、τ=4 并列报告。

## 冻结输入

| 项 | 路径 |
|---|---|
| DUT | `/home/xdu/JuWade_research/fft1024_ft_exp/vivado/K_S3_subfft/hdl/rtl/top_s3_kernel.sv` 中 `top_s3_subfft_ecc` |
| 同目录 RTL | `twiddle_rom_1024.sv`, `fft_common.sv`, `datapath_v5.sv`, `protection_rtl.sv`, `protection_primitives_v5.sv`, `ecc_stage4_v5.sv` |
| 激励 | `.../kernels/S3/vectors/qualification_input_10frames.hex`（2560 beat） |
| 功能对照 | `.../kernels/S3/vectors/qualification_subfft_expected_8frames.hex`（2048 beat） |
| 采样 | Stage 1–8，`syn_v==1` 时的寄存综合征 `sy0r,sy0i,sy1r,sy1i` |

仿真器：`iverilog` + `vvp` only。

## 输出（隔离，不覆盖冻结包）

`experiments/fault_injection_1024/results/s3_gao2023_threshold_v1_001/`

- `syndrome_faultfree.csv`
- `threshold_3sigma.json`
- `threshold_3sigma.md`
- `compile.log` / `sim.log`
- `input_hashes.json`

## PASS / FAIL

1. 编译退出 0；仿真收到 2048 个输出 beat，无 TIMEOUT。
2. 与 expected hex 逐 beat 比较：mismatch 数写入结果。若 mismatch>0，**停止**，不给出 3σ 门限主张。
3. 有效综合征样本 Stage 1–8 均 >0。
4. 报告：每级/每分量 mean、σ（样本标准差, ddof=1）、M=\(\max\lvert sy\rvert\)、\(3\sigma\)、建议整数 \(T_h=\mathrm{ceil}(3\sigma_{\max})\)、标定集虚警（任一分量 \(\lvert sy\rvert>T_h\)）。
5. 若 \(T_h=0\)：记为与“定点必须有阈值”冲突，不采用，停止询问。
6. 不把 3σ 自动写回 K_S3 的 `THRESHOLD(4)`；5040 枪等作者确认 \(T_h\)。

## 停止条件

- 需要改 K_S3 源文件或论文。
- 需要 Vivado / XSim / 上板。
- bit-exact 失败。
- 证据与既有 M=3 / τ=4 数字若用于改冻结包。

## 命令

```bash
bash experiments/fault_injection_1024/results/s3_gao2023_threshold_v1_001/run_calibrate.sh
python3 experiments/fault_injection_1024/results/s3_gao2023_threshold_v1_001/analyze_3sigma.py
```
