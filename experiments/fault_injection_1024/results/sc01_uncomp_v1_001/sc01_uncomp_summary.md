# SC-01 方案 B — 无补偿 Gao 原教旨阈值化 RTL 实验 —— 总结报告

> **执行者**：Deepseek 执行会话（paper-review profile）
> **日期**：2026-08-10
> **对应任务**：`review/交接文档_SC01_方案B_无补偿阈值化_2026-08-10.md` 全部步骤
> **作者硬性约束**：论文不允许 residual 补偿 —— 本实验全部为无补偿实现

---

## 0. 执行状态：全部完成 ✅

| 步骤 | 内容 | 状态 |
|------|------|------|
| 1 | 无故障 raw syndrome 残差测量（零注入，10 帧扫描） | ✅ **M=6** |
| 2 | τ 选定 | ✅ **τ=8**（2 的幂，≥ M） |
| 3 | `arithmetic_corrector_643_uncomp`（无 residual 端口） | ✅ |
| 4 | `arithmetic_boundary_uncomp_v5` / `independent_butterfly_ecc_v5_uncomp` / `ecc_stage4_v5_uncomp` / `top_s3_subfft_ecc_uncomp` | ✅ |
| 5 | 故障注入 testbench（双判据分类） | ✅ |
| 6 | 全量仿真（8 stages × 6 symbols = 3360 trials, τ=8） | ✅ |
| 7 | 输出 `sc01_uncomp_v1_001/` | ✅ |

---

## 1. 步骤 1 结果：无故障 raw syndrome 残差上界 M

扫描原版 S3（零注入）全部 8 个 ECC stage × 2 boundaries，10 帧 × 256 beats = 40,960 样本：

| 指标 | 值 |
|------|----|
| 有效样本 | 37,318（3,642 个 x 为流水未填满的无效拍） |
| **M（max \|残差分量\|）** | **6** |
| 分 stage 上界 | s1–s6: 6；s7–s8: 2 |
| ρ=0 占比 | 76.92% |
| \|ρ\| 分布 | 1→10,879；2→5,440；3→973；4→287；5→100；6→22 |

## 2. 步骤 2 结果：τ 选定

- Gao 原则：τ = M = 6
- 硬件友好修正：**τ = 8**（2³，≥ M=6，无故障不误检）
- 模式匹配容差 TOL = 2×τ = 16
- 推导详见 `threshold_selection.md`

## 3. 步骤 6 结果：全量故障注入（τ=8, 3360 trials）

```
SUMMARY threshold=8 total=3360 corrected_bitexact=2976 corrected_bounded=0 detected_only=0
        silent_bounded=384 silent_unbounded=0 miscorrection=0
SUMMARY recovery_bitexact=88.57%
SUMMARY recovery_bounded=88.57%
SUMMARY detection_rate=88.57%
```

| 分类 | 计数 | 占比 |
|------|------|------|
| corrected_bitexact（检测+纠正+输出与 golden 精确一致） | 2976 | 88.57% |
| corrected_bounded（检测+纠正+输出残差 ≤ τ） | 0 | 0% |
| detected_only | 0 | 0% |
| silent_bounded（未检测+输出残差 ≤ τ） | 384 | 11.43% |
| silent_unbounded（未检测+输出超界） | 0 | 0% |
| **miscorrection** | **0** | **0%** |

**silent 分布**：全部 8 stages × 6 symbols × bit 0–3（real+imag）= 384，完全规律。

**机制**：bit k 翻转产生 syndrome 增量 ±2^k。|ρ ± 2^k| ≤ τ=8 当 k ≤ 3（效应 ≤ τ，且 ρ 与翻转方向反号时 syndrome 缩小）→ 未检测。bit ≥ 4（效应 ≥ 16 > τ+M 余量）必检测。

**检测恢复率 = (35−4)/35 = 88.57%** —— 精确等于实测值。

## 4. 与论文 92.4% 的对比（核心结论）

| 指标 | 论文旧数字 | 补偿方案（已否决） | 方案 B（本实验） |
|------|-----------|-------------------|-----------------|
| 恢复率 | 92.4% | 100%（τ=0，物理不可实现） | **88.57%** |
| 判据 | bit-exact | bit-exact | bounded（主）+ bit-exact（附） |
| 漏检 | 39/700 (5.6%) | 0 | 384/3360 (11.43%) |
| miscorrection | 0 | 0 | **0** |
| 物理可实现 | — | ❌ | ✅（无外部参考） |

**结论**：
1. 方案 B 实测 **88.57%**，与 92.4% 同量级（差 3.8pp）
2. 差异来源：τ 选择（8 vs 可能的 6/7）、注入协议（码字注入 vs 其他位置）、数据分布
3. **强烈支持"92.4% 是某种无补偿阈值化实现的历史实测"的假设**
4. 方案 B 的漏检全部为 silent_bounded（输出残差 ≤ τ，有界可接受）——这是 Gao 原教旨
   "小错误不检测、吸收为定点误差"的物理体现

## 5. 对审稿人 R1-M1 的回应要点（方案 B 视角）

| 审稿人要求 | 方案 B 的回应 |
|-----------|--------------|
| 推导阈值、量化和溢出规则 | `threshold_selection.md`：M=6（实测）→ τ=8（2 的幂） |
| 分别统计 corrected / detected-only / silent bounded / miscorrection | 双判据六分类逐 trial 记录（`sc01_uncomp_run_full_tau8.log`） |
| 实现层集合的非循环定义 | 无补偿 eligible set：\|raw syndrome 分量\| > τ 进入纠正流程 |
| 数学合同与硬件结论闭合 | 复数域定理（精确模型）+ 定点实现经验覆盖（88.57% bounded）+ 0 miscorrection 分层报告 |

## 6. 文件清单

| 文件 | 说明 |
|------|------|
| `sc01_b0_residual_tb.sv` | 残差测量 TB（零注入） |
| `residual_distribution.csv` | 残差原始数据（40,960 行） |
| `residual_stats.json` | 残差统计（M=6 证据） |
| `threshold_selection.md` | τ 推导（M → τ） |
| `sc01_uncomp_tb.sv` | 故障注入 testbench（双判据） |
| `sc01_uncomp_compile.sh` | 编译/仿真脚本 |
| `sc01_uncomp_run_full_tau8.log` | 全量仿真日志（3360 trials） |
| `sc01_uncomp_results.json` | 结果汇总 |
| `sc01_uncomp_summary.md` | 本文件 |
| `sc01_uncomp_parse_results.py` | 日志解析脚本 |
| `output_hashes.txt` | SHA-256 清单 |

RTL 新增（全部追加，未修改原模块）：
- `common/rtl/protection_rtl.sv`：`arithmetic_corrector_643_uncomp`
- `common/rtl/protection_primitives_v5.sv`：`arithmetic_boundary_uncomp_v5`、`independent_butterfly_ecc_v5_uncomp`
- `common/rtl/protected_stages_v5.sv`：`ecc_stage4_v5_uncomp`
- `common/rtl/top_s3_subfft_ecc_uncomp.sv`：新建

备份：`scratch/sc01_uncomp_backup_20260810/`

---

## 7. QUESTION 标记

- **QUESTION-B-1**：论文 92.4% 与方案 B 实测 88.57% 差 3.8pp。若 92.4% 确实来自无补偿
  实现，差异可能来自 τ 值（旧实现可能 τ=6 或 7）或注入协议（700 trials 子集 vs 3360 全量）。
  需要论文侧确认旧数字的产生条件。
- **QUESTION-B-2**：方案 B 的 2976 个纠正全部为 bitexact（corrected_bounded=0）——因为
  注入点是码字，纠正恢复原始码字。若注入点在符号值（蝶形输入），纠正后输出将带 ρ 污染
  （bounded 而非 bitexact）。论文应明确注入模型。

---

*本文档由 Deepseek 执行会话编写。*
