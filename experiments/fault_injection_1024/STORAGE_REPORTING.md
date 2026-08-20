# 存储资源三层报告口径

为避免仅用BRAM块数掩盖容量碎片，七架构资源结果同时报告以下三层指标。

## 1. 逻辑存储需求

对每种存储结构记录：

`effective_bits = width × depth × instances`

不同用途的存储分别列出，不把反馈延迟、PFFT公共双帧缓存和P1额外待配对缓存混为一项。

## 2. 物理映射

分别报告：

- RAMB18E1；
- RAMB36E1；
- BRAM36等效；
- Xilinx LUTRAM原语及其占用。

## 3. 容量利用率

`utilization = effective_bits / allocated_physical_capacity_bits`

利用率只说明固定块容量造成的碎片，不用于把LUT、FF、DSP和BRAM合并成单一“总资源”。

## 报告原则

- 主结果保留综合器正常映射；
- 强制LUTRAM只能作为单独的敏感性分析，不替代主结果；
- SubFFT和PFFT分别相对本组基线比较；
- Yosys结果只称为综合资源估计。

