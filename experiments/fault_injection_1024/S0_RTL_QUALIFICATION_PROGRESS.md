# S0 RTL资格验证分步记录

- 总记录号：`S0-RTL-QA-001`
- 当前步骤：`S0-RTL-QA-001-S01`
- 当前状态：`S01_COMPLETE / S02_NOT_STARTED / SIMULATION_NOT_RUN`
- 启动日期：`2026-07-23`

## 六步顺序

| 步骤记录号 | 内容 | 状态 |
|---|---|---|
| `S0-RTL-QA-001-S01` | 保存修改前快照 | `COMPLETE` |
| `S0-RTL-QA-001-S02` | 将`tb_s0.sv`展开为独立testbench | `NOT_STARTED` |
| `S0-RTL-QA-001-S03` | 增加可选波形开关 | `NOT_STARTED` |
| `S0-RTL-QA-001-S04` | 修正qualification runner的PASS标记 | `NOT_STARTED` |
| `S0-RTL-QA-001-S05` | 运行S0冒烟测试并查看GTKWave | `NOT_STARTED` |
| `S0-RTL-QA-001-S06` | S0 bit-exact通过后再推广至其余六工程 | `NOT_STARTED` |

六步必须串行执行。每一步完成、复核并向作者报告后，才可接受下一步授权。

## S01快照

- 路径：
  `archive/migration/2026-07-23/S0-RTL-QA-001-S01_pre_modification_snapshot/`
- 载荷：31个文件，565,928字节；
- 源文件与快照副本SHA-256不一致数：0；
- 清单SHA-256：
  `BD4E57D28058C189F898CF2CAFC0CDE4CA5B6180550D71F0E317618D330016F3`。

## 后续资格判据冻结

在后续步骤修改testbench或runner时，不得改变以下功能判据：

- 输入向量：
  `common/vectors/qualification_input_10frames.hex`；
- SubFFT期望向量：
  `common/vectors/qualification_subfft_expected_8frames.hex`；
- 比较输出：2,048个四路复数beat，280位逐bit一致；
- S0首输出延迟：268周期；
- `out_last`：仅在每帧第255个有效输出beat置位；
- timeout：6,000周期；
- S0不声明检测、纠错或掩蔽能力。

波形仅用于调试，不替代上述自动PASS/FAIL判据。

## 当前禁止

S01不授权修改`tb_s0.sv`、公共TB模板或runner，不授权运行Icarus/vvp，
不授权启动GTKWave，也不授权其余六工程的testbench改造。
