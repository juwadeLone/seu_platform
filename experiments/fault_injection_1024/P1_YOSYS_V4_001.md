# P1-YOSYS-V4-001：P1 RTL V4 资源估计

## 授权与范围

作者于 2026-07-24 授权使用指定 Yosys 检查当前 P1 RTL 的资源。本任务只综合
`P1-RTL-V4-001`，不重跑 P0/P2，不覆盖 `PFFT-RES-V3-001`，不启动 Vivado、
XSim、上板或辐照流程。

## 固定工具与流程

- Yosys：`C:\Users\pc\Downloads\oss-cad-suite\bin\yosys.exe`
- 流程：`read_verilog -sv`、`hierarchy -check`、
  `synth_xilinx -family xc7 -top top_p1_pfft_ecc`
- 输入：当前 P1 RTL V4 及其六个公共 RTL 依赖
- 前置资格：
  `results/p1_rtl_v4_001/qualification_attempt1/qualification.json`
  必须为 `VERIFIED`

## 隔离输出

- `results/p1_yosys_v4_001/attempt1/`
- `logs/p1_yosys_v4_001/attempt1/`
- `build/p1_yosys_v4_001/attempt1/`

作者随后授权隔离 `attempt2`。它必须复用 attempt1 的冻结 RTL 哈希、同一脚本
模板和全部 xc7 判据，输出分别进入：

- `results/p1_yosys_v4_001/attempt2/`
- `logs/p1_yosys_v4_001/attempt2/`
- `build/p1_yosys_v4_001/attempt2/`

attempt1 在生成 `.ys` 文件前已停止，因此 attempt2 所称“复用综合脚本”是从
冻结的 attempt1 runner 原样展开同一 `read_verilog`、`hierarchy -check`、
`check`、`write_json`、`synth_xilinx -family xc7`、`stat` 脚本模板；不修改
流程或判据。

attempt2 额外启动门槛：

1. 使用与历史 `PFFT-RES-V3-001 attempt2` 等价的显式受控 `env=`；
2. 在唯一 ASCII `%TEMP%\P1V4A2XXXXXXXX` 目录运行；
3. 在启动前落盘最终环境、完整 PATH、工作目录、Yosys 路径和 SHA-256；
4. 单独执行 `yosys -V`，完整保存 stdout/stderr 和退出码；
5. `-V` 非零时立即停止，不生成或执行 `read_verilog`；
6. 只有 `-V` 成功后才允许 preflight 和正式综合。

作者继续授权隔离 `attempt3`。attempt3 复用相同冻结 RTL、xc7 判据、受控
`env=` 和唯一 ASCII 临时目录。相对 attempt2，唯一允许的脚本变化是在每个
`write_json` 前增加：

```text
proc
opt_clean
```

不得修改其余 preflight 或正式综合逻辑。preflight 失败即停止，不创建新
attempt；成功后才运行 P1 正式综合。P0/P2 不在本次执行范围。

## PASS / FAIL

1. 输入文件、工具和 RTL 资格状态验证通过，并保存 SHA-256；
2. preflight 读取、层级检查和 JSON 导出退出码为 0；
3. 正式 `xc7` 综合退出码为 0，必须生成综合前层级和综合后 netlist JSON；
4. 活动综合前层级中 Stage 8、Stage 9 各保留三个完整副本，Stage 10 保留一个
   两拍四蝶形 ECC，旧 Stage-8 scheduler 和旧 Stage-10 TMR 均不可达；
5. 无关键 unresolved/blackbox/multiple-driver/no-driver 警告；
6. 分别报告 LC estimate、LUT1--6、FF、DSP48E1、RAMB18E1、RAMB36E1、
   BRAM36 equivalent 和 distributed-memory cells，不合并为“总资源”；
7. 结构诊断目标为 48 个通用复乘、768 个 DSP48E1。若实测不等于目标，必须
   保留真实结果并标记 `FAILED_TARGET_DIAGNOSTIC`，不得修改 RTL 或结果迎合目标；
8. 所有命令、日志、JSON 和 SHA-256 写入 attempt1，失败即停止且不静默重试。

结果只能称为 Yosys `xc7` 综合资源估计，不能称为 Vivado post-implementation、
布线后 Fmax、功耗或物理实测。
