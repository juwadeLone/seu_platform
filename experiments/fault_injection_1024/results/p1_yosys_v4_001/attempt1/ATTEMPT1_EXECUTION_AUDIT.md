# P1-YOSYS-V4-001 attempt1 执行审计

状态：`FAILED_YOSYS_STARTUP / VERILOG_NOT_READ / SYNTHESIS_NOT_RUN`

## 已完成

- P1 RTL V4 资格状态验证为 `VERIFIED`；
- 七个 RTL 输入已复制到隔离 staging 目录并逐文件复核 SHA-256；
- 指定工具路径存在；
- `input_validation.json` 已写入 attempt1。

## 失败点

runner 在任何 Verilog 读取之前调用指定 Yosys 的 `-V` 启动检查。进程退出码为
`3221225785`，即 Windows `0xC0000139`（入口点未找到），且未产生版本文本。
runner 按失败即停止规则写入 `preflight.json` 后退出。

本次没有执行：

- `read_verilog`；
- `hierarchy -check`；
- `synth_xilinx`；
- 资源统计或后综合审计。

## 与历史成功启动方式的差异

历史 `PFFT-RES-V3-001 attempt2` runner 为 Yosys 子进程构造最小环境：
`YOSYSHQ_ROOT`、`OSS_ROOT/bin`、`OSS_ROOT/lib` 和
`PYTHON_EXECUTABLE=OSS_ROOT/lib/python3.exe`，并在唯一 ASCII 临时目录运行。
本 attempt1 由外层加载完整 `environment.ps1` 后再从 Inkscape Python 启动，
出现 DLL 入口点冲突。该对照只定位启动环境差异，不构成 RTL 或资源失败。

## 后续边界

attempt1 不覆盖、不删除、不补写。若继续，应由作者授权隔离 attempt2，并采用
历史已验证的最小 Yosys 子进程环境；attempt2 仍须复用同一冻结 RTL 输入和相同
`xc7` 综合判据。
