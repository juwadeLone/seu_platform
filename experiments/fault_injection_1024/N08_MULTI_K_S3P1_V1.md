# 多错误注入实验合同：S3/P1 × k={2,5,8}

记录号：`N08-MULTI-K-S3P1-V1`
日期：2026-08-14
状态：`PLANNED / 待作者执行`
决策：D164（预留）
前置：N07 已完成（S3/P1 单错误 3360 枪、S1 中间级 3920 枪）

---

## 0. 一句话目标

把"每枪 1 个错误"升级为"每枪 k 个错误（不同级、每级最多 1 个）"，测 S3/P1 在
**跨级多故障**下的四分类行为，并与单错误结果对照。**唯一变量 = 同时错误数 k。**

## 1. 决策点（执行前先确认，默认走 A）

| 选项 | k 集合 | 说明 |
|---|---|---|
| **A（推荐）** | {2, 5, **8**} | 严格守"每级 1 错误"；k=8 = 可注入级数上限（S3: Stage1-8；P1: Stage1-7+10） |
| B | {2, 5, 10} | k=10 需 2 级各打 2 个错误（upper/lower 双窗口），牺牲约束，不推荐 |

> ⚠️ 若选 B，k=10 的数据与 k=2/5 口径不一致，论文表格必须加脚注。

## 2. 枪数与错误总数

| k | 枪数 | 错误总数 | 理由 |
|---|---|---|---|
| 2 | 500 | 1000 | miscorr 统计主力 |
| 5 | 200 | 1000 | 中等密度 |
| 8 | **200** | **1600** | 加量：k 大枪少则 miscorr 测不到（100 枪×8=800 错时 0.2% 误纠率期望仅 1.6 枪） |

S3、P1 各自跑这三组 = **6 组仿真**。每组目录：

```
results/n08_multi_k2_s3_v1_001/   （k=2，S3）
results/n08_multi_k5_s3_v1_001/
results/n08_multi_k8_s3_v1_001/
results/n08_multi_k2_p1_v1_001/
results/n08_multi_k5_p1_v1_001/
results/n08_multi_k8_p1_v1_001/
```

## 3. 错误位置生成（分层均匀 + 固定种子）

**目的**：多错误实验的位置边际分布必须与单错误注入一致，差异只反映 k。

位点空间：
- S3：级 {1..8} × 符号 {0..5} × 分量 {0,1} × bit {0..34}
- P1：级 {1..7,10} × 符号 {0..5} × 分量 {0,1} × bit {0..34}

生成规则（脚本 `gen_multi_sites.py`，种子固定 `20260814`）：
1. 每枪 k 个位置，**级互不重复**（不放回抽样）
2. 四层配额均匀：级 → 符号 → 分量 → bit，逐层轮询取，保证
   - 每级出现次数 ≈ 总错误数/8（跨所有枪）
   - 每符号 ≈ 总错误数/6，每分量 ≈ 1/2，每 bit ≈ 1/35
3. 输出 `sites_k{k}.csv`：每行一枪，k 个 `(stage,symbol,component,bit)` 用 `;` 分隔
4. 生成后自检打印各级/各 bit 出现次数直方图，偏差 >5% 报警

## 4. TB 改造规格（在现有 sc01 TB 基础上）

现有 TB 是单错误（一个 inject_enable / inject_symbol / component / bit）。
多错误 TB 扩展：

```verilog
// 每枪读 sites 行，解析 k 个错误
reg [2:0] err_stage  [0:7];
reg [2:0] err_symbol [0:7];
reg       err_comp   [0:7];
reg [5:0] err_bit    [0:7];
reg [7:0] err_done;   // 每级一个注入完成标志
```

注入逻辑（对每个错误 e，所属级 s）：
- S3：`fault.u.s{s}.work_valid && fault.u.s{s}.work_second` 成立的那一拍，对该级拉
  `inject_enable`，并给 `inject_symbol/component/bit = err_*[e]`，置 `err_done[e]=1`
- P1：Stage 1–7 同 S3；Stage 10 窗口 = `fault.u.s10.pair_phase==1`
- **k 个错误的窗口在流水推进的不同拍**（不同级不同时刻），逐错误等自己的窗口即可；
  一枪内所有 k 个注入必须在同一帧（512 beat）监视窗口内完成，超时打印 WARN

检测/纠正 flag 采集（关键差异）：
- `det_seen = OR(所有注入级对应 flag)`；`cor_seen = OR(同)`；`loc` 记录第一个举手的级
- **miscorr 判定不变**：顶层 `clean_word !== fault_word` 且 `cor_seen==1`

四分类逻辑、输出对照、监视窗口全部沿用现有 TB。

## 5. 执行顺序（先回归后正式）

```bash
# 0) 生成位点
python3 experiments/fault_injection_1024/scripts/gen_multi_sites.py --seed 20260814 \
  --arch s3 --k 2 --trials 500 --out results/n08_multi_k2_s3_v1_001/sites_k2.csv
# （s3/p1 × k=2/5/8 共 6 份，同上）

# 1) 回归：多错误 TB 先跑 k=1 小样（36 枪），应复现单错误行为
iverilog -g2012 -o sim_regress tb_multi.sv top_s3_subfft_ecc_thresholded.sv ...
vvp sim_regress

# 2) 正式：每组
iverilog -g2012 -o sim_k2_s3 tb_multi.sv <DUT> ...
vvp sim_k2_s3 > run_k2_s3.log

# 3) 汇总
python3 analyze_multi.py results/n08_multi_k2_s3_v1_001/run_k2_s3.log ...
```

τ 沿用 N07 标定：**S3 τ=2，P1 τ=3**（不重新标定，多错误与单错误同一阈值口径）。

## 6. 输出与统计

每组输出：
- `run_k{k}.log`：每枪 `TRIAL ... category=...` + `SUMMARY`
- `problem_sites.csv`：非 corrected 行（枪号、k、该枪全部位点、类别、detected/corrected/loc）
- `combined_summary.txt`：四分类计数
- `AUDIT.md` / `sha256sums.txt`

汇总表（论文表 B 骨架）：

| 架构 | k | 枪数 | corrected | bounded | unbounded | miscorr |
|---|---|---|---|---|---|---|
| S3 | 1 | 3360 | 94.29% | 3.15% | 2.56% | 0 |
| S3 | 2 | 500 | ? | ? | ? | ? |
| S3 | 5 | 200 | ? | ? | ? | ? |
| S3 | 8 | 200 | ? | ? | ? | ? |
| P1 | 1 | 3360 | 94.29% | 1.90% | 3.81% | 0 |
| P1 | 2 | 500 | ? | ? | ? | ? |
| P1 | 5 | 200 | ? | ? | ? | ? |
| P1 | 8 | 200 | ? | ? | ? | ? |

## 7. 验收标准（全过才算 PASS）

1. 每枪实际注入数 = k（日志核对 `injected==k`，0 失败）
2. 四分类计数合计 = 枪数
3. k=1 回归与 N07 单错误结果一致（94.29/3.15/2.56/0 与 94.29/1.90/3.81/0）
4. 位置直方图偏差 ≤5%
5. 墙钟、vvp 版本、exit 0 记录在案

## 8. 预期（对账用，非验收标准）

- corrected 随 k 下降但**不崩**（每级检查器仍面对可纠域）
- **miscorr 预期 = 0**（逐级隔离、syndrome 干净）——若出现，立即记录位点组合并回报
- bounded+unbounded 随 k 上升（多 silent 残差叠加）

## 9. 不能写成什么

- k 实验枪数 ≠ 论文 700 分母；不得用新百分比覆盖 94.4%
- 不得把"多错误下 corrected 下降"说成架构劣化——先对照 k=1 基线
- 位置生成必须可复现（种子写进 AUDIT），否则审稿人无法核验
