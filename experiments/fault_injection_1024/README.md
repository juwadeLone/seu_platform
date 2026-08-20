# 七架构 1024 点 FFT 实验

当前实验固定研究1024点、四通道、十级radix-2 FFT。

## 七个工程

七个可见工程目录统一位于[`projects/`](projects/)。

### SubFFT组

| ID | 工程 | 当前RTL顶层 |
|---|---|---|
| S0 | 未保护SubFFT基线 | `top_s0_subfft_unprotected` |
| S1 | Gao完整路径ECC | `top_s1_gao_subfft_ecc` |
| S2 | 逐级完整TMR | `top_s2_subfft_tmr` |
| S3 | 逐级ECC方案 | `top_s3_subfft_ecc` |

### PFFT组

| ID | 工程 | 当前RTL顶层 |
|---|---|---|
| P0 | 未保护PFFT基线 | `top_p0_pfft_unprotected` |
| P1 | 逐级ECC方案 | `top_p1_pfft_ecc` |
| P2 | 逐级完整TMR | `top_p2_pfft_tmr` |

只允许组内相对各自基线比较：S1/S2/S3相对S0，P1/P2相对P0。

## 目录阅读顺序

1. `projects/`：S0–S3、P0–P2七个工程入口；
2. `SEVEN_ARCHITECTURE_MATRIX_V1.md`：七架构定义和既有证据边界；
3. `config/`：当前V2合同、故障矩阵、存储映射和Yosys合同；
4. `common/`：七工程共享的数学、编码、I/O、底层RTL原语、向量和资格工具；
5. `results/seven_arch_v1/`：只读冻结结果。

## 两项论文实验

### 资源代价

RTL qualification通过后，使用指定Yosys进行`xc7`综合。资源按LUT/LC、FF、DSP、BRAM分别报告。

存储资源按三层指标报告：

| 层次 | 指标 |
|---|---|
| 逻辑需求 | 有效存储位数 |
| 物理映射 | BRAM18、BRAM36、LUTRAM |
| 利用效率 | 有效位数/已分配物理容量 |

### 恢复能力

Python位级注入验证能否恢复；Markov/CTMC量化归一化stage-level恢复能力水平。

- 既有`results/seven_arch_v1/`仅冻结memory-only、arithmetic-only及replica-effect等已执行行；
- [`ECC_CROSS_DOMAIN_COMBINED_V1.md`](ECC_CROSS_DOMAIN_COMBINED_V1.md)记录同一ECC interval内memory与arithmetic各一次的组合注入计划，状态为`PLANNED / NOT_RUN / NO_RESULTS`，不得提前计入论文行数或PASS结论。

## 版本状态

- `results/seven_arch_v1/`及既有七架构CSV：冻结证据，旧路径保留为provenance；
- `projects/S0...P2/`：七个独立V2工作工程，尚未执行；
- `STRICT_SEVEN_PROJECT_SPLIT_V2.md`：七工程代码归属和静态验收合同；
- `STRICT_SEVEN_PROJECT_SPLIT_AUDIT_V2.md`：严格拆分静态验收结果；
- `PFFT_RESOURCE_REEVALUATION_V3.md`：当前已授权的 P0/P1/P2 D94 资源验证合同；
- `ECC_CROSS_DOMAIN_COMBINED_V1.md`：D134组合故障验证计划，尚未执行；
- [`N07_S3_S1_P1_Gao2023_三轮对照记录.md`](N07_S3_S1_P1_Gao2023_三轮对照记录.md)：2026-08-13～08-14 S3/S1/P1 的 Gao 2023 3σ 标定 + iverilog 位级注入对照（TB、XOR 钩子、阈值公式与三轮数字）；**不是**论文 700 分母；
- 旧五架构材料：已移至`../../archive/frozen_fault_injection_1024_v1/`，不再是当前入口。
