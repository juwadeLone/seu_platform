# N08 V2 多错误 RTL 注入重复执行记录

记录号：`N08-MULTI-K-S3P1-V2-REPEAT`
日期：2026-08-14
状态：`COMPLETED / PASS`
目的：在不修改既有 RTL、testbench 或首轮结果的前提下，用相同位点表独立重跑 S3/P1 × k={2,5,8}，检查结果可复现性。

---

## 1. 固定配置

- 仿真器：`iverilog -g2012` + `vvp`
- 注入对象：RTL
- 分类器：N08 V2 逐级归因分类
- 注入语义：`LEGACY_N07_HOLD=0`（一级一个错误、各级局部窗口单拍注入）
- S3 阈值：`THRESHOLD=2`
- P1 阈值：`THRESHOLD=3`
- 枪数：k=2 为 500 枪；k=5、k=8 各 200 枪；每个架构共 900 枪
- 位点：逐字节沿用 V2_001 的 `sites_k{k}_v1.csv`
- 输出目录：六个全新 `n08_multi_k{k}_{arch}_v2_002/` 目录

本次只新增执行脚本、审计脚本、V2_002 结果及本记录；未修改任何既有仿真代码或 V2_001 结果。

## 2. 第二轮结果

| 架构 | k | 枪数 | 错误数 | corrected | detected_only | miscorr | timeout | corrected 比例 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S3 | 2 | 500 | 1000 | 497 | 3 | 0 | 0 | 99.4% |
| S3 | 5 | 200 | 1000 | 195 | 5 | 0 | 0 | 97.5% |
| S3 | 8 | 200 | 1600 | 188 | 12 | 0 | 0 | 94.0% |
| P1 | 2 | 500 | 1000 | 495 | 5 | 0 | 0 | 99.0% |
| P1 | 5 | 200 | 1000 | 190 | 10 | 0 | 0 | 95.0% |
| P1 | 8 | 200 | 1600 | 185 | 15 | 0 | 0 | 92.5% |

六组中的 `corrected_no_flag`、`silent_bounded_residual`、`silent_unbounded` 均为 0。合计 1800 枪、7200 个 RTL 注入事件，未出现 `MISCORRECTION`、`MISCORR_EVIDENCE` 或 `TIMEOUT`。

## 3. V2_001 与 V2_002 复现性审计

审计脚本逐组完成以下比较，六组全部 PASS：

1. 位点文件 SHA-256 相同；
2. `SUMMARY` 行逐字符相同；
3. 1800 条 `TRIAL` 行逐字符相同；
4. 7200 条 `INJECT` 行逐字符相同；
5. 每枪 `injected=k`，总枪数和注入事件数均符合合同；
6. timeout、miscorrection、miscorrection evidence 均为 0。

因此，第二轮不仅聚合计数相同，而且每枪的注入、逐级 flag、location 和最终分类均与首轮一致。

## 4. 位点文件 SHA-256

| 架构 | k | SHA-256 |
|---|---:|---|
| S3 | 2 | `4a2efc6513be003b7f7d45793d9280b60db98810e8f00b5a5cc2076fc58665f1` |
| S3 | 5 | `a837c08a56addd0c3615e9ed15ef761f174f7bd0e55ded4c32dfe2e10f284353` |
| S3 | 8 | `49396ba03cb0e9904cd4830f2727128479e95085bc80b517c16f2b8c1f23db85` |
| P1 | 2 | `61644a68c2985aa8693d402791967965e000aa21ce91dd762732b25aeeb55ba3` |
| P1 | 5 | `a9122ee68bdac60d7314baba33ea1d380c33cb08b093882d3ffa893b8e003f35` |
| P1 | 8 | `59275769b190feef4d3c81f5886ce2c5141f0599a64d2bd2f0f4bae8ef3e8518` |

## 5. 关键执行文件 SHA-256

- S3 V2 TB：`65dae412919fc466369f30840ed8be607b8cef0a737dfa4901a8ddaa5b8f3bf6`
- P1 V2 TB：`e0bc3b7fd77aeaea0e9cb89e93bb02f7896aa8c48664c0ce550e12c33c97a380`
- 重跑脚本：`002f1ca8cefb2f6e16d85b7d858127676fa16f92d973e7c101d49ea27d332fe1`
- 重跑审计脚本：`137765767ae9351c08ee875e3f60b16a4249b1c3a39dea2a5cc356756ca07847`

每个 V2_002 结果目录另含 `run_k*.log`、`compile.log`、`progress.txt`、`combined_summary.txt`、`AUDIT.md` 和 `sha256sums.txt`，用于逐组追溯。

## 6. 结论边界

在本次固定 RTL、固定输入、固定跨级位点表和固定分类规则下，N08 V2 的六组结果可完全复现。该结论只支持当前受控注入配置，不外推为任意多错误模式或任一单一码字纠正多个错误。
