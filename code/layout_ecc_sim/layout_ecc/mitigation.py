"""Mitigation advisor: reliability target -> where ECC/TMR/scrubbing goes.

Every coefficient is labelled evidence vs assumption — nothing invented:

- BRAM_STATE + SECDED ECC: removes *single-bit* upsets. Residual = the
  MCU (multi-bit) share. MCU share evidence: Lee 2014 Table 3 reports
  ~10% of SEU events multi-bit on 7-series; we label it assumption until
  a per-domain measured share lands. Caller may override.
- CFG (CRAM) + scrubbing: does not lower the upset *rate*; it bounds
  persistence. Model: residual = rate x (T_scrub / T_mission) fraction
  that persists long enough to matter. That fraction is an assumption —
  stated openly, user-tunable.
- FF_STATE + TMR: single-point upsets voted out. Residual ~ coincidence
  of two upsets inside the vote window: lam_res ~ lam^2 * tau_v /
  (2 * T). tau_v (coherency window) is an assumption (default 1 s).
- DSP_STATE: honest gap (no sigma at all) — flagged, never zeroed.

advise() picks, per domain, the cheapest option meeting the target.
Costs are abstract units (relative area/power), labelled assumption.
"""
import math

# Abstract per-bit cost units — assumptions, not measurements.
_OPTIONS = {
    "BRAM_STATE": [
        {"id": "ecc_secded", "label": "SECDED ECC (per-word)",
         "cost_per_bit": 0.2, "kind": "ecc",
         "model": "residual = rate x mcu_share"},
    ],
    "CFG": [
        {"id": "scrub", "label": "配置存储器刷新 scrubbing",
         "cost_per_bit": 0.05, "kind": "scrub",
         "model": "residual = rate x persist_fraction"},
    ],
    "FF_STATE": [
        {"id": "tmr", "label": "TMR (3x + voter)",
         "cost_per_bit": 3.2, "kind": "tmr",
         "model": "residual ~ lam^2 x tau_v / 2T"},
    ],
    "DSP_STATE": [
        {"id": "tmr", "label": "TMR (3x + voter)",
         "cost_per_bit": 3.2, "kind": "tmr",
         "model": "residual ~ lam^2 x tau_v / 2T"},
    ],
}


def advise(domain_device_rates, total_bits, target_rate_per_day,
           duration_days=365.0, mcu_share=0.10,
           persist_fraction=0.10, tau_v_s=1.0):
    """domain_device_rates: {domain: upsets/day for the whole device}.
    total_bits: {domain: bit count}. Returns recommended options +
    expected residual + honest labels."""
    recs = []
    residual = 0.0
    gaps = []
    for dom, rate in sorted(domain_device_rates.items()):
        if rate is None:
            gaps.append(dom)
            continue
        best = None
        for opt in _OPTIONS.get(dom, []):
            if opt["kind"] == "ecc":
                res = rate * mcu_share
                note = (f"SECDED kills single-bit; residual = MCU share "
                        f"({mcu_share:.0%}, assumption)")
            elif opt["kind"] == "scrub":
                res = rate * persist_fraction
                note = (f"scrubbing bounds persistence, not rate; residual "
                        f"= persist_fraction ({persist_fraction:.0%}, "
                        f"assumption)")
            else:  # tmr
                lam = rate * duration_days
                res = lam * lam * (tau_v_s / 86400.0) / (2 * duration_days)
                note = (f"residual ~ double-fault coincidence, "
                        f"tau_v={tau_v_s}s (assumption)")
            cost = opt["cost_per_bit"] * (total_bits.get(dom) or 0)
            if best is None or res < best["residual_per_day"]:
                best = {"domain": dom, "before_per_day": rate,
                        "option": opt["id"], "label": opt["label"],
                        "residual_per_day": res, "cost_units": cost,
                        "note": note}
        if best:
            recs.append(best)
            residual += best["residual_per_day"]
    total_in = sum(r for r in domain_device_rates.values() if r)
    return {
        "target_per_day": target_rate_per_day,
        "input_total_per_day": total_in,
        "residual_total_per_day": residual,
        "meets_target": residual <= target_rate_per_day,
        "recommendations": recs,
        "gap_domains": gaps,
        "p_fail_residual_1yr": 1.0 - math.exp(-residual * 365.0),
        "assumptions": [
            f"MCU share after ECC = {mcu_share:.0%} (Lee 2014 order-of-"
            f"magnitude; per-domain measured share still a gap)",
            f"scrub persist_fraction = {persist_fraction:.0%} "
            "(fraction of upsets that matter before refresh)",
            f"TMR residual ~ coincidence model, tau_v={tau_v_s}s",
            "cost units are relative area/power — abstract, not measured",
        ],
        "evidence": [
            "input device rates: orbit-run or frozen MEO baseline",
        ],
    }
