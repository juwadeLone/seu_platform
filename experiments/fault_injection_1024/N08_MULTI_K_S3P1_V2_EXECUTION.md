# N08 V2 多错误 RTL 重跑报告

记录号：`N08-MULTI-K-S3P1-V2`
执行日期：2026-08-14
状态：`RTL_EXECUTED / AUDIT_PASS`

本次只新增 V2 testbench、脚本、回归证据和 V2 结果目录；V1 与更早的仿真代码、位点表和日志均未修改。正式重跑保持 S3 τ=2、P1 τ=3、原激励和 N08 V1 位点，且每个级只注入一拍。

## 正式结果

| 架构 | k | 枪数 | corrected | detected_only | bounded | unbounded | miscorrection | timeout |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S3 | 2 | 500 | 497 (99.4%) | 3 (0.6%) | 0 | 0 | 0 | 0 |
| S3 | 5 | 200 | 195 (97.5%) | 5 (2.5%) | 0 | 0 | 0 | 0 |
| S3 | 8 | 200 | 188 (94.0%) | 12 (6.0%) | 0 | 0 | 0 | 0 |
| P1 | 2 | 500 | 495 (99.0%) | 5 (1.0%) | 0 | 0 | 0 | 0 |
| P1 | 5 | 200 | 190 (95.0%) | 10 (5.0%) | 0 | 0 | 0 | 0 |
| P1 | 8 | 200 | 185 (92.5%) | 15 (7.5%) | 0 | 0 | 0 | 0 |

六组共 1800 枪、7200 个 RTL 故障事件。每枪 `injected=k`，无 timeout、无 corrected_no_flag、无真误纠正。

## V1 → V2 重分类结论

V1 的 50 个 `MISCORRECTION` 枪号与 V2 的 50 个 `detected_only` 枪号逐枪完全一致：

- S3：3 / 5 / 12 枪；
- P1：5 / 10 / 15 枪。

V2 没有任何 `MISCORR_EVIDENCE`。这些枪均属于“至少一级正确定位并纠正，但另一级静默残差使顶层输出不等”，不能称为误纠正。V1 的 50 枪 miscorr 结论作废，不得进入论文。

## k=1 回归发现

从 N07 原始日志抽取 36 个已知位点（12 corrected、12 bounded、12 unbounded）进行逐点回归：

1. 真正的逐级一拍注入结果：12 corrected、24 bounded、0 unbounded；
2. 精确复现 N07 的“共享注入口并持续拉高到输入帧结束”后：12 corrected、12 bounded、12 unbounded，与 N07 逐点 36/36 一致。

因此，N07 的 silent-unbounded 位点依赖旧 TB 的两个联合行为：`inject_enable` 在命中后未立即清零，以及同一个注入口同时连接所有 ECC 级。N07 结果不能作为严格的“单级、单拍、单错误”基线；正式 N08 V2 未启用该兼容模式。

## 验收与证据

- V1/V2 位点 CSV 的 SHA-256 六组逐一相同；
- 六组枪数与分类合计正确；
- `bad_injected=0`，`timeout=0`；
- `miscorrection=0`，`MISCORR_EVIDENCE=0`；
- V1 miscorr 枪号与 V2 detected_only 枪号逐组完全相同；
- 每组目录包含 `run_k{k}.log`、`combined_summary.txt`、`AUDIT.md`、`compile.log` 和 `sha256sums.txt`。

```text
results/n08_multi_k2_s3_v2_001/
results/n08_multi_k5_s3_v2_001/
results/n08_multi_k8_s3_v2_001/
results/n08_multi_k2_p1_v2_001/
results/n08_multi_k5_p1_v2_001/
results/n08_multi_k8_p1_v2_001/
results/n08_regress_s3_v2_001/
results/n08_regress_p1_v2_001/
```

## 问题网更新

- `N08-V1-CLASS-OR`：已关闭。OR 合并导致的误纠正误判已由逐级 `det/cor/unc/loc` 归因修复。
- `N07-INJECT-HOLD-SHARED`：新发现。旧单错误 TB 的注入使能持续到帧末且共享到全部 ECC 级，N07 silent-unbounded 证据需重新界定。
