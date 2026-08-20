"""One strike: kernel -> ellipse ∩ sites -> flips.

Guide 8/9: several fault domains coexist at the same (x, y) of one site.
The SAME ellipse is tested once per site, then each resident domain becomes
its own candidate.

Defaults keep WP3/WP4 regressions:
  kernel_model='legacy_linear'  (a0 + k_let·LET)
  flip_model='bernoulli'        (independent per-domain coin)
"""
import math
import random

from .domains import LABEL, ORDER, P_DEFAULT
from .geometry import classify_hits, ellipse_intersects_rect
from .kernel import kernel_axes, kernel_axes_from_area
from .mbu_patterns import sample_k, select_k
from .units import RPM_TO_UM, area_um2_from_let, radius_um_from_area


def _resolve_axes(let, theta_deg, a0, k_let, kernel_model, area_um2, rpm_to_um):
    model = kernel_model or "legacy_linear"
    meta = {"kernel_model": model, "k_let": k_let, "a0": a0}
    if model == "anchored":
        if area_um2 is None:
            area_um2 = area_um2_from_let(let)
        a, b = kernel_axes_from_area(area_um2, theta_deg, rpm_to_um)
        meta["area_um2"] = float(area_um2)
        meta["rpm_to_um"] = float(rpm_to_um)
        meta["a0_eq_grid"] = float(b)  # normal-incidence half-axis in grid units
        meta["radius_um"] = radius_um_from_area(area_um2)
    elif model == "legacy_linear":
        if a0 is None:
            raise ValueError("legacy_linear kernel requires a0")
        a, b = kernel_axes(let, theta_deg, a0, k_let=k_let)
        meta["area_um2"] = None
    else:
        raise ValueError(f"unknown kernel_model {model!r}")
    return a, b, meta


def _collect_candidates(layout, x0, y0, a, b, phi):
    candidates = []
    for t in layout["tiles"]:
        if not ellipse_intersects_rect(x0, y0, a, b, phi,
                                       t["x"], t["y"], t["w"], t["h"]):
            continue
        domains = t.get("domains") or {}
        for dom in ORDER:
            bits = domains.get(dom, 0)
            if bits <= 0:
                continue
            candidates.append({
                "unit_id": t["unit_id"],
                "site": t.get("site"),
                "domain": dom,
                "bits": bits,
                "grid_x": t["grid_x"], "grid_y": t["grid_y"],
                "res_type": t["res_type"],
                "stage_id": t["stage_id"],
                "module_role": t["module_role"],
                "codeword_id": t.get("codeword_id"),
                "symbol_id": t.get("symbol_id"),
                "codeword_confidence": t.get("codeword_confidence") or "proxy",
                "is_shared": bool(t.get("is_shared")),
                "is_used": t["is_used"],
            })
    return candidates


def _flip_bernoulli(candidates, rng, p_by_domain):
    flipped = []
    for entry in candidates:
        if rng.random() < p_by_domain.get(entry["domain"], 0.2):
            flipped.append(dict(entry, n_bits=1))
    return flipped


def _flip_pattern(candidates, rng, x0, y0, shape):
    k = sample_k(rng)
    chosen = select_k(candidates, k, rng, shape=shape, x0=x0, y0=y0)
    return [dict(e, n_bits=1, pattern_k=k) for e in chosen], k


def run_strike(layout, x0, y0, let, theta_deg, phi_deg, a0,
               seed=1, k_let=0.25, p_by_domain=None,
               kernel_model="legacy_linear", area_um2=None,
               rpm_to_um=None, flip_model="bernoulli",
               pattern_shape="cluster"):
    p_by_domain = dict(P_DEFAULT if p_by_domain is None else p_by_domain)
    rpm = RPM_TO_UM if rpm_to_um is None else rpm_to_um
    a, b, kmeta = _resolve_axes(
        let, theta_deg, a0, k_let, kernel_model, area_um2, rpm)
    phi = math.radians(phi_deg)
    rng = random.Random(int(seed))
    candidates = _collect_candidates(layout, x0, y0, a, b, phi)
    flip_model = flip_model or "bernoulli"
    pattern_k = None
    if flip_model == "bernoulli":
        flipped = _flip_bernoulli(candidates, rng, p_by_domain)
    elif flip_model == "pattern":
        flipped, pattern_k = _flip_pattern(
            candidates, rng, x0, y0, pattern_shape or "cluster")
    else:
        raise ValueError(f"unknown flip_model {flip_model!r}")

    by_domain = {
        d: {
            "cand": sum(1 for c in candidates if c["domain"] == d),
            "flip": sum(1 for f in flipped if f["domain"] == d),
        }
        for d in ORDER
    }
    stages = sorted({f["stage_id"] for f in flipped if f["stage_id"] > 0})
    roles = sorted({f.get("module_role") or "unknown" for f in flipped})
    return {
        "proxy": True,
        "x0": x0, "y0": y0,
        "let": let, "theta_deg": theta_deg, "phi_deg": phi_deg,
        "a0": a0, "a": a, "b": b, "seed": int(seed), "k_let": k_let,
        "kernel_model": kmeta["kernel_model"],
        "area_um2": kmeta.get("area_um2"),
        "a0_eq_grid": kmeta.get("a0_eq_grid"),
        "radius_um": kmeta.get("radius_um"),
        "rpm_to_um": kmeta.get("rpm_to_um"),
        "flip_model": flip_model,
        "pattern_shape": pattern_shape if flip_model == "pattern" else None,
        "pattern_k": pattern_k,
        "n_candidates": len(candidates),
        "n_sites_covered": len({c["unit_id"] for c in candidates}),
        "n_flipped": len(flipped),
        "by_domain": by_domain,
        "domain_labels": LABEL,
        "stages_hit": stages,
        "roles_hit": roles,
        "preview_class": classify_hits(flipped),
        "candidates": candidates,
        "flipped": flipped,
        "note": ("Ellipse is a parameterized sensitive-area proxy on the die "
                 "plane. One site can contribute several domain candidates; "
                 "n_bits=1 is a placeholder multiplicity unless flip_model="
                 "pattern. The 3D ion track is display-only; depth is a "
                 "scalar folded into a via 1/cos(theta), not a 3D collection "
                 "volume."),
    }


def g4_presets(layout):
    """Named strike centres covering guide 9.3 cases (geometry debug)."""
    used = [t for t in layout["tiles"] if t["is_used"]]
    if not used:
        return {}
    def first_kind(*kinds):
        for t in used:
            if t["res_type"] in kinds:
                return t
        return used[0]
    clb = first_kind("SLICE", "CLB")
    dsp = first_kind("DSP")
    bram = first_kind("BRAM")
    a_site = 8.0
    return {
        "center_on_clb": {
            "label": "椭圆中心落在已用 Site",
            "x0": clb["x"] + 0.5, "y0": clb["y"] + 0.5, "a0": a_site,
        },
        "multi_tile": {
            "label": "覆盖多个相邻 Site",
            "x0": clb["x"] + 1.5, "y0": clb["y"] + 1.5, "a0": 16.0,
        },
        "cross_column": {
            "label": "打在 DSP 列附近",
            "x0": dsp["x"] + 0.5, "y0": dsp["y"] + 0.5, "a0": 14.0,
        },
        "die_edge": {
            "label": "跨越占用包围盒边缘",
            "x0": 0.5, "y0": layout["nrows"] * 0.5, "a0": 18.0,
        },
        "bram_delay": {
            "label": "打在 BRAM/RAMB Site",
            "x0": bram["x"] + 0.5, "y0": bram["y"] + 0.5, "a0": 12.0,
        },
    }
