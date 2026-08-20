# N08 修正指令：多错误 TB 逐级归因分类 + 重跑

记录号：`N08-MULTI-K-S3P1-V2`
日期：2026-08-14
状态：`PLANNED / 待作者执行`
前置：N08 V1 已跑完但分类有 bug（OR 合并误判 miscorr），需修正后重跑

---

## 0. 为什么重跑（一句话）

V1 的 TB 用 `cor_seen = OR(所有注入级 fcor)` 判 miscorr：只要有一级纠正成功
且顶层输出不等，就误判为误纠正。实测三枪样例全是"Stage 7 正确纠 + Stage 8
静默漏检穿透"的组合被错标成 MISCORRECTION。**修正 = 逐级归因，不 OR 合并。**

## 1. TB 修改清单（在 `results/n08_multi_rtl_tb_s3.sv` / `_p1.sv` 上改）

### 1.1 逐级 flag 存数组（不再只 OR）

```verilog
// 每级单独记录，注入时刻 capture 到数组
reg [7:0] det_vec, cor_vec, unc_vec;   // bit i = stage i+1 的 flag
reg [23:0] loc_vec;                    // 每级 3-bit location

// capture_flag(x) 改为：det_vec[stage[x]-1]=fdet[stage[x]-1]; 同理 cor/unc/loc
```

### 1.2 分类逻辑替换（核心改动，逐级归因）

```verilog
// 输入：mismatch_seen（顶层输出是否不等）、det_vec/cor_vec/unc_vec/loc_vec

// 1) 真误纠正：存在某级 g 声称纠正(cor_vec[g]=1)，但该级纠正动作把数据改坏
//    ——用"纠正的 location 与注入 symbol 不符"近似判定
miscorr_found = 0;
for (g=0; g<8; g=g+1) begin
  if (cor_vec[g]) begin
    // 找该枪注入到 stage g+1 的 symbol（从 sites 行解析）
    // 若 loc_vec[g*3 +: 3] != 注入 symbol → 定位错 → 真误纠正
    if (loc_vec[g*3 +: 3] != inject_symbol_of_stage[g]) miscorr_found = 1;
  end
end

// 2) 分类（按优先级）：
if (mismatch_seen == 0) begin
  if (|cor_vec)            category = corrected;        // 全部纠正且输出 bit-exact
  else if (|det_vec)       category = corrected_no_flag; // 理论不该出现，记下
  else                     category = silent_bounded_residual;
end else begin
  if (miscorr_found)       category = MISCORRECTION;    // 真误纠正
  else if (|cor_vec)       category = detected_only;    // 有级纠对了但另有级漏检 → 输出不等，不是误纠
  else if (|det_vec)       category = detected_only;
  else                     category = silent_unbounded;
end
```

**关键语义变化**：
- `MISCORRECTION` 现在只留给"location 定位错"的真误纠正
- "某级纠对 + 另一级静默漏检" → `detected_only`（输出不等但无级纠错位置错）——这是**正确的归类**，V1 错把它当成 miscorr
- silent_bounded / silent_unbounded 重新按 `|det_vec==0` 判定，不再被 OR 吃掉

### 1.3 每枪打印逐级向量（诊断 + 事后可审计）

```verilog
$display("TRIAL trial=%0d k=%0d injected=%0d match=%0d det=%b cor=%b unc=%b loc=%h category=%s",
         trial, K_MODE, inj_count, !mismatch_seen, det_vec, cor_vec, unc_vec, loc_vec, category);
```

## 2. 执行顺序（先回归，后正式）

```bash
# 0) 位点表沿用 V1（种子 20260814，不用重新生成）
ls results/n08_multi_k{2,5,8}_s3_v1_001/sites_k*.csv

# 1) 回归：k=1 小样 36 枪（单错误），必须与 N07 单错误分类一致
iverilog -g2012 -o sim_regress_s3 n08_multi_rtl_tb_s3.sv n08_s3_multifault_top.sv <依赖>
vvp sim_regress_s3 +K_MODE=1 +TRIALS=36
#   检查：corrected+bounded+unbounded 合计=36；bounded 与 N07 silent 位点吻合

# 2) 正式六组（S3 三组 + P1 三组），每组一个新目录 v2：
#    results/n08_multi_k2_s3_v2_001/ 等
iverilog -g2012 -o sim_k2_s3 n08_multi_rtl_tb_s3.sv n08_s3_multifault_top.sv <依赖>
vvp sim_k2_s3 +SITE=.../sites_k2.csv > run_k2_s3.log

# 3) 汇总：每组的 SUMMARY 行填进下表
```

## 3. 验收标准（全过才算 PASS）

1. 回归：k=1 36 枪分类与 N07 单错误行为一致（无 miscorr、silent 位点吻合）
2. 正式六组：每枪 injected=k、四分类合计=枪数、无 timeout
3. **miscorr 判定的每一枪，必须能在 log 里看到 loc != 注入 symbol 的证据**
4. 若有真 miscorr：记录完整位点组合（级/符号/分量/bit）与 loc，回报

## 4. 预期（对账用）

- **miscorr 预期 = 0**（与 k=1 及机制判断一致；V1 的 50 枪应全部重分类为 detected_only 或 silent_unbounded）
- bounded / unbounded 重新出现，且随 k 增大而增多（多 silent 残差叠加）
- corrected 随 k 下降（每枪至少一枪出错被纠的概率模型）

## 5. 不能做什么

- 位点表不要重新生成（保持种子 20260814，与 V1 同位置才能直接对比）
- 不要改 τ（S3=2, P1=3）、不要动 TMR、不要改激励
- V1 的 50 枪 miscorr **不得写入论文**，等 V2 重分类结果

## 6. 产出

每组 `run_k{k}.log`（含逐级向量行）+ `combined_summary.txt` + `AUDIT.md`，
丢给我对账 + 更新问题网。
