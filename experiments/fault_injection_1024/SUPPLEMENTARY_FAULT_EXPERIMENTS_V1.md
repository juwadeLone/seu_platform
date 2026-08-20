# 补充故障实验方案 V1

状态：`FROZEN / AUTHOR_APPROVED_2026-07-26`
日期：2026-07-26

**作者决策（2026-07-26）**：
1. 实验 A、B 都执行；
2. ECC 双符号 miscorrection 计数**暂不写入论文**——结果仅作内部证据留存（检查.md 挂接），
   供审稿阶段按需引用；论文集成范围限实验 A（多级并发）+ SECDED 双 bit 全枚举结果；
3. S1 "同路径双故障可纠"公平行保留。
动机：审稿模拟五人一致意见——现有 219,991 行 campaign 七架构全部 0/0，无架构间区分度；
"多级并发独立纠错"这一唯一差异化主张零测试行（DA-C2）；out-of-capability 仅 7 行（R1-M3）。
本方案只新增 Python 实验，不动 RTL、不动 Yosys、不覆盖任何冻结结果。

---

## 实验 A：多级并发故障（记录号建议 `SUPP-CONC-V1-001`）

**目的**：验证论文 L560 的主张 "independent codewords let $L$ stages correct $L$ concurrent
in-model effects"，并诚实展示 S1（路径级 ECC）在同场景下的能力边界——这是 S3/P1 相对 S1
的**唯一**功能差异点，也是回应 "S1 更便宜也全通过" 质疑的关键证据。

**故障模型扩展**：一个纠错区间内，在 $L$ 个不同 stage 各注入一个本级 in-model 效应
（ECC 级=单符号单 bit；TMR 级=单副本单 bit）。每级效应各自在声明能力内；跨级并发是新增维度。

**试验矩阵**：

| 对象 | 场景 | 行数 | 预期结果 |
|---|---|---|---|
| S3 | 全部 C(10,2)=45 个 stage 对 × bit{0,34} × comp{re,im} | 180 | 每级各自纠正，输出位精确 |
| S3 | 论文例 {3,5,8} 三级并发 ×4 变体 | 4 | 同上 |
| S3 | L=10 全级并发 ×4 变体 | 4 | 同上 |
| P1 | 同 S3 结构（1–7 ECC、8–9 TMR、10 两拍 ECC） | 188 | 同上 |
| S1 | 双效应落在**同一路径**的两个不同 stage（45 对 ×4） | 180 | 单路径错→路径级可纠（对 S1 公平） |
| S1 | 双效应落在**两条不同路径**（45 对 ×4） | 180 | 双路径错→超 d=3 能力，须拒纠不误纠 |
| S2 | 45 stage 对 × 单副本效应 ×4 | 180 | TMR 逐级掩蔽（诚实：TMR 也能做到） |
| P2 | 同 S2 | 180 | 同上 |

小计约 **1,096 行**。

**论文叙事落点**：S3/P1 与 TMR 同样具备多级并发恢复（差异在资源）；S1 不具备（差异在功能）。
把 DA-C2 的 "cherry-picking" 变成正面三方对比。

**PASS/FAIL**：受保护对象输出与无故障参考位精确（S3/P1/S2/P2 行）；S1 跨路径行按
`declared_out_of_capability` 判：不产生错误的"已纠正"主张即 PASS；全 campaign 确定性二次重放
SHA-256 一致；行数与枚举公式一致。**不允许**因结果不符合预期而修改判据或删行。

---

## 实验 B：超界负样本系统化枚举（记录号建议 `SUPP-NEG-V1-001`）

**目的**：把 7 行 out-of-capability 扩到约 7,700 行，按**三分类**报告超界行为：
`detected_uncorrectable`（诚实拒纠）/ `miscorrected`（误纠出错值）/ `silent`（未检出）。
同时修复内部检查 H4：现判据允许静默误纠计 PASS，与论文措辞不符。

**试验矩阵**：

| 类别 | 枚举 | 行数 | 理论预期 |
|---|---|---|---|
| [6,4,3] 双符号 | 15 个符号对 × 4 bit 组合{(0,0),(0,34),(17,17),(34,34)} × 2 comp 模式，8 个组（S3 三级、P1 三级、P1 Stage10 upper/lower 各 beat0） | 960 | 功能符号对权重互异→silent 应为 0；部分 miscorrected 属 d=3 固有，如实报数 |
| SECDED 双 bit | **全枚举** C(78,2)=3,003 对 × S3-Stage1 与 P1-Stage1 各一字 | 6,006 | 100% detected_uncorrectable（SECDED 保证），零误纠 |
| TMR 双副本同位 | 70 bit × S2{1,5,10}/P2{1,5,10}/S3{9,10}/P1{8,9} 各代表位置 | 700 | 表决输出错误值（TMR 固有短板，如实报告——反衬 ECC 检测力） |
| Stage-10 跨拍同符号对标注 | upper/lower 内 6 个功能符号对 ×4 bit 组合（含于双符号集，单独打标签） | 48 | 回应 R2-M4 持续故障双符号质疑 |

小计 **7,666 行**（Stage-10 跨拍 48 行为双符号集内的标签子集，不重复计行）。

**判定原则（关键，防"迎合结论"）**：三分类分布本身是**报告结果**，不是 PASS 门槛。
实验级 PASS 仅要求：(a) 每行分类完备且可复算；(b) SECDED 双 bit 零误纠（编码理论保证，
若违背说明实现有 bug）；(c) 确定性重放一致；(d) 行数闭合。ECC 双符号的 miscorrected 计数
无论多少都如实写入论文（d=3 码的教科书行为），并同步修正论文第 IV-C 节
"declines to make a supported-correction claim" 的措辞为按测得分布表述。

---

## 实验 C（可选，第二批）：统一注入面对比

同一逻辑故障清单（stage×position×bit）映射到七架构，报告 corrected/DUE/SDC 分布矩阵。
工作量大于 A+B，建议 A+B 完成并写入论文后再决定是否做。本方案不含其执行细节。

---

## 工程约束（遵守 AGENTS.md）

1. **代码**：新建 `common/tools/run_supplementary_concurrent.py` 与
   `run_supplementary_negative.py`，只复用 `common/python/` 现有模块；
   **不修改**任何现有 `run_*.py`、gate、合同和冻结结果。
2. **输出隔离**：`experiments/fault_injection_1024/results/supp_concurrent_v1_001/` 与
   `.../supp_negative_v1_001/`，raw CSV + summary JSON + SHA-256，格式沿用现有 campaign。
3. **批准后动作**：本文件状态改 `FROZEN`；实验决策记录新增 D121；任务卡登记两条记录号；
   检查.md 的 H4、DA-C2 相关条目挂接。
4. **预计运行时间**：全部 <10 分钟（纯 Python 位级模型，约 8,800 行）。
5. **论文集成**（实验完成后）：Section IV 新增小节 "Concurrent Multi-Stage and
   Out-of-Model Behavior" + 一张三分类结果表；摘要与结论补一句多级并发结果；
   Table VI 标题改 "In-Model Fault Enumeration Results"。

## 作者决策点（已于 2026-07-26 确认）

- [x] A/B 两个实验都做；
- [x] ECC 双符号误纠计数**暂不写进论文**（内部证据留存）；
- [x] S1 的"同路径双故障可纠"公平行保留。

---

## 执行结果（2026-07-26，两实验均 VERIFIED）

### SUPP-CONC-V1-001（实验 A：多级并发）

- 状态：`VERIFIED`；1,096/1,096 行 PASS，零失败；确定性二次重放一致。
- raw SHA-256：`57DF1F094E51AE0A363BF7189857DAD6...`（完整值见 summary JSON）。
- 结果分解：
  - S3/P1：45 个 stage 对、论文例 {3,5,8}、十级全并发——每级独立位精确恢复，全部 PASS；
  - S1 同路径双故障（180 行）：全部可纠（对基线公平）；
  - S1 跨路径双故障（180 行）：**全部 detected-uncorrectable，零误纠**——路径级方案不具备
    多点隔离能力的正面证据；
  - S2/P2（各 180 行）：TMR 逐级掩蔽全部成功（诚实承认 TMR 同样具备多级能力）。
- 论文落点：论文 L560 "L stages correct L concurrent in-model effects" 现在有 384 行直接证据；
  S3/P1 vs S1 的功能差异（多点隔离）与 vs TMR 的资源差异形成完整叙事。

### SUPP-NEG-V1-001（实验 B：超界负样本三分类）

- 状态：`VERIFIED`；7,666 行；确定性二次重放一致。
- raw SHA-256：`3EE1269769FAACF7B7B6262A434F3903...`。
- 三分类分布：
  - **SECDED 双 bit（6,006 行全枚举）：100% detected_uncorrectable，零误纠、零静默**——可直接写入论文的强结论；
  - ECC 双符号（960 行）：detected_uncorrectable 625（65.1%）、miscorrected 335（34.9%）、
    **silent 0**（理论预言证实：功能符号权重两两互异，双符号错不可能静默）——
    按作者决策仅作内部证据，不入论文；
  - Stage-10 跨拍标签子集：实际 **96 行**（upper+lower 各 48，合同原估 48 系漏乘 2，以实测为准）：
    64 拒纠 / 32 误纠 / 0 静默；
  - TMR 双副本（700 行）：100% 表决输出错误值（模型内有失配标志）——TMR 固有短板的量化记录。
- 论文落点（按作者决策）：仅 SECDED 全枚举结果 + 多级并发（实验 A）进入论文；
  ECC/TMR 双故障分布留作审稿答复弹药。
