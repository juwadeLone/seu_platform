# 无界面批跑：P1 示例

从仓库根目录进入 `code/layout_ecc_sim`，使用 Python 3.10+（仅标准库）：

```sh
cd code/layout_ecc_sim
python -m layout_ecc.campaign --out campaign-p1
```

默认读 [P1 样例场景](../code/layout_ecc_sim/data/campaign_p1_smoke.json)，并报告仓库里已有的 MEO 基线（约 46.16 翻转位/天，**不是重算**）。示例按输入顺序运行三次指定打击，包含多位翻转和空命中；这些打击**不是**从该轨道谱抽样的，不能据此计算在轨功能错误率。批跑本身只产出翻转记录；保护开关对比见下文。

## 配置与输出

用 `--scenario path/to/scenario.json` 选择其他配置。布局 CSV 与黄金向量路径相对该场景文件；黄金向量记录在清单中，用于对齐后续回放工作负载，本命令不运行 FFT。当前布局解读仍按 P1/XC7VX690T，不代表支持任意器件与设计。

- 每个 case 给出唯一 `id`、`let`（MeV·cm²/mg）、`theta_deg`（0–75°）、`phi_deg`（0–360°）和非空的 `seeds`（不重复的非负整数）。
- 打击中心填 `preset`，或同时填写 `x0`、`y0`、`a0`（RPM 布局格；`a0` 只影响 `legacy_linear` 的核尺寸）。
- `kernel_model` 支持 `anchored` / `legacy_linear`，`flip_model` 支持 `weibull` / `bernoulli` / `pattern`。后两种是代理模式。

`--out` 必须是不存在的目录，不会覆盖已有证据。成功运行生成两个文件：

| 文件 | 内容 |
|---|---|
| `events.jsonl` | 每行一次打击。稳定的 `event_id = case_id/seed`、独立 seed、完整打击参数、候选计数与原始 `flipped` 记录；保留空命中、未翻转和实际翻转重数。Site/域记录不是准确 bit 地址。 |
| `run_manifest.json` | 源码版本与工作区状态、Python 版本、场景/布局/黄金向量/模型输入的 SHA-256、轨道数据来源与分域率、事件统计与事件文件 SHA-256。此文件最后写入；缺失即表示运行未完成。 |

相同检出版本、Python 和输入使用不同输出目录重跑，事件及清单内容相同。运行结果不写入布局、谱或冻结实验目录。

## 复算轨道与 CI

公开 PR 和 master CI 用冻结快照，不访问私有 `tcas`；依赖实算的旧测试会显式列为跳过。拥有 [tcas](https://github.com/juwadeLone/tcas) 读取权限时，将其检出到 [固定提交](../code/layout_ecc_sim/orbit-seu.rev)，设置 `ORBIT_SEU_ROOT` 指向该检出的 `code/orbit_seu`，再运行：

```sh
export ORBIT_SEU_ROOT=/path/to/tcas/code/orbit_seu
python -m layout_ecc.campaign --live-orbit --out campaign-p1-live
```

Windows PowerShell 用 `$env:ORBIT_SEU_ROOT = 'C:\path\to\tcas\code\orbit_seu'`。实算路径要求 Git、固定提交与干净的 orbit_seu 子树，不合条件或结果偏离冻结基线就失败，不回退到快照。实算清单额外记录配置、LET 谱及谱 manifest 的哈希。

合并后若需要在 GitHub 手动实算，在 [仓库 Environments 设置](https://github.com/juwadeLone/seu_platform/settings/environments) 中建 `orbit-seu-integration`，部署分支只允许 `master`，并设环境 secret `ORBIT_SEU_READ_TOKEN`（仅限 `tcas` 的 Contents 读取权限）。然后在 [Headless campaign Actions](https://github.com/juwadeLone/seu_platform/actions) 从 `master` 手动运行。此凭据不用于 PR 作业；实算作业不上传私有依赖或产物。

## 无保护 / 有保护对比

```sh
python -m layout_ecc.campaign --scenario data/campaign_p1_ff.json --out campaign-p1-ff
python -m layout_ecc.compare --events campaign-p1-ff/events.jsonl
```

[FF 场景](../code/layout_ecc_sim/data/campaign_p1_ff.json)：30 个已映射码字的 FF Site（算术 [6,4,3]、存储 SECDED、TMR 各 10 个）为打击中心，LET 60、Weibull、每点 64 个 seed，共 1920 次打击（约 3 分钟）。P1 布局没有 BRAM_STATE Site，故只覆盖 FF。`compare` 用同一份故障清单分别关闭/打开保护回放（`layout_ecc.joint_replay`），写出 `comparison.json`：`outcomes` 按整次事件分类（含 CFG 或未映射位即 UNMAPPED，绝不算 CORRECTED）；`mapped_outcomes` 只看同一事件中已映射的 FF 位。字内比特位按 seed 抽样，未建模寿命屏蔽；结果是受控仿真，不是在轨错误率。
