# orbit_seu — 芯片在轨 SEU 效应估算报告

- 工具版本: orbit_seu v0.1.0
- 环境类型: files  Environment: imported files (see provenance).

## 1. 轨道与磁场
- 轨道: 高度 20200 km, 倾角 55.0°, 偏心率 0.001, 周期 718.70 min, 采样点 2304
- north dipole pole 80.59 deg, -72.68 deg lon (from g/h inputs)
- 垂直截止刚度 GV: min 0.04 / mean 0.44 / max 0.86
- McIlwain L: 4.16 ~ 19.95

## 2. 粒子环境强度（全向积分通量）

| 离子组 | 通量 /cm²/s | LET≥1 /cm²/s | LET≥10 /cm²/s | 最大 LET |
|---|---:|---:|---:|---:|
| H | 4.185e+00 | 0.000e+00 | 0.000e+00 | 0.3 |
| He | 4.032e-01 | 0.000e+00 | 0.000e+00 | 0.9 |
| Z03-10 | 3.113e-02 | 9.890e-05 | 0.000e+00 | 9.5 |
| Z11-20 | 5.302e-03 | 3.136e-04 | 1.500e-06 | 22.1 |
| Z21-28 | 1.775e-03 | 1.561e-03 | 7.936e-06 | 32.1 |
| Z29-92 | 7.679e-07 | 7.679e-07 | 2.752e-07 | 112.4 |

## 3. 器件
- DomainWeibull [CRAM: Weibull LET: Lth=0.4 MeV*cm^2/mg, W=338.5, s=0.852, sigma_sat=3.34e-08 cm^2 bits=229878496 | BRAM: Weibull LET: Lth=0.1 MeV*cm^2/mg, W=87.5, s=0.893, sigma_sat=3.82e-08 cm^2 bits=54190080 | FF: Weibull LET: Lth=1.1 MeV*cm^2/mg, W=271.3, s=1.09, sigma_sat=1.47e-07 cm^2 bits=866400]
- 规模: 284934976 bit

## 4. SEU 事件率

器件次数 = Σ_d bits_d × (events/day/bit)_d，不用顶层占位 bits 去除。

| 域 | bits | events/day/bit | events/day | events/s |
|---|---:|---:|---:|---:|
| CRAM | 229,878,496 | 9.037e-08 | 2.077e+01 | 2.405e-04 |
| BRAM | 54,190,080 | 4.668e-07 | 2.530e+01 | 2.928e-04 |
| FF | 866,400 | 1.009e-07 | 8.742e-02 | 1.012e-06 |
| **合计/器件** | **284,934,976** | **1.620e-07** (bit 加权均) | **4.616e+01** | **5.343e-04** |

### 4.0 分离子组贡献（整片 events/day）

| 离子组 | events/day | 占比 |
|---|---:|---:|
| H | 6.449e-01 | 1.4% |
| He | 2.919e+00 | 6.3% |
| Z03-10 | 1.268e+01 | 27.5% |
| Z11-20 | 1.362e+01 | 29.5% |
| Z21-28 | 1.626e+01 | 35.2% |
| Z29-92 | 2.904e-02 | 0.1% |

### 4.1 与 Lee DUT bits 线性对照
- DUT: XC7K325T-1FBG900C；Lee, Wirthlin, Swift, Le, 2014 IEEE REDW Table 1 tested-device bits (DOI 10.1109/REDW.2014.7004595)

| 域 | DUT bits | DUT /day | 本器件 bits | 本器件 /day | bits 比 |
|---|---:|---:|---:|---:|---:|
| CRAM | 67,930,000 | 6.139e+00 | 229,878,496 | 2.077e+01 | 3.3840 |
| BRAM | 16,404,480 | 7.658e+00 | 54,190,080 | 2.530e+01 | 3.3034 |
| FF | 393,216 | 3.968e-02 | 866,400 | 8.742e-02 | 2.2034 |
| **合计** | | **1.384e+01** | | **4.616e+01** | **3.3360** |

同一组 Weibull 与同一条谱下，器件次数只随 bits 线性变。

### 4.2 与文献在轨率对照（每 bit）
- 参照：Lee, Wirthlin, Swift, Le 2014 REDW Table 2: GEO, solar minimum, 100 mils Al (same Weibull parameters)

| 域 | 本次 /day/bit | 参照 /day/bit | 本次/参照 |
|---|---:|---:|---:|
| CRAM | 9.037e-08 | 1.00e-07 | 0.90 |
| BRAM | 4.668e-07 | 5.20e-07 | 0.90 |
| FF | 1.009e-07 | 9.00e-08 | 1.12 |

Lee 的参照是 GEO（几乎没有地磁屏蔽）；本次是 MEO 20200 km / 55°，截止刚度 0.04–0.86 GV，预期与 GEO 同量级、略低。两者都是 GCR 太阳极小 + 100 mil Al。

## 5. 任务期统计（泊松）
- 任务时长: 1.00 年
- 每 bit 期望事件数: 5.917e-05, P(≥1) = 5.917e-05
- 每器件期望事件数: 1.686e+04, P(≥1) = 1.000e+00, 即约每 31.2 分钟一次

## 6. 方法与局限

- Centered-dipole Størmer vertical cutoff (±20% vs multi-pole maps).
- First-order secular J2 propagation; no short-period terms.
- Effective-LET thin-slab rate approximation (CREME86-era): R = (φ_omni/2)·<σ(L/cosθ)>, θ over 0–90° with the crossing-angle density 2cosθ·sinθ; full IRPP, funneling and MBU sharing are not modelled.
- Environment read from user files; verify orbit/shielding matching.
- LET files (spenvis_let): SPENVIS spectra for 20200.0 km / 55.0°, shield 100.0 mil Al (CSDA, no nuclear fragmentation); LET model: Bethe-Bloch in Si, Barkas effective charge, Sternheimer density effect; no shell/Bloch corrections. Status: interim; replace with SPENVIS CREME96 shielded LET spectrum (TRANS+LETSPEC) when exported.
- Environment is GCR only (solar minimum): solar particle events (CREME96 worst week/day/5-min) and trapped protons are not included.
- Proton contribution requires a measured sigma(E) table.
- 未计入 DSP（DS180 DSP slices = 3600）: Lee 2014 REDW Table 1 has no DSP heavy-ion Weibull; DSP is not included in N_SEU.

## 7. 溯源
- config SHA-256: `561bcc5a544f07ed620fc8143b822e178d22f287f4da75228409a861880df8a3`
- `env_data/spenvis_let/spenvis_H.let.txt` SHA-256: `95e4f7fa30b90aefea6ace6b08dd6e0a75d8c61152eb2c016dc235fe5b0205e0`
- `env_data/spenvis_let/spenvis_He.let.txt` SHA-256: `98b8888defa2ac5d3facd8d66ac9410c20a69821dd766c62123d44dbc215d2d0`
- `env_data/spenvis_let/spenvis_Z03-10.let.txt` SHA-256: `f190f844ac32c408b61fdfc009ab39146cb4b5df964335c2158bfe231afe06cd`
- `env_data/spenvis_let/spenvis_Z11-20.let.txt` SHA-256: `bb0f3a1d3fa722d49157d78f48f1e1ae783752f300ff3fdba60a81d032149325`
- `env_data/spenvis_let/spenvis_Z21-28.let.txt` SHA-256: `cf688b76dab6c7a46f63a83b49acd1b748a176b1ac8cb06e5b8601baf02ce1e8`
- `env_data/spenvis_let/spenvis_Z29-92.let.txt` SHA-256: `207efb15478ad70cacd119276b2807fb857f95adf63518c7c77c5c604ed9cf59`
