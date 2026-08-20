# Gao 方法对比表

## 1. 对比表

| 指标 | Gao 2016 | 本论文（当前 TeX 报告） | 本论文（Python 阈值化实验） |
|------|----------|----------------------|--------------------------|
| 阈值 τ | 1 | "quantization-derived residual threshold" | **0**（精确整数模型） |
| 数据宽度 | 12–16 bit | 35 bit (data) / 39 bit (check) | 35 bit / 39 bit |
| 定点截断 | 有 | 有（RTL 实现） | **无**（精确整数） |
| fault coverage | ~99.9% | 92.4% (Level-1 recovery) | **100%** (τ=0) / 97.14% (τ=1) |
| 零 syndrome 漏检 | 未报告 | 39/700 (5.6%) | **0** (τ=0) / 96/3360 (2.86%, τ=1) |
| 检测但不可纠正 | 未报告 | 14/700 (2.0%) | **0** |
| miscorrection | 未报告 | 0 | **0** (必须为 0，已验证) |

## 2. 四分类计数

### 2.1 阈值 τ=0（推荐：精确整数模型的正确 Gao 阈值）

| 分类 | S3 | P1 | 定义 |
|------|----|----|------|
| **corrected** | 3360 (100%) | 3360 (100%) | 检测到 + 纠正 + 输出 bit-exact 匹配 |
| **detected-only** | 0 (0%) | 0 (0%) | 检测到但无法纠正 |
| **silent bounded residual** | 0 (0%) | 0 (0%) | 未检测到（syndrome 低于阈值）+ 输出残差有界 |
| **miscorrection** | 0 (0%) | 0 (0%) | 纠正后输出与 golden 不一致 |

- **严格 bit-exact PASS 率**：S3=100%, P1=100%
- **Gao 式 PASS 率**：S3=100%, P1=100%

### 2.2 阈值 τ=1（对比参考：模拟 Gao 2016 的 τ=1）

| 分类 | S3 | P1 | 定义 |
|------|----|----|------|
| **corrected** | 3264 (97.14%) | 3264 (97.14%) | 检测到 + 纠正 + 输出 bit-exact 匹配 |
| **detected-only** | 0 (0%) | 0 (0%) | 检测到但无法纠正 |
| **silent bounded residual** | 96 (2.86%) | 96 (2.86%) | 未检测到（|syndrome|≤1）+ 输出残差有界 |
| **miscorrection** | 0 (0%) | 0 (0%) | 纠正后输出与 golden 不一致 |

- **严格 bit-exact PASS 率**：S3=97.14%, P1=97.14%
- **Gao 式 PASS 率**：S3=100%, P1=100%

## 3. 关键差异分析

### 3.1 为什么 Python 模型得到 100% 而论文报告 92.4%

论文 TeX (L1213–1230) 报告的 92.4% 来自 **RTL 硬件实现** 中的定点截断效应：

1. **39 个 zero-syndrome 漏检**：RTL 中 butterfly 和 twiddle 乘法的定点截断产生残差，使低位翻转的 syndrome 被截断为零
2. **14 个检测但不可纠正**：定点截断使 syndrome 偏离精确模式，无法匹配单一 symbol 位置

Python 仿真使用**精确整数运算**（`int` 类型，无截断），因此：
- 无故障 compensated syndrome 恰好为 (0, 0)
- 所有单 bit 翻转产生非零 syndrome
- 所有 syndrome 精确匹配单 symbol 模式
- 100% 检测 + 100% 纠正 + 0% miscorrection

### 3.2 这对审稿人问题意味着什么

| 审稿人要求 | Python 实验的回应 |
|-----------|------------------|
| "给出实现层集合的非循环定义" | 阈值化的 eligible set：syndrome 分量超过 τ=0 才进入纠正流程 |
| "推导阈值、量化和溢出规则" | τ=0 是精确整数模型的正确 Gao 阈值；无故障残差 = 0 → τ = 0 |
| "分别统计 corrected/detected-only/silent/miscorrection" | τ=0: 3360/0/0/0; τ=1: 3264/0/96/0 |
| "将精确复数域定理与定点实现命题分开" | 精确模型 = 100% 纠正；定点实现 = RTL 阈值化实测覆盖率 |
| "若不能做到，改为经验覆盖主张" | Python 精确模型验证了复数域定理的 100% 纠正能力；92.4% 是 RTL 定点实现的经验数字 |

### 3.3 Gao 方法的正确实现

本实验在 `protection.py` 中新增了 `arithmetic_643_decode_thresholded` 函数：

- **检测**：syndrome 各分量 |值| ≤ τ → 视为无错
- **纠正**：纠正后 syndrome 各分量 |值| ≤ τ → 纠正成功
- **模式匹配**：用阈值比较替代精确比较
- **多匹配处理**：选择纠正后残差最小的位置

## 4. 文件清单

| 文件 | SHA-256 |
|------|---------|
| `four_class_breakdown.csv` | 68639DD07040817A5C6B33929182FBC3363F0C3F1265C6FAE9D9236C7ACCBD11 |
| `s3_threshold_results.json` | 4D3046FCA54637E9CE63738E63F7705B8A949FB372ED4CEDD0B7FF0A747F8236 |
| `p1_threshold_results.json` | 19596750AA724784FB51B135E9B583380535080A97BE2246B30447C775DB7702 |
| `combined_results.json` | 85E1AAD6A6B985FB42D7417AE289BE91A3FF576CED3E6140B1C1B0471C77DA3D |
| `syndrome_distribution.csv` | (见 output_hashes.json) |
| `syndrome_stats.json` | (见 output_hashes.json) |
