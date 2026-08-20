# P1-RTL-V4-001 执行审计

状态：`VERIFIED`

## 实现结果

- Stage 1--7：保留旋转因子交换后的 `[6,4,3]` 算法 ECC；
- Stage 8：三个 `p1_stage8_functional_v3` 完整副本和 8 个 35-bit 数据表决器；
- Stage 9：三个 `p1_pfft_stage9_exchange_v3` 完整副本和 8 个 35-bit 数据表决器；
- Stage 10：一个两拍四蝶形 `[6,4,3]` 码字，六个完整蝶形运算路径，
  upper/lower 各一个独立纠错边界；
- V4 core 不再实例化旧 Stage-8 single-check-pair scheduler 或 Stage-10 TMR。

Icarus 展开文件中可见 3 个 Stage-8 完整副本和 3 个 Stage-9 完整副本；旧
Stage-8 scheduler 与旧 Stage-10 TMR 在活动展开层级中的计数均为 0。

## Bit-exact 资格

- 输入：8 帧，共 2048 个四路 beat；
- 首输出延迟：267 cycle；
- `gaps=0`；
- `last_errors=0`；
- `data_errors=0`；
- 编译退出码：0；
- 仿真退出码：0。

旧 V3 延迟为 525 cycle。删除 Stage-8 的 258-cycle 历史任务调度路径，同时
Stage-10 两拍配对相对单拍实现增加 1 cycle；新活动 Stage-8 路径本身相对旧
scheduler 输出少 259 cycle，因此净变化为 `525 - 259 + 1 = 267`。

## 证据

- `qualification_attempt1/qualification.json`
- `../../logs/p1_rtl_v4_001/qualification_attempt1/compile.log`
- `../../logs/p1_rtl_v4_001/qualification_attempt1/simulation.log`
- `../../build/p1_rtl_v4_001/qualification_attempt1/tb_p1.vvp`

`qualification.json` SHA-256：
`94744A73F09ADFC1CA2DB60CA8558E8DA99E8CF3DD21B59D014323715FD295F5`。

## 证据边界

本审计只证明当前 P1 RTL 的结构边界、Icarus 可编译性和 8 帧 bit-exact
功能资格。它不是 Yosys 资源结果、Vivado implementation、时序/Fmax、功耗、
板级或辐照证据。旧 `PFFT-RES-V3-001` 的 P1 资源数字不代表本 V4 RTL。
