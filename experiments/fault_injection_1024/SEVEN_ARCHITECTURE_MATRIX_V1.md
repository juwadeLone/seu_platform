# FFT1024 七对象 Python → RTL → Yosys 冻结矩阵 V1

状态：`FROZEN`  
用户确认日期：2026-07-21

## 1. 比较分组

| ID | 组 | 架构 | Stage 1--8 | Stage 9--10 | 资源基线 |
|---|---|---|---|---|---|
| S0 | SubFFT | 无防护 | 四个单路经典256点八级R2SDF | 单份普通级 | S0 |
| S1 | SubFFT | Gao路径ECC | 四functional+三coded完整SubFFT路径 | 完整级TMR | S0 |
| S2 | SubFFT | 逐级TMR | 每级完整三份并投票 | 每级完整三份并投票 | S0 |
| S3 | SubFFT | 逐级ECC | memory SECDED+两条独立check arithmetic streams | 完整级TMR | S0 |
| P0 | PFFT | 无防护 | 单份四并行P-SDF | 单份普通级+公共帧BRAM | P0 |
| P1 | PFFT | 逐级ECC | Stage1--7 direct ECC；Stage8 BRAM buffered ECC | 完整级TMR+公共帧BRAM | P0 |
| P2 | PFFT | 逐级TMR | 每级完整三份并投票 | 每级完整三份并投票+公共帧BRAM | P0 |

禁止跨SubFFT/PFFT组直接归因。S0/P0是独立完整top，不通过公式从保护对象扣除资源。

## 2. 固定数值与流契约

- 1024点、四lane、十级radix-2、每帧256 beat；实虚各35-bit二补码；twiddle为30-bit Q2.28。
- 四个SubFFT子核均为独立单路经典R2SDF，反馈深度`128/64/32/16/8/4/2/1`。
- 深度128反馈采用同步读BRAM，其他反馈采用异步读distributed RAM。
- SubFFT七对象中的四个对象统一延迟268 cycle。
- P0/P1/P2均含相同`2×1024` complex-word公共BRAM重排缓存，统一延迟525 cycle。
- P1另含512-word Stage8保护BRAM，但不得改变组内外部时序。

## 3. Python门槛

- S0/P0：八个冻结无故障帧、valid/last/order和值全部bit-identical；不声明纠错。
- S1/S2/S3/P1/P2：继承schema-v4冻结的114447条单故障trial集合，但以schema-v5流延迟重新运行。
- Gao与arithmetic expected residual必须在注错前捕获，received symbols变化不得改变expected residual。
- P1 Stage8必须覆盖同帧组和相邻帧跨帧组、512个首帧未决符号、frame/index回填。
- 任意未解释failure或SDC均停止，不进入RTL。

## 4. RTL门槛

- 七个top均为完整、可综合的1024点实现并逐beat匹配Python。
- 两条arithmetic check streams必须独立执行受保护算子；禁止在functional输出后重编码。
- Gao三条coded路径为真实完整R2SDF链；expected residual不得从received path outputs重算。
- P1 Stage8缓存必须在corrected data的传递闭包内，综合后不得删除。
- 保护连接spot必须在五个保护top内对实际恢复边界注错，不得只测试孤立primitive。
- 同规格memory template跨对象不一致即`BLOCKED`。

## 5. Yosys门槛与输出

- 唯一工具：`C:\Users\pc\Downloads\oss-cad-suite\bin\yosys.exe`。
- 固定`Yosys 0.66+181`、`synth_xilinx -family xc7`、相同source set和脚本。
- 先验证七个top hierarchy与memory primitive class，再提取LUT/FF/DSP/BRAM和distributed RAM。
- SubFFT表为S0/S1/S2/S3并给出相对S0的绝对/百分比变化；PFFT表为P0/P1/P2并给出相对P0变化。
- 只称Yosys综合资源估计，不称Vivado实现后结果，不报告Fmax或功耗。

## 6. 旧证据状态

旧五架构Yosys汇总、旧分组表及对应审计报告已移至
`archive/frozen_fault_injection_1024_v1/legacy_results/`，状态保持
`SUPERSEDED/INVALID_FOR_FINAL_COMPARISON`。旧结果仅用于追溯存储映射不统一、
公共帧缓存被展开为FF、P1 Stage 8缓存被删除以及ECC连接不满足冻结定义等历史问题。
