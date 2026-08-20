# PFFT-RES-V2-001：PFFT 三工程资源重新评估合同

状态：`BLOCKED_BY_D94 / PRE_D94_CONTRACT_SUPERSEDED / NOT_EXECUTED`

> **停止使用说明（D94）**
>
> 本合同在 D94 冻结前错误地把一个完整蝶形单元内部的 feedback、
> upper 和 lower 路径继续向下拆分，并把 upper 与 feedback 当成两套
> 独立复乘资源。D94 已冻结：ECC 的最小保护与资源计数单元是完整
> radix-2 SDF 蝶形单元；`[6,4,3]` 表示 4 个功能蝶形加 2 个校验
> 蝶形，共 6 个完整蝶形。含非平凡旋转时，每个完整蝶形只拥有并复用
> 一个通用复乘，当前结构诊断口径为 16 DSP48E1，因此普通 ECC 级应按
> \(6\times16=96\) DSP 诊断，不得按“6 路 upper + 6 路 feedback”
> 重复计为 192 DSP。
>
> 下文保留为修改前合同及失败证据的历史记录，其中原 DSP 诊断表和
> upper/feedback 分立表述均已失效。重写合同、RTL 和 PASS/FAIL 判据
> 并重新获得作者批准前，禁止执行 `qualification_attempt2`、Yosys
> preflight 或正式综合。

## 目的与边界

本记录只重新评估 1024 点、四通道、十级 radix-2 PFFT 的三个完整工程：

| ID | 工程 | 角色 |
|---|---|---|
| P0 | `projects/P0/` | 无防护完整基线 |
| P1 | `projects/P1/` | 本文逐级算术 ECC 架构 |
| P2 | `projects/P2/` | 逐级完整 TMR |

本次采用 D89、D90 的冻结口径修正 RTL 后，以指定 Yosys 同流比较
LUT/LC、FF、DSP48E1、BRAM 和 distributed memory。结果只属于
`Yosys xc7 synthesis resource estimate`，不属于 Vivado
post-implementation、时序、Fmax、功耗或板级实测。

冻结 V1 结果保持原样，只作为旧通用复乘实现的历史对照；本次不得覆盖
`results/seven_arch_v1/`。

## 预先冻结的 RTL 纠正规则

1. 加减法、符号变换和选择逻辑归入 LUT/LC；寄存器另计 FF。
2. 非平凡通用复乘使用 `fft_complex_mul_q28`，按 Yosys 实际映射统计 DSP。
3. \(1,-1,\pm j\) 使用连线、实虚交换和二进制补码取负，不实例化通用复乘。
4. 公平性要求 P0、P1、P2 的 Stage 1 同时采用相同平凡旋转原语。
5. P1 Stage 1--7 的 lower branch 指数恒为 \(W^0=1\)，直接旁路，不实例化
   6 路通用复乘。
6. P1 Stage 1 的 upper rotation 与 feedback rotation 只取
   \(\{1,-j\}\)，各 6 路改用平凡旋转原语。
7. P1 Stage 2--7 的 upper/feedback 非平凡同算子复乘、Stage 8 缓冲辅助
   ECC、Stage 9--10 局部 TMR、所有编码/译码和存储策略均不得借本次评估改变。

## 运行前结构推导

当前冻结 V1 的 `fft_complex_mul_q28` 每个复乘映射为 16 个 DSP48E1。按上述
RTL 纠正，预先得到以下诊断值；它们用于核对是否还有不应存在的通用复乘，
不是通过修改结果迎合的目标：

| ID | 应消除的通用复乘 | 预期 DSP48E1 变化 | 从 V1 推导的诊断值 |
|---|---:|---:|---:|
| P0 | Stage 1 四通道共 4 个 | \(-64\) | 512 |
| P1 | 42 个 lower \(W^0\) + Stage 1 的 12 个 \(1/-j\) | \(-864\) | 1568 |
| P2 | Stage 1 三副本四通道共 12 个 | \(-192\) | 1536 |

最终论文数字只能取指定 Yosys 的新结果；若实测不等于诊断值，必须保留差异并
追查结构，禁止回填或修改数据。

## 冻结输入

- 共享 RTL：
  `common/rtl/twiddle_rom_1024.sv`、`fft_common.sv`、
  `protection_rtl.sv`、`datapath_v5.sv`、
  `protection_primitives_v5.sv`、`protected_stages_v5.sv`；
- 三个独立顶层：
  `top_p0_pfft_unprotected.sv`、`top_p1_pfft_ecc.sv`、
  `top_p2_pfft_tmr.sv`；
- 三个独立 testbench：`tb_p0.sv`、`tb_p1.sv`、`tb_p2.sv`；
- 固定输入与期望向量：
  `common/vectors/qualification_input_10frames.hex`、
  `qualification_pfft_expected_8frames.hex`；
- 存储合同：`config/seven_architecture_memory_map.json`；
- 修改前快照：
  `archive/migration/2026-07-23/pre_edit/2026-07-23_PFFT-RES-V2-001_resource_reevaluation/`。

正式 runner 必须在运行时记录全部输入、工具、命令、日志和输出的 SHA-256。

## 固定命令

```powershell
& 'C:\Program Files\Inkscape\bin\python.exe' experiments/fault_injection_1024/common/tools/run_pfft_resource_qualification.py
& 'C:\Program Files\Inkscape\bin\python.exe' experiments/fault_injection_1024/common/tools/run_pfft_yosys_resources.py --validate-only
& 'C:\Program Files\Inkscape\bin\python.exe' experiments/fault_injection_1024/common/tools/run_pfft_yosys_resources.py --preflight
& 'C:\Program Files\Inkscape\bin\python.exe' experiments/fault_injection_1024/common/tools/run_pfft_yosys_resources.py --synthesize --attempt attempt1
```

工具固定为：

- `C:\Program Files\Inkscape\bin\python.exe`（只作标准库编排器）；
- `C:\iverilog\bin\iverilog.exe` 与 `C:\iverilog\bin\vvp.exe`；
- `C:\Users\pc\Downloads\oss-cad-suite\bin\yosys.exe`；
- Yosys 流程固定为 `synth_xilinx -family xc7`。

一次命令只运行一次；失败时停止并保留失败证据，不静默重试。

说明：原计划使用的 `py -3` 在正式执行前的环境检查中指向无法由当前受控
会话启动的用户目录 Python 3.14。该检查没有运行 RTL 仿真或 Yosys。因 runner
只使用 Python 标准库，合同在首次正式执行前将编排器显式冻结为上列可用的
Python 3.12.12，并要求结果记录可执行文件路径与 SHA-256。

## 输出位置

- 首次结构审计失败证据：
  `results/pfft_resource_v2_001/rtl_structure_manifest.json`；
- 待授权的第二次资格结果：
  `results/pfft_resource_v2_001/qualification_attempt2/`；
- Yosys 日志：`logs/pfft_resource_v2_001/`；
- 隔离构建：`build/pfft_resource_v2_001/`；
- 正式表：`results/pfft_resource_v2_001/yosys_pfft_group.csv`；
- 正式汇总：`results/pfft_resource_v2_001/yosys_pfft_summary.json`；
- 审计说明：`results/pfft_resource_v2_001/yosys_pfft_resource_audit.md`。

## PASS/FAIL 判据

仅当以下条件全部满足时记为 `VERIFIED`：

1. P0/P1/P2 分别编译成功并对 2048 个输出 beat 逐 bit 匹配冻结 PFFT 向量，
   延迟均为 525 cycle；
2. 静态审计确认三个 Stage 1 均使用平凡旋转，P1 Stage 1--7 lower branch
   均旁路，P1 的 Stage 8 与 Stage 9--10 保护结构未改变；
3. Yosys 输入验证、三顶层 preflight 和三顶层正式综合均退出 0；
4. 无 critical blackbox、critical warning 或缺失资源指标；
5. P0/P1/P2 存储映射满足冻结合同，同规格存储映射一致；
6. P2 全十级三副本以及 P1 Stage 9--10 三副本均被保留；
7. P1 的 Stage 8 两个 functional pending BRAM、四个 operand-metadata BRAM
   均存在且到顶层数据输出可达；
8. 只做 PFFT 组内比较，P1/P2 只相对 P0 报告逐项绝对值和百分比；不得把
   LUT、FF、DSP、BRAM 相加成“总资源”。

任一条件失败即停止，不生成可用于论文的最终比较表。

## 资格 attempt1 失败记录

首次资格命令在仿真前停止。九项结构检查通过，一项
`p0_is_complete_unprotected_baseline` 失败。只读诊断确认 P0 完整八级实例
位于 `pfft_functional_pipeline_v5`，而审计器错误地只截取其外层
`pfft_functional_core_v5` 包装模块；这是审计范围错误，不是 P0 RTL 结构失败。

- 失败 manifest SHA-256：
  `CA689B086FFF1A668C893964B23FCA3D109BB87BFDCC701A265045E6243C2D66`；
- 失败 runner 快照 SHA-256：
  `45DBD7D3F13BA06ED5611466A0608D09965373119CDFCF0859B15DC6D4ED6722`；
- P0/P1/P2 RTL 仿真次数：0；
- Yosys 执行次数：0。

审计器已改为检查 `pfft_functional_pipeline_v5`，第二次资格输出使用隔离的
`qualification_attempt2/`，不得删除或覆盖 attempt1。重新执行须由作者确认。
