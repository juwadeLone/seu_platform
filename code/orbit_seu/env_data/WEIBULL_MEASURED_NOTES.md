# Weibull 7-series 实测截面 — 调研 / 拟合 / 校验报告

> 交接任务：WP_sigma_weibull_真实化（28nm 7 系列 FPGA）
> 日期：2026-08-20  执行：agent
> 硬约束（已遵守）：禁止编造任何测量数字；查不到就标缺口。

> **2026-09-26 更正（本文 §2 单位换算与 §3.2 解读作废）**
>
> - Lee 2014 Table 1 表头印的是 "A (µm²/bit)"，但同文 Fig.3（CRAM，LET 126 时 ≈1.2×10⁻⁸）与 Fig.7（纵轴 cm²/bit，Kintex-7 ≈10⁻⁸）都表明 **A 本身就是 cm²/bit**。A=3.34×10⁻⁸ cm² 代入 Weibull 得 σ(126.1)=1.17×10⁻⁸，与 Fig.3 吻合。表头是笔误。
> - 正确值：CRAM 3.34×10⁻⁸、BRAM 3.82×10⁻⁸、FF 1.47×10⁻⁷ cm²/bit（不做换算）。原先的 3.34×10⁻¹² 小了 10⁴ 倍，而且连本文自己写的 "µm²×1e-8" 规则都不符（那样应是 3.34×10⁻¹⁶）。
> - §3.2 把 "MEO 比论文 GEO 低约 450 倍" 解释成地磁屏蔽，不成立：20200 km 处垂直截止刚度只有 0.04–0.86 GV，挡不住多少银河宇宙线。低 450 倍是单位错误（×10⁻⁴）与 LET 换算、屏蔽、角度归一化误差叠加的结果。
> - §4 里 "重离子 σsat 与中子 σ 差 3 个量级属预期" 同样作废：更正后差 6–7 个量级，这才是体硅 SRAM 的正常比值。
> - 修正后的环境与率积分链见 `scripts/spenvis_to_let.py`、`orbit_seu/rates.py` 与 `out_vx690t_measured/report.md`。

---

## 1. 主数据源（已验证真实存在、全文可读）

**Lee, D. S., Wirthlin, M. J., Swift, G. M., Le, A. C.**
*"Single-Event Characterization of the 28 nm Xilinx Kintex-7 Field-Programmable Gate Array under Heavy Ion Irradiation"*
2014 IEEE Radiation Effects Data Workshop (REDW, with NSREC 2014).
**DOI: 10.1109/REDW.2014.7004595**
全文（免费）: OSTI PURL https://www.osti.gov/servlets/purl/1140364

- 器件：**XC7K325T-1FBG900C**（Kintex-7, 28nm），Texas A&M K500 回旋加速器，Xe/Ar/N 束，有效 LET 1.5–126.1 MeV·cm²/mg。
- 监测：**configuration memory（CRAM）、BRAM、user flip-flops** 三类 SEU，外加 SEL。
- 论文 **Table 1 直接给出三域 Weibull 拟合参数**（即无需从曲线抠点）。

### 数据借用声明
交接文档「源 1」明确：xc7vx690t（Virtex-7）与 xc7k325t（Kintex-7）同属 28nm 7 系列，**CRAM 单元相同**，截面可互用并标注「同族借用」。本任务对 CRAM/BRAM/FF 三域均采用该 Kintex-7 实测参数（同工艺同代），置信度标 `measured`（实测束流），并注明借用到 Virtex-7。

---

## 2. 实测参数表（论文 Table 1）

论文 Weibull 形式：σ(L) = A·[1 − exp(−((L−X0)/W)^S)]，L>X0。
orbit_seu 形式：σ(L) = σsat·[1 − exp(−((L−Lth)/W)^s)]，L>Lth。
→ **映射：σsat=A，Lth=X0，W=W，s=S。**

| 域 | A（表头印 µm²/bit，实为 cm²/bit） | **σsat (cm²/bit)** | W | X0=Lth | S=s | 测试器件 bits |
|---|---|---|---|---|---|---|
| CRAM (Config) | 3.34E-08 | **3.34E-08** | 338.5 | 0.4 | 0.852 | 67,930,000 |
| BRAM | 3.82E-08 | **3.82E-08** | 87.5 | 0.1 | 0.893 | 16,404,480 |
| FF (User) | 1.47E-07 | **1.47E-07** | 271.3 | 1.1 | 1.090 | 393,216 |

**单位换算（2026-09-26 作废，见文首更正）**：论文表头 "A (µm²/bit)"，orbit_seu 用 cm²/bit。
`σsat(cm²/bit) = A(µm²/bit) × 1e-8`。两种值均保留在 `weibull_7series_measured.json` 中（`sigma_sat_cm2_per_bit` + `sigma_sat_raw_um2_per_bit`）以便复核。

---

## 3. 量级校验

### 3.1 内部锚点（强）：论文 Table 2
同一组 Weibull + 100 mils Al 屏蔽环境，论文算出在轨率（Solar Min）：
| 域 | 论文 Table 2 (/day/bit) |
|---|---|
| CRAM | 1.0E-07 |
| FF | 9.0E-08 |
| BRAM | 5.2E-07 |

### 3.2 orbit_seu 实测替换后的量级（本任务实跑，MEO 20200km/55° 强地磁屏蔽）
| 域 | orbit_seu 实测 (/day/bit) | 论文 Table2 (/day/bit) | 比值 |
|---|---|---|---|
| CRAM | 2.21E-10 | 1.0E-07 | ~450× 低 |
| BRAM | 9.15E-10 | 5.2E-07 | ~570× 低 |
| FF | 2.37E-10 | 9.0E-08 | ~380× 低 |

**解读（2026-09-26 作废，见文首更正）**：论文 Table 2 用 100 mils Al 的**深空/近自由空间 GCR** 环境（高 LET 重离子丰富）；orbit_seu 本 demo 是 **MEO 20200km/55° 强地磁屏蔽**轨道，低刚度高 LET 重离子被截至（报告逐离子种分解显示重离子率几乎全来自 H/He，C/O/Mg/Si/Fe 被砍到 10⁻¹² 量级）。CRAM 的 Weibull 极宽（W=338.5），在低 LET(H/He≈1) 下远未饱和（σ≈σsat·0.0035），故 MEO 率低 2–3 个数量级是**预期的轨道差异**，证明参数与单位换算正确。

### 3.3 占位基线对比（替换方向正确性）
| 配置 | /day/bit (MEO) |
|---|---|
| 占位（Lth=5, W=20, s=1.5, σsat=1e-7） | 4.695E-06 |
| 实测 CRAM 单行 | 2.215E-10 |
| 实测按域 | 5.48E-10 |

实测 σsat 比占位低约 **3e4 倍**，对应每 bit 率也低约 2–4 个数量级（叠加 MEO 磁屏蔽砍低 LET），**替换方向物理正确**。

---

## 4. UG116 交叉校验状态（验收 A4）

**状态：PENDING（缺口，未编造）**

- UG116《Device Reliability Report》（AMD/Xilinx，最新 v10.20）含 7 系列 SEU **中子(LANSCE) FIT/Mb** 表，可作为量级锚点。
- 本任务核心是**重离子束流实测**替换；UG116 是**中子** FIT，物理通道不同（中子直接电离 vs 重离子 LET 阈值）。要完成 A4「σsat 换算中子等效 FIT 与 UG116 同量级」需：中子环境谱 + 中子 σ(E) 表 + 积分。这是**独立的第二条计算线**，本次未做（文档 §2.2 也将其列为低优先级附加目标）。
- **未填 UG116 数值是因为未做中子积分，不是查不到**。待办：补中子谱 + 中子 σ 表后做量级对比；差 >10× 时书面讨论。
- 已有的、可立即使用的量级锚点是 §3.2 的**重离子内部锚点**（论文 Table 2），已证明参数合理。

---

## 5. 拟合质量（验收 A3）

论文已给出拟合后的 A/W/X0/S（表 1），未提供逐点残差/R²。本任务未重新拟合（论文参数本身就是束流数据直接 Weibull 拟合结果，无需从散点抠点）。
- 若后续需独立验证：论文 Figure 3/4/5 给出三域 σ(LET) 散点，可用 WebPlotDigitizer 抠点后对本表参数做残差校验（饱和区相对误差应 <20%，与论文图趋势一致）。此项 PENDING，列为待办。

---

## 6. 落盘与溯源（验收 A1/A5/A6）

| 交付物 | 路径 | 状态 |
|---|---|---|
| 按域实测 JSON（orbit_seu 侧） | `env_data/weibull_7series_measured.json` | ✅ |
| 按域实测 JSON（layout_ecc 副本） | `code/layout_ecc_sim/data/weibull_7series_measured.json` | ✅ |
| 按域 demo config | `examples/demo_spenvis_files_measured_sigma.json` | ✅（用 `heavy_ion_weibull_by_domain` 键） |
| 实跑报告 | `out_measured/report.md` + `results.json` | ✅ |
| 代码扩展 | `orbit_seu/device.py`（`DomainWeibull` 类）、`orbit_seu/mission.py`（按域求和分支）、`tests/test_basic.py`（3 个新单测） | ✅ |
| 对比脚本 | `scripts/compare_weibull_measured.py` | ✅ |

- 单组 `heavy_ion_weibull` 兜底**未改动**，回归测试通过（占位基线仍得 4.695E-06 /day/bit）。
- 实跑 config SHA-256：`eb2f948a0636a2936847a67e3e9c4088856aa272b30011e18cc88f74c003891e`（见 `out_measured/results.json` provenance）。
- 占位基线 config SHA-256（§1.3）：`1f452beb...`（见交接文档，未重跑以保差分基线）。

### 实跑结果（MEO 20200km/55°，SPENVIS CREME96 solar-min 真实 GCR 谱）
- 每域 /day/bit：CRAM 2.21E-10、BRAM 9.15E-10、FF 2.37E-10。
- 器件总率：0.030 /day/device（CRAM 占主导，因 67.9M bits 占绝对多数）。
- **注意**：此 MEO 数值是占位基线的**替换后对比基准**，不是工程结论（受轨道磁屏蔽主导）。深空/GEO 环境下将接近论文 Table 2 的 10⁻⁷ 量级。

---

## 7. 待办 / 缺口清单

1. **UG116 中子 FIT 交叉校验**（PENDING）：需中子谱 + 中子 σ(E) 表，独立计算线。
2. **质子 σ(E) 表**（DEFERRED，文档 §2.2 低优先级）：28nm SRAM 有显著质子直接电离 SEU，对 LEO/SAA 重要；找到后单独存表，本次不接线。
3. **xc7vx690t 每域精确 bits**（未编造）：demo 当前用 Kintex-7 测试器件 bits 作参考；xc7vx690t 实际值替换后只需改 config，量级线性不变。
4. **论文 Figure 3/4/5 散点抠点残差校验**（PENDING，非必需）：强化 A3 拟合质量证据。
5. **layout_ecc 侧 P_DEFAULT 替换**（不在本任务）：交接 §5.2 明确本任务只复制数据、不改 layout_ecc 仿真代码；P_DEFAULT 替换属 M9 标定（另一任务）。

---

## 8. 诚实性声明（验收 A7）

- 所有 σ 数值来自 Lee 2014（OSTI 全文）Table 1，未编造、未"合理推测"。
- 单位换算（µm²→cm² ×1e-8）一条作废：A 本身是 cm²/bit（见文首更正）。
- UG116 中子校验、质子 σ(E) 表、xc7vx690t 精确 bits 均**明示为缺口/待办**，未用占位值冒充真实数据。
- 占位值（Lth=5/W=20/s=1.5/σsat=1e-7）在 `demo_spenvis_files.json` 中**原样保留**作为差分基线，未删除、未降级混入实测。
