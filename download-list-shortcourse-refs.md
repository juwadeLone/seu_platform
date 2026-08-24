> 视图副本，方便聊天内点击预览；正本在 second brain vault 的 wiki/projects/ 下。

---
title: 待下载文献清单 · 重离子束 short course 系列引文
type: project
tags: [SEE, 下载清单, 参考文献]
updated: 2026-08-23
---

> For future agent: short course 2026 第一个报告（凡人造芯传六节）的高价值引文下载清单；库内核对日期 2026-08-23（对 lit-cache 1236 篇全文按作者/DOI/标题检索，均不在库）；下载后丢 F 盘论文夹 → 重跑 tools/ 管线入库

# 待下载文献清单 · 重离子束 short course 系列引文

来源：凡人造芯传「从太空粒子到地面重离子束」六节（short course 2026 第一个报告）参考文献 [101]–[105]、[73][74][43][93]–[100] 等，经库内查重后筛出对 layout_ecc_platform 有直接补充作用的 8 篇。

## ✅ 下载进度（2026-08-23：**8/8 全部入库**）

- 已下载入 `C:\朱奥☆☆☆☆☆☆☆☆科研\朱奥博士看论文\凡人造芯\`，管线已重跑入库：
  - 第 1 篇 Pellish 屏蔽（文件名 20110015411.pdf）→ **library/01**
  - 第 2 篇 Likar DART（Initial_In-Flight_Error_Rates…pdf）→ **library/09**（无 OA 版，用户自行获取）
  - 第 3 篇 Tylka CREME96 → library/01；第 4 篇 Pellish 1GeV Fe → library/01
  - 第 5 篇 Reed 输运文集（065307341.pdf）→ library/01；第 6 篇 Guild TOR → library/01
  - 第 7 篇 ESCC 25100 → library/01；第 8 篇 Ginet AE9/AP9（s11214-….pdf）→ **library/09**（人工改判）
- 额外收获：用户一并下载的 *On-board fault-tolerant SAR processor for spaceborne imaging radar systems* 已入 **library/04_SAR成像容错**
- 管线升级：`tools/overrides.csv` 人工覆写机制上线（match→category/action），4 个工作笔记与 Ginet 改判已固化，重跑 classify 不再丢人工判定

## 第一优先级：补 σ 标定与在轨验证缺口

1. **Pellish et al. 2010** — "Impact of Spacecraft Shielding on Direct Ionization Soft Error Rates for Sub-130 nm Technologies," *IEEE Trans. Nucl. Sci.*, Vol. 57, No. 6, pp. 3183–3189, Dec 2010. DOI: `10.1109/TNS.2010.2084595`
   - 用途：屏蔽→LETeff→软错误率的方法论原文，平台 σ 标定缺口的理论框架
   - 建议归库：01_SEU机理与软错误建模

2. **Likar et al. 2023** — "Initial In-Flight Error Rates for 16-MB SRAM as Flying on the Double Asteroid Redirection Test (DART) Mission," *IEEE Trans. Nucl. Sci.*, Vol. 70, No. 4, pp. 426–433, Apr 2023. DOI: `10.1109/TNS.2022.3229973`
   - 用途：在轨实测 SRAM 错误率，平台预测结果的对照锚点
   - 建议归库：09_平台器件与在轨测试

3. **Tylka et al. 1997** — "CREME96: A Revision of the Cosmic Ray Effects on Micro-Electronics Code," *IEEE Trans. Nucl. Sci.*, Vol. 44, No. 6, pp. 2150–2160, 1997. DOI: `10.1109/23.659030`
   - 用途：CREME96 源头文献，平台环境输入的规范引用
   - 建议归库：09_平台器件与在轨测试

4. **Pellish et al. 2010** — "Heavy Ion Testing With Iron at 1 GeV/amu," *IEEE Trans. Nucl. Sci.*, Vol. 57, No. 5, pp. 2948–2954, Oct 2010. DOI: `10.1109/TNS.2010.2066575`
   - 用途：掠入射 MCU、RPP 余弦修正失效，对应"打击位置布局"研究
   - 建议归库：01_SEU机理与软错误建模

## 第二优先级：工具链与标准化

5. **Reed et al. 2013** — "Anthology of the Development of Radiation Transport Tools as Applied to Single Event Effects," *IEEE Trans. Nucl. Sci.*, Vol. 60, No. 3, pp. 1876–1911, Jun 2013. DOI: `10.1109/TNS.2013.2262101`
   - 用途：SRIM/Geant4/FLUKA/MCNP 输运工具选型与谱系
   - 建议归库：01_SEU机理与软错误建模

6. **Guild et al. 2021** — "Best Practices for Generating Space Environment Specifications with Modern Tools," Aerospace Technical Report No. TOR-2022-00016, Dec 2021.（Aerospace Corp 技术报告，无 DOI，官网或 NASA NTRS 找）
   - 用途：环境规范制定最佳实践，贯穿全课程的方法论主干 [1]
   - 建议归库：09_平台器件与在轨测试

7. **ESCC 25100** — "Single Event Effects Test Method and Guidelines," European Space Components Coordination Basic Specification No. 25100, Issue 2, Oct 2014.（ESCC 官网免费）
   - 用途：SEE 测试国际标准（通量/注量建议出处 [73]）
   - 建议归库：09_平台器件与在轨测试

8. **Ginet et al. 2013** — "AE9, AP9 and SPM: New Models for Specifying the Trapped Energetic Particle and Space Plasma Environment," *Space Science Reviews*, Vol. 179, pp. 579–615, 2013. DOI: `10.1007/s11214-013-9964-y`
   - 用途：AP9/AE9 环境模型原文，平台环境输入升级路径（替代 CREME96 内嵌 AP8）
   - 建议归库：09_平台器件与在轨测试

## 暂不下载（第三档，做地面束流实验时再议）

- [93] Buchner 2011 VDBP 方法（DOI: 10.1109/TNS.2011.2170587）；[94] Roche 2014 VDBP 验证（DOI: 10.1109/TNS.2014.2367593）
- [95]–[97] CERN 碎片束三篇（DOI: 10.1109/TNS.2018.2883501 / 10.1109/TNS.2022.3210403 / 10.1109/TNS.2024.3396737）

## 已在库、无需下载（概念页已挂链）

- Hansen et al. 2025, "A Review of Single-Event Upset-Rate Calculation Methods," TNS 72(4) — F 盘翻转概率计算模型夹
- Xapsos, "The SEE Environment of Space," TAMU Bootcamp 讲义 — nasa项目夹
- Sajid et al. 2015, OMERE LEO 环境预测 — 辐射软防护/梅林-伯格夹
