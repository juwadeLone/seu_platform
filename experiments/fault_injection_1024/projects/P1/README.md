# P1：PFFT 混合 ECC/TMR

## 当前有效边界

当前 P1 由 `P1-PY-V3-001` 数学/位级模型和 `P1-RTL-V4-001` RTL 共同定义：

- Stage 1--7：旋转因子交换后的 `[6,4,3]` 算法 ECC；
- Stage 8--9：三个完整功能级副本及多数表决；
- Stage 10：相邻两个四路 beat 组成四个完整 radix-2 蝶形，四个 A 和四个 B
  分别编码，六个蝶形独立计算，upper/lower 分别完成 `[6,4,3]` 译码。

Stage 10 每帧有 256 个 beat，因此两拍分组不跨帧。旧 Stage-8 跨位置、跨帧
check-pair 调度器仍保存在 `top_p1_pfft_ecc.sv` 中作为 V3 历史源码，但不在
当前 V4 顶层的活动层级闭包内。

## 当前验证状态

- Python gate：`VERIFIED`；
- P1 独立故障 campaign：`124834/124834`，failures=0，SDC=0；
- RTL V4 Icarus 资格：8 帧、2048 beat bit-exact；
- 首输出延迟：267 cycle；
- `gaps=0`、`last_errors=0`、`data_errors=0`；
- Yosys：`P1-YOSYS-V4-001 attempt3` 已通过；xc7估计为 LC 82,986、
  LUT1--6 104,774、FF 8,436、DSP48E1 768、BRAM36 equivalent 6.0。

RTL 资格结果：
`../../results/p1_rtl_v4_001/qualification_attempt1/qualification.json`。

Yosys资源结果：
`../../results/p1_yosys_v4_001/attempt3/resource_result.json`。

## 文件

- `run_p1.py`：P1 Python 故障注入与恢复 campaign；
- `top_p1_pfft_ecc.sv`：当前 V4 顶层及保留的历史 V3 模块；
- `tb_p1.sv`：P1 8 帧 bit-exact testbench；
- `config.json`、`project.json`：当前结构和证据入口。

修改前 RTL 快照位于
`archive/migration/2026-07-24/pre_edit/P1-RTL-V4-001_authorized/`。
