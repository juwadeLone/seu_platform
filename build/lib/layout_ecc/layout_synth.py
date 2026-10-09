"""Synthetic 7-series-like tile grid with FFT stage tags.

This is a *layout proxy* until Vivado `primitive_map.csv` exists (M1).
Column rhythm is schematic (CLB / DSP / BRAM), not a real part database.
"""

from .domains import build_domains

# column type cycle approximating 7-series fabric
_COL = tuple(["CLB"] * 5 + ["DSP"] + ["CLB"] * 5 + ["BRAM"])

# synthetic per-tile primitive/FF proxies for domain occupancy
_SYNTH_OCC = {"CLB": (2, 8), "DSP": (1, 0), "BRAM": (1, 0)}

COLOR_USED = "#3d7ec9"
COLOR_UNUSED = "#14181e"

ROLE_H = 0.12


def _role_for(col_type, stage_id, row, nrows):
    if stage_id < 0:
        return "unused"
    band = row / max(nrows - 1, 1)
    if col_type == "DSP":
        return "twiddle" if band < 0.35 else "butterfly"
    if col_type == "BRAM":
        return "delay"
    if stage_id >= 9 and band > 0.75:
        return "ecc"
    return "butterfly"


def synthesize(ncols=24, nrows=40, n_stages=10, margin=2):
    """Return a list of tile dicts in tile-index coordinates (1x1 cells)."""
    tiles = []
    uid = 0
    inner_h = max(nrows - 2 * margin, 1)
    for ix in range(ncols):
        col_type = _COL[ix % len(_COL)]
        for iy in range(nrows):
            edge = (ix < margin or iy < margin
                    or ix >= ncols - margin or iy >= nrows - margin)
            if edge:
                stage_id = -1
                used = False
                rtype = "unused"
            else:
                used = True
                rtype = col_type
                # 10 bands along +Y so successive FFT stages occupy successive rows.
                stage_id = 1 + int((iy - margin) / inner_h * n_stages)
                stage_id = min(max(stage_id, 1), n_stages)
            role = _role_for(rtype if used else "unused", stage_id, iy, nrows)
            site = f"{rtype}_X{ix}Y{iy}"
            n_prims, n_ff = _SYNTH_OCC.get(rtype, (0, 0)) if used else (0, 0)
            tiles.append({
                "unit_id": f"t{uid}",
                "x": float(ix), "y": float(iy),
                "w": 1.0, "h": 1.0,
                "zh": ROLE_H,
                "grid_x": ix, "grid_y": iy,
                "res_type": rtype if used else "unused",
                "stage_id": stage_id,
                "module_role": role,
                "is_used": used,
                "color": COLOR_USED if used else COLOR_UNUSED,
                "site": site,
                "bels": {"CLB": "2 slice / 8 FF 代理",
                         "DSP": "1 DSP48 代理",
                         "BRAM": "1 RAMB36 代理",
                         "unused": "空 Tile"}.get(
                             rtype if used else "unused", ""),
                "n_prims": n_prims,
                "n_ff": n_ff,
                "domains": build_domains(rtype if used else "unused",
                                         n_prims, n_ff),
            })
            uid += 1
    return {
        "source": "synthetic_proxy",
        "disclaimer": ("Tile XY are architecture-proxy units, not microns. "
                       "Replace with Vivado primitive_map.csv (M1)."),
        "ncols": ncols, "nrows": nrows, "n_stages": n_stages,
        "tiles": tiles,
    }


def bounding_box(layout):
    tiles = layout["tiles"]
    return {
        "x0": 0.0, "y0": 0.0,
        "x1": float(layout["ncols"]),
        "y1": float(layout["nrows"]),
        "n": len(tiles),
        "n_used": sum(1 for t in tiles if t["is_used"]),
    }
