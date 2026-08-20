# P1-PY-V3-001 Python audit

## 状态

`PYTHON_VERIFIED / RTL_STALE_NOT_MODIFIED / YOSYS_NOT_RUN`

## 当前保护边界

- Stage 1--7：旋转因子交换后的`[6,4,3]`算法ECC；
- Stage 8--9：完整级TMR；
- Stage 10：相邻两拍的四个完整蝶形；upper/lower分别形成`[6,4,3]`码字；
- Stage 8跨位置、跨帧ECC与pending buffer不属于当前P1。

## Python gate

- 状态：`VERIFIED`；
- 两拍组：128；
- upper码字：128；
- lower码字：128；
- 覆盖物理输出：1024/1024，零重复、零遗漏；
- Stage 10单符号分量位注入：107,520；
- 注入失败：0；
- 功能不匹配：0；
- 补偿后闭合失败：0；
- 输入对齐：1 beat；
- 输出对齐：1 beat；
- 裸数据对齐寄存器：560 bit；
- 若对齐寄存器使用78-bit SECDED码字：624 bit。

gate SHA-256：
`76E2F8FEE4576007DA4CC036707842793FED675CD8664A27E9B486AE2B019BC4`。

## P1独立campaign

- 状态：`VERIFIED`；
- trials：124,834/124,834；
- failures：0；
- SDC：0；
- 二次进程内完整重放：PASS；
- Stage 1--7 arithmetic ECC：每级1,680个computation trials；
- Stage 1--7 memory SECDED：每级312个storage trials；
- Stage 8--9 TMR：每级840个computation和840个storage trials；
- Stage 10 arithmetic ECC：107,520个computation trials；
- no-fault：8；
- declared out-of-capability：2。

summary SHA-256：
`EBCB457E4FC2718EA719B51EA93932EF0996FCB9DADA84EE495E04C49BCED920`。

raw CSV SHA-256：
`5A12E2A65DBBFC7449537F826246FC305E8429C22034A5CE5DC5781B48626827`。

## 证据边界

本证据只证明Python数学分组、定点功能闭合和受控单故障恢复。当前P1 RTL仍为
历史`PFFT-RES-V3-001` Stage-8单check-pair实现，尚未按新边界修改、进行
cycle-exact qualification或Yosys资源估计。
