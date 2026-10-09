"""Map strike flipped (site × domain) rows to guide-8 fault records."""
from .functional import inject_and_classify


def map_flipped(flipped, strike_id="s0"):
    """Translate run_strike()['flipped'] into fault records.

    Lifecycle v1:
      BRAM_STATE → delay buffer
      FF_STATE   → the site's module_role
      CFG        → configuration of that module (codeword stays proxy)
      DSP_STATE  → twiddle/butterfly datapath state
    Codeword/symbol come from hier_cell names (WP5); CFG stays proxy.
    """
    records = []
    for i, f in enumerate(flipped):
        domain = f.get("domain") or "FF_STATE"
        role = f.get("module_role") or "unknown"
        if domain == "BRAM_STATE":
            role = "delay"
        elif domain == "DSP_STATE" and role in ("unknown", "placed"):
            role = "twiddle"
        elif domain == "CFG" and role in ("unknown", "placed"):
            role = "control"
        stage = int(f.get("stage_id") or -1)
        cw = f.get("codeword_id")
        sym = f.get("symbol_id")
        conf = f.get("codeword_confidence") or "proxy"
        if not cw:
            cw = f"{stage}:{role}"
            conf = "proxy"
            if f.get("grid_x") is not None and sym is None:
                sym = int(f.get("grid_x") or 0) % 4
        rec = {
            "fault_id": f"{strike_id}/f{i}",
            "domain": domain,
            "unit_id": f.get("unit_id"),
            "location_id": f.get("site") or f.get("unit_id"),
            "stage_id": stage,
            "module_role": role,
            "fault_action": "bit_flip",
            "start_cycle": 0,
            "duration": "until_overwrite",
            "multiplicity": int(f.get("n_bits") or 1),
            "codeword_id": cw,
            "symbol_id": sym,
            "source_model": "proxy" if conf == "proxy" else "layout_name",
            "confidence": conf,
            "is_shared": bool(f.get("is_shared")),
        }
        if domain == "CFG":
            rec["confidence"] = "proxy"
            rec["source_model"] = "proxy"
            rec["cfg_note"] = "essential bits not in hier_cell names"
        records.append(rec)
    return records


def classify_strike_faults(records):
    stages = sorted({r["stage_id"] for r in records if r["stage_id"] > 0})
    roles = sorted({r["module_role"] for r in records})
    by_cw = {}
    for r in records:
        cw = r.get("codeword_id")
        if not cw or r.get("confidence") == "proxy":
            continue
        by_cw.setdefault(cw, set()).add(r.get("symbol_id"))
    multi_symbol = sorted(cw for cw, syms in by_cw.items()
                          if len({s for s in syms if s is not None}) > 1)
    n_proxy = sum(1 for r in records if r.get("confidence") == "proxy")
    return {
        "n_faults": len(records),
        "n_stages": len(stages),
        "stages": stages,
        "roles": roles,
        "cross_stage": len(stages) > 1,
        "same_codeword_multi_symbol": multi_symbol,
        "n_proxy_confidence": n_proxy,
        "source_model": "layout_name",
        "confidence": "mixed",
    }


def replay_strike(flipped, golden=None, max_inject=8, strike_id="s0"):
    """Map then inject up to max_inject representative faults (WP3 closed loop)."""
    records = map_flipped(flipped, strike_id=strike_id)
    summary = classify_strike_faults(records)
    outcomes = []
    for rec in records[:max_inject]:
        fault = {
            "stage_id": max(rec["stage_id"], 1),
            "module_role": rec["module_role"],
            "domain": rec["domain"],
            "bit": 0,
            "component": "real",
            "symbol": rec["symbol_id"],
        }
        outcomes.append(inject_and_classify(fault, golden=golden))
    summary["outcomes"] = [o["outcome"] for o in outcomes]
    summary["injections"] = outcomes
    return records, summary
