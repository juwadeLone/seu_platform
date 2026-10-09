# X post draft — seu_platform launch thread

## Main post (EN)

I'm building an open-source simulator of space-radiation effects on SRAM
FPGAs — the layer SPENVIS doesn't have.

SPENVIS tells you what radiation is on your orbit.
seu_platform tells you what that radiation does to your design:

orbit env → per-bit upset rates (46.2/day whole-chip, within 10% of Lee
et al. IEEE REDW 2014) → ion strike on a real Vivado layout → module &
mission consequences → mitigation advice + RHA report.

- Any orbit SPENVIS covers (import spenvis_gcf.txt / .let.txt / proton spectra)
- Your own placed&routed design via primitive_map.csv
- "Validate your ECC scheme" — real inferred codeword mapping
- Every number carries provenance; gaps are labelled gaps, never invented
- pip install . && seu-platform — stdlib only, no deps

Live demo + docs + code: https://juwadelone.github.io/seu_platform/
https://github.com/juwadeLone/seu_platform

## Follow-up (what I'd ship next with Devin Max)

- Trapped-proton σ(E) tables for all domains (LEO/SAA full coverage)
- Solar-particle-event worst cases (CREME96 worst week/day)
- A second device family with real beam data (UltraScale / RTG4)
- Per-net consequence granularity; golden fault-injection validation set
- PyPI release + hosted public instance

## 中文附贴（可选）

做 SPENVIS 的下游：它告诉你轨道上有什么辐射，这个平台告诉你辐射把你的
设计打成什么样。全链：轨道环境→每 bit 翻转率（Lee 2014 交叉验证差
10%）→离子打在真实 Vivado 布局→模块/任务后果→加固建议+RHA 报告。
数字全带出处，缺数据标 gap 不编数。
