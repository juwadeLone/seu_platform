# 七工程严格拆分合同（V2）

状态：`WORKING_COPY_NOT_EXECUTED`

本合同只约束源码归属和可复现入口，不产生新的故障注入、RTL qualification
或 Yosys 结果。

## 重构前冻结输入

- 快照：`archive/migration/2026-07-23/pre_strict_seven_project_split_v2/`
- 文件数：82
- `SHA256_MANIFEST.csv` 的 SHA-256：
  `CF6C0A217A91767D8A25CE24DBB757D7FD01C241A3856FCEEDC59D05051FB510`
- 七对象、故障域、trial 数、stage map 和论文数字均不得因拆分改变。

## 目标输出

每个 `projects/<ID>/` 必须独立拥有：

1. 唯一 Python 入口 `run_<id>.py`，且其中直接声明本架构的试验日程；
2. 唯一架构 RTL 文件 `top_<id>_*.sv`，文件内包含本架构专属 core 和综合顶层；
3. 唯一 testbench 文件；
4. `config.json`、`project.json` 和独立 `results/`。

`common/` 只允许保留：

- 固定点 FFT 数学；
- SECDED、算术 ECC、Gao 编码和 TMR 原语；
- 合同读取、哈希、CSV/JSON I/O 和通用单点注错原语；
- 蝶形、存储、级、保护和帧缓冲等底层 RTL 原语；
- 公共向量和跨工程资格工具。

## PASS/FAIL 判据

只有同时满足以下条件才可把“严格拆分”记为 `PASS`：

- 活动目录中不存在 `campaign_engine.py`、混合七架构 `model.py` 或
  `architecture_cores_v2.sv`；
- 七个 `run_<id>.py` 均可独立导入，且不从其他工程导入架构逻辑；
- 架构专属 core module 只定义在对应项目的唯一 `top_*.sv`；
- 每个工程只使用公共 RTL 原语和本工程 RTL 即可通过 Icarus 静态编译；
- 七个 `project.json` 和 `config.json` 均可解析，且 source 列表存在；
- Yosys/qualification source contract 指向新的项目内 core；
- `results/seven_arch_v1/` 和 Markov V1 不被修改；
- 本次不运行正式 Python campaign、RTL simulation、Yosys 或 Vivado。

任何一项不满足即为 `FAIL`，不得将 V2 写成已验证实验。
