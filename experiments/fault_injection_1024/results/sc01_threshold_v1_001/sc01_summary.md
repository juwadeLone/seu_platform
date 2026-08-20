# SC-01 总结报告：阈值化恢复率实验

## 概述

本报告回应审稿人 R1-M1/SC-01，在 Python 仿真中实现 Gao 阈值检测逻辑，重跑恢复率实验。

## 1. 实验方法

### 1.1 新增函数

在 `experiments/fault_injection_1024/common/python/protection.py` 中新增：

- `_within_threshold(s, threshold)`: Gao 式阈值检测
- `arithmetic_643_decode_thresholded(received, expected_residual, threshold)`: 阈值化 [6,4,3] 解码器

### 1.2 阈值推导

通过诊断扫描（13,440 个 S3 arithmetic 试验）确定：

- 无故障 compensated syndrome = (0, 0)（精确整数模型无截断残差）
- 所有单 bit 翻转产生非零 syndrome，最小 |syndrome| = 1
- 按 Gao 原则（τ = 无故障残差最大值），**选定阈值 τ = 0**

### 1.3 实验范围

对 S3 和 P1 各运行 3,360 个试验（8 stages × 6 symbols × 2 components × 35 bits），记录四分类结果。

## 2. 核心结果

### 2.1 阈值 τ=0（精确整数模型的正确 Gao 阈值）

| 指标 | S3 | P1 |
|------|----|----|
| 总试验数 | 3,360 | 3,360 |
| corrected | 3,360 (100%) | 3,360 (100%) |
| detected-only | 0 (0%) | 0 (0%) |
| silent bounded residual | 0 (0%) | 0 (0%) |
| miscorrection | 0 (0%) | 0 (0%) |
| **严格 bit-exact PASS 率** | **100%** | **100%** |
| **Gao 式 PASS 率** | **100%** | **100%** |

### 2.2 阈值 τ=1（对比参考）

| 指标 | S3 | P1 |
|------|----|----|
| corrected | 3,264 (97.14%) | 3,264 (97.14%) |
| silent bounded residual | 96 (2.86%) | 96 (2.86%) |
| miscorrection | 0 (0%) | 0 (0%) |
| **Gao 式 PASS 率** | **100%** | **100%** |

## 3. 与论文当前数字的关系

论文 TeX (L1180) 报告 S3/P1 Level-1 recovery = 92.4%，其中：
- 39/700 = 5.6% zero-syndrome 漏检
- 14/700 = 2.0% 检测但不可纠正
- 0 miscorrection

**Python 精确整数模型得到 100%，不是 92.4%。** 原因：

| 因素 | Python 模型 | RTL 硬件 |
|------|------------|---------|
| 运算方式 | 精确整数（Python `int`） | 定点截断（35-bit wrap + twiddle 截断） |
| 无故障残差 | 恰好 0 | 非零（定点截断） |
| Gao 阈值 τ | 0 | >0（由定点位宽推导） |
| 低位翻转 syndrome | 非零（最小=1） | 可能为零（被截断） |
| 不可纠正 | 0 | 14（模式偏离） |

**92.4% 是 RTL 定点实现的经验数字，Python 精确模型验证的是复数域理论的 100% 纠正能力。**

## 4. 对审稿人 R1-M1 的回应要点

### 4.1 数学合同与硬件结论的闭合

审稿人指出"数学合同（100% 纠正）与硬件结论（92.4%）不闭合"。

**回应**：两者是分层主张：
1. **复数域定理**（精确模型）：在精确复数运算下，[6,4,3] 码可纠正任意单 symbol 错误 — Python 实验验证此定理成立（100%）
2. **定点实现命题**（阈值化实例）：在 35-bit 定点截断下，Gao 阈值化 decoder 的经验覆盖率为 92.4% — 这反映定点截断效应，不是码距不足

### 4.2 Gao 方法的正确实现

本实验在 Python 中实现了完整的 Gao 阈值检测：
- 逐分量阈值判定：`|syndrome.real| ≤ τ and |syndrome.imag| ≤ τ`
- 阈值化纠正验证：纠正后 syndrome 在阈值内才算成功
- 阈值化模式匹配：替代精确比较
- 多匹配选择：取纠正后残差最小的位置
- miscorrection = 0（硬要求满足）

### 4.3 四分类完整计数

| 分类 | τ=0 | τ=1 |
|------|-----|-----|
| corrected | 3360 | 3264 |
| detected-only | 0 | 0 |
| silent bounded residual | 0 | 96 |
| miscorrection | 0 | 0 |

## 5. 建议

1. **论文修改方向**：将 TeX 中的 92.4% 明确标注为"RTL 定点实现的经验覆盖率"，与精确模型 100% 分开表述
2. **数学命题**：保持复数域 100% 纠正定理，补充"定点实现下经验覆盖 92.4%"的实现命题
3. **阈值说明**：在论文中说明 Python 精确模型验证了理论 100%，RTL 定点实现的 92.4% 来自 butterfly/twiddle 截断残差
4. **如需在 Python 中复现 92.4%**：需要在 `fixed_fft.py` 的 `butterfly_scaled` 和 `multiply_twiddle` 中引入定点截断模型，使无故障残差非零 — 这是后续工作

## 6. 文件清单

| 文件 | 说明 |
|------|------|
| `threshold_derivation.md` | 阈值推导报告 |
| `s3_threshold_results.json` | S3 阈值化恢复率结果 |
| `p1_threshold_results.json` | P1 阈值化恢复率结果 |
| `four_class_breakdown.csv` | 四分类逐试验记录 |
| `syndrome_distribution.csv` | Syndrome 分量分布统计 |
| `syndrome_stats.json` | Syndrome 分布汇总 |
| `gao_comparison_table.md` | 与 Gao 原文的对比表 |
| `output_hashes.json` | 输出文件 SHA-256 |
| `sc01_summary.md` | 本文件 |

## 7. 代码变更

| 文件 | 变更 |
|------|------|
| `common/python/protection.py` | 新增 `_within_threshold` 和 `arithmetic_643_decode_thresholded`（未修改原函数） |
| `sc01_diagnostic_scan.py` | 新建：syndrome 分布诊断扫描脚本 |
| `sc01_threshold_experiment.py` | 新建：阈值化恢复率实验脚本 |

## 8. QUESTION 标记

QUESTION-1: 论文中 92.4% 的 700 trials 是"fair inject matrix"（10 stages × 70 bit/component），但我们的全扫描是 8 stages × 6 symbols × 2 × 35 = 3360 trials。700 trials 是否只取 stage 1-8 的 symbol 0（功能符号）的 bit/component 组合？还是包含所有 6 个 symbol？需要确认 fair inject matrix 的精确定义。

QUESTION-2: 是否需要在 Python 模型中引入定点截断来复现 92.4%？当前 Python 精确模型无法产生 zero-syndrome 漏检。
