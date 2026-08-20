# 七工程严格拆分静态审计（V2）

结论：`PASS / EXECUTION-NOT-RUN`

日期：2026-07-23

## 结构审计

| 检查项 | 结果 |
|---|---|
| 工程目录 | S0、S1、S2、S3、P0、P1、P2，共 7 个 |
| 每工程 Python 入口 | 1 个，PASS |
| 每工程综合顶层 | 1 个，PASS |
| 每工程 testbench | 1 个，PASS |
| 项目内架构 RTL source | 共 7 个文件，每工程恰好 1 个 |
| 活动区 `campaign_engine.py` | 不存在，PASS |
| 活动区混合七架构 `model.py` | 不存在，PASS |
| 活动区 `architecture_cores_v2.sv` | 不存在，PASS |
| Python 跨项目架构导入 | 0，PASS |
| Yosys 合同 source | 13 个（6 个公共原语文件 + 7 个工程 RTL），全部存在 |
| 冻结 V1/Markov 变更 | 0，PASS |

## 项目自有代码

| ID | Python 行数 | 项目自有 RTL 行数 | Python/Top/TB |
|---|---:|---:|---|
| S0 | 56 | 36 | 1/1/1 |
| S1 | 208 | 39 | 1/1/1 |
| S2 | 98 | 29 | 1/1/1 |
| S3 | 294 | 29 | 1/1/1 |
| P0 | 55 | 50 | 1/1/1 |
| P1 | 531 | 445 | 1/1/1 |
| P2 | 103 | 30 | 1/1/1 |

S2、S3、P2 的 RTL 物理行数较少，是因为每一级实例采用长行表达，而且
蝶形、SECDED 和 voter 等底层原语按合同允许共享；十级架构连接与顶层已经
合并在各自唯一的 `top_*.sv`，不再藏在公共目录。

## 静态与模型单元验证

- Python AST/导入：PASS；
- trial 数公式：
  `S0=8, S1=34729, S2=16809, S3=26794, P0=8, P1=19306, P2=16809`；
- S3 四通道同算子分组：32 个抽样组与对应级输出一致；
- P1 Stage-1--7 直接同算子组：28 个抽样组与对应级输出一致；
- P1 Stage-8：256 个同帧组、256 个跨帧组、512 个首帧 pending
  symbol、0 个未消费 symbol；
- RTL 原结构审计：18/18 PASS；
- 七工程分别只使用 6 个公共原语文件和本工程唯一 RTL 进行 Icarus 静态编译：
  7/7 PASS。

## 证据边界

本审计没有运行正式 Python fault campaign、RTL simulation、Yosys、Vivado、
XSim、板级或辐照流程。因此这里只能证明“七工程已经严格拆分且可静态解析/
编译”，不能把 V2 标记为新的实验验证结果。
