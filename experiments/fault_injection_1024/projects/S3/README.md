# S3：SubFFT 逐级 ECC

- 分组：SubFFT；
- RTL顶层：`top_s3_subfft_ecc`；
- Stage 1–8：存储SECDED加两条独立算术校验流；
- Stage 9–10：完整级TMR；
- 资源基线：S0；
- 角色：本文SubFFT逐级保护方案。

本工程文件：`run_s3.py`、`top_s3_subfft_ecc.sv`、`tb_s3.sv`、`config.json`。

注意：V2正式执行前必须先复核算术边界的clean/received端口次序。

## 代码归属

- `run_s3.py`：S3 的四通道同算子分组、SECDED、算术 ECC、TMR 和注错日程；
- `top_s3_subfft_ecc.sv`：S3 自己的 Stage-1--8 ECC、Stage-9/10 TMR 核及综合顶层；
- `tb_s3.sv`：S3 独立 testbench。
