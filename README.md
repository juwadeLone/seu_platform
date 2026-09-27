# seu_platform · FPGA 在轨辐射效应仿真平台

<p align="center">
  <img src="docs/media/orbit.webp" width="760" alt="轨道页实跑画面：辐射带、SAA、宇宙线、磁力线，卫星沿 MEO 轨道运行并闪出 SEU">
</p>
<p align="center"><sub>平台实跑画面 · MEO 20200 km / 55° · 内带质子、外带电子、SAA、宇宙线、磁力线 · 轨道颜色 = 地磁截止刚度 · 卫星上的闪点按算出的翻转率抽样</sub></p>

从**轨道辐射环境**算到**芯片每天翻几位**，再看**一颗离子打中之后**，芯片、模块和 SAR 出图各发生了什么。
环境谱、截面、位数都来自标准模型或实测数据；没有数据的效应标成「缺数据」，不编数字。

当前器件：Xilinx Virtex-7 **XC7VX690T**（28 nm）。示例设计：一个 1024 点流水线 FFT 的 Vivado 布局。平台按层次名自动划分模块，换成别的设计同样适用。

> **English.** An open simulation platform for space-radiation effects on an SRAM FPGA (Xilinx XC7VX690T). It goes from the orbit radiation environment (SPENVIS/CREME96 spectra, Bethe LET, 100 mil Al shielding) to per-bit upset rates (46.2 upsets/day for the whole chip in MEO; per-bit rates within 10% of the Lee et al. 2014 reference), then to where a single ion lands on a real Vivado layout and what that does to an on-board SAR image. The UI is in Chinese; every screen below is a real platform run.

---

## 一条链，五个画面

| 星载 SAR：从照射到出图 | 一颗离子打在真实布局上 |
|---|---|
| <img src="docs/media/sar.gif" width="100%" alt="SAR 页动图"> | <img src="docs/media/strike.gif" width="100%" alt="打击页动图"> |
| 3D 侧视几何 + 单机时间线（往返 6.3 ms、距离向压缩 262 µs……），逐级显示每台单机的外形 | 入射 → 电荷收集 → 4 位翻转（MCU）→ 后果与 SEL 风险 → 配置刷新恢复；每次打击按 SEU / MCU / SET / SEFI / SEL 分类 |

<p align="center"><img src="docs/media/sar_seu.jpg" width="880" alt="SAR 页：距离向 FFT 翻转前后的出图对比"></p>
<p align="center"><sub>一次 SEU 打在距离向 FFT（s1–s5）：右上是无故障出图，右下是翻转之后，点目标沿距离向被拉成横条</sub></p>

| 效应总览 | 器件内部 |
|---|---|
| <img src="docs/media/effects.png" width="100%" alt="效应总览页"> | <img src="docs/media/device.png" width="100%" alt="器件内部页"> |
| 整片 46.2 次/天，以及 CRAM / BRAM / FF 分项；每种效应标「在算 / 缺数据 / 范围外」 | 存储单元为什么会翻：收集电荷 1.4 × Qcrit 越过阈值，再生环锁到另一边 |

---

## 对谁有用

| 谁 | 能拿它做什么 |
|---|---|
| 做在轨处理载荷的 FPGA 工程师（SAR 成像、在轨 AI、计算星座） | 看自己的设计在这条轨道上每天翻几次、落在哪个模块、对出图有什么影响，据此决定哪一级加 TMR / ECC、刷新多快 |
| 可靠性与任务建模研究者 | 拿到有物理出处的故障率和后果参数，代替任务模型里常见的示意值 |
| 方案论证、抗辐射保证阶段的工程师 | 束流试验前先估量级，用画面向评审解释为什么要刷新、要加固 |
| 教学与科普 | 空间辐射 → 器件 → 电路 → 图像，一条链看完 |
| 航空、汽车、数据中心的软错误分析 | 「翻转 → 模块 → 功能后果」这一层可以复用，前端换成中子谱即可 |

它**不能替代**束流试验和鉴定。低轨以质子为主的场景和太阳粒子事件目前还缺数据，见下文「还没做的」。

---

## 当前结果

MEO 20200 km / 55°，银河宇宙线（GCR）太阳极小，100 mil Al 屏蔽：

| 域 | 每 bit 每天 | 整片每天 | 与 Lee 2014 表 2（GEO）之比 |
|---|---:|---:|---:|
| CRAM（配置存储） | 9.04×10⁻⁸ | 20.8 | 0.90 |
| BRAM | 4.67×10⁻⁷ | 25.3 | 0.90 |
| FF | 1.01×10⁻⁷ | 0.09 | 1.12 |
| **整片** | | **46.2 次/天** | 约每 31 分钟一次 |

交叉验证：同一组截面在 Lee 等人用 CREME96 算的 GEO 太阳极小环境下给出 1.0 / 5.2 / 0.9 ×10⁻⁷，本平台的 MEO 结果与之相差 10% 以内（MEO 地磁屏蔽弱，应与 GEO 同量级、略低）。

**不含**：太阳粒子事件、束缚质子、DSP。这些缺数据，不等于零。

---

## 计算链与依据

| 环节 | 做法 | 依据 |
|---|---|---|
| GCR 能谱 | CREME96 太阳极小，Z = 1–92，含该轨道地磁屏蔽 | SPENVIS 4.6（20200 km / 55°） |
| 屏蔽 | 100 mil Al 球壳，连续慢化输运 | CREME96 / Lee 2014 的参考屏蔽 |
| LET | Bethe-Bloch + Barkas 有效电荷 + Sternheimer 密度修正 | 与 NIST PSTAR 差 1.3%；Fe 峰值 29 MeV·cm²/mg |
| 截面 σ(LET) | CRAM / BRAM / FF 三域 Weibull | Lee, Wirthlin, Swift, Le, IEEE REDW 2014 表 1（A 为 cm²/bit） |
| 位数 | CRAM 229,878,496 · BRAM 54,190,080 · FF 866,400 | AMD UG470 / DS180 / UG474 |
| 事件率 | 有效 LET 薄板近似 R = (φ/2)·⟨σ(L/cosθ)⟩ | CREME86 传统方法 |
| 任务统计 | 泊松：P(≥1) = 1 − e^(−RT) | |
| 截止刚度 | IGRF-13 2020 偶极 Størmer 式 | |
| 多位比例、SEL 起始 LET 15 | 用于打击页分类 | Lee 2014 表 3、§IV.C |

## 还没做的

- 太阳粒子事件最恶劣情况（CREME96 最恶劣一周 / 一天 / 5 分钟）
- 束缚质子（AP8/AP9）与质子 σ(E)；DSP、SEFI、SEL 截面；总剂量（SHIELDOSE）
- 完整 IRPP（目前是有效 LET 近似）；屏蔽输运目前是平台内过渡实现，标准做法是 SPENVIS 直接导出带屏蔽的 LET 谱
- 现有能谱只对 20200 km / 55° 有效，换轨道要在 SPENVIS 重跑（平台会拒绝不匹配的轨道）

---

## 运行

需要 Python 3.10+（只用标准库；原生窗口另需 `pywebview`），以及轨道计算包 **orbit_seu**（在 [juwadeLone/tcas](https://github.com/juwadeLone/tcas) 的 `code/orbit_seu`）。

```bash
set ORBIT_SEU_ROOT=<tcas 仓库>\code\orbit_seu
cd code/layout_ecc_sim
python -m unittest discover -s tests
python desktop/app.py --server-only
```

最后一条会打印本地端口，用浏览器打开即可看到全部五个页面：`/` 打击 · `/orbit` 轨道 · `/sar` SAR · `/effects` 效应 · `/seu` 器件内部。去掉 `--server-only` 则打开原生窗口。

复算整片翻转次数：

```bash
cd <tcas 仓库>/code/orbit_seu
python scripts/spenvis_to_let.py
python -m orbit_seu examples/xc7vx690t_measured_meo.json -o out_vx690t_measured/
```

`dist/` 与 `release/` 里的 exe 是旧版本，不含 v1.2.0 的更正，请从源码运行。

## 目录

```
code/layout_ecc_sim/
  layout_ecc/          打击模型、效应分类、布局导入、Web 服务
  layout_ecc/webapp/   五个页面
  desktop/             桌面入口（pywebview）与 orbit_seu 接入
  data/                布局、截面、位数、效应表等证据文件
  out_vx690t_measured/ 现行翻转次数报告
  tests/               单元测试
experiments/fault_injection_1024/   冻结的 FFT 位级故障注入实验包
docs/media/                         README 里的实跑画面（无头浏览器逐帧截取）
```

## 版本

**v1.2.0（2026-09）**：更正整片翻转次数（0.1007 → 46.2 次/天：Lee 2014 表头单位笔误、LET 换算、屏蔽、角度归一化、离子种类五处）；重做五个页面。

地表贴图：NASA Blue Marble（公有领域）。引用的论文与厂商文档不随仓库分发。
