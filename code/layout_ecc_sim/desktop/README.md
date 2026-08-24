# LayoutECC 桌面版（辐射打击仿真器 exe）

> 打包日期：2026-08-24（v1.0.1）。单文件 exe ≈ 20.6 MB，
> 含全部布局数据、物理参数与轨道环境谱文件，双击即用，不再打开浏览器。


## 变更记录（v1.0.1，2026-08-24）

- 版本号：`desktop/app.py` 中 `VERSION = "1.0.1"`；窗口标题、启动日志、打击页页眉/页脚均显示 v1.0.1。
- 候选为 0 的诚实说明：anchored（默认）核半径物理上小于 1 个 Site 格（UG475 标定 ~0.96 µm vs 22.79 µm/格）时，界面与 `/api/strike` 的 `note` 写明这是预期，不是崩溃。
- RPM→µm：打击/界面注释改为 `units.py` 标定值（`RPM_TO_UM_Y=22.79`，`X_IN_CLB=8.63`，`source=calibrated`，`data/rpm_grid_calibration.json`），不再写成 assumption。
- `orbit_env.py` 不再只死盯 `C:\Users\zhuao\tcas\code\orbit_seu`：按 (a) 冻结 `_MEIPASS` 副本 → (b) 环境变量 `ORBIT_SEU_ROOT` → (c) 上述 tcas 路径若存在 → (d) 清晰报错；不编造谱。
- `/oseu-static` 改写只替换已在用的路径前缀（`"/static/"` → `"/oseu-static/"`，`"/api/run"` → `"/oseu/api/run"`）；保留 `/3d` 路由。
- `LayoutECC_StrikeViewer.spec` 与 `desktop/build_exe.bat` 打包清单对齐（仍以 bat 为构建入口）。

未改：MEO 冻结 0.1007/day；质子/DSP 仍不进 N_SEU；thin-slab 不是 IRPP；Weibull/Lee 数字与 SPENVIS 文件与 N_SEU 公式均未动。

## 桌面交付物

- `C:\Users\zhuao\Desktop\辐射打击仿真器.exe`（桌面版 v1.0.1）
- 仓库构建产物：`code/layout_ecc_sim/dist/LayoutECC_StrikeViewer.exe`
- 启动日志（排障用）：`%TEMP%\LayoutECC_viewer.log`

## 两个页面

1. **打击仿真器**（首页 `/`）：三维 Site 栅格 + 打击核 + 按域翻转抽样。
2. **轨道辐射环境**（`/orbit`，首页右上入口）：**orbit_seu 原版仪表盘**（2026-08-22 v3 起
   直接打包 tcas 仓库 orbit_seu 的 webapp 只读副本——与单独运行 `python -m orbit_seu.gui`
   完全同效），含：
   - 预设轨道（SSO/ISS/MEO/GEO/自定义）+ 全套轨道根数表单
   - 器件库（xc7vx690t / xc7k325t / Zynq-7045，页内自带 UG470/DS180/UG474/Lee 2014 引用）
   - 环境模式切换：合成演示谱 / 真实 GCR 模型（BON，系数已打包）/ SPENVIS CREME96 冻结谱
   - 3D 地磁环境 + 卫星飞行动画（NASA Blue Marble 地表、截止刚度渐变场、辐射带示意）
   - LET 谱图、截止刚度曲线、多轨道对比、任务统计与哈希溯源面板
   - 独立 3D 大视图（`/orbit3d`）

   页面顶栏注入"← 返回打击仿真器"导航；原版页面的绝对路径（/static/、/api/run）在响应时
   改写为 /oseu-static/、/oseu/api/run，页面本身零改动。

## 界面里的出处标注（与审计报告一致）

| 界面位置 | 标注的来源 |
|---|---|
| 打击参数卡 | 布局=P1 OOC DCP（Vivado 2018.3, xc7vx690tffg1761-2）；anchored 核面积=Radaelli 2005（Ebrahimi DAC'13 Table 1, α≈0.70，能量→LET 桥为显式假设）；a0/k_LET=几何调试参数 |
| 翻转模型选择 | weibull = Lee REDW 2014 Table 1（DOI 10.1109/REDW.2014.7004595） |
| 故障域卡 | CFG 2122 bits/slice ← UG470 Table 1-1 ÷ DS180 108,300 slices；BRAM 36,864 ← UG473 RAMB36E1；FF ← 布局实例/UG474 866,400；DSP 169 ← UG479（无实测 σ，永不翻转） |
| 格子含义卡 | 1 格 = Y 向 22.79 µm / X 向 8.63 µm ← UG475 v1.9 官方 die 尺寸 × Project X-Ray 栅格标定（`data/rpm_grid_calibration.json`，含 SHA-256） |
| 资料总表抽屉 | Lee REDW 2014 / UG475 / Radaelli-Ebrahimi / Pérez-Celis TNS 2021 + Wirthlin JINST 2014 / DS180 v2.6.1 / UG470 / UG473 / UG479 / UG116 v10.20（交叉校验通过）/ 质子表 Wirthlin JINST 2014 / 已知缺口声明 |

## 重新构建

```bat
cd C:\hermes\layout_ecc_platform\code\layout_ecc_sim
desktop\build_exe.bat
```

依赖：`pip install pywebview pyinstaller`（本机已装 pywebview 6.2.1 + PyInstaller 6.22.2；
窗口内核用系统 WebView2，Win11 自带）。构建脚本同步冻结：
`webapp/`、`primitive_map.csv`、`weibull_7series_measured.json`、`rpm_grid_calibration.json`、
`data/golden/`、`experiments/fault_injection_1024/common/python` 与 `projects/P1`
（`layout_ecc/__init__` 会在导入期引入冻结注入器，纯标准库，零改动）。

## 开发/测试模式

```bash
python desktop/app.py                # 开发：直接开原生窗口
python desktop/app.py --server-only  # 无头：只起 HTTP，端口写日志，供自动测试
```

## 验证记录（2026-08-22）

- `--server-only`：/、/static/engine.js、/seu、/api/layout（24,446 sites）、/api/strike 全部 200 ✓
- v3：/orbit = 原版 orbit_seu 仪表盘（浏览器实测：表单/环境切换/计算按钮/3D 区块全部工作；
  切"SPENVIS CREME96 真实谱"重算 → 器件 1.01e-1/day，与冻结基线 0.100723/day 一致）✓
- exe 实启（v3）：`orbit env prewarmed: device/day=0.1007`；exe 内 POST /oseu/api/run
  全 7 离子种 files 模式 = 0.100723/day，与基线精确一致 ✓；engine.js/earth.jpg/orbit3d 均 200 ✓
- v4（修复 3D 黑屏三重防护）：① 路由原版 `window.open("/3d?…")`（此前 404 → 黑页）；
  ② WebView2 启动参数 `--disable-accelerated-2d-canvas`（规避加速 2D 画布整幅变黑的驱动级问题，
  在 import webview 前经 `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS` 设置）；
  ③ tcas 仓库 engine.js 渲染循环加 try/catch 自愈（单帧异常自动复位视角并继续，不再永久黑屏）。
  浏览器复测：全新标签页画布正常定尺寸、卫星读数实时跳动；exe 内 /orbit、/3d、engine 补丁全部生效 ✓
- 界面包含 UG475/REDW/JINST/SPENVIS 等出处标注 + 两页各自的资料总表 ✓

## 打包内容清单（v3）

- `desktop/orbit_env.py` → exe 根（orbit_seu 路径解析 + 预热自检）
- tcas 仓库只读副本：`orbit_seu` 包（含其 webapp：index/3d/engine.js/earth.jpg）→ `orbit_seu_lib/`；
  `env_data/spenvis_let/*.let.txt`（冻结谱）与 `examples/*.json` → `orbit_seu_env/`；
  `env_data/oneill_lis_coefficients.csv`（真实 GCR 模式系数）→ `orbit_seu_lib/env_data/`
- 开发态（`python desktop/app.py`）直接引用 `C:\Users\zhuao\tcas\code\orbit_seu`，不复制
