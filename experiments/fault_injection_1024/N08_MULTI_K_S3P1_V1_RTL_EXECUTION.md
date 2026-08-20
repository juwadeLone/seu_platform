# N08 多错误 RTL 执行报告

记录号：`N08-MULTI-K-S3P1-V1`
执行日期：2026-08-14
状态：`RTL_EXECUTED`

本报告对应 `N08_MULTI_K_S3P1_V1.md`。本次只新增 N08 wrapper、testbench、位点表、脚本和结果文件；已有仿真源码未修改。故障实际通过 Icarus Verilog/VVP RTL 链路注入，Python 仅用于生成可复现位点 CSV，不参与功能仿真。

## 结果

| 架构 | k | 枪数 | 实际注入 | corrected | detected_only | bounded | unbounded | miscorrection | timeout |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| S3 | 2 | 500 | 2/枪 | 497 | 0 | 0 | 0 | 3 | 0 |
| S3 | 5 | 200 | 5/枪 | 195 | 0 | 0 | 0 | 5 | 0 |
| S3 | 8 | 200 | 8/枪 | 188 | 0 | 0 | 0 | 12 | 0 |
| P1 | 2 | 500 | 2/枪 | 495 | 0 | 0 | 0 | 5 | 0 |
| P1 | 5 | 200 | 5/枪 | 190 | 0 | 0 | 0 | 10 | 0 |
| P1 | 8 | 200 | 8/枪 | 185 | 0 | 0 | 0 | 15 | 0 |

六组共 1800 枪、7200 个 RTL 故障事件；六组均满足实际注入数等于 k，且无 timeout。四分类计数与枪数相加一致。

## 关键结论边界

两种架构均观察到误纠正，且误纠正计数随 k 增加：S3 为 3/5/12，P1 为 5/10/15。合同中的“miscorrection 预期为 0”未实现，因此这些结果不能写成“预期验证通过”，只能作为实际 RTL 观测结果进一步分析。

本报告不把多级错误的 `corrected` 直接解释为任意单个码字纠正多个错误；每个错误仍落在不同级、每级最多一个位置，最终分类依据是全输出 bit-exact 对照与对应级 flag。

## 证据位置

每组目录均包含 `run_k{k}.log`、`sites_k{k}.csv`、`problem_sites.csv`、`combined_summary.txt`、`compile.log` 和 `sha256sums.txt`：

```text
results/n08_multi_k2_s3_v1_001/
results/n08_multi_k5_s3_v1_001/
results/n08_multi_k8_s3_v1_001/
results/n08_multi_k2_p1_v1_001/
results/n08_multi_k5_p1_v1_001/
results/n08_multi_k8_p1_v1_001/
```

固定位点种子为 `20260814`；S3 阈值为 τ=2，P1 阈值为 τ=3。运行时终端持续打印每组完成枪数和最后一枪分类，原始逐枪输出保存在对应 `run_k{k}.log`。
