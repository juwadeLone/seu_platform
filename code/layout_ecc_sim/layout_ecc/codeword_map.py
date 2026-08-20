"""hier_cell -> codeword_id / symbol_id from P1 RTL names (WP5).

A stage-1..7 arithmetic [6,4,3] codeword is the six-symbol group
``complete_butterflies[0..5]`` (plus hold/bnd of the same index, and the
shared ``u_apply`` / syndrome / residual logic). Index 0..3 are functional
symbols, 4..5 are checks. Stage 10 uses two independent words (upper ``qu*``
vs lower ``ql*``). Memory SECDED is one codeword per ``mem0..mem3`` lane.
TMR replicas are not ECC codewords but are labelled ``sN:tmr`` so two
replica hits can be counted. CFG bits have no name-level essential-bit map
and stay ``proxy``.
"""
import re

from .stage_tags import tag

_BFLY = re.compile(r"complete_butterflies\[(\d+)\]")
_HOLD = re.compile(r"hold_[ri]_reg\[(\d+)\]")
_BND = re.compile(r"bnd_[ri]_reg\[(\d+)\]")
_APP = re.compile(r"app_[ri]_reg\[(\d+)\]")
_MEM = re.compile(r"(?:^|/)mem([0-3])(?:/|$)")
_MEM2 = re.compile(r"mem([0-3])/")
_QU = re.compile(r"(?:^|/)q([ul])([0-5])[ri]")
_AU = re.compile(r"(?:^|/)([ah])([ul])([0-5])[ri]")  # au/al/hu/hl
_RES_SY = re.compile(r"(?:^|/)(?:res|sy)([01])")


def codeword_of(hier_cell, domain=None):
    """Return dict codeword_id, symbol_id, confidence, scheme, reason."""
    h = hier_cell or ""
    stage, role, replica = tag(h)
    base = {
        "stage_id": stage, "module_role": role, "replica_id": replica,
        "codeword_id": None, "symbol_id": None,
        "confidence": "proxy", "scheme": None, "reason": None,
    }
    if domain == "CFG":
        base["reason"] = "CFG essential bits are not named in hier_cell"
        return base
    if stage < 1:
        base["reason"] = "no u/sN/ prefix"
        return base

    m = _BFLY.search(h)
    if m:
        sym = int(m.group(1))
        base.update(codeword_id=f"s{stage}:arith", symbol_id=sym,
                    confidence="inferred", scheme="arithmetic_643",
                    reason="complete_butterflies[g] is symbol g of the stage [6,4,3] group")
        return base
    m = _HOLD.search(h) or _BND.search(h)
    if m:
        sym = int(m.group(1))
        base.update(codeword_id=f"s{stage}:arith", symbol_id=sym,
                    confidence="inferred", scheme="arithmetic_643",
                    reason="hold/bnd[k] pipelines symbol k of the same [6,4,3] group")
        return base
    m = _APP.search(h)
    if m:
        sym = int(m.group(1))
        base.update(codeword_id=f"s{stage}:arith", symbol_id=sym,
                    confidence="inferred", scheme="arithmetic_643",
                    reason="app[k] is a functional symbol after arithmetic apply")
        return base
    m = _QU.search(h)
    if m:
        side, sym = m.group(1), int(m.group(2))
        word = "upper" if side == "u" else "lower"
        base.update(codeword_id=f"s{stage}:arith:{word}", symbol_id=sym,
                    confidence="inferred", scheme="arithmetic_643",
                    reason="s10 qu/ql[k] are symbols of the upper/lower two-beat codeword")
        return base
    m = _AU.search(h)
    if m:
        _kind, side, sym = m.group(1), m.group(2), int(m.group(3))
        word = "upper" if side == "u" else "lower"
        base.update(codeword_id=f"s{stage}:arith:{word}", symbol_id=sym,
                    confidence="inferred", scheme="arithmetic_643",
                    reason="s10 au/al/hu/hl snapshot registers of the two-beat codeword")
        return base
    if _RES_SY.search(h) or "u_apply" in h or "res_v" in h or "syn_v" in h:
        cw = f"s{stage}:arith"
        if stage == 10:
            cw = "s10:arith:decoder"
        base.update(codeword_id=cw, symbol_id=None,
                    confidence="inferred", scheme="arithmetic_643",
                    reason="syndrome/residual/u_apply belong to the stage arithmetic word as a whole")
        return base
    m = _MEM.search(h) or _MEM2.search(h)
    if m:
        lane = int(m.group(1))
        base.update(codeword_id=f"s{stage}:secded:mem{lane}", symbol_id=0,
                    confidence="inferred", scheme="memory_secded70",
                    reason="memN is one SECDED lane (one memory codeword)")
        return base
    if replica is not None:
        base.update(codeword_id=f"s{stage}:tmr", symbol_id=replica,
                    confidence="inferred", scheme="tmr3",
                    reason="replicas[k] is TMR copy k, not an ECC symbol")
        return base
    if role == "replica" and stage in (8, 9):
        base.update(codeword_id=f"s{stage}:tmr", symbol_id=0,
                    confidence="inferred", scheme="tmr3",
                    reason="stage 8/9 voter/output is the TMR boundary")
        return base

    base["reason"] = f"named role {role} has no explicit codeword index in hier_cell"
    return base


def majority_codeword(hier_cells, domain=None):
    """Site-level codeword from primitive majority (None counts as no vote)."""
    from collections import Counter
    cws, syms = Counter(), Counter()
    confs = Counter()
    schemes = Counter()
    n_proxy = 0
    details = []
    for h in hier_cells:
        rec = codeword_of(h, domain=domain)
        details.append(rec)
        if rec["confidence"] == "proxy" or rec["codeword_id"] is None:
            n_proxy += 1
            continue
        cws[rec["codeword_id"]] += 1
        if rec["symbol_id"] is not None:
            syms[rec["symbol_id"]] += 1
        confs[rec["confidence"]] += 1
        if rec["scheme"]:
            schemes[rec["scheme"]] += 1
    if not cws:
        return {
            "codeword_id": None, "symbol_id": None,
            "confidence": "proxy", "scheme": None,
            "n_proxy": n_proxy, "n_tagged": 0,
            "reason": "no inferred codeword among site primitives",
        }
    cw = cws.most_common(1)[0][0]
    sym = syms.most_common(1)[0][0] if syms else None
    return {
        "codeword_id": cw,
        "symbol_id": sym,
        "confidence": confs.most_common(1)[0][0] if confs else "inferred",
        "scheme": schemes.most_common(1)[0][0] if schemes else None,
        "n_proxy": n_proxy,
        "n_tagged": sum(cws.values()),
        "n_codewords_on_site": len(cws),
        "reason": "site majority of inferred hier_cell tags",
    }
