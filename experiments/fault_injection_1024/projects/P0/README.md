# P0：未保护 PFFT 基线

- 分组：PFFT；
- Python对象：`pfft_no_exchange_1024`；
- RTL顶层：`top_p0_pfft_unprotected`；
- Stage 1–10：四通道并行、未交换旋转因子的 canonical DIF P-SDF；
- 公共结构：双帧重排缓冲；
- 保护：无；
- 故障实验：只运行无故障功能基线，不提出纠错主张；
- 资源比较：P1、P2均相对P0计算。

本工程文件：`run_p0.py`、`top_p0_pfft_unprotected.sv`、`tb_p0.sv`、`config.json`。

## 代码归属

- `run_p0.py`：P0 完整且唯一的 Python 试验日程；
- `top_p0_pfft_unprotected.sv`：P0 自己的十级 PFFT 核、输出缓冲连接及综合顶层；
- `tb_p0.sv`：P0 独立 testbench。

## PFFT-RES-V3-001 结构口径

- P0 不调用 `pfft_phi_calc`，Stage 1–8 使用 canonical DIF 的
  lower-branch 旋转日程；
- 乘 \(1,-1,\pm j\) 的蝶形保留完整加减与反馈结构，但旋转部分不使用
  通用复乘器；
- Stage 1–10 的通用复乘器结构目标为
  `[4,4,4,4,4,4,3,2,0,0]`，合计 29 个；
- 上述数字是修改后的结构判据，不是 Yosys 实测结果。

## 当前证据状态

`PFFT-RES-V3-001` 的2048-beat bit-exact资格已通过：延迟525 cycle，
`gap_errors/last_errors/data_errors`均为0。指定Yosys input validation通过，
但首次preflight在读取RTL前因执行环境的 `GetShortPathName()` 失败而停止；
因此464仍是理论目标，不是综合测量值。
