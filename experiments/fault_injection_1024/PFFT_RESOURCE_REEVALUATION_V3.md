# PFFT-RES-V3-001：PFFT 三工程 D94 资源验证合同

状态：`AUTHORIZED / S03-S04_STATIC_READY / QUALIFICATION_PENDING / NOT_YET_MEASURED`

## 1. 目的与证据边界

本记录只重新验证 1024 点、四通道、十级 radix-2 PFFT 的三个完整工程：

- `P0`：原生 DIF、无旋转因子交换、无保护基线；
- `P1`：本文旋转因子交换、Stage 1--8 算术 ECC、Stage 9--10 局部 TMR；
- `P2`：原生 DIF、无旋转因子交换、十级完整 TMR。

本记录取代被 D94 阻塞的 `PFFT-RES-V2-001` 结构合同，但不修改或覆盖其合同、
失败 manifest、日志、结果与修改前快照。最终结果只能称为指定 Yosys 的
`xc7 synthesis resource estimate`，不能称为 Vivado post-implementation、
布线后 Fmax、功耗或板级结果。

## 2. 冻结理论假设

依据 D89、D90、D94 和 D95：

1. 加减、符号变换、实虚交换、选择器计入 LUT/LC，寄存器另计 FF。
2. \(1,-1,\pm j\) 使用平凡旋转原语，不实例化通用复乘。
3. 一个 Stage 1--8 完整 SDF 蝶形包含 feedback 状态及 upper/lower 分支；
   三者分时复用一个输出旋转单元，不得拆成多套复乘库。
4. 当前 35-bit 数据乘 30-bit 系数的一个 `fft_complex_mul_q28` 结构诊断为
   16 个 DSP48E1；最终仍以指定 Yosys 实测为准。
5. 平凡旋转按物理 lane 的完整指数集合特化，而不是按“整级只要出现过
   非平凡旋转就保留所有通用复乘器”的粗粒度上限。

冻结的逐级结构假设为：

| 工程 | Stage 1--10 通用复乘器 | Stage 1--10 DSP48E1 假设 | 总计 |
|---|---|---|---:|
| P0 | `[4,4,4,4,4,4,3,2,0,0]` | `[64,64,64,64,64,64,48,32,0,0]` | 464 |
| P1 | `[0,6,6,6,6,6,6,4,6,0]` | `[0,96,96,96,96,96,96,64,96,0]` | 736 |
| P2 | `[12,12,12,12,12,12,9,6,0,0]` | `[192,192,192,192,192,192,144,96,0,0]` | 1392 |

这些数字是待验证假设，不是测量结果。

## 3. P1 Stage 8 硬停止门槛

P1 Stage 8 只允许一个物理 check-pair，即两个校验蝶形。五类分组必须通过
FIFO、分组标签、bank/address 返回标签和确定性调度复用这一对校验蝶形。

在修改 P1 RTL 前，静态调度审计必须证明：

- 单服务器每周期最多接收并完成一个 check codeword；
- 两帧 512 个输入 beat 的所有任务均可服务；
- 最大积压有有限、明确的 FIFO 深度；
- 最终积压为零；
- 稳态输出保持 II=1，不因校验调度产生气泡；
- 输出返回地址和 frame/bank 标签无歧义。

若任一条件失败，状态立即改为
`BLOCKED_P1_STAGE8_SINGLE_CHECK_PAIR_INFEASIBLE`，停止 P1 RTL 修改、RTL
qualification 和 Yosys；不得自动增加第二个 check-pair，也不得把理论目标改成
768 后继续。

S02 首次静态审计结果为
`PASS_STATIC_FEASIBILITY_SINGLE_CHECK_PAIR`：512 个任务采用
earliest-output-first 调度，可实现为 urgent cross FIFO 与 background same FIFO；
入队先于发射时峰值为 129 项（或 128 项存储加一个同周期 skid），固定 Stage 8
局部延迟为 258 周期，II=1，四个帧对重放无无界增长。证据为
`results/pfft_resource_v3_001/schedule_feasibility_attempt1.json`。该结果只解除
静态调度硬停止条件，不替代 S04 的真实 RTL、存储端口/返回标签实现或 S05
bit-exact 资格验证。

S04 的活动 RTL 静态审计结论为 `PASS_STATIC_CONDITIONAL`：Stage 8 活动层级中
只有一个 `independent_check_operator_pair_v5`，其内部只有两个通用复乘器；
存储结构为 12 个 512×78 SECDED F/A/B history、registered head 加 128×959
background tail RAM、四项 urgent register skid，以及两个 512×312
corrected-result bank。同步读、单写端口、返回地址和同址显式转发的静态检查
通过。该结论仅适用于本合同冻结的连续 `in_valid`、II=1 输入，不扩展为任意
帧间空隙，也不替代 S05 RTL 仿真或 S06 Yosys 映射。

上述 15 个声明为 block 的数组合计 921,472 个逻辑 bit。S06 的保守聚合映射
门槛为：单 check-pair scheduler 后代层级中的
`36864×RAMB36E1 + 18432×RAMB18E1 >= 921472`，即至少 25 个
BRAM36 等效容量。该门槛防止“仅出现一个 RAMB 即通过”，但只证明聚合容量
保留，不扩写为 history、FIFO 和 result 三类存储的逐角色 primitive 归属。

## 4. 输入、快照与输出

修改前快照：

`archive/migration/2026-07-23/pre_edit/2026-07-23_PFFT-RES-V3-001_authorized/`

原始输出只能写入：

- `experiments/fault_injection_1024/results/pfft_resource_v3_001/`
- `experiments/fault_injection_1024/logs/pfft_resource_v3_001/`
- `experiments/fault_injection_1024/build/pfft_resource_v3_001/`

运行前必须生成 `config/pfft_resource_v3_input_manifest.json`，记录 RTL、TB、
include、向量、合同、runner、工具路径和 SHA-256。禁止覆盖 V1/V2 结果。

## 5. 资格门槛

Yosys 前必须全部满足：

1. P0/P2 使用 canonical DIF，无 `pfft_phi_calc` 或交换版 stage 泄漏；
2. P1 只使用交换日程；
3. Stage 1--8 每个完整 SDF 蝶形最多一个输出旋转单元；
4. P1 Stage 1--8 为四功能加两校验，upper/feedback/lower 不形成独立复乘库；
5. P1 Stage 8 活跃层级中恰有一个 check-pair；
6. P2 十级均保留三副本和级末 voter；P1 Stage 9--10 保留三副本；
7. P0 活跃层级无 ECC、TMR、voter 或 P1 专属模块；
8. P0/P1/P2 分别编译退出 0；
9. 每个工程输出 2048 beat，逐 bit 匹配其冻结向量；
10. `out_last` 帧边界零错误，首个 `out_valid` 后不允许气泡；
11. 延迟为确定值并写入结果；目标值为 525 cycle，若改变则停止而非静默改合同；
12. connectivity spot test 覆盖 P1 SECDED、算术 ECC、Stage 8
    same/cross-frame/pending 路径、P1 Stage 9 TMR 和 P2 TMR。

## 6. 指定工具与命令

- Python：`C:\Program Files\Inkscape\bin\python.exe`
- Icarus：`C:\iverilog\bin\iverilog.exe`
- VVP：`C:\iverilog\bin\vvp.exe`
- Yosys：`C:\Users\pc\Downloads\oss-cad-suite\bin\yosys.exe`
- 综合流：`synth_xilinx -family xc7`

固定执行顺序：

```powershell
& 'C:\Program Files\Inkscape\bin\python.exe' experiments/fault_injection_1024/projects/P1/audit_p1_stage8_single_check_pair_v3.py
& 'C:\Program Files\Inkscape\bin\python.exe' experiments/fault_injection_1024/common/tools/write_pfft_resource_v3_input_manifest.py
& 'C:\Program Files\Inkscape\bin\python.exe' experiments/fault_injection_1024/common/tools/run_pfft_resource_qualification_v3.py
& 'C:\Program Files\Inkscape\bin\python.exe' experiments/fault_injection_1024/common/tools/run_pfft_yosys_resources_v3.py --validate-only
& 'C:\Program Files\Inkscape\bin\python.exe' experiments/fault_injection_1024/common/tools/run_pfft_yosys_resources_v3.py --preflight
& 'C:\Program Files\Inkscape\bin\python.exe' experiments/fault_injection_1024/common/tools/run_pfft_yosys_resources_v3.py --synthesize --attempt attempt1
```

S02 调度命令已经完成一次，不得重跑；其余命令从输入 manifest 开始各运行一次。
失败即保留证据并停止，不静默重试。

## 7. Yosys 判据

三顶层 input validation、preflight 和正式综合必须退出 0，无关键 blackbox、
关键 warning 或缺失指标。除总 DSP 外，必须审计逐级 DSP/通用复乘分布及 TMR
副本保留，防止总数碰巧相同。

若 Yosys DSP48E1 不等于 `P0=464 / P1=736 / P2=1392`：

- 原样保留 `yosys_raw_measurements_attempt1.json` 和日志；
- 状态标为 `BLOCKED_D95_THEORY_MISMATCH`；
- 不生成论文可用的正式比较表；
- 不修改 RTL 或结果迎合预算后静默重跑。
