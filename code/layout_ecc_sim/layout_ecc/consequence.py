"""Mission-consequence engine: which module's upsets kill the mission?

v1 model (every coefficient labelled evidence vs assumption):
- Each tile carries per-domain occupancy (bits) from build_domains().
- A module's upset rate in a domain = its bit share x the domain's
  device-per-bit rate/day. Evidence: bit counts are measured from the
  real layout; rates come from the orbit run (evidence) or the frozen
  MEO baseline (evidence, orbit-specific).
- Critical modules: P(mission failure) = 1 - exp(-rate x duration).
  Assumption: any upset inside a critical module is mission-fatal —
  deliberately conservative; per-net criticality is a later phase.
"""
import math

_ORDER = ("CFG", "FF_STATE", "BRAM_STATE", "DSP_STATE")
# Device-per-bit domain rates for the frozen MEO baseline (evidence:
# effects_coverage.json frozen_seu_hi, Lee-2014-validated). Callers may
# pass their own orbit-run rates instead.
_DEFAULT_RATES = None


def default_domain_rates():
    global _DEFAULT_RATES
    if _DEFAULT_RATES is None:
        import json, os
        p = os.path.join(os.path.dirname(__file__), "data",
                         "effects_coverage.json")
        with open(p, encoding="utf-8") as fh:
            fr = json.load(fh)["frozen_seu_hi"]["per_domain_rates_day_per_bit"]
        _DEFAULT_RATES = {
            "CFG": fr.get("CRAM"),
            "FF_STATE": fr.get("FF"),
            "BRAM_STATE": fr.get("BRAM"),
            "DSP_STATE": None,   # honest gap — no Lee DSP sigma
        }
    return _DEFAULT_RATES


def module_domain_bits(layout):
    """{module_idx: {domain: bits}} measured from tile occupancies."""
    out = {}
    for t in layout["tiles"]:
        mi = t.get("module_idx", -1)
        if mi < 0:
            continue
        rec = out.setdefault(mi, {d: 0 for d in _ORDER})
        for d, b in (t.get("domains") or {}).items():
            if d in rec:
                rec[d] += b
    return out


def assess(layout, critical_modules=None, domain_rates=None,
           duration_days=365.0):
    """Mission-failure estimate for the marked-critical modules.

    critical_modules: list of module_idx the user marked critical
                      (None -> all modules critical).
    domain_rates:     {domain: per-bit rate/day}; missing keys fall
                      back to the frozen MEO baseline; a None value is
                      an honest gap, not zero.
    Returns per-module rates, total critical rate, P(fail), and the
    assumption/evidence labels for the report.
    """
    rates = default_domain_rates()
    rates = dict(rates)
    if domain_rates:
        rates.update(domain_rates)
    mbits = module_domain_bits(layout)
    mods = {m["id"]: m for m in (layout.get("modules") or [])}
    crit = set(critical_modules) if critical_modules is not None \
        else set(mbits)
    per_module = []
    total = 0.0
    gaps = []
    for mi, doms in sorted(mbits.items()):
        rate = None
        for d, bits in doms.items():
            r = rates.get(d)
            if r is None:
                if bits:
                    gaps.append(f"{d} σ 缺数据 → 该域贡献未计入（非零）"
                                if d == "DSP_STATE" else
                                f"{d}: rate missing -> contribution not counted")
                continue
            rate = (rate or 0.0) + bits * r
        m = mods.get(mi, {})
        per_module.append({
            "module_idx": mi,
            "name": m.get("name") or m.get("path") or str(mi),
            "critical": mi in crit,
            "bits": doms,
            "rate_per_day": rate,
        })
        if mi in crit and rate:
            total += rate
    lam = total * duration_days
    return {
        "model": "module_bit_share_v1",
        "duration_days": duration_days,
        "critical_rate_per_day": total,
        "expected_events": lam,
        "p_fail": 1.0 - math.exp(-lam),
        "per_module": per_module,
        "gaps": sorted(set(gaps)),
        "evidence": [
            "module bit shares: measured from placed layout occupancies",
            "domain rates: orbit-run or frozen MEO baseline (Lee 2014 "
            "validated)",
        ],
        "assumptions": [
            "any upset inside a critical module is mission-fatal "
            "(conservative upper bound)",
            "Poisson process: P(fail) = 1 - exp(-rate x duration)",
        ],
    }
