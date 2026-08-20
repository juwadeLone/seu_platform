"""Load Vivado primitive_map.csv into a site-level occupancy grid.

Each unique Site is one cell. Coordinates are RPM_X/RPM_Y from the DCP
export, shifted so the used bounding box starts at (0,0). Empty cells
inside that box are unused (drawn black). This is still a layout proxy:
RPM units are not microns.
"""
import csv
import os
import re

from .domains import build_domains, is_ff_ref
from .layout_synth import COLOR_UNUSED, COLOR_USED
from .stage_tags import (
    N_STAGES, RESOURCE_COLORS, STAGE_COLORS, majority_site, report_csv,
    stage_hex,
)
from .codeword_map import majority_codeword

_SITE_KIND = (
    ("SLICE", "SLICE"),
    ("DSP", "DSP"),
    ("RAMB", "BRAM"),
    ("FIFO", "BRAM"),
)


def _kind(site, ref):
    s = (site or "") + " " + (ref or "")
    for prefix, kind in _SITE_KIND:
        if prefix in s:
            return kind
    return "OTHER"


def load_primitive_map(path, zh=0.12):
    sites = {}
    n_prims = 0
    n_placed = 0
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            n_prims += 1
            loc = (row.get("loc") or "").strip()
            if not loc:
                continue
            n_placed += 1
            gx, gy = row.get("grid_x"), row.get("grid_y")
            if gx == "" or gy == "" or gx is None or gy is None:
                m = re.search(r"X(\d+)Y(\d+)", loc)
                if not m:
                    continue
                gx, gy = m.group(1), m.group(2)
            key = (row.get("site") or loc).strip()
            x, y = int(float(gx)), int(float(gy))
            ref = row.get("ref_name") or ""
            rec = sites.get(key)
            if rec is None:
                sites[key] = {
                    "site": key,
                    "gx": x, "gy": y,
                    "n": 1,
                    "n_ff": 1 if is_ff_ref(ref) else 0,
                    "ref": ref,
                    "tile": row.get("tile") or "",
                    "kind": _kind(key, ref),
                    "hier": [row.get("hier_cell") or ""],
                }
            else:
                rec["n"] += 1
                rec["hier"].append(row.get("hier_cell") or "")
                if is_ff_ref(ref):
                    rec["n_ff"] += 1

    if not sites:
        raise ValueError(f"no placed sites in {path}")

    xs = [s["gx"] for s in sites.values()]
    ys = [s["gy"] for s in sites.values()]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    ncols = xmax - xmin + 1
    nrows = ymax - ymin + 1

    tiles = []
    n_shared = 0
    for i, s in enumerate(sites.values()):
        ix = s["gx"] - xmin
        iy = s["gy"] - ymin
        maj = majority_site(s["hier"])
        cw = majority_codeword(s["hier"])
        if maj["is_shared"]:
            n_shared += 1
        tiles.append({
            "unit_id": f"s{i}",
            "x": float(ix), "y": float(iy),
            "w": 1.0, "h": 1.0,
            "zh": zh,
            "grid_x": ix, "grid_y": iy,
            "rpm_x": s["gx"], "rpm_y": s["gy"],
            "res_type": s["kind"],
            "stage_id": maj["stage_id"],
            "module_role": maj["module_role"],
            "replica_id": maj["replica_id"],
            "is_shared": maj["is_shared"],
            "stages": maj["stages"],
            "is_used": True,
            "color": stage_hex(maj["stage_id"]),
            "color_resource": RESOURCE_COLORS.get(
                s["kind"], RESOURCE_COLORS["OTHER"]),
            "site": s["site"],
            "bels": f"{s['n']} primitives · {s['kind']}",
            "n_prims": s["n"],
            "n_ff": s["n_ff"],
            "domains": build_domains(s["kind"], s["n"], s["n_ff"]),
            "codeword_id": cw.get("codeword_id"),
            "symbol_id": cw.get("symbol_id"),
            "codeword_confidence": cw.get("confidence"),
            "codeword_scheme": cw.get("scheme"),
        })

    used_xy = {(t["grid_x"], t["grid_y"]) for t in tiles}
    cx = sum(t["x"] for t in tiles) / len(tiles)
    cy = sum(t["y"] for t in tiles) / len(tiles)

    return {
        "source": "vivado_primitive_map",
        "part": "xc7vx690tffg1761-2",
        "csv_path": os.path.abspath(path),
        "disclaimer": (
            f"P1 routed OOC, {n_placed} placed primitives on {len(sites)} sites. "
            f"{n_shared} sites mix more than one FFT stage. "
            "Colour-by-stage uses HSV bands s1–s10; black = empty in the used "
            "bounding box. RPM_X/Y are architecture units, not microns."
        ),
        "ncols": ncols, "nrows": nrows,
        "n_stages": N_STAGES,
        "xmin": xmin, "ymin": ymin,
        "n_prims": n_prims, "n_placed": n_placed, "n_sites": len(sites),
        "n_shared_sites": n_shared,
        "tag_stats": report_csv(path),
        "stage_colors": STAGE_COLORS,
        "resource_colors": RESOURCE_COLORS,
        "tiles": tiles,
        "used_xy": used_xy,
        "default_x0": cx, "default_y0": cy, "default_a0": 12.0,
        "color_used": COLOR_USED, "color_unused": COLOR_UNUSED,
    }
