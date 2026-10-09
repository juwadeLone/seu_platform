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
    'seu_platform">juwadeLone/seu_platform</a></div>')

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

        save("README.txt",
             "Static snapshot of seu_platform for GitHub Pages.\n"
             "Interactive: pip install . && seu-platform\n")
        print("done ->", _out)
    finally:
        srv.shutdown()


if __name__ == "__main__":
    main()
