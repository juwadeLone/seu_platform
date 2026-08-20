# N-07 Linux 确认：τ=1 全 6 symbol（家里未做完的覆盖核实）

> 日期：2026-08-13  
> 记录号：`N07-S3-TAU1-ALLSYM-V1`  
> 状态：`PASS / COVERAGE_CLOSED`  
> 对应：`实验室任务_N07阈值确认_20260813.md`  
> 不改论文。本数字不能直接改写 700 分母的 94.4%。

## 1. 家里缺的是哪一步

旧 RTL τ=1 只跑了 **stage 1–8 × symbol 0 = 560**，得到 silent_bounded=14、silent_unbounded=2。  
Python τ=1 是 **8×6×2×35 = 3360**，silent_bounded=96。  
τ=0 全 symbol 早已 3360/3360 = 100%（`sc01_rtl_run_full_tau0.log`）。

本轮补跑：`sc01_rtl_compile.sh 1 1 8 S S`，S=0 用既有 `sc01_rtl_run_tau1.log`；S=1..5 新日志 `sc01_rtl_run_tau1_sym{1..5}.log`。

## 2. 带回清单

```
1. 实际阈值（本枪）τ = 1（精确模型对照 τ = 0）
2. RTL 全 symbol τ=1, stage 1..8, symbol 0..5:
   total=3360 corrected=3264 detected_only=0
   silent_bounded=53 silent_unbounded=43 miscorrection=0
3. τ=0 全 symbol: corrected=3360 / 3360 = 100%（既有 full_tau0，未重跑）
4. 96 个 silent 全部是 bit 0；每 symbol 恰好 16 = 8 stage × 2 component
5. bug 类型: C（阈值吸收 |syndrome|=1）为主；A（旧枪只测 symbol 0）解释 14 vs 96；
   不是 B（译码器对校验符号误判）。detected_only=0。
6. 本枪 Level-1（8 级×6 符号，不是论文 700 分母）:
   严格 bit-exact = 3264/3360 = 97.14%
   Gao 式 (corrected+silent_bounded) = 3317/3360 = 98.72%
7. 新选题噪声本底本轮未另跑；τ 扫描 0/1/2/4/8 仍见 sc01_rtl_results.json（仅 symbol 0）
```

## 3. 分 symbol 结果（每格 560 试）

| symbol | corrected | silent_bounded | silent_unbounded | 含义 |
|---|---:|---:|---:|---|
| 0（旧枪） | 544 | 14 | 2 | 家里看到的 14+2 |
| 1 | 544 | 7 | 9 | real 多 unbounded，imag 多 bounded |
| 2 | 544 | 0 | 16 | 功能符号，bit0 全部顶层失配 |
| 3 | 544 | 0 | 16 | 同上 |
| 4 | 544 | 16 | 0 | 校验符号，bit0 全部顶层仍匹配 |
| 5 | 544 | 16 | 0 | 同上 |
| **合计** | **3264** | **53** | **43** | 53+43=**96** |

Python τ=1：corrected=3264，silent_bounded=96，无 unbounded 类。  
严格恢复率两边都是 **97.14%**。差别只在 Python 把 96 个 bit0 全算 bounded，RTL 按 FFT 顶层是否 bit-exact 拆成 53+43。

## 4. 那 14 个是什么

不是译码器漏纠。特征：

- 全部 `detected=0`（|syndrome|=1 ≤ τ=1，被阈值吸收）
- 全部 **bit 0**
- symbol 0 上：stage 1,3–8 的 real/imag 共 14 个顶层仍匹配 → 记 silent_bounded  
- 另 2 个是 stage 2 bit0 → 残差经后续 `>>>1` 传播，顶层失配 → silent_unbounded

扩到 6 个 symbol 后，**这 14 个不会变成 corrected**；只是同一类 bit0 吸收从 16 扩成 96。

校验符号 4/5 的 32 个 bit0 **全部 bounded**，说明不是“译码器对校验符号有 bug”。功能符号 2/3 的 32 个 bit0 **全部 unbounded**，是阈值吸收后残差走功能通路。

## 5. 与论文 94.4%（661/700）的关系

**对不上，不要用本枪改 94.4%。**

| 口径 | 分母 | 本枪 |
|---|---|---|
| 本 RTL τ=1 全 symbol | 3360（stage 1–8，6 symbol） | 严格 97.14% / Gao 98.72% |
| 本 RTL τ=0 全 symbol | 3360 | 100% |
| 论文 Level-1 | 700（10 stage × 70 bit，含 TMR 9–10） | 未在本枪测量 |

94.4%=661/700 来自旧 TLFI 把 53 失败里的 14 个 detected-uncorrectable 改记为可恢复。  
当前 RTL **detected_only=0**，那套 39+14 分类在本 testbench 里复现不出来。

同日另有隔离包 `n07_tau2_s3_v1_001`（τ=2 / Gao 2023 3σ，3360 试），也不是 700 分母。

## 6. 文件与 SHA-256

| 文件 | 内容 | SHA-256 |
|---|---|---|
| `sc01_rtl_run_tau1.log` | τ=1 symbol 0（旧） | `3d28e528f0accc24641a2e2700ffecb0b61ca1ed457804c11ccd03e4b7366ef7` |
| `sc01_rtl_run_tau1_sym1.log` | τ=1 symbol 1 | `58783c87512d9c8d60193a22c750471680bac5ff1aa4558ed3860b8fa32b3484` |
| `sc01_rtl_run_tau1_sym2.log` | τ=1 symbol 2 | `a81bf12a2e74f3baaa9d2b2c2622a4444fd10565b838f2e4828f1f71958b4615` |
| `sc01_rtl_run_tau1_sym3.log` | τ=1 symbol 3 | `c45c1b5b748687d4ed4ee63355aeee146909ec6511a75c6603de889fef293f62` |
| `sc01_rtl_run_tau1_sym4.log` | τ=1 symbol 4 | `27e06aea9dcb7dd554b0209e1e29d45a62d315b2756e57f75f68f6de10a90c39` |
| `sc01_rtl_run_tau1_sym5.log` | τ=1 symbol 5 | `249f7efe7120a2b061d20f317462765ea922aaa0570252905b804e10a07b911f` |
| `sc01_rtl_run_full_tau0.log` | τ=0 全 symbol（旧） | 未重算；SUMMARY `corrected=3360` |

命令：`bash sc01_rtl_compile.sh 1 1 8 <sym> <sym>`，iverilog/vvp 11.0，未开 Vivado。
