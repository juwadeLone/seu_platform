# layout_ecc_sim — 布局感知打击核（M3 三维查看器）

> 下一步执行计划见 [第一阶段执行手册](./第一阶段执行手册.md)（WP1 标签解析 → WP2 功能注入 → WP3 翻译器；认识建设导向，与当前 TCAS 稿件脱钩）。

第一阶段 **几何打击器**：在芯片代理布局上用椭圆核选候选资源，再按**故障域**做伯努利翻转。

## 故障域模型（指南第 8 节）

一个 Site 在同一个 (x, y) 上叠加多个故障域（`layout_ecc/domains.py`）：

| 域 | 含义 | 占位位数代理 |
|---|---|---|
| `CFG` | 配置位 CRAM | 基数（按 Site 类型）+ 8×原语数 |
| `FF_STATE` | 用户 FF 状态位 | 从 `ref_name` 实数（FD*/LD*） |
| `BRAM_STATE` | BRAM 数据位 | RAMB36 = 36864 |
| `DSP_STATE` | DSP 流水/输出状态 | 96 |

四个域是**同一平面上的逻辑叠加层**，不是垂直堆叠的物理层。同一次打击的同一个椭圆对每个域分别求交、分别用各域概率翻转，因此跨域相关故障（同一打击同时翻配置位和 FF）天然保留。`n_bits=1` 的重数是占位值，待标定（M9）。SET/布线暂不建模：net 横跨多个 Tile，不属于 Site 级占用。

计算在芯片平面上进行（指南 9.1）。三维界面只用来显示离子径迹（θ、φ）、落在硅面上的椭圆核，以及候选（黄，域×Site）/翻转（红）；左侧勾选框按域过滤显示，计算始终覆盖全部域。

当前布局来自 P1 在 **xc7vx690tffg1761-2** 上的本地 Vivado 2018.3 OOC 布线 DCP 导出的 `primitive_map.csv`。一格 = 一个占用 Site；默认按 FFT 级 HSV 着色（可切资源类型）；包围盒内未占用格子为黑。RPM_X/Y 是架构单位，不是微米。椭圆尺寸是参数化占位模型，不是已标定的电荷收集半径。

查看器：`python -m layout_ecc` → http://127.0.0.1:8610/  
标签报告：`python -m layout_ecc.stage_tags`  
WP2/WP3 手扫：`python scripts/wp2_stage_scan.py`、`python scripts/wp3_handscan.py`

Yosys 论文资源表与这次 DCP 数字不得混用。

## 启动

```bash
cd code/layout_ecc_sim
python -m unittest discover -s tests
python -m layout_ecc          # http://127.0.0.1:8610
```

与 `orbit_seu`（默认 8600）分开的端口，两套界面可同时开。

布局文件：`data/layout/p1_ooc_win/primitive_map.csv`（约 2.4 万 Site）。浏览器用占用位图贴在芯片面上，不逐格挤出 3D 盒子。

## 还不是什么

- 不是晶体管级 MCU 预测；
- Site 坐标是布局代理，不是微米级敏感体积；
- 域的位数与翻转概率是占位常量，未经 SEM/束流标定；
- 不接入 `orbit_seu` 环境谱（那是 M7；M3 按网格扫 LET/角度）；
- 预览分类不是完整 M4 分类器。码字/符号规则目前是占位（`confidence: proxy`）。
