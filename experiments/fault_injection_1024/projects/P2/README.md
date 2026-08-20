# P2：PFFT 逐级完整 TMR

- 分组：PFFT；
- Python对象：`pfft_no_exchange_1024`；
- RTL顶层：`top_p2_pfft_tmr`；
- Stage 1–10：P0 canonical DIF 未交换日程的每一级完整三模冗余；
- 级间：多数表决；
- 公共结构：与P0一致的双帧重排缓冲；P1改由其Stage-8调度存储完成返回重排；
- 资源基线：P0；
- 作用：作为PFFT全级TMR对照。

本工程文件：`run_p2.py`、`top_p2_pfft_tmr.sv`、`tb_p2.sv`、`config.json`。

## 代码归属

- `run_p2.py`：P2 十级 TMR 的完整注错日程；
- `top_p2_pfft_tmr.sv`：P2 自己的十级完整级 TMR 核、帧缓冲连接及综合顶层；
- `tb_p2.sv`：P2 独立 testbench。

## PFFT-RES-V3-001 结构口径

- P2 的三个 stage replica 都使用与 P0 相同的 canonical DIF
  lower-branch 旋转日程，不调用 `pfft_phi_calc`；
- 乘 \(1,-1,\pm j\) 的蝶形保留在三个完整副本中，但旋转部分不使用
  通用复乘器；
- Stage 1–10 的通用复乘器结构目标为
  `[12,12,12,12,12,12,9,6,0,0]`，合计 87 个；
- 上述数字是修改后的结构判据，不是 Yosys 实测结果。

## 当前证据状态

`PFFT-RES-V3-001` 的2048-beat bit-exact资格已通过：延迟525 cycle，
`gap_errors/last_errors/data_errors`均为0。指定Yosys input validation通过，
但首次preflight在P0读取RTL前因执行环境的 `GetShortPathName()` 失败而停止，
所以P2 preflight与综合未运行；1392仍是理论目标。
