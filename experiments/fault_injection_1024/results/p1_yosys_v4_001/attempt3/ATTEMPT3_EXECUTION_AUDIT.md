# P1-YOSYS-V4-001 attempt3 执行审计

状态：`VERIFIED`

## 执行边界

- 仅执行 P1；
- 复用 attempt1 冻结 RTL 输入及 SHA-256；
- RTL 未修改；
- 使用 attempt2 已验证的显式受控 `env=`；
- 使用唯一 ASCII `%TEMP%\P1V4A3XXXXXXXX` 工作目录；
- 相对 attempt2 的唯一流程变化是在两个层级 `write_json` 前加入
  `proc; opt_clean`；
- attempt1、attempt2 均未覆盖。

`runner_transform.json` 保存了 attempt2 runner 到 attempt3 展开 runner 的完整
unified diff，并确认恰有两个 `write_json` 位置发生授权变化。

## Preflight

- `yosys -V`：退出码 0，stderr 为空；
- `read_verilog`：通过；
- `hierarchy -check`：通过；
- `check`：`Found and reported 0 problems`；
- `proc`：通过；
- `opt_clean`：通过；
- `write_json`：通过；
- preflight 状态：`VERIFIED`。

## 正式综合

`synth_xilinx -family xc7 -top top_p1_pfft_ecc` 完成，退出码 0；综合前层级
JSON 和综合后 netlist JSON 均已生成。

结构审计：

- Stage 8 TMR wrapper：1；
- Stage 8 完整功能副本：3；
- Stage 9 TMR wrapper：1；
- Stage 9 完整功能副本：3；
- Stage 10 两拍 ECC：1；
- Stage 10 `[6,4,3]` operator：1；
- 旧 Stage-8 scheduler：0；
- 旧 Stage-10 TMR：0；
- 通用复乘：48/48；
- DSP48E1：768/768；
- critical blackbox：0；
- critical warning：0。

## P1资源估计

| 指标 | Yosys xc7估计 |
|---|---:|
| LC estimate | 82,986 |
| LUT1--6 | 104,774 |
| FF | 8,436 |
| DSP48E1 | 768 |
| RAMB18E1 | 12 |
| RAMB36E1 | 0 |
| BRAM36 equivalent | 6.0 |
| Distributed-memory cells | 484 |

distributed-memory 细分为 `RAM32M=380`、`RAM64M=104`。

## P0/P1/P2生成状态

- P0：未运行，未生成 attempt3 新统计；
- P1：已运行，资源统计 `VERIFIED`；
- P2：未运行，未生成 attempt3 新统计。

这是因为本记录及作者授权对象为 `P1-YOSYS-V4-001`，不得借此重跑 P0/P2。

## 证据

- `startup_environment.json`
- `yosys_version_gate.json`
- `preflight.json`
- `script_manifest.json`
- `runner_transform.json`
- `resource_result.json`
- `../../../logs/p1_yosys_v4_001/attempt3/`
- `../../../build/p1_yosys_v4_001/attempt3/`

`resource_result.json` SHA-256：
`D33505A5EE3E1CCE3932E72FE2AEBEF2EE75D194FE3A334596A86AA4934B39A1`。

## 证据边界

以上数字仅为指定 Yosys 0.66+181 的 `xc7 synth_xilinx` 综合资源估计，不是
Vivado post-implementation、布线后 Fmax、功耗、板级或辐照结果。
