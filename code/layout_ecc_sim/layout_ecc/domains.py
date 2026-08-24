"""Fault-domain occupancy (guide section 8).

One physical site hosts several fault domains at the SAME (x, y): config
bits, FF state, BRAM state, DSP state. Domains share the site rectangle for
geometry but have independent bit counts.

Bit counts are device-manual numbers where a table exists. They are still
NOT essential-bit masks (that needs bitstream / SEM). SET/routing is
deliberately absent: nets span tiles and do not fit site-level occupancy.
"""

ORDER = ("CFG", "FF_STATE", "BRAM_STATE", "DSP_STATE")

LABEL = {
    "CFG": "配置位 CRAM",
    "FF_STATE": "FF 状态位",
    "BRAM_STATE": "BRAM 数据位",
    "DSP_STATE": "DSP 状态位",
}

# Legacy coin-flip used only by flip_model='bernoulli' (tests / geometry debug).
# The viewer default is flip_model='weibull' (Lee 2014 σ(LET), M9).
P_DEFAULT = {
    "CFG": 0.30,
    "FF_STATE": 0.35,
    "BRAM_STATE": 0.40,
    "DSP_STATE": 0.45,
}

# UG470 Table 1-1 bitstream length, device 7VX690T.
UG470_BITSTREAM_VX690T = 229_878_496
# UG474 Table 3 / DS180: Virtex-7 7VX690T Slices.
DS180_SLICES_VX690T = 108_300
# Uniform share of the configuration bitstream per slice. This is NOT an
# essential-bit count and NOT a measured per-SLICE CRAM cell count.
CFG_BITS_PER_SLICE = UG470_BITSTREAM_VX690T // DS180_SLICES_VX690T  # 2122
# 7-series CLB = 2 slices (UG474).
CFG_BITS_PER_CLB = CFG_BITS_PER_SLICE * 2

# DS180 / UG473: RAMB36E1 is a 36 Kb block (36 × 1024 bits).
BRAM_BITS = 36 * 1024  # 36864

# UG479 DSP48E1 data-path register widths, one pipeline stage each.
# A 30 + B 18 + C 48 + D 25 + P 48. Occupancy for geometry only: Lee 2014
# Table 1 has no DSP σ, so flip_model='weibull' never upsets DSP_STATE.
DSP48E1_DATA_REG_BITS = 30 + 18 + 48 + 25 + 48  # 169
DSP_BITS = DSP48E1_DATA_REG_BITS

_FF_REF_PREFIX = ("FD", "LD")   # FDRE/FDSE/FDCE/FDPE/LDCE...

BITS_PASSPORT = {
    "CFG_SLICE": {
        "value": CFG_BITS_PER_SLICE,
        "source": (
            "UG470 Table 1-1 bitstream length 229,878,496 / "
            "UG474 Table 3 slices 108,300. Uniform share, not essential bits."
        ),
    },
    "BRAM_STATE": {
        "value": BRAM_BITS,
        "source": "DS180 / UG473 RAMB36E1 36 Kb = 36 × 1024 bits.",
    },
    "FF_STATE": {
        "value": "from primitive_map ref_name (FD*/LD*)",
        "source": "Vivado placed FF instances; device total 866,400 is UG474 Table 3.",
    },
    "DSP_STATE": {
        "value": DSP_BITS,
        "source": (
            "UG479 DSP48E1 data-path register widths (A+B+C+D+P). "
            "Not an SEE-tested bit count; no Lee 2014 DSP σ."
        ),
    },
}


def is_ff_ref(ref_name):
    r = (ref_name or "").upper()
    return r.startswith(_FF_REF_PREFIX)


def build_domains(kind, n_prims=0, n_ff=0):
    """Return {domain: bits} for one site; zero-bit domains are omitted.

    n_prims is kept in the signature for layout_import / synth callers but is
    no longer added as invented CFG_PER_PRIM bits.
    """
    del n_prims  # occupancy comes from kind + n_ff, not 8×primitives
    if kind == "unused":
        return {}
    d = {}
    if kind == "SLICE":
        d["CFG"] = CFG_BITS_PER_SLICE
    elif kind == "CLB":
        d["CFG"] = CFG_BITS_PER_CLB
    elif kind == "BRAM":
        # Data bits are the RAMB36 array. Extra CRAM on the BRAM tile is
        # already in the device bitstream share assigned to SLICE/CLB;
        # do not invent a second CFG occupancy here.
        d["BRAM_STATE"] = BRAM_BITS
    elif kind == "DSP":
        d["DSP_STATE"] = DSP_BITS
    elif kind == "OTHER":
        d["CFG"] = CFG_BITS_PER_SLICE
    if n_ff > 0:
        d["FF_STATE"] = int(n_ff)
    return d


def summarize(domains):
    """Short per-site occupancy string for hover display."""
    return " · ".join(f"{LABEL.get(k, k)} {v}"
                      for k, v in domains.items() if v) or "—"
