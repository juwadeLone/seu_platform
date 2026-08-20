# S0：未保护 SubFFT 基线

- 分组：SubFFT；
- Python对象：`subfft_1024`；
- RTL顶层：`top_s0_subfft_unprotected`；
- Stage 1–8：四路独立256点radix-2 SDF；
- Stage 9–10：单份跨路合并；
- 保护：无；
- 故障实验：只运行无故障功能基线，不提出纠错主张；
- 资源比较：S1、S2、S3均相对S0计算。

本工程文件：`run_s0.py`、`top_s0_subfft_unprotected.sv`、`tb_s0.sv`、`config.json`。

## 代码归属

- `run_s0.py`：S0 完整且唯一的 Python 试验日程；
- `top_s0_subfft_unprotected.sv`：S0 自己的十级无防护 SubFFT 核及综合顶层；
- `tb_s0.sv`：S0 独立 testbench。
