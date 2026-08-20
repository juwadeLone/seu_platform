# P1-YOSYS-V4-001 attempt2 执行审计

状态：`FAILED_PREFLIGHT_JSON_BACKEND / SYNTHESIS_NOT_RUN`

## 启动门槛

- attempt1 七个冻结 RTL 输入 SHA-256 全部匹配；
- 最终完整子进程环境、PATH、DLL 搜索上下文、cwd、Yosys 路径和 SHA-256
  已在 Yosys 启动前写入 `startup_environment.json`；
- 工作目录为唯一 ASCII `%TEMP%\P1V4A2XXXXXXXX`；
- Yosys 子进程使用与历史 `PFFT-RES-V3-001 attempt2` 等价的显式受控
  `env=`；
- `yosys -V` 退出码为 0，stderr 为空；
- 版本：Yosys 0.66+181。

因此 attempt1 的 `0xC0000139` 启动问题在受控 `env=` 下未复现。

## Preflight

版本门槛通过后，attempt2 按授权继续读取七个冻结 RTL 输入。`read_verilog`、
`hierarchy -check` 和 `check` 均完成，Yosys 报告 `Found and reported 0
problems`。

随后 `write_json P1_hierarchy.json` 失败：

```text
ERROR: Module ...\fft_memory_v5 contains processes, which are not supported
by JSON backend (run `proc` first).
```

退出码为 1。原因是冻结的 attempt1 脚本模板在 `write_json` 前没有执行 `proc`
和 `opt_clean`；历史 `PFFT-RES-V3-001 attempt2` 脚本在层级 JSON 前包含这两个
pass。

## 停止边界

runner 保留全部 stdout、stderr、Yosys log、命令和 SHA-256 后停止：

- 正式 `synth_xilinx` 执行 0 次；
- `P1_netlist.json` 未生成；
- 没有资源数字；
- RTL 未修改；
- attempt1 未覆盖。

若继续，必须另行授权隔离 attempt3，并明确允许只对脚本在层级 JSON 前增加
`proc`、`opt_clean`；冻结 RTL 与 xc7 判据保持不变。
