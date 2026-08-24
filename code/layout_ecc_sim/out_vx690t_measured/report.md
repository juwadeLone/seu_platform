# orbit_seu — 芯片在轨 SEU 效应估算报告

- 工具版本: orbit_seu v0.1.0
- 环境类型: files  Environment: imported files (see provenance).

## 1. 轨道与磁场

- 轨道: 高度 20200 km, 倾角 55.0°, 偏心率 0.001, 周期 718.70 min, 采样点 2304
- north dipole pole 80.59 deg, -72.68 deg lon (from g/h inputs)
- 垂直截止刚度 GV: min 0.04 / mean 0.44 / max 0.86
- McIlwain L: 4.16 ~ 19.95

## 2. 器件

- DomainWeibull [CRAM: Weibull LET: Lth=0.4 MeV*cm^2/mg, W=338.5, s=0.852, sigma_sat=3.34e-12 cm^2 bits=229878496 | BRAM: Weibull LET: Lth=0.1 MeV*cm^2/mg, W=87.5, s=0.893, sigma_sat=3.82e-12 cm^2 bits=54190080 | FF: Weibull LET: Lth=1.1 MeV*cm^2/mg, W=271.3, s=1.09, sigma_sat=1.47e-11 cm^2 bits=866400]
- 规模: 284934976 bit



## 3. SEU 事件率

器件次数 = Σ_d bits_d × (events/day/bit)_d，不用顶层占位 bits 去除。


| 域         | bits            | events/day/bit          | events/day    | events/s      |
| --------- | --------------- | ----------------------- | ------------- | ------------- |
| CRAM      | 229,878,496     | 2.215e-10               | 5.091e-02     | 5.892e-07     |
| BRAM      | 54,190,080      | 9.155e-10               | 4.961e-02     | 5.742e-07     |
| FF        | 866,400         | 2.372e-10               | 2.055e-04     | 2.378e-09     |
| **合计/器件** | **284,934,976** | **3.535e-10** (bit 加权均) | **1.007e-01** | **1.166e-06** |




### 3.1 与 Lee DUT bits 线性对照

- DUT: XC7K325T-1FBG900C；Lee, Wirthlin, Swift, Le, 2014 IEEE REDW Table 1 tested-device bits (DOI 10.1109/REDW.2014.7004595)


| 域      | DUT bits   | DUT /day      | 本器件 bits    | 本器件 /day      | bits 比     |
| ------ | ---------- | ------------- | ----------- | ------------- | ---------- |
| CRAM   | 67,930,000 | 1.504e-02     | 229,878,496 | 5.091e-02     | 3.3840     |
| BRAM   | 16,404,480 | 1.502e-02     | 54,190,080  | 4.961e-02     | 3.3034     |
| FF     | 393,216    | 9.326e-05     | 866,400     | 2.055e-04     | 2.2034     |
| **合计** |            | **3.015e-02** |             | **1.007e-01** | **3.3402** |


同一组 Weibull 与同一条 MEO 谱下，器件次数只随 bits 线性变；DUT 合计修单位后应回到 NOTES 的 ~0.030 /day，而不是 2605 /day。

## 4. 任务期统计（泊松）

- 任务时长: 1.00 年
- 每 bit 期望事件数: 1.291e-07, P(≥1) = 1.291e-07
- 每器件期望事件数: 3.679e+01, P(≥1) = 1.000e+00, 即约每 9.93 天一次



## 5. 方法与局限

- Centered-dipole Størmer vertical cutoff (±20% vs multi-pole maps).
- First-order secular J2 propagation; no short-period terms.
- Effective-LET thin-slab rate approximation (CREME86-era); full IRPP, funneling and MBU sharing are not modelled.
- Environment read from user files; verify orbit/shielding matching.
- Proton contribution requires a measured sigma(E) table.
- 未计入 DSP（DS180 DSP slices = 3600）: Lee 2014 REDW Table 1 has no DSP heavy-ion Weibull; DSP is not included in N_SEU.



## 6. 溯源

- config SHA-256: `84b5c78e69fa589814a6cb1d871ad609b35c7061c99c396dc258d36e789318c0`
- `env_data/spenvis_let/spenvis_H.let.txt` SHA-256: `fcf343422022caa200736dfdc105b22bd80cb2377f6b9be883198f64c3698e19`
- `env_data/spenvis_let/spenvis_He.let.txt` SHA-256: `216c04ab20cd93459e3c548f6347ed53c18a8576b9e53dab9caaaa25b86d0c67`
- `env_data/spenvis_let/spenvis_C.let.txt` SHA-256: `c4c2478dfe2bf91aba3f42e8142daecee8c65fb9b06b67c767c1430106a8c54c`
- `env_data/spenvis_let/spenvis_O.let.txt` SHA-256: `8aaf67dce163a3a71b857417d535f3b81c15bc3fe9335d348aad852fffd2408e`
- `env_data/spenvis_let/spenvis_Mg.let.txt` SHA-256: `d0b7473d1baf65e326ad294b6ceb89c42d8be6ecce66608472ae4ee9ded19995`
- `env_data/spenvis_let/spenvis_Si.let.txt` SHA-256: `201571543af6057cba30549b19ea3320b9a7077d13aefa5cfdc822a84445abe5`
- `env_data/spenvis_let/spenvis_Fe.let.txt` SHA-256: `811c1109fa1ae3dc6257c07b47067aa9d1b2e745b0fc80b73d6efd4fa3e780b4`

