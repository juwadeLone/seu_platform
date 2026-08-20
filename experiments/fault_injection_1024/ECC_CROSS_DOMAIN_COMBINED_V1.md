# ECC跨域组合注入计划 V1

状态：`PLANNED / NOT_RUN / NO_RESULTS`  
决策依据：D134（2026-07-28）  
实验归属：论文实验二“恢复能力”的补充验证，不是第三项论文实验

## 目的

验证同一ECC-mode stage–phase recovery interval内同时出现以下两项eligible effects时，串联恢复边界能否保持该级前传结果与无故障结果bit-exact一致：

1. 所选SDF feedback-memory codeword中至多一个bit effect；
2. 同一级算术\([P+2,P,3]\) codeword中至多一个symbol effect。

该计划只验证两个独立域各一次的组合，不扩大为单个SECDED codeword多bit纠正、单个算术codeword多symbol纠正、地址/调度错误、公共模式故障或恢复逻辑故障。

## 结构前提

活动RTL中，feedback-memory SECDED译码输出先进入功能算术路径及check-operand generators；随后功能输出与两个check outputs在前传前经过算术ECC译码。因此两个故障域具有连续且独立的恢复边界，形式化集合为

\[
\mathcal F^{\mathrm{ECC}}_{s,k}
=
\mathcal F^{\mathrm{mem}}_{s,k}
\times
\mathcal F^{\mathrm{ari}}_{s,k}.
\]

结构前提不是组合注入的实验结果；本文件建立的Python campaign用于补足该经验验证。

## 计划对象

- S3中同时具有SDF feedback memory与直接算术ECC的stage；
- P1中同时具有SDF feedback memory与直接算术ECC的stage；
- 仅选择两个保护域都非空的stage–phase interval；
- TMR-mode stages、S1 path-level ECC及无保护S0/P0不属于本计划。

精确stage集合、phase集合、memory bit sites、arithmetic symbol sites与抽样/全枚举策略必须在执行前写入本文件的执行版合同并冻结，不能根据运行结果反向修改。

## 计划注入顺序

对每个已冻结case：

1. 生成并保存无故障reference；
2. 在所选feedback-memory codeword注入一个bit effect；
3. 在同一stage–phase interval的算术codeword注入一个symbol effect；
4. 按实现顺序执行memory decode、功能运算、arithmetic decode；
5. 比较该级前传结果及最终FFT输出与reference；
6. 记录两个域的注入位置、综合征/分类、恢复结果和最终比较结果。

## PASS/FAIL判据

PASS必须同时满足：

- memory-domain effect位于声明集合内；
- arithmetic-domain effect位于声明集合内；
- 该级前传结果与无故障值bit-exact一致；
- 最终FFT输出、顺序和有效边界与无故障reference一致；
- 零failure、零silent data corruption。

任何不满足上述条件的行均为FAIL，不得通过修改输入矩阵、过滤输出或放宽比较规则消除。

## 执行与证据要求

- 只使用工作区Python程序；本计划不授权Vivado、XSim、板级或辐照流程；
- 不修改`results/seven_arch_v1/`及任何现有冻结CSV；
- 计划输出目录：`results/ecc_cross_domain_combined_v1_001/`；
- 执行前记录Python版本、完整命令、输入文件、配置、预期行数和PASS/FAIL判据；
- 执行后记录stdout/stderr、逐行结果、汇总、git状态及所有输入/输出SHA-256；
- 在实际运行完成并验收前，论文不得把该计划写成已验证结果，也不得把其行数并入219,991。

## 当前记录

截至2026-07-28：

- 未新增或修改注入代码；
- 未运行Python、RTL、Yosys、Vivado或XSim；
- 未创建结果目录；
- 无结果、无PASS比例、无新增论文数字。
