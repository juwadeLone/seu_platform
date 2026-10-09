# data/tid/ — 总剂量文件投放处

把 **SPENVIS SHIELDOSE-2**（或等效）剂量输出放到本目录。软件**只解析并展示文件里已有的数字**，不会从 LET 谱计算 krad，也不会发明 TID 率。

## 当前状态

本目录除本 README 外没有剂量文件 → `/api/effects` 的 `tid_slot.status` 为 `MISSING`，效应表 TID 行为 `data_missing`。

## 接受的文件

- `.json`：原样读入。若键名含 `dose` / `krad` / `gray` / `gy` / `rad` 且值为数字，则作为“来自文件的字段”列出。
- `.txt` / `.dat` / `.dose`：按行提取至少两个数字的表（常见 SHIELDOSE 厚度–剂量表）。单位保持文件原文，不做 rad↔krad 换算。

不要把 `env_data/spenvis_let/*.let.txt`（LET 微分通量）拷到这里充剂量——那不是 SHIELDOSE 输出。

投放后重启仿真器，效应总览页会显示解析结果；解析成功也不等于开始做 TID 损伤仿真。
