# 收窄说明：先把整片芯片的 SEU 次数算准

> 日期：2026-08-20  
> 范围：layout_ecc 侧只交代口径，**不改**仿真代码。  
> 次数以本目录旁的 `out_vx690t_measured/report.md` 为准，不以功能损伤链为准。

> **2026-09-26 更正：旧的 0.1007 次/天作废，现行值为 46.2 次/天。** 原链路有五处误差，互相抵消了一部分：
>
> 1. Lee Table 1 的 A 实为 cm²/bit（表头 µm² 是笔误，同文 Fig.3/Fig.7 为证），旧 σ 小了 10⁴ 倍；
> 2. LET 用 K·Z²/β²，没有布拉格峰（Fe 最高到 527，实际约 29），现改 Bethe-Bloch + 有效电荷；
> 3. SPENVIS 能谱是舱外未屏蔽谱，现按 CREME96 / Lee 惯例过 100 mil Al 球壳屏蔽；
> 4. 入射角权重归一到 1，薄板全向通量应为 φ/2，现已改正并积到 90°；
> 5. 只用了 7 种离子，现用 SPENVIS 文件里的全部 92 种（分 6 组）。
>
> 更正后每 bit 率为 Lee Table 2（GEO、太阳极小、100 mil Al）的 0.90 / 0.90 / 1.12 倍（CRAM/BRAM/FF），MEO 略低于 GEO 符合预期。

---

## 1. 目标已收窄

要的量只有 `orbit_seu` 这条线：整片 **bit 翻转次数**（CREME96 标准产出），不是打中芯片的离子个数，也不是功能损伤。

\[
N_{\mathrm{SEU}}(T)=\sum_d N_{\mathrm{bits},d}\;\frac{1}{2}\int \Phi_{\mathrm{omni}}(L)\,\big\langle\sigma_d(L/\cos\theta)\big\rangle\,\mathrm{d}L\cdot T
\]

\(\Phi_{\mathrm{omni}}\) 是全向（4π）微分 LET 通量，1/2 是全向通量穿过薄板的几何因子，⟨·⟩ 按穿越角密度 \(2\cos\theta\sin\theta\) 在 0–90° 上平均（有效 LET 近似，不是完整 IRPP）。一次 MCU 会计入 \(k\) 次翻转。当前 σ 是 per-bit，这样定义是对的。

器件：XC7VX690T。轨道：MEO 20200 km / 55°。环境：SPENVIS CREME96 太阳极小 GCR 能谱（H–U 全 92 种）→ 100 mil Al 球壳 CSDA 屏蔽 → Bethe LET（过渡路径，待 SPENVIS 直接导出带屏蔽的 LET 谱替换）。σ：Lee 2014 REDW Table 1，A 取 cm²/bit（Kintex-7 同族借用到 7 系列）。

## 2. 功能损伤链全部停

下列 layout_ecc 内容与整片次数无关，本阶段全部停，**不要接着改**：

- `P_DEFAULT`、CORRECTED / DUE、码字、η、L3
- WP2–WP7、功能分类
- `layout_ecc/domains.py`
- 任何 WP 仿真代码

`data/weibull_7series_measured.json` 副本可以留着给以后 M9 标定用；现在不要拿它去替换 `P_DEFAULT`。

## 3. 本文件夹里的次数产物

均在 `code/layout_ecc_sim/` 下（本仓库交付口径）：

| 文件 | 作用 |
|---|---|
| `out_vx690t_measured/report.md` | **现行次数表**（2026-09-26 更正后：46.2 次/天） |
| `out_vx690t_measured/results.json` | 同一次运行的完整 JSON |
| `data/xc7vx690t_measured_meo.json` | 实测 Weibull + DS180/UG470 官方 bits |
| `docs/SEU次数收窄_以orbit_seu为准.md` | 本页：目标收窄、功能链停 |

计算工具仍在 `C:\Users\zhuao\tcas\code\orbit_seu`；复跑命令：

```
python -m orbit_seu examples/xc7vx690t_measured_meo.json -o out_vx690t_measured/
```

然后把 `report.md` / `results.json` 再拷回本目录，并同步 `desktop/orbit_env.py` 的 `_frozen_baseline` 与 `data/effects_coverage.json`（`tests/test_orbit_frozen_consistency.py` 会检查三者一致）。LET 谱由 `python scripts/spenvis_to_let.py` 从 `env_data/spenvis_gcf.txt` 生成，参数写在 `env_data/spenvis_let/manifest.json`。`demo_spenvis_files.json` 是合成 σ 差分基线，不删、不当结论。旧 `out_measured/report.md`（`/day` 写成 `/s`、55 Mbit 去除）作废。

官方 bits（不许编造）：

- CRAM 229,878,496：UG470 Table 1-1，7VX690T Configuration Bitstream Length。DS180/UG470 没有另给 FAR 可寻址 CRAM 单元数，用厂商配置规模。
- BRAM 54,190,080：DS180 XC7VX690T Total Block RAM 52,920 Kb × 1024。与 Lee 2014 XC7K325T 16,020 Kb × 1024 = 16,404,480 同一换算。
- FF 866,400：UG474 Table 3 / DS180，7VX690T Flip-Flops。
- DSP：DS180 有 3,600 slices，Lee 无截面，**不计入**，报告里写明缺口。

## 4. 明确缺口（这一步只声明不补）

- 质子 σ(E) 未计入。这条 MEO GCR 重离子线可以先出数；换 LEO 后质子会变成主项。
- 中子 / UG116 是地面/大气锚点，不是 20200 km 重离子次数的输入。
- 轨道已锁死。现有 LET 文件带着 20200 km / 55° 的磁屏蔽；换轨道必须在 SPENVIS 重跑。`orbit_seu.mission` 读 manifest，轨道不符直接报错。
- 只有 GCR 太阳极小背景。太阳粒子事件（CREME96 最恶劣一周/一天/5 分钟）没算；MEO 几乎没有地磁屏蔽，峰值事件率会高几个数量级。
- 屏蔽按 100 mil Al 假设，不是整星/板卡的扇区分析。
- LET 与屏蔽输运是过渡实现（Bethe + CSDA，无碎裂）；标准路径是 SPENVIS CREME96 TRANS+LETSPEC 直接给出的带屏蔽 LET 谱。
- 不是飞行鉴定值。单位和 bits 不再是错的；质子、DSP、bitstream≠FAR 单元这些边界仍在。

## 5. layout_ecc 仓库里不要动什么

不改 `domains.py`，不改 WP 代码，不把占位 `P_DEFAULT` 当成 SEU 次数。需要引用整片次数时，打开 `out_vx690t_measured/report.md`。
