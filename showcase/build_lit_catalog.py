# Build literature catalog from the PhD paper archive (read-only) into the vault.
# Output: wiki/literature/文献目录全表.md (full table) + stats for the curated map.
import os, json, collections

ROOT = r"C:\朱奥☆☆☆☆☆☆☆☆科研\朱奥博士看论文"
VAULT = r"C:\hermes\fpgahorizons-journal"
OUT_DIR = os.path.join(VAULT, "wiki", "literature")
os.makedirs(OUT_DIR, exist_ok=True)

rows = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    rel_dir = os.path.relpath(dirpath, ROOT)
    for fn in filenames:
        ext = os.path.splitext(fn)[1].lower()
        full = os.path.join(dirpath, fn)
        try:
            size = os.path.getsize(full)
        except OSError:
            size = -1
        rows.append({"dir": rel_dir, "file": fn, "ext": ext, "size": size})

ext_stat = collections.Counter(r["ext"] for r in rows)
top_dirs = collections.Counter(r["dir"].split(os.sep)[0] for r in rows)
print("total files:", len(rows))
print("ext:", dict(ext_stat.most_common(12)))
print("top-level dirs:", len(top_dirs))

# full table, grouped by top-level dir
lines = ["# 博士文献目录全表", "",
         "> 机器生成（2026-08-22）。根目录：`C:\\朱奥☆☆☆☆☆☆☆☆科研\\朱奥博士看论文`（指针，不复制）。",
         "> 共 %d 个文件。按相对路径分组。重扫脚本：`C:\\hermes\\layout_ecc_platform\\showcase\\build_lit_catalog.py`。" % len(rows), ""]
cur = None
for r in sorted(rows, key=lambda x: (x["dir"], x["file"])):
    if r["dir"] != cur:
        cur = r["dir"]
        lines.append("## %s" % cur)
        lines.append("")
    sz = ("%.1f MB" % (r["size"] / 1048576)) if r["size"] > 1048576 else ("%d KB" % (r["size"] // 1024) if r["size"] >= 0 else "?")
    lines.append("- `%s`（%s）" % (r["file"], sz))
    if r["dir"] != cur:
        pass
    # blank line after group handled at next header
with open(os.path.join(OUT_DIR, "文献目录全表.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print("written 文献目录全表.md")
