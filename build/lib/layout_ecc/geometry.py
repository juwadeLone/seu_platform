"""2D ellipse vs axis-aligned resource rectangles (die-plane query).

The 3D viewer only *displays* the ion track; candidate selection is this
planar test (guide 9.1). Rectangles are [x, x+w] x [y, y+h].
"""
import math


def _to_ellipse_frame(px, py, cx, cy, phi):
    dx, dy = px - cx, py - cy
    c, s = math.cos(phi), math.sin(phi)
    return c * dx + s * dy, -s * dx + c * dy


def point_in_ellipse(px, py, cx, cy, a, b, phi):
    u, v = _to_ellipse_frame(px, py, cx, cy, phi)
    return (u / a) ** 2 + (v / b) ** 2 <= 1.0 + 1e-12


def ellipse_intersects_rect(cx, cy, a, b, phi, rx, ry, rw, rh):
    """True iff the closed ellipse overlaps the closed axis-aligned rect."""
    if a <= 0 or b <= 0 or rw <= 0 or rh <= 0:
        return False
    x0, x1 = rx, rx + rw
    y0, y1 = ry, ry + rh
    if x0 <= cx <= x1 and y0 <= cy <= y1:
        return True
    corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    if any(point_in_ellipse(px, py, cx, cy, a, b, phi) for px, py in corners):
        return True
    qx = min(max(cx, x0), x1)
    qy = min(max(cy, y0), y1)
    if point_in_ellipse(qx, qy, cx, cy, a, b, phi):
        return True
    c, s = math.cos(phi), math.sin(phi)
    tips = ((cx + a * c, cy + a * s), (cx - a * c, cy - a * s),
            (cx - b * s, cy + b * c), (cx + b * s, cy - b * c))
    for px, py in tips:
        if x0 <= px <= x1 and y0 <= py <= y1:
            return True
    return False


def classify_hits(tiles):
    """Lightweight preview of guide section 10 classes (not the M4 classifier).

    Entries may be per-(site, domain) pairs; dedupe by unit_id so several
    domain flips on one site count as one affected site.
    """
    seen, used = set(), []
    for t in tiles:
        if not t.get("is_used"):
            continue
        uid = t.get("unit_id")
        if uid is not None:
            if uid in seen:
                continue
            seen.add(uid)
        used.append(t)
    if not used:
        return "NO_EFFECT"
    stages = {t["stage_id"] for t in used if t.get("stage_id") not in (None, -1)}
    if len(used) == 1:
        return "SINGLE_BIT_SINGLE_STAGE"
    if len(stages) <= 1:
        return "MULTI_BIT_SINGLE_STAGE"
    return "CROSS_STAGE"
