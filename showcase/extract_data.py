# Extract real data for the SEU showcase page:
# 1) downsampled CREME96 LET spectra (7 species) -> spectra.json
# 2) coarse occupancy bitmap from primitive_map.csv -> layout.json
import csv, json, math, os

BASE = r"C:\hermes\layout_ecc_platform"
SRC = os.path.join(BASE, "showcase", "data_src")
OUT = os.path.join(BASE, "showcase")

SPECIES = ["H", "He", "C", "O", "Mg", "Si", "Fe"]

spectra = {}
for sp in SPECIES:
    pts = []
    with open(os.path.join(SRC, f"spenvis_{sp}.let.txt")) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            a, b = line.split()
            pts.append((float(a), float(b)))
    # downsample to ~60 log-uniform points
    if len(pts) > 60:
        lo, hi = math.log10(pts[0][0]), math.log10(pts[-1][0])
        picked = []
        for i in range(60):
            target = 10 ** (lo + (hi - lo) * i / 59)
            best = min(pts, key=lambda p: abs(p[0] - target))
            if not picked or best[0] != picked[-1][0]:
                picked.append(best)
        pts = picked
    spectra[sp] = [[round(x, 6), round(y, 12)] for x, y in pts]

with open(os.path.join(OUT, "spectra.json"), "w") as f:
    json.dump(spectra, f, separators=(",", ":"))
print("spectra species:", {k: len(v) for k, v in spectra.items()})

# occupancy bitmap
csv_path = os.path.join(BASE, "code", "layout_ecc_sim", "data", "layout", "p1_ooc_win", "primitive_map.csv")
max_x = max_y = 0
cells = set()
with open(csv_path, newline="", encoding="utf-8") as f:
    r = csv.DictReader(f)
    for row in r:
        if row["is_used"] != "1" or not row["grid_x"]:
            continue
        x, y = int(row["grid_x"]), int(row["grid_y"])
        cells.add((x, y))
        max_x, max_y = max(max_x, x), max(max_y, y)
print("occupied sites:", len(cells), "grid:", max_x + 1, "x", max_y + 1)

W, H = 96, 240  # display bins (chip is tall: x small, y large)
bw = (max_x + 1) / W
bh = (max_y + 1) / H
bitmap = [[0] * W for _ in range(H)]
for (x, y) in cells:
    bitmap[min(int(y / bh), H - 1)][min(int(x / bw), W - 1)] += 1
maxv = max(max(row) for row in bitmap)
bitmap = [[round(v / maxv, 3) for v in row] for row in bitmap]
with open(os.path.join(OUT, "layout.json"), "w") as f:
    json.dump({"w": W, "h": H, "cells": bitmap}, f, separators=(",", ":"))
print("bitmap max density:", maxv)
