# S2：SubFFT 逐级完整 TMR

- 分组：SubFFT；
- RTL顶层：`top_s2_subfft_tmr`；
- Stage 1–10：每一级完整三模冗余；
- 级间：多数表决；
- 资源基线：S0；
- 作用：作为全级TMR对照。

本工程文件：`run_s2.py`、`top_s2_subfft_tmr.sv`、`tb_s2.sv`、`config.json`。

## 代码归属

- `run_s2.py`：S2 十级 TMR 的完整注错日程；
- `top_s2_subfft_tmr.sv`：S2 自己的十级完整级 TMR 核及综合顶层；
- `tb_s2.sv`：S2 独立 testbench。
