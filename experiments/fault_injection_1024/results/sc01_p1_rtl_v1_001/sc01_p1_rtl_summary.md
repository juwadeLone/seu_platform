# SC-01 P1 RTL 级 Gao 阈值验证 —— 总结报告

> **执行者**：Deepseek 执行会话（paper-review profile）
> **日期**：2026-08-10
> **对应任务**：`review/交接文档_SC01_P1_RTL阈值仿真_2026-08-10.md` 全部步骤
> **前置**：S3 RTL 实验已完成（`results/sc01_rtl_v1_001/`）

---

## 0. 执行状态

| 步骤 | 内容 | 状态 |
|------|------|------|
| 1 | `p1_stage10_two_beat_ecc_v4_thresholded`（修正接线 bug 的 stage 10） | ✅ |
| 1' | `p1_ecc_stage4_v3_thresholded`（stages 1–7 注入版，接线本就正确） | ✅ |
| 2 | `top_p1_pfft_ecc_thresholded`（P1 thresholded 顶层） | ✅ |
| 3 | `sc01_p1_rtl_tb.sv`（P1 故障注入 testbench，3360 trials） | ✅ |
| 4 | 编译 + 仿真（iverilog -g2012） | ✅ |
| 5 | 结果分析 | 全量运行中 |
| 6 | τ=1 对比（可选） | 待定 |
| 7 | 输出 `sc01_p1_rtl_v1_001/` | 进行中 |

---

## 1. RTL 代码变更（未修改任何原版模块）

| 文件 | 新增内容 |
|------|---------|
| `common/rtl/p1_thresholded_stages.sv`（新建） | `p1_ecc_stage4_v3_thresholded`（stages 1–7 注入版 + 标志引出）、`p1_stage10_two_beat_ecc_v4_thresholded`（stage 10 修正版）、`p1_pfft_ecc_core_v4_thresholded` + `top_p1_pfft_ecc_thresholded`（P1 顶层） |

要点：
- **stages 1–7**：原版 `p1_ecc_stage4_v3` 的 boundary 例化接线正确（rotated→c 端口，
  received→r 端口），thresholded 版仅加注入 hook（received 路径 mux）并换成
  `arithmetic_boundary_from_clean_v5_thresholded`（同一接线语义）
- **stage 10**：原版内部例化 `independent_butterfly_ecc_v5`（boundary 端口反转的 S3 bug），
  thresholded 版换成 `independent_butterfly_ecc_v5_thresholded`，保持
  `TRIVIAL_UPPER(1), BYPASS_LOWER(1)`
- stage 8/9 保持 TMR 不变

---

## 2. 仿真结果

### 2.1 stage 10 独立验证（τ=0，420 trials）

```
SUMMARY threshold=0 total=420 corrected=420 detected_only=0 silent_bounded_residual=0 miscorrection=0 silent_unbounded=0
SUMMARY recovery_rate=100.00%
```

stage 10 的 pair_phase==1 注入时机正确，接线修正后 **420/420 corrected**。

### 2.2 全量（τ=0，3360 trials = stages 1–7 × 420 + stage 10 × 420）

（运行中，待填充）

| 范围 | 总 trials | corrected | detected-only | silent | miscorrection |
|------|-----------|-----------|---------------|--------|---------------|
| stages 1–7 | 2940 | ? | ? | ? | ? |
| stage 10 | 420 | 420 (100%) | 0 | 0 | 0 |
| **总计** | **3360** | **?** | **?** | **?** | **?** |

---

## 3. 与 S3 结果的对比（待全量完成后填充）

| 指标 | S3 (τ=0) | P1 (τ=0) |
|------|----------|----------|
| 总 trials | 3360 | 3360 |
| corrected | 3360 (100%) | ? |
| miscorrection | 0 | ? |
| silent | 0 | ? |

---

## 4. 意外与 QUESTION

- **QUESTION-P1-1**：`connectivity_spot_tb_v2.sv` 的 CASE_ID==3（P1）引用了旧版 P1 层次
  （`fault.u.s1.protected_butterfly`、`fault.u.pair`），与当前 P1 V3-001 RTL 不兼容，
  编译失败。**这是既有 TB 与当前 RTL 的失配**（非本次改动引起——本次只新增模块，
  未改 P1 原版 RTL）。P1 的资格验证需用更新的 TB（如 `pfft_project_tb_v3.svh`）。

---

## 5. 输出文件清单（待全量完成后补 SHA-256）

| 文件 | 说明 |
|------|------|
| `sc01_p1_rtl_tb.sv` | P1 故障注入 testbench |
| `sc01_p1_rtl_compile.sh` | 编译/仿真脚本 |
| `sc01_p1_rtl_run_s10_tau0.log` | stage 10 独立日志（420 trials） |
| `sc01_p1_rtl_run_full_tau0.log` | 全量日志（3360 trials） |
| `sc01_p1_rtl_results.json` | 结果汇总 |
| `sc01_p1_rtl_summary.md` | 本文件 |
| `sc01_p1_rtl_parse_results.py` | 日志解析脚本 |
| `output_hashes.txt` | SHA-256 清单 |

RTL 新增：`common/rtl/p1_thresholded_stages.sv`

---

*本文档由 Deepseek 执行会话编写。*
