# N07-P1-GAO2023-V1 审计

状态：`PASS / RTL_IVERLOG_ONLY / NOT_PAPER_700`  
日期：2026-08-14  
记录号：`N07-P1-GAO2023-V1`

## 合同符合

| 判据 | 结果 |
|---|---|
| 六个 `SUMMARY threshold=3 total=560` | PASS |
| TRIAL 合计 3360 | PASS（6×560） |
| 四分类原样记录 | PASS：corrected=3168，silent_bounded=64，silent_unbounded=128，detected_only=0，miscorrection=0 |
| 未覆盖 `sc01_p1_rtl_v1_001` | PASS |
| 未改 manuscript、未开 Vivado、未跑 TMR 8–9 | PASS |

仿真器：`/usr/bin/iverilog` + `/usr/bin/vvp` 11.0。DUT：`top_p1_pfft_ecc_thresholded`。TB：本目录 `sc01_p1_rtl_tb.sv`（`FRAME_BEATS=512`，`THRESHOLD=3`，Stage 1–7+10）。有效仿真墙钟约 36 min（symbol 0 于 2026-08-13 20:06–20:13；symbol 1–5 于 2026-08-14 09:05–09:35 续跑）。

## 按符号

Gao 口径 = (corrected + silent_bounded) / 560。

| symbol | corrected | bounded | unbounded | Gao |
|---|---:|---:|---:|---:|
| 0 | 528 | 0 | 32 | 94.29% |
| 1 | 528 | 0 | 32 | 94.29% |
| 2 | 528 | 0 | 32 | 94.29% |
| 3 | 528 | 0 | 32 | 94.29% |
| 4 | 528 | 32 | 0 | 100.00% |
| 5 | 528 | 32 | 0 | 100.00% |
| **合计** | **3168** | **64** | **128** | **3232/3360 = 96.19%** |

每符号 corrected 恒为 528 = 560 − 32。32 = 8 级 × 2 分量 × bit{0,1}。bit≥2 的 3168 枪全部 `corrected`。

## silent 位点（192 = 64 + 128）

全部且仅 bit 0 与 bit 1（各 96；τ=3 吸收 \|sy\|∈{1,2}）。清单：`silent_sites.csv`。8 个 ECC 级各 24 枪 silent；real/imag 各 96。

| symbol | bounded | unbounded | 结构 |
|---|---:|---:|---|
| 0–3 | 0 | 32 | 8 级全部 LSB unbounded |
| 4–5 | 32 | 0 | 8 级全部 LSB bounded |

功能符号 0–3 的 LSB 一律 unbounded；校验符号 4–5 的 LSB 一律 bounded。无 S3 那种 Stage 2 混杂。

## 不得外推

- 3360 ≠ 论文 700 分母；不得改写 94.4% = 661/700。
- 本 DUT 是 thresholded P1 iverilog 副本，不是 `K_P1` 源 RTL，也不是现网 THRESHOLD=8。
- τ=3 标定集有虚警（1.15%）；本战役每枪均有注入，`miscorrection=0` 不证明无故障帧无虚警。
- Yosys/Vivado 数字未测。

## SHA-256（审计落盘时）

见同目录 `sha256sums.txt`。`combined_summary.txt` 在审计时去掉了 runner 在 `ALL_DONE` 后追加的无前缀重复 SUMMARY；六段带 `symbol=` 前缀的 SUMMARY 与各 `run_symN.log` 一致。
