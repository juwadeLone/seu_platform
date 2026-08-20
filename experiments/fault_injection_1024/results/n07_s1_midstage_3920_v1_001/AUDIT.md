# N07-S1-MIDSTAGE-3920-V1 审计

状态：`PASS / RTL_IVERLOG_ONLY / NOT_PAPER_700`  
日期：2026-08-14  
记录号：`N07-S1-MIDSTAGE-3920-V1`

## 合同符合

| 判据 | 结果 |
|---|---|
| 八个 `SUMMARY threshold=5 total=490` | PASS |
| TRIAL 合计 3920 | PASS（8×490） |
| 四分类原样记录 | PASS：corrected=3534，bounded=292，unbounded=86，MISCORRECTION=8，detected_only=0 |
| 未覆盖 `n07_s1_gao2023_v1_001` | PASS |
| 未改 manuscript、未开 Vivado、未注 TMR 9–10 | PASS |

仿真器：iverilog/vvp 11.0。DUT：`top_s1_midstage_thresholded`。τ=5。墙钟约 27 min（10:31–10:57）。

## 按级 Gao 口径

| stage | corrected | bounded | unbounded | miscorr | Gao |
|---|---:|---:|---:|---:|---:|
| 1–4 | 448×4 | 42×4 | 0 | 0 | 100.00% |
| 5 | 434 | 40 | 16 | 0 | 96.73% |
| 6 | 426 | 29 | 27 | **8** | **92.86%** |
| 7 | 434 | 31 | 25 | 0 | 94.90% |
| 8 | 448 | 24 | 18 | 0 | 96.33%（与旧 490 一致） |
| **合计** | **3534** | **292** | **86** | **8** | **3826/3920 = 97.60%** |

## MISCORRECTION（8 枪）

全部：`stage=6`，`bit=4`，路径 ∈ {2,4,5,6}，real 与 imag 各 4。  
路径 0/1/3（校验路径）在同一条件无 miscorrection。

## 不得外推

- 3920 ≠ 论文 700。
- 整体 Gao 高于边界 96.33% **不** 否定 Stage 6 误纠正；排雷结论成立。
- 不是 K_S1 源 RTL / 现网 τ=16。

## SHA-256

见同目录 `sha256sums.txt`。
