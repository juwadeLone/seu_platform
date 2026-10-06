# orbit_seu — 芯片在轨 SEU 效应估算工具（v0.1.0）

给定**任意地球轨道**（开普勒根数）与**器件截面数据**，估算单粒子翻转（SEU）事件率与任务期概率：

```
轨道根数 → J2 传播 → 倾斜中心偶极磁场（磁纬/L/垂直截止刚度 Rc）
        → 粒子/LET 环境（文件导入 或 明确标注的合成演示谱）
        → 器件 σ(LET)（Weibull/表格） → 事件率积分 → 泊松任务统计 → Markdown/JSON 报告
```

纯 Python 标准库实现，无第三方依赖。**所有报告自动附带输入 SHA-256 溯源与局限声明**（遵循工作区证据规则）。

## 快速开始

**网页界面（推荐）**：

```bash
cd code/orbit_seu
python -m orbit_seu.gui          # 自动打开 http://127.0.0.1:8600
```

界面左侧填轨道根数/任务/器件参数（或选 ISS/SSO/MEO/GEO 预设），点“计算”即出结果：四张指标卡（每 bit 天事件率、每器件天事件率、任务期期望、P≥1）、分核素事件率表、透射 LET 谱（对数-对数）与截止刚度沿轨道曲线；3D 场景包含真实地表地球（NASA Blue Marble，公有领域，随包分发）、按截止刚度红→蓝渐变着色的 SEU 危险度体渲染场（多层等截止壳）、太阳/宇宙线粒子流、卫星飞行动画（可点击轨道点定位、速度可调、拖拽旋转、滚轮缩放）、SAA 示意区与多轨道对比叠加；「⛶ 独立窗口」可在大窗口中单独展示 3D 场景。纯本地服务，除内置纹理外无外网依赖。

**命令行**：

```bash
cd code/orbit_seu
python -m unittest discover -s tests          # 34 项单元测试
python -m orbit_seu examples/demo_leo_sso.json -o out/
```

演示输出（550 km / 97.6° SSO / 3 年 / **合成演示谱**）：

```
SEU rate: 2.296e-11 /s/bit (1.984e-06 /day/bit)
per device (55 Mbit): 109 /day
```

## 配置（JSON）

| 键 | 内容 |
|---|---|
| `mission` | `duration_years`；`sampling.orbits`×`points_per_orbit` 轨道采样密度 |
| `orbit` | `altitude_km`（半长轴≈Re+h）、`inclination_deg`、`eccentricity`、`raan/argp/M0` |
| `magnetosphere` | 可覆盖 `g10/g11/h11_nt`（默认 IGRF-13 2020.0）、`cutoff_eq_gv`（默认 14.9 GV） |
| `environment.type` | `demo_gcr`（合成演示）或 `files`（工程路径，见下） |
| `device` | `heavy_ion_weibull{let_threshold,width,shape,sigma_sat_cm2_per_bit}` 或 `sigma_table` 路径；`bits` |

## 工程级使用（重要）

内置 `demo_gcr` 是**合成演示谱**（幂律刚度谱 + L=K·Z²/β² 近似，未含 Betle 对数项，低 β 段低估约 2–3×），**禁止用于任务评估**。推荐真实数据走以下路径：

### 路径 0（推荐，已内置打通）：SPENVIS CREME96 真实 GCR 谱

在 **SPENVIS**（www.spenvis.oma.be，ESA 免费注册）中，对你的目标轨道跑
**GCR particle model → CREME96 (Sol. Minimum)**，下载 `spenvis_gcf.txt` 放到
`env_data/`，然后：

```bash
python scripts/spenvis_to_let.py          # 生成 env_data/spenvis_let/*.let.txt
python -m orbit_seu examples/demo_spenvis_files.json -o out/   # files 模式跑通
```

GUI 里环境模式直接选 **“SPENVIS CREME96 真实 GCR 谱（已导入）”** 即可。
本工作区已随附一份取自 **20200 km / 55°** 轨道的 CREME96 solar-min 谱及转换
好的 6 组 LET 谱（Z=1–92 全部离子，100 mil Al 屏蔽，Bethe LET；参数见 `env_data/spenvis_let/manifest.json`）。
XC7VX690T 在此谱下为 46.2 次/天，每 bit 率与 Lee 2014 Table 2（GEO）相差 10% 以内。
这是过渡路径：标准做法是在 SPENVIS 里直接导出 CREME96 带屏蔽的 LET 谱（TRANS+LETSPEC）替换这些文件。
⚠️ SPENVIS 谱携带其生成轨道的磁屏蔽；换轨道需在 SPENVIS 重跑并重转换。

### 路径 A：真实 GCR 模型（`bo_gcr`）


力场调制（Gleeson–Axford 1968 标准方程）+ LIS 系数文件：

1. 从 **NASA NTRS**（ntrs.nasa.gov，公有领域）下载 **NASA/TM-2013-217978**（O'Neill, *Badhwar-O'Neill 2014 GCR Flux Model Description*）；
2. 将其逐元素系数表整理为 `env_data/oneill_lis_coefficients.csv`（格式与函数形式见 `env_data/README.md`）；
3. 配置 `"environment": {"type": "bo_gcr", "phi_mv": 600}`（φ：太阳极大 300–400，极小 800–1200）。

### 路径 B：AE9/AP9 束缚辐射（`ae9ap9`）

1. 从 **AFRL/SET** 公开渠道下载 **AE9/AP9-IRENE v1.50 程序包**，解压到 `env_data/ae9ap9/`（含 `ae9ap9.exe` 与数据目录）；
2. 配置 `"type": "ae9ap9"`（可与 bo_gcr 组合：`"type": ["bo_gcr", "ae9ap9"]`，GUI 里选“组合”）；
3. 工具自动生成轨道星历 → 调用模型 → 解析能量-通量表 → 进事件率积分，输出哈希入报告溯源。

### 路径 C：SPENVIS/CREME96 导入（`files`）

在 SPENVIS / AE9AP9 / CREME96 中输入你的轨道与屏蔽，导出微分 LET 谱与质子能谱文本：

```json
"environment": {
  "type": "files",
  "let_spectra_files": {"gcr": "spenvis_let_spectrum.txt"},
  "let_columns": {"let": 0, "diff_flux": 1},
  "proton_file": "spenvis_trapped_proton.txt",
  "proton_columns": {"energy": 0, "diff_flux": 1}
}
```

解析器容忍 `# % ! ; *` 注释行与表头行，列号可配；文件谱按“与该轨道和屏蔽条件对应”直接使用。无论哪条路径，**器件 σ(LET)/σ(E) 都必须来自地面试验或可信文献**——工具不提供、不虚构器件截面。

## 方法与已知局限（v0.1）

| 环节 | 实现 | 局限 |
|---|---|---|
| 轨道 | 一阶长期 J2（RAAN/ω/M 漂移）+ 开普勒 | 无短周期项；GMST 线性模型 |
| 磁场 | IGRF 偶极项（可更新系数）、地磁纬、偶极 L | 多极场/真实 L 与 Smart-Shea 网格差异 ±20% |
| 截止 | Størmer 垂直截止 Rc=Rc_eq(Re/r)²cos⁴λm，硬阈透射（κ 可调） | 无方向依赖、无 SAA 辐射带质子的空间映射（靠导入谱承载） |
| 重离子率 | 有效 LET 薄片近似（CREME86 传统）：R=(φ_omni/2)·⟨σ(L/cosθ)⟩，θ 取 0–90°、按 2cosθ·sinθ 加权 | 未做完整 IRPP、funnel、MBU 共享 |
| LET/屏蔽（files 过渡路径） | Bethe-Bloch + Barkas 有效电荷 + Sternheimer 密度修正；Al 球壳 CSDA 输运（`orbit_seu/stopping.py`） | 无壳层/Bloch 修正、无核碎裂；布拉格峰附近约 ±10% |
| 质子率 | 直接积分 ∫φ(E)σ(E)dE（仅表格 σ） | 未实现 Bendel 解析式（避免记错常数） |
| 任务统计 | 泊松：期望 = R·T，P(≥1)=1−e^(−RT) | 环境不随太阳调制/在轨时间变化 |

## 路线图

AE9/AP9 本地适配器、完整 IRPP（RPP 弦长分布）、Bendel/双参数质子拟合、方向相关截止、SAA 遍历映射、TID/DDD 剂量链、器件库（XML+哈希）。

## 参考

- Størmer 截止与中心偶极近似（Smart & Shea 网格为精化基准）
- J. C. Petersen, *Single Event Effects in Aerospace*, Wiley（有效 LET/IRPP 方法论）
- CREME96（Tylka et al., 1997）、SPENVIS（ESA）、AE9/AP9（Ginet et al., Space Weather 2014）
- JEDEC JESD89 / ECSS-E-ST-10-12（地面试验数据与任务评估规范）
- IGRF-13（Alken et al., 2021）偶极系数默认值来源
