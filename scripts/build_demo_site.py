"""Build a static snapshot of the platform for GitHub Pages.

Starts the real server, captures every page's HTML plus the JSON APIs,
then rewrites the pages to replay the snapshots through a fetch shim —
no backend needed. Output: demo/ (deploy to Pages).

    python scripts/build_demo_site.py [--port 0] [--out demo]
"""
import json
import os
import shutil
import sys
import threading
import time
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "code", "layout_ecc_sim"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "code", "orbit_seu"))

REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
_out = os.path.join(REPO, "demo")
OUT = _out

BANNER = (
    '<div style="padding:8px 16px;font:12px \'Segoe UI\',sans-serif;'
    'background:#132032;color:#8fb3d9;border-bottom:1px solid #1b3350">'
    'Static snapshot of a live run &middot; interactive strike/orbit controls '
    'replay precomputed responses &middot; full simulator: '
    '<code style="color:#00e5ff">pip install . &amp;&amp; seu-platform</code> '
    'from <a style="color:#00e5ff" href="https://github.com/juwadeLone/'
    'seu_platform">juwadeLone/seu_platform</a> &middot; '
    '<a style="color:#00e5ff" href="docs.html">Docs</a></div>')

LANDING_HTML = '<!doctype html><html lang="en"><head><meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1">\n<title>SEU Platform — Radiation effects on SRAM FPGAs, end to end</title>\n<style>\nbody{font:15px/1.65 \'Segoe UI\',system-ui,sans-serif;background:#0a1120;color:#d8e9f7;\nmargin:0}.wrap{max-width:900px;margin:0 auto;padding:0 22px}\n.hero{padding:70px 0 40px;text-align:center}\nh1{font-size:38px;color:#fff;margin:0 0 10px}\n.tag{font-size:19px;color:#8fb3d9;max-width:640px;margin:0 auto 26px}\n.cta a{display:inline-block;margin:5px 8px;padding:11px 22px;border-radius:7px;\nbackground:#00b8e6;color:#04222e;font-weight:700;text-decoration:none}\n.cta a.gh{background:#1b3350;color:#cfe3f4}\nh2{color:#00e5ff;font-size:21px;margin-top:44px}\n.chain{display:flex;gap:8px;flex-wrap:wrap;justify-content:center;margin:26px 0}\n.chain span{background:#132032;border:1px solid #1b3350;border-radius:6px;\npadding:9px 13px;font-size:13px}\ntable{border-collapse:collapse;margin:10px auto}\ntd,th{border:1px solid #1b3350;padding:6px 12px;font-size:14px}\ncode{background:#132032;padding:1px 6px;border-radius:4px}\npre{background:#132032;padding:13px;border-radius:8px;overflow:auto}\na{color:#00b8e6}ul li{margin:7px 0}\n.foot{color:#5a7a99;font-size:13px;text-align:center;padding:30px 0}\n</style></head><body><div class="wrap">\n<div class="hero">\n<h1>SEU Platform</h1>\n<p class="tag">SPENVIS tells you what radiation is on your orbit.\nThis platform tells you what that radiation does to your design.</p>\n<div class="cta">\n<a href="index.html">Try the live demo</a>\n<a class="gh" href="https://github.com/juwadeLone/seu_platform">GitHub</a>\n<a class="gh" href="docs.html">Docs</a>\n</div></div>\n<div class="chain">\n<span>Orbit environment (SPENVIS/CREME96)</span><b>→</b>\n<span>Per-bit upset rates</span><b>→</b>\n<span>Ion strike on real Vivado layout</span><b>→</b>\n<span>Module &amp; mission consequences</span><b>→</b>\n<span>Mitigation advice + RHA report</span>\n</div>\n<h2>What you get</h2>\n<ul>\n<li><b>Any orbit SPENVIS covers</b> — import <code>spenvis_gcf.txt</code> /\n<code>.let.txt</code> / proton spectra; orbit elements lock from the manifest</li>\n<li><b>Validated numbers</b> — whole-chip 46.2 upsets/day in MEO, within 10% of\nLee et al. IEEE REDW 2014</li>\n<li><b>Your design, not a toy</b> — drop your own\n<code>primitive_map.csv</code> from any placed&amp;routed Vivado design; ions land\non your netlist</li>\n<li><b>Consequences, not just rates</b> — mark critical modules → P(mission\nfailure); ask where ECC/TMR/scrubbing goes → per-domain residual advice</li>\n<li><b>Honest data</b> — every number carries provenance; gaps are labelled\ngaps, never invented</li>\n<li><b>EN/中 UI</b> on every page; stdlib-only Python, no dependencies</li>\n</ul>\n<h2>Install</h2>\n<pre>pip install git+https://github.com/juwadeLone/seu_platform.git\nseu-platform</pre>\n<h2>The five pages</h2>\n<table>\n<tr><td><a href="index.html">Strike</a></td><td>drop an ion on the die; ECC validator + RHA report</td></tr>\n<tr><td><a href="orbit.html">Orbit</a></td><td>mission config, SPENVIS import, device library</td></tr>\n<tr><td><a href="orbit3d.html">Orbit 3D</a></td><td>cutoff rigidity around the Earth</td></tr>\n<tr><td><a href="effects.html">Effects</a></td><td>effect taxonomy &amp; rates overview</td></tr>\n<tr><td><a href="sar.html">SAR</a> · <a href="seu.html">Inside</a></td><td>on-board SAR consequences · device internals</td></tr>\n</table>\n<p class="foot">MIT · <a href="https://github.com/juwadeLone/seu_platform">juwadeLone/seu_platform</a> · static snapshot of a live run</p>\n</div></body></html>\n'

DOCS_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>SEU Platform — Docs</title>
<style>body{font:14px/1.6 'Segoe UI',sans-serif;background:#0c1522;color:#cfe3f4;
max-width:880px;margin:32px auto;padding:0 20px}h1{color:#00e5ff}
h2{color:#8fb3d9;border-bottom:1px solid #1b3350;padding-bottom:4px}
code{background:#132032;padding:1px 5px;border-radius:3px}
table{border-collapse:collapse}td,th{border:1px solid #1b3350;padding:5px 10px}
a{color:#00e5ff}</style></head><body>
<h1>SEU Platform — Usage &amp; Provenance</h1>
<p>Space-radiation effects on SRAM FPGAs: orbit environment → per-bit upset rates →
ion strike on a real Vivado layout → mission-level consequences.
<b>Downstream of SPENVIS:</b> it tells you what radiation is on your orbit;
this platform tells you what that radiation does to your design.</p>

<h2>Install &amp; run</h2>
<pre style="background:#132032;padding:10px">pip install git+https://github.com/juwadeLone/seu_platform.git
seu-platform            # merged server, all pages
# or per-page:  python -m layout_ecc.gui | python -m orbit_seu.gui</pre>
<p>Pages: <a href="index.html">Strike</a> · <a href="orbit.html">Orbit</a> ·
<a href="orbit3d.html">Orbit 3D</a> · <a href="effects.html">Effects</a> ·
<a href="sar.html">SAR</a> · <a href="seu.html">Inside the device</a>.
Every page has an EN/中 toggle (bottom-right).</p>

<h2>Bring your own data</h2>
<ul>
<li><b>SPENVIS orbit export</b> — Orbit page → "Import SPENVIS exports":
<code>spenvis_gcf.txt</code>, per-group <code>.let.txt</code>, or a trapped-proton
spectrum. <code>POST /oseu/api/import_spenvis</code> does the same headless.</li>
<li><b>Device library</b> — bundled: xc7vx690t (family-borrow anchors),
xc7k325t (Lee 2014 native DUT), xc7z045 (bits = gap). Upload your own
σ(LET)/σ(E) JSON from the Orbit page, or drop a file into
<code>orbit_seu/env_data/devices/</code>.</li>
<li><b>Your Vivado layout</b> — Strike page → "导入布局": a
<code>primitive_map.csv</code> (unit_id, hier_cell, ref_name, loc, bel, site,
tile, grid_x, grid_y) from a placed&amp;routed DCP. Strikes then land on
<i>your</i> netlist, not the bundled P1 FFT.</li>
</ul>

<h2>Provenance (every number carries a source)</h2>
<table>
<tr><th>Data</th><th>Source</th></tr>
<tr><td>GCR LET spectra (MEO 20200km/55°)</td><td>SPENVIS CREME96 export, solar min, 100 mil Al</td></tr>
<tr><td>xc7vx690t σ(LET) Weibull</td><td>Lee et al., IEEE TNS/REDW 2014 (family-borrowed anchors)</td></tr>
<tr><td>xc7k325t bits + proton anchors</td><td>Lee 2014 DUT itself — native, not borrowed</td></tr>
<tr><td>Proton σ(E) anchors</td><td>Wirthlin et al., JINST 2014 (180 MeV lower bound)</td></tr>
<tr><td>P1 FFT layout</td><td>Own Vivado OOC place&amp;route of a 1024-pt FFT</td></tr>
<tr><td>Cross-check</td><td>Whole-chip 46.2/day vs Lee 2014 — within 10%</td></tr>
</table>
<p>Missing data is marked <b>gap</b>, never invented (e.g. xc7z045 bit count,
FF/DSP proton cross-sections).</p>
<p><a href="https://github.com/juwadeLone/seu_platform">Source</a> · MIT license.</p>
</body></html>
"""

FETCH_SHIM = """
<script>
(function(){
  var real = window.fetch;
  var base = document.getElementById('static-demo-base').getAttribute('data-api');
  var strikes = null;
  var strikeIdx = 0;
  window.fetch = function(url, opts){
    var u = (typeof url === 'string') ? url : url.url;
    var path = u.split('?')[0];
    var map = {'/api/layout':'layout.json','/api/effects':'effects.json'};
    if (map[path]) return real(base + '/' + map[path], opts);
    if (path === '/api/strike' && opts && (opts.method||'GET').toUpperCase()==='POST'){
      var files = window.__STRIKE_FILES__ || [];
      if (!files.length) return Promise.reject(new Error('no strikes'));
      var f = files[strikeIdx++ % files.length];
      return real(base + '/strikes/' + f, opts);
    }
    if (path === '/oseu/api/run') return real(base + '/orbit_run.json', opts);
    if (path === '/api/run') return real(base + '/orbit_run.json', opts);
    return real(url, opts);
  };
})();
</script>
"""


def get(url):
    return urllib.request.urlopen(url, timeout=120).read()


def post(url, payload):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    return urllib.request.urlopen(req, timeout=120).read()


def save(path, data):
    full = os.path.join(_out, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    mode = "wb" if isinstance(data, bytes) else "w"
    with open(full, mode, encoding=None if isinstance(data, bytes) else "utf-8") as fh:
        fh.write(data)


_ROUTES = {"/": "index.html", "/index.html": "index.html",
           "/orbit": "orbit.html", "/orbit3d": "orbit3d.html",
           "/sar": "sar.html", "/seu": "seu.html",
           "/effects": "effects.html", "/3d": "orbit3d.html"}


def _rel(html):
    """Rewrite absolute hrefs/srcs to relative paths for Pages hosting."""
    html = html.replace('"/oseu-static/', '"oseu-static/')
    html = html.replace("'/oseu-static/", "'oseu-static/")
    html = html.replace('"/static/', '"static/')
    html = html.replace("'/static/", "'static/")
    for route, name in _ROUTES.items():
        html = html.replace('href="' + route + '"', 'href="' + name + '"')
    return html


def inject(html, api_relprefix):
    """Insert the static-demo shim + banner into served HTML."""
    html = _rel(html)
    shim = FETCH_SHIM.replace(
        "<script>",
        '<script>var __d=document.createElement("div");__d.id="static-demo-base";'
        '__d.setAttribute("data-api","' + api_relprefix + '");'
        'document.documentElement.appendChild(__d);', 1)
    html = html.replace("<head>", "<head>" + shim, 1) \
        if "<head>" in html else shim + html
    html = html.replace("<body>", "<body>" + BANNER, 1) \
        if "<body>" in html else BANNER + html
    return html


def main():
    global _out
    _out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else OUT
    if os.path.isdir(_out):
        shutil.rmtree(_out)
    os.makedirs(_out)

    from layout_ecc import serve, gui
    from http.server import ThreadingHTTPServer
    srv = ThreadingHTTPServer(("127.0.0.1", 0), serve.make_handler(gui))
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    try:
        # ---- pages (each fetch already returns orbit-mounted HTML) ----
        pages = {"/": "index.html", "/effects": "effects.html",
                 "/sar": "sar.html", "/seu": "seu.html",
                 "/orbit": "orbit.html", "/orbit3d": "orbit3d.html"}
        for route, name in pages.items():
            try:
                html = get(base + route).decode("utf-8")
            except Exception as exc:
                print(f"!! {route}: {exc} — skipped")
                continue
            save(name, inject(html, "api"))
            print("page", name, len(html), "B")

        # ---- JSON APIs ----
        save("api/layout.json", get(base + "/api/layout"))
        save("api/effects.json", get(base + "/api/effects"))
        print("api layout + effects saved")

        # ---- a spread of representative strikes ----
        strikes = [
            {"x0": 600, "y0": 400, "let": 5,  "theta": 0,  "phi": 0},
            {"x0": 900, "y0": 500, "let": 15, "theta": 30, "phi": 45},
            {"x0": 400, "y0": 600, "let": 30, "theta": 45, "phi": 90},
            {"x0": 750, "y0": 350, "let": 60, "theta": 60, "phi": 135},
        ]
        files = []
        for i, s in enumerate(strikes):
            payload = dict(s, a0=12, k_let=0.25, seed=i + 1,
                           kernel_model="anchored", flip_model="weibull")
            body = post(base + "/api/strike", payload)
            fn = f"strike_{i}.json"
            save(f"api/strikes/{fn}", body)
            files.append(fn)
            print("strike", fn, len(body), "B")
        save("api/strikes/manifest.json", json.dumps(files))
        shim_files = ("<script>window.__STRIKE_FILES__=" +
                      json.dumps(files) + ";</script>")
        for name in ("index.html",):
            p = os.path.join(_out, name)
            if os.path.isfile(p):
                with open(p, encoding="utf-8") as fh:
                    html = fh.read()
                html = html.replace("</head>", shim_files + "</head>", 1)
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write(html)

        # ---- orbit mission result (frozen example config) ----
        cfg_path = os.path.join(
            REPO, "code", "orbit_seu", "orbit_seu", "examples",
            "xc7vx690t_measured_meo.json")
        with open(cfg_path, encoding="utf-8") as fh:
            cfg = json.load(fh)
        try:
            body = post(base + "/oseu/api/run", cfg)
            save("api/orbit_run.json", body)
            print("orbit_run.json", len(body), "B")
        except Exception as exc:
            print("!! orbit run failed:", exc)

        # ---- layout_ecc webapp assets -> /static/ ----
        lweb = os.path.join(REPO, "code", "layout_ecc_sim", "layout_ecc",
                            "webapp")
        for fn in os.listdir(lweb):
            if os.path.splitext(fn)[1] in (".js", ".jpg", ".png", ".css"):
                body = open(os.path.join(lweb, fn), "rb").read()
                if fn.endswith(".js"):
                    body = body.replace(b'"/static/', b'"static/') \
                               .replace(b"'/static/", b"'static/")
                save(f"static/{fn}", body)

        # ---- orbit webapp static assets -> /oseu-static/ ----
        webapp = os.path.join(REPO, "code", "orbit_seu", "orbit_seu", "webapp")
        for fn in os.listdir(webapp):
            if os.path.splitext(fn)[1] in (".js", ".jpg", ".png", ".css"):
                body = open(os.path.join(webapp, fn), "rb").read()
                if fn.endswith(".js"):
                    body = body.replace(b'"/static/', b'"oseu-static/') \
                               .replace(b"'/static/", b"'oseu-static/")
                save(f"oseu-static/{fn}", body)

        save("docs.html", DOCS_HTML)
        save("landing.html", LANDING_HTML)
        save("README.txt",
             "Static snapshot of seu_platform for GitHub Pages.\n"
             "Interactive: pip install . && seu-platform\n")
        print("done ->", _out)
    finally:
        srv.shutdown()


if __name__ == "__main__":
    main()
