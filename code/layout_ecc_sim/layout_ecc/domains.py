"""Fault-domain occupancy model (guide section 8).

One physical site hosts several fault domains at the SAME (x, y): config
bits, FF state, BRAM state, DSP state. Domains share the site rectangle for
geometry but have independent bit counts and upset probabilities, so a single
ellipse can produce correlated faults across domains.

All bit counts below are PLACEHOLDER proxies until SEM/beam calibration
(guide 1.3). SET/routing is deliberately absent: nets span tiles and do not
fit site-level occupancy.
"""

ORDER = ("CFG", "FF_STATE", "BRAM_STATE", "DSP_STATE")

LABEL = {
    "CFG": "配置位 CRAM",
    "FF_STATE": "FF 状态位",
    "BRAM_STATE": "BRAM 数据位",
    "DSP_STATE": "DSP 状态位",
}

# default per-domain upset probability given the site is inside the kernel
P_DEFAULT = {
    "CFG": 0.30,
    "FF_STATE": 0.35,
    "BRAM_STATE": 0.40,
    "DSP_STATE": 0.45,
}

# placeholder config-bit proxies per used site, by resource kind
_CFG_BASE = {"SLICE": 400, "CLB": 400, "DSP": 300, "BRAM": 250,
             "OTHER": 200, "unused": 0}
CFG_PER_PRIM = 8

BRAM_BITS = 36864   # RAMB36 proxy
DSP_BITS = 96       # visible pipeline/output state proxy

_FF_REF_PREFIX = ("FD", "LD")   # FDRE/FDSE/FDCE/FDPE/LDCE...


def is_ff_ref(ref_name):
    r = (ref_name or "").upper()
    return r.startswith(_FF_REF_PREFIX)


def build_domains(kind, n_prims=0, n_ff=0):
    """Return {domain: bits} for one site; zero-bit domains are omitted."""
    if kind == "unused":
        return {}
    d = {"CFG": _CFG_BASE.get(kind, 200) + CFG_PER_PRIM * n_prims}
    if n_ff > 0:
        d["FF_STATE"] = n_ff
    if kind == "BRAM":
        d["BRAM_STATE"] = BRAM_BITS
    if kind == "DSP":
        d["DSP_STATE"] = DSP_BITS
    return d


def summarize(domains):
    """Short per-site occupancy string for hover display."""
    return " · ".join(f"{LABEL.get(k, k)} {v}"
                      for k, v in domains.items() if v) or "—"
