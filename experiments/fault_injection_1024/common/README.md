# 七工程公共实现

这里只保存七个工程都会复用的内容，不是第八个实验工程。

## Python

- `python/fixed_fft.py`：SubFFT/PFFT固定点数据流；
- `python/protection.py`：SECDED、算术ECC、Gao码、TMR原语；
- `python/campaign_support.py`：只提供合同读取、哈希、CSV/JSON记录和通用单点注错原语；不含任何 S0--P2 试验日程。
- `python/stream_contract.py`：两种无防护数据流共用的时序/令牌合同。

具体运行入口不在这里，而在`projects/S0/run_s0.py`至
`projects/P2/run_p2.py`。

## RTL

- `fft_common.sv`、`datapath_v5.sv`：公共蝶形、延迟存储、级原语和帧缓冲原语；
- `protection_rtl.sv`、`protection_primitives_v5.sv`、`protected_stages_v5.sv`：公共保护原语；
- 架构核心不得放在本目录；S0--P2 的核心均归入各自 `projects/<ID>/`。
- `project_tb_template.svh`：七个独立testbench共用的检查模板；
- `twiddle_rom_1024.sv`：旋转因子ROM。

每个可综合顶层均位于自己的`projects/<ID>/top_*.sv`中。

## 工具

`tools/`只负责跨工程静态审计、资格调度和Yosys汇总，不承载某个架构的故障注入入口。
