# orbit_seu — 芯片在轨 SEU 效应估算报告

- 工具版本: orbit_seu v0.1.0
- 环境类型: demo_gcr  **⚠ SYNTHETIC-DEMO ENVIRONMENT — 非工程数据，禁止用于任务评估**

## 1. 轨道与磁场
- 轨道: 高度 550 km, 倾角 97.6°, 偏心率 0.001, 周期 95.65 min, 采样点 2304
- north dipole pole 80.59 deg, -72.68 deg lon (from g/h inputs)
- 垂直截止刚度 GV: min 0.00 / mean 4.74 / max 12.63
- McIlwain L: 1.09 ~ 3103.26

## 2. 器件
- Weibull LET: Lth=5.0 MeV*cm^2/mg, W=20.0, s=1.5, sigma_sat=1e-07 cm^2
- 规模: 55000000 bit

## 3. SEU 事件率
| 来源 | 事件率 (events/s/bit) | (events/day/bit) |
|---|---|---|
| 重离子 p | 0.000e+00 | 0.000e+00 |
| 重离子 He | 0.000e+00 | 0.000e+00 |
| 重离子 O | 0.000e+00 | 0.000e+00 |
| 重离子 Si | 1.084e-12 | 9.362e-08 |
| 重离子 Fe | 3.218e-11 | 2.781e-06 |
| **合计/bit** | **3.327e-11** | **2.874e-06** |
| 合计/器件 | 1.830e-03 | 1.581e+02 |

## 4. 任务期统计（泊松）
- 任务时长: 3.00 年
- 每 bit 期望事件数: 3.149e-03, P(≥1) = 3.144e-03
- 每器件期望事件数: 1.732e+05, P(≥1) = 1.000e+00, 即约每 0.01 天一次

## 5. 方法与局限

- Centered-dipole Størmer vertical cutoff (±20% vs multi-pole maps).
- First-order secular J2 propagation; no short-period terms.
- Effective-LET thin-slab rate approximation (CREME86-era); full IRPP, funneling and MBU sharing are not modelled.
- DEMO spectra are SYNTHETIC and must not be used for flight estimates; import SPENVIS/CREME96/AE9AP9 spectra for engineering work.
- Proton contribution requires a measured sigma(E) table.

## 6. 溯源
- config SHA-256: `ef05220bd9bd97712b8156f07698fa5ef9a945f511d6240a2abc08477ef77f73`
