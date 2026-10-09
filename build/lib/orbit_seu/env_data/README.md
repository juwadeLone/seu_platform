# env_data — 真实辐射数据/模型文件的存放位置

本目录存放激活“真实模型”模式所需的**用户获取的公开数据**（工具本身不捆绑、
不虚构任何通量数字）。

## 0. SPENVIS CREME96 真实 GCR 谱（已打通，推荐）✅

- 在 **SPENVIS**（www.spenvis.oma.be，ESA 免费注册）中：生成轨道 →
  **GCR particle model → CREME96 (Sol. Minimum)** → 下载 `spenvis_gcf.txt`，
  放到本目录。
- 本工作区已随附一份已导入的真实谱：
  - `spenvis_gcf.txt` —— 原始 SPENVIS 输出（CREME96 solar-min，H→U 全 92
    元素，1 MeV/n–1e5 MeV/n；本项目下它取自 **20200 km / 55°** 轨道，已含
    SPENVIS 施加的地磁屏蔽）
  - `spenvis_let/` —— 由 `scripts/spenvis_to_let.py` 生成的 6 组微分 LET 谱
    （H、He、Z3–10、Z11–20、Z21–28、Z29–92，覆盖全部 92 种），默认过 100 mil Al
    屏蔽、Bethe LET；`manifest.json` 记录来源轨道、屏蔽与哈希。`files` 模式直接读取，
    轨道与 manifest 不符时拒绝计算。
- **量级验证已通过**：H 在 1 GeV/n ≈ 1.2×10⁴/(m²·s·sr·GeV)，质子积分通量
  ≈ 4.1/cm²·s，与公认太阳极小 GCR 一致。
- **GUI 用法**：环境模式选 **“SPENVIS CREME96 真实 GCR 谱（已导入）”**
  即直接用它积分，无需其它配置。
- **改轨道**：SPENVIS 谱携带它生成时那条轨道的屏蔽。要评估其它轨道，请在该
  轨道下重新跑 SPENVIS GCR 并 `python scripts/spenvis_to_let.py` 重转换。

## 1. `oneill_lis_coefficients.csv` — BON14 系数（标度待核实，勿用于任务评估）

- 由 `scripts/make_oneill_lis_csv.py` 按 **NASA/TP-2015-218569**（BON2014
  模型）Table 2 + 式(2) 生成。
- **谱形（相对丰度、能量斜率）正确，但直接复现的绝对通量比实测 GCR 低约
  12 个数量级**——BON 论文发表的 LIS 参数表与其实测模型的绝对标度存在
  断裂。**本文件不得用于任务级 SEU 评估**；真实评估请用 SPENVIS CREME96
  谱（第 0 节，files 模式）或提供其它已标定 LIS 源。
- 文件格式（`bo_gcr` 模式读取）：
  `Z,A,J0,gamma0,gamma1,gamma2,R0_GeV,R1_GeV`
- 函数形式（工具按此式计算 LIS）：
  `J_LIS(R) = J0 · R^g0 · (1+(R/R0)^2)^((g1-g0)/2) · (1+(R/R1)^2)^((g2-g1)/2)`
  （平滑双折断幂律：R<R0 斜率 g0，R0–R1 间 g1，>R1 g2）
- 调制势 φ 在任务配置里给 `environment.phi_mv`（太阳极大期≈300–400，
  极小期≈800–1200；缺省 600）。

## 2. `ae9ap9/` — 束缚辐射真实数据（ae9ap9 模式）

- 下载 **AE9/AP9-IRENE v1.50 公开程序包**（美空军 AFRL/SET 发布，
  https://www.vdl.afrl.afmil/programs/ae9ap9/ ，公开注册后可下载，
  约 100–700 MB），解压到本目录：
  ```
  env_data/ae9ap9/ae9ap9.exe        # 或在配置里指定 exe_path
  env_data/ae9ap9/<数据目录>        # 随包携带
  ```
- 工具自动：按你的轨道生成星历文件 → 调用 exe → 解析输出的
  能量-通量表 → 作为质子谱进入事件率积分。
- 运行结果缓存在 `env_data/ae9ap9/runs/`，每次任务的星历与输出哈希
  记入报告溯源。
- 屏蔽（mil Al）在包内配置；本工具按 0 mil 处理并在报告注明。

## 3. 备用：`files` 模式（任意导入）

SPENVIS / CREME96 网页导出的 LET 谱与质子谱文本，直接在配置里指向文件路径
即可（见主 README“工程级使用”节）。这也是第 0 节 SPENVIS GCR 谱进入工具
的通道。

## 数据获取核对清单

| 文件 | 来源 | 许可 | 放置路径 |
|---|---|---|---|
| oneill_lis_coefficients.csv | NASA/TM-2013-217978 表格整理（标度待核实） | 公有领域 | env_data/ |
| ae9ap9 程序包 v1.50 | AFRL/SET 公开发布 | 公开发布许可 | env_data/ae9ap9/ |
| spenvis_gcf.txt (CREME96) | SPENVIS 在线导出 | 免费 | env_data/ |
