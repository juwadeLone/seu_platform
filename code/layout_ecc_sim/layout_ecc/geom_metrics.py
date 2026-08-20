"""WP4 layout geometry: per-stage bands, adjacency, min distances.

Pure geometry on Site tiles. No injection, no Vivado. Distances are RPM
grid units (same as the strike kernel), not microns.
"""
import math
from collections import Counter, defaultdict

from .geometry import ellipse_intersects_rect
from .kernel import kernel_axes
from .stage_tags import N_STAGES


def stage_points(tiles):
    """stage_id -> list of (grid_x, grid_y) for used sites with a tagged stage."""
    pts = defaultdict(list)
    for t in tiles:
        if not t.get("is_used"):
            continue
        st = int(t.get("stage_id") or -1)
        if st < 1:
            continue
        pts[st].append((int(t["grid_x"]), int(t["grid_y"])))
    return {k: v for k, v in pts.items()}


def stage_bboxes(points):
    out = {}
    for st, pts in points.items():
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        cx = sum(xs) / len(pts)
        cy = sum(ys) / len(pts)
        out[st] = {
            "n_sites": len(pts),
            "xmin": xmin, "xmax": xmax, "ymin": ymin, "ymax": ymax,
            "width": xmax - xmin + 1,
            "height": ymax - ymin + 1,
            "thickness": min(xmax - xmin + 1, ymax - ymin + 1),
            "centroid_x": cx, "centroid_y": cy,
        }
    return out


def adjacency(points, include_diag=False):
    """Undirected neighbour edges between different stages.

    shared_edges = number of unique cell-cell sides (or king-moves if
    include_diag) whose two cells belong to different stages.
    """
    loc = {}
    for st, pts in points.items():
        for p in pts:
            loc[p] = st
    seen = set()
    counts = Counter()
    dirs = ((1, 0), (0, 1), (1, 1), (1, -1)) if include_diag else ((1, 0), (0, 1))
    for (x, y), st in loc.items():
        for dx, dy in dirs:
            q = (x + dx, y + dy)
            st2 = loc.get(q)
            if st2 is None or st2 == st:
                continue
            pair = (min(st, st2), max(st, st2))
            edge = ((x, y), q)
            if edge in seen:
                continue
            seen.add(edge)
            counts[pair] += 1
    return [
        {"a": a, "b": b, "shared_edges": int(n)}
        for (a, b), n in sorted(counts.items())
    ]


def _min_euclid(pa, pb):
    """Squared-then-sqrt nearest neighbour via a coarse spatial hash."""
    if not pa or not pb:
        return None
    left, right = (pa, pb) if len(pa) <= len(pb) else (pb, pa)
    x0, y0 = left[0]
    best = min((qx - x0) ** 2 + (qy - y0) ** 2 for qx, qy in right)
    if best == 0:
        return 0.0
    cell = 16
    buckets = defaultdict(list)
    for x, y in right:
        buckets[(x // cell, y // cell)].append((x, y))
    for x, y in left:
        ix, iy = x // cell, y // cell
        reach = int(best ** 0.5) // cell + 2
        for dx in range(-reach, reach + 1):
            for dy in range(-reach, reach + 1):
                for qx, qy in buckets.get((ix + dx, iy + dy), ()):
                    d = (qx - x) ** 2 + (qy - y) ** 2
                    if d < best:
                        best = d
                        if best == 0:
                            return 0.0
    return math.sqrt(best)


def min_distance_matrix(points, stages=None, adj=None):
    """Euclidean min distance (grid units) between any two sites of i and j.

    Same stage → 0. Missing stage → None. Stages that share a 4-neighbour
    edge have distance 1 (no need to scan the point sets).
    """
    stages = list(stages or range(1, N_STAGES + 1))
    n = len(stages)
    idx = {s: i for i, s in enumerate(stages)}
    mat = [[None] * n for _ in stages]
    for s in stages:
        if s in points:
            mat[idx[s]][idx[s]] = 0.0
    adjacent = {}
    if adj is None:
        adj = adjacency(points)
    for e in adj:
        adjacent[(e["a"], e["b"])] = 1.0
        adjacent[(e["b"], e["a"])] = 1.0
    items = [(s, points[s]) for s in stages if s in points]
    for i, (sa, pa) in enumerate(items):
        ia = idx[sa]
        for sb, pb in items[i + 1:]:
            ib = idx[sb]
            if (sa, sb) in adjacent:
                mat[ia][ib] = mat[ib][ia] = 1.0
                continue
            dist = _min_euclid(pa, pb)
            mat[ia][ib] = mat[ib][ia] = dist
    return {"stages": stages, "matrix": mat}


def stages_covered_by_ellipse(tiles, x0, y0, a0, theta_deg, phi_deg=30.0,
                              let=15.0, k_let=0.25, points=None, boxes=None):
    """Stages whose occupied sites intersect the strike ellipse.

    One hit per stage is enough. Prefer ``points`` (stage → (gx,gy) list)
    so unused tiles and already-covered stages are skipped.
    """
    a, b = kernel_axes(let, theta_deg, a0, k_let=k_let)
    phi = math.radians(phi_deg)
    pad = max(a, b) + 1.5
    xmin, xmax = x0 - pad, x0 + pad
    ymin, ymax = y0 - pad, y0 + pad
    hit = set()
    if points is None:
        points = stage_points(tiles)
    if boxes is None:
        boxes = stage_bboxes(points)
    for st, pts in points.items():
        bb = boxes.get(st)
        if bb and (bb["xmax"] < xmin or bb["xmin"] > xmax
                   or bb["ymax"] < ymin or bb["ymin"] > ymax):
            continue
        for gx, gy in pts:
            if gx + 1 < xmin or gx > xmax or gy + 1 < ymin or gy > ymax:
                continue
            if ellipse_intersects_rect(x0, y0, a, b, phi, gx, gy, 1.0, 1.0):
                hit.add(st)
                break
    return sorted(hit)


def geometric_cross_scan(layout, a0s, thetas, phi_deg=30.0, let=15.0,
                         n_uniform=80, seed=1):
    """Centroid coverage + uniform occupied-centre coverage vs (a0, theta)."""
    import random
    tiles = layout["tiles"]
    pts = stage_points(tiles)
    boxes = stage_bboxes(pts)
    x0 = float(layout["default_x0"])
    y0 = float(layout["default_y0"])
    used = [(p[0] + 0.5, p[1] + 0.5) for st_pts in pts.values() for p in st_pts]
    rng = random.Random(int(seed))
    samples = [used[rng.randrange(len(used))] for _ in range(n_uniform)] if used else []
    cells = []
    for a0 in a0s:
        for theta in thetas:
            cent = stages_covered_by_ellipse(
                tiles, x0, y0, a0, theta, phi_deg=phi_deg, let=let,
                points=pts, boxes=boxes)
            n_cross = 0
            n_sum = 0
            for sx, sy in samples:
                cov = stages_covered_by_ellipse(
                    tiles, sx, sy, a0, theta, phi_deg=phi_deg, let=let,
                    points=pts, boxes=boxes)
                n_sum += len(cov)
                if len(cov) > 1:
                    n_cross += 1
            n = len(samples) or 1
            cells.append({
                "a0": a0, "theta": theta, "phi": phi_deg,
                "centroid_stages": cent,
                "centroid_n_stages": len(cent),
                "centroid_cross": len(cent) > 1,
                "uniform_n": len(samples),
                "uniform_cross_rate": n_cross / n if samples else 0.0,
                "uniform_mean_n_stages": n_sum / n if samples else 0.0,
            })
    return {"x0": x0, "y0": y0, "cells": cells}


def explain_saturation(bboxes, adj, dist_obj, a0_sat=8, adj8=None):
    """Plain-language geometry reason that a0>=a0_sat crosses stages."""
    stages = dist_obj["stages"]
    mat = dist_obj["matrix"]
    neighbour_d = []
    for i, a in enumerate(stages):
        if i + 1 >= len(stages):
            continue
        d = mat[i][i + 1]
        if d is None:
            continue
        neighbour_d.append((a, a + 1, d, bboxes.get(a, {}).get("thickness"),
                            bboxes.get(a + 1, {}).get("thickness")))
    longest = max(adj, key=lambda e: e["shared_edges"]) if adj else None
    if longest is None and adj8:
        longest = max(adj8, key=lambda e: e["shared_edges"])
        if longest:
            longest = dict(longest, neighbour="8")
    thinnest = min(bboxes.items(), key=lambda kv: kv[1]["thickness"]) if bboxes else None
    min_nb = min((t[2] for t in neighbour_d), default=None)
    n4 = sum(e["shared_edges"] for e in adj)
    n8 = sum(e["shared_edges"] for e in (adj8 or []))
    return {
        "a0_sat": a0_sat,
        "min_adjacent_stage_distance": min_nb,
        "n_4neighbour_shared_edges": n4,
        "n_8neighbour_shared_edges": n8,
        "consecutive_distances": [
            {"a": a, "b": b, "min_dist": d, "thickness_a": ta, "thickness_b": tb}
            for a, b, d, ta, tb in neighbour_d
        ],
        "longest_boundary": longest,
        "thinnest_band": ({"stage": thinnest[0], **thinnest[1]}
                          if thinnest else None),
        "reason": (
            f"After site-majority tagging, stages have {n4} four-neighbour "
            f"shared sides and {n8} diagonal touches; consecutive stages sit "
            f"{min_nb} RPM apart at nearest used sites. Axis-aligned bboxes "
            f"overlap, so the occupancy centroid already covers two stages at "
            f"a0=4 (WP3's sampling point). An ellipse with a0>={a0_sat} is "
            f"larger than the {min_nb} RPM frontier gap, which is why WP3's "
            f"centroid strikes saturate at cross-stage=1. Uniform-interior "
            f"centres stay inside one blob more often."
            if min_nb is not None else "missing consecutive-stage distances"
        ),
    }


def compute_all(layout):
    pts = stage_points(layout["tiles"])
    boxes = stage_bboxes(pts)
    adj = adjacency(pts)
    adj8 = adjacency(pts, include_diag=True)
    dist = min_distance_matrix(pts, adj=adj)
    return {
        "n_stages": N_STAGES,
        "bboxes": {str(k): v for k, v in boxes.items()},
        "adjacency": adj,
        "adjacency_diag": adj8,
        "min_distance": dist,
    }
