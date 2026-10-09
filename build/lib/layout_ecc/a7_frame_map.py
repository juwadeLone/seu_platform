"""Tile / site -> CRAM frame bounding box for Artix-7.

7-series tiles do NOT carry a FRAME/FAR property in Vivado 2018.3
(see CSA PBLOCK0 S7 PoC). Mapping therefore has two layers:

1. Always: site/tile -> clock_region + tile column + tile kind
   -> frame_bbox_id = '{clock_region}|{kind}|COL{tile_x}'
2. Optional: JSON column table (UG470 / XAPP538 / SEM S dump) attaching
   integer frame_lo..frame_hi. Absent table => frame range is None;
   injection must not invent LFA from the UG470 bits/slice share.

Never use layout_ecc.domains.CFG_BITS_PER_SLICE as a location.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

TILE_XY = re.compile(
    r"(?P<kind>[A-Z0-9_]+)_X(?P<x>\d+)Y(?P<y>\d+)$"
)
SITE_XY = re.compile(r"X(\d+)Y(\d+)")

# 7-series clock regions are 50 CLB rows tall (UG472).
CR_HEIGHT = 50


def parse_tile(tile: str):
    """Return (kind, x, y) or None."""
    t = (tile or "").strip()
    m = TILE_XY.search(t)
    if not m:
        return None
    kind = m.group("kind")
    # strip L/R side suffixes that are not the resource class
    # CLBLL_L / CLBLM_R / BRAM_L / DSP_R / ...
    return kind, int(m.group("x")), int(m.group("y"))


def tile_class(kind: str) -> str:
    k = (kind or "").upper()
    if k.startswith("CLB"):
        return "CLB"
    if k.startswith("BRAM") or k.startswith("RAMB") or "FIFO" in k:
        return "BRAM"
    if k.startswith("DSP"):
        return "DSP"
    if k.startswith("INT"):
        return "INT"
    if "CFG" in k or k.startswith("CLK"):
        return "CFG"
    return "OTHER"


def infer_clock_region(tile: str, site: str = "", clock_region: str = ""):
    """Prefer Vivado CLOCK_REGION; else infer from tile/site Y."""
    cr = (clock_region or "").strip()
    if cr:
        return cr.replace("CLOCKREGION_", "").replace("CLOCK_REGION_", "")
    parsed = parse_tile(tile)
    y = None
    x = 0
    if parsed:
        _kind, x, y = parsed
    else:
        m = SITE_XY.search(site or "")
        if m:
            x, y = int(m.group(1)), int(m.group(2))
    if y is None:
        return ""
    cr_y = y // CR_HEIGHT
    cr_x = 0 if x < 50 else 1
    return f"X{cr_x}Y{cr_y}"


def bbox_id(clock_region: str, kind: str, tile_x: int) -> str:
    return f"{clock_region or 'CR?'}|{tile_class(kind)}|COL{tile_x}"


def load_frame_table(path):
    """JSON: {part, source, columns: [{tile_kind, tile_x, clock_region, frame_lo, frame_hi}]}"""
    if path is None:
        return None
    p = Path(path)
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    idx = {}
    for col in data.get("columns") or []:
        key = (col.get("clock_region"), tile_class(col.get("tile_kind") or ""),
               int(col["tile_x"]))
        idx[key] = (int(col["frame_lo"]), int(col["frame_hi"]))
    return {"part": data.get("part"), "source": data.get("source"), "index": idx}


def lookup_frames(table, clock_region, kind, tile_x):
    if not table:
        return None
    key = (clock_region, tile_class(kind), int(tile_x))
    return table["index"].get(key)


def bbox_of_row(row, frame_table=None):
    """row: dict with site/tile/clock_region (primitive_map columns)."""
    tile = row.get("tile") or ""
    site = row.get("site") or row.get("loc") or ""
    parsed = parse_tile(tile)
    if parsed:
        kind, tx, ty = parsed
    else:
        kind, tx, ty = "OTHER", -1, -1
        m = SITE_XY.search(site)
        if m:
            tx, ty = int(m.group(1)), int(m.group(2))
    cr = infer_clock_region(tile, site, row.get("clock_region") or "")
    bid = bbox_id(cr, kind, tx)
    fr = lookup_frames(frame_table, cr, kind, tx)
    return {
        "clock_region": cr,
        "tile_kind": kind,
        "tile_class": tile_class(kind),
        "tile_x": tx,
        "tile_y": ty,
        "frame_bbox_id": bid,
        "frame_lo": None if fr is None else fr[0],
        "frame_hi": None if fr is None else fr[1],
        "frame_source": "column_table" if fr is not None else "clock_region_column",
    }


def frame_in_bbox(frame: int, bbox: dict) -> bool:
    lo, hi = bbox.get("frame_lo"), bbox.get("frame_hi")
    if lo is None or hi is None or frame is None:
        return False
    return lo <= int(frame) <= hi
