# N07-S3-TAU2-GAO2023-V1 审计

状态：`PASS / RTL_IVERLOG_ONLY / NOT_PAPER_700`  
日期：2026-08-13  
记录号：`N07-S3-TAU2-GAO2023-V1`

## 合同符合

| 判据 | 结果 |
|---|---|
| 六个 `SUMMARY threshold=2 total=560` | PASS |
| TRIAL 合计 3360 | PASS（6×560） |
| 四分类原样记录 | PASS：corrected=3168，silent_bounded=106，silent_unbounded=86，detected_only=0，miscorrection=0 |
| 未覆盖 `sc01_rtl_v1_001` 旧 τ=0/1 日志 | PASS |
| 未改 manuscript、未开 Vivado、未跑 Stage 9–10 | PASS |

仿真器：`/usr/bin/iverilog` + `/usr/bin/vvp`。DUT：`top_s3_subfft_ecc_thresholded.sv`。TB：`sc01_rtl_tb.sv`（`FRAME_BEATS=512`，`THRESHOLD=2`，Stage 1–8）。墙钟约 3414 s。

## 按符号

Gao 口径 = (corrected + silent_bounded) / 560。

| symbol | corrected | bounded | unbounded | Gao |
|---|---:|---:|---:|---:|
| 0 | 528 | 28 | 4 | 99.29% |
| 1 | 528 | 14 | 18 | 96.79% |
| 2 | 528 | 0 | 32 | 94.29% |
| 3 | 528 | 0 | 32 | 94.29% |
| 4 | 528 | 32 | 0 | 100.00% |
| 5 | 528 | 32 | 0 | 100.00% |
| **合计** | **3168** | **106** | **86** | **3274/3360 = 97.44%** |

每符号 corrected 恒为 528 = 560 − 32。32 = 8 级 × 2 分量 × bit{0,1}。bit≥2 的 3168 枪全部 `corrected`。

## silent 位点（192 = 106 + 86）

全部且仅 bit 0 与 bit 1（τ=2 吸收 \|sy\|∈{1,2}）。清单：`silent_sites.csv`。

| symbol | bounded | unbounded | 结构 |
|---|---:|---:|---|
| 0 | 28 | 4 | Stage 2 的 4 个 LSB 为 unbounded；其余 7 级 LSB 为 bounded |
| 1 | 14 | 18 | Stage 2 全 4 LSB unbounded；其余 7 级 real LSB unbounded、imag LSB bounded |
| 2, 3 | 0 | 32 | 8 级全部 LSB unbounded |
| 4, 5 | 32 | 0 | 8 级全部 LSB bounded |

Stage 2 对功能符号 0–3 的 LSB 一律 unbounded。校验符号 4–5 的 LSB 一律 bounded。

## 不得外推

- 3360 ≠ 论文 700 分母；不得改写 94.4% = 661/700。
- 本 DUT 是 thresholded S3 iverilog 副本，不是 `K_S3` 源 RTL；不是 D159 的 5040 枪。
- τ=2 标定集有虚警（M=3）；本战役每枪均有注入，`miscorrection=0` 不证明无故障帧无虚警。
- Yosys/Vivado 数字未测。

## SHA-256（审计落盘时）

见同目录 `sha256sums.txt`。`combined_summary.txt` 在审计时去掉了 runner 在 `ALL_DONE` 后追加的无前缀重复 SUMMARY；六段带 `symbol=` 前缀的 SUMMARY 与各 `run_symN.log` 一致。
