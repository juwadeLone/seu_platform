# S1：Gao 完整路径 ECC

- 分组：SubFFT；
- RTL顶层：`top_s1_gao_subfft_ecc`；
- Stage 1–8：4条功能SubFFT路径加3条完整编码路径；
- 路径码：Hamming (7,4,3)；
- Stage 9–10：完整级TMR；
- 资源基线：S0；
- 作用：与逐级TMR和本文逐级ECC方案进行SubFFT组内比较。

本工程文件：`run_s1.py`、`top_s1_gao_subfft_ecc.sv`、`tb_s1.sv`、`config.json`。

## 代码归属

- `run_s1.py`：Gao 七路径构造、注错日程及越界试验；
- `top_s1_gao_subfft_ecc.sv`：S1 自己的完整八级 SubFFT 路径、七路径编码、Stage-8 解码和 Stage-9/10 TMR；
- `tb_s1.sv`：S1 独立 testbench。
