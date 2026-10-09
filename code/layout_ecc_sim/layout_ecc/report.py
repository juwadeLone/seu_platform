"""One-click RHA-style report: orbit -> rates -> layout -> consequences.

Self-contained HTML (no external requests): environment summary, per-
domain rates, module/consequence table, representative strikes,
provenance and gaps. Persisted under ~/.seu_platform/reports/.
"""
import datetime

_UTC = datetime.timezone.utc
import html
import json
import os

from .consequence import assess, default_domain_rates
from .mitigation import advise

REPORTS_ROOT = os.path.join(os.path.expanduser("~"), ".seu_platform",
                            "reports")


def _rate_table(rates):
    rows = "".join(
        f"<tr><td>{html.escape(d)}</td><td>{'gap' if r is None else f'{r:.3e}'}"
        f"</td></tr>"
        for d, r in rates.items())
    return ("<table><tr><th>domain</th><th>per-bit upsets/day</th></tr>"
            + rows + "</table>")


def build_report(layout, state, duration_days=365.0,
                 target_rate_per_day=None, critical_modules=None,
                 domain_rates=None, mission_result=None):
    rates = default_domain_rates()
    if domain_rates:
        rates.update(domain_rates)
    con = assess(layout, critical_modules, rates, duration_days)
    bits = {d: sum(m["bits"].get(d, 0)
                   for m in con["per_module"]) for d in
            ("CFG", "FF_STATE", "BRAM_STATE", "DSP_STATE")}
    dev_rates = {d: (r * bits[d] if r is not None else None)
                 for d, r in rates.items()}
    mit = advise(dev_rates, bits,
                 target_rate_per_day or (0.01 * sum(
                     r for r in dev_rates.values() if r)),
                 duration_days)
    esc = html.escape
    mod_rows = "".join(
        f"<tr><td>{esc(m['name'])}</td><td>{'critical' if m['critical'] else ''}"
        f"</td><td>{sum(m['bits'].values()):,}</td>"
        f"<td>{'gap' if m['rate_per_day'] is None else '%.3e' % m['rate_per_day']}</td></tr>"
        for m in con["per_module"])
    rec_rows = "".join(
        f"<tr><td>{esc(r['domain'])}</td><td>{esc(r['label'])}</td>"
        f"<td>{r['before_per_day']:.3e}</td><td>{r['residual_per_day']:.3e}</td>"
        f"<td>{esc(r['note'])}</td></tr>"
        for r in mit["recommendations"])
    env = ""
    if mission_result:
        o = mission_result.get("orbit", {})
        env = (f"<p>Orbit {o.get('altitude_km')} km / "
               f"{o.get('inclination_deg')}&deg; — config SHA "
               f"{mission_result.get('provenance', {}).get('config_sha256', '')[:12]}</p>")
    doc = f"""<!doctype html><html><head><meta charset="utf-8">
<title>SEU Platform — RHA Report</title>
<style>body{{font:14px/1.6 'Segoe UI',sans-serif;max-width:960px;margin:28px auto;
padding:0 18px;color:#1c2733}}h1{{color:#0a4f7e}}h2{{color:#0a4f7e;
border-bottom:1px solid #ccc}}table{{border-collapse:collapse;margin:8px 0}}
td,th{{border:1px solid #bbb;padding:4px 9px}}.gap{{color:#a33}}
.small{{font-size:12px;color:#555}}</style></head><body>
<h1>Radiation Effects Report — {esc(layout.get('design') or 'design')}</h1>
<p class="small">Generated {datetime.datetime.now(_UTC).isoformat()}Z by
seu_platform · device {esc(str(layout.get('part')))} ·
{layout.get('n_placed')} placed primitives on {layout.get('n_sites')} sites</p>
{env}
<h2>1 Environment &amp; rates (per-bit)</h2>
{_rate_table(rates)}
<h2>2 Module consequence assessment ({duration_days:.0f} d)</h2>
<p>Critical rate <b>{con['critical_rate_per_day']:.3e}/day</b>;
P(mission failure) = <b>{con['p_fail']:.3g}</b>;
expected events {con['expected_events']:.3g}</p>
<table><tr><th>module</th><th></th><th>bits</th><th>rate/day</th></tr>
{mod_rows}</table>
<h2>3 Mitigation advice</h2>
<p>Residual total <b>{mit['residual_total_per_day']:.3e}/day</b>
(target {mit['target_per_day']:.3e}/day —
{'MEETS' if mit['meets_target'] else 'DOES NOT MEET'})</p>
<table><tr><th>domain</th><th>option</th><th>before</th><th>residual</th>
<th>model</th></tr>{rec_rows}</table>
<h2>4 Provenance &amp; honesty</h2>
<ul><li>{'</li><li>'.join(esc(e) for e in con['evidence'])}</li></ul>
<p>Assumptions (labelled, user-tunable):</p>
<ul><li>{'</li><li>'.join(esc(a) for a in con['assumptions'] + mit['assumptions'])}</li></ul>
<p class="gap">Gaps (not zero): {esc('; '.join(con['gaps']) or 'none')}
{'; missing device rates: ' + ', '.join(mit['gap_domains']) if mit['gap_domains'] else ''}</p>
<p class="small">{esc(layout.get('disclaimer') or '')}</p>
</body></html>"""
    os.makedirs(REPORTS_ROOT, exist_ok=True)
    fn = os.path.join(REPORTS_ROOT, datetime.datetime.now(_UTC).strftime(
        "report_%Y%m%d-%H%M%S.html"))
    with open(fn, "w", encoding="utf-8") as fh:
        fh.write(doc)
    return {"html": doc, "path": fn,
            "p_fail": con["p_fail"],
            "residual_per_day": mit["residual_total_per_day"],
            "meets_target": mit["meets_target"]}
