"""Evaluate a user's ECC scheme against the real codeword mapping.

The layout's tiles carry inferred codeword_id / scheme / confidence from
the FFT pipeline (wp5_codeword_report: 92.6% of sites inferred).
evaluate() asks: "if my scheme corrects up to t upset bits per codeword,
what residual rate remains?"

Model (each term labelled):
- Per-codeword upset rate: codeword FF_STATE bits x FF per-bit rate
  (evidence: measured occupancies x orbit/baseline rate).
- Multi-bit multiplicity within one event: geometric P(k) = p(1-p)^(k-1)
  with mean_k. ASSUMPTION — Lee 2014 reports ~10% of events multi-bit;
  the shape here is parameterized, not measured.
- Events with k > t are uncorrectable (DUE). Evidence: SECDED/TMR
  semantics; confidence of the codeword inference is surfaced so
  'proxy' codewords can be discounted by the caller.
"""
import math

from .consequence import default_domain_rates


def codewords(layout):
    """{codeword_id: {bits_by_domain, scheme, confidence, n_tiles}}."""
    out = {}
    for t in layout["tiles"]:
        cid = t.get("codeword_id")
        if not cid:
            continue
        rec = out.setdefault(cid, {"bits": {}, "scheme":
                                   t.get("codeword_scheme"),
                                   "confidence": t.get("codeword_confidence"),
                                   "n_tiles": 0})
        rec["n_tiles"] += 1
        for d, b in (t.get("domains") or {}).items():
            rec["bits"][d] = rec["bits"].get(d, 0) + b
    return out


def _tail_prob(t, mean_k):
    """P(k > t) for geometric k>=1 with mean_k (assumption model)."""
    if mean_k <= 1.0:
        return 0.0 if t >= 1 else 1.0
    p = 1.0 / mean_k
    # P(k>t) = (1-p)^t
    return (1.0 - p) ** t


def evaluate(layout, t_correct=1, mean_k=1.5, domain="FF_STATE",
             domain_rates=None, include_proxy=True):
    rates = default_domain_rates()
    rates = dict(rates)
    if domain_rates:
        rates.update(domain_rates)
    r = rates.get(domain)
    cws = codewords(layout)
    rows = []
    residual = total = 0.0
    by_scheme = {}
    for cid, rec in sorted(cws.items()):
        if not include_proxy and rec["confidence"] == "proxy":
            continue
        bits = rec["bits"].get(domain, 0)
        if not bits or r is None:
            continue
        lam = bits * r
        res = lam * _tail_prob(t_correct, mean_k)
        rows.append({"codeword": cid, "scheme": rec["scheme"],
                     "confidence": rec["confidence"], "bits": bits,
                     "rate_per_day": lam, "residual_per_day": res})
        total += lam
        residual += res
        s = by_scheme.setdefault(rec["scheme"] or "unknown",
                                 {"rate": 0.0, "residual": 0.0})
        s["rate"] += lam
        s["residual"] += res
    return {
        "model": "ecc_eval_v1",
        "t_correct": t_correct, "mean_k": mean_k, "domain": domain,
        "n_codewords": len(rows),
        "in_rate_per_day": total, "residual_per_day": residual,
        "by_scheme": by_scheme,
        "codewords": rows[:64],      # cap payload
        "evidence": [
            "codeword mapping inferred from real layout (wp5: 92.6% "
            "sites inferred, rest proxy-labelled)",
            "per-codeword rate = measured bits x domain per-bit rate",
        ],
        "assumptions": [
            f"multiplicity geometric, mean_k={mean_k} (Lee 2014 ~10% "
            "multi-bit share; shape parameterized, not measured)",
            "k > t per codeword is uncorrectable (DUE)",
        ],
    }
