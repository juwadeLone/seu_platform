# N07-S1-MIDSTAGE-3920-V1

状态：`PASS / COMPLETE`  
日期：2026-08-14  
τ=5（D162 标定）。8×7×2×35=3920。TMR 9–10 不注入。  
实测：corrected=3534，bounded=292，unbounded=86，MISCORRECTION=8；Gao 3826/3920=97.60%。Stage 6 最差（含 8 枪误纠正）。

## 命令

```bash
bash experiments/fault_injection_1024/results/n07_s1_midstage_3920_v1_001/run_inject.sh 5
```

## PASS / FAIL

1. 八个 `SUMMARY threshold=5 total=490`
2. TRIAL 合计 3920
3. 四分类原样记录
4. 不覆盖 `n07_s1_gao2023_v1_001`

## 不做

改论文；开 Vivado；TMR 9–10；写成 700 分母。
