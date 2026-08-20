# N07-S1-MIDSTAGE-3920-V1 — S1 中间级路径注入

状态：`PASS / COMPLETE`  
记录：D163  
日期：2026-08-14

## 为什么开这一枪

既有 `N07-S1-GAO2023-V1` 的 490 枪只在 **Stage-8 译码器入口** 对 7 条 received 路径翻 1 bit。Python `run_s1.py` 虽按 `path_effect_stages=1..8` 记账，实际翻转的仍是算完八级之后的码字，并不是把残差推进中间 SDF。

作者本轮确认：要回答「Gao 单点检查在故障发生在中间级时到底能救多少」，必须

```
8 级 × 7 路径 × 2 分量 × 35 bit = 3920
```

TMR Stage 9–10 不注入。不改论文、不开 Vivado、不覆盖 `n07_s1_gao2023_v1_001/`。

预期：结果可能低于 96.33%，甚至低于 P1 的 96.19%。本枪就是补口径和给结论排雷，不预先改主张。

## 冻结输入

| 项 | 路径 |
|---|---|
| 清洁对照 | `projects/S1/top_s1_gao_subfft_ecc.sv` |
| 故障 DUT | `results/n07_s1_midstage_3920_v1_001/top_s1_midstage_thresholded.sv` |
| TB | 同目录 `sc01_s1_midstage_tb.sv` |
| 激励 | `common/vectors/qualification_input_10frames.hex`（TB 读 512 beat） |
| τ | 5（沿用 `S1-GAO2023-TH-V1-001` 的 ceil(3σ)，不重标定） |
| 仿真器 | iverilog/vvp 11.0 |

## 注入模型

- 在路径 `y∈0..6` 的 Stage `k∈1..8` **寄存输出进入下一级（k=8 则进入译码器）之前**，于该级第一次 `out_valid` 翻 1 bit，只翻一拍。
- 残差按 **K_S1 现网**：`s = H·received`（不减 golden from_clean）。`from_clean` 在中间级注入时 c/r 同源会把综合征打成 0，回答不了本题。
- 校正器仍是 τ=5 的 `gao_corrector_743_thresholded`。
- 分类与既有 S1/S3 TB 相同。flag 在「该路径输出相对清洁实例首次分叉且 `pv[0]`」那一拍采样；若始终不分叉则 flag=0。

## 命令

```bash
bash experiments/fault_injection_1024/results/n07_s1_midstage_3920_v1_001/run_inject.sh 5
```

逐级 490 枪，八个 `run_st{1-8}.log`。

## PASS / FAIL

1. 八个 `SUMMARY threshold=5 total=490`
2. TRIAL 合计 3920
3. 四分类原样记录；允许低于 96.33%
4. 中途失败保留 log，不改 RTL 静默重试
5. 不覆盖 490 包；3920 ≠ 论文 700

## 不做

改论文；开 Vivado；注入 TMR 9–10；把本数字写成 700 分母；改 K_S1 源 RTL。
