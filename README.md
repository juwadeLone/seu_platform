# seu_platform

布局感知 ECC 仿真平台（`layout_ecc_sim`）与辐射打击仿真器桌面版。

## 仓库内容

| 路径 | 说明 |
|---|---|
| `code/layout_ecc_sim/` | 平台源码、布局数据、打击核 / Weibull 模型、Web 与桌面入口 |
| `code/layout_ecc_sim/desktop/` | 桌面版源码（pywebview 封装） |
| `code/layout_ecc_sim/dist/LayoutECC_StrikeViewer.exe` | 构建产物 |
| `release/辐射打击仿真器.exe` | 桌面交付 exe（与上者同构建，v1.0.1） |
| `experiments/fault_injection_1024/` | 冻结位级注入实验包（只读依赖） |

## 运行

- **桌面 exe**：双击 `release/辐射打击仿真器.exe`（约 20.6 MB，含布局数据；日志 `%TEMP%\LayoutECC_viewer.log`）。
- **开发**：`cd code/layout_ecc_sim` 后 `python desktop/app.py`，或 `python -m layout_ecc` 开浏览器版。
- **重新打包**：`code/layout_ecc_sim/desktop/build_exe.bat`（需 PyInstaller + pywebview）。

详见 `code/layout_ecc_sim/desktop/README.md`。
