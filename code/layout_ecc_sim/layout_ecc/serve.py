"""Full-platform HTTP server: strike viewer + orbit dashboard + effects + SAR.

Serves all five pages on 127.0.0.1 without pywebview:

    python -m layout_ecc.serve [port]        # dev
    seu-platform [port]                      # console script (pip install)

The orbit pages mount orbit_seu when it can be resolved (vendored
code/orbit_seu, ORBIT_SEU_ROOT, or an installed package). Without it the
other four pages still serve; /orbit returns a clear message.
"""
import hashlib
import json
import os
import sys
import threading
import time
import webbrowser
from http.server import ThreadingHTTPServer

VERSION = "1.2.0"

UPLOAD_ROOT = os.path.join(os.path.expanduser("~"),
                           ".seu_platform", "uploads")
_MAX_UPLOAD_CHARS = 60_000_000   # ~60 MB of text per request part


def _rewrite_oseu_prefixes(text):
    """Rewrite only the path prefixes already used by the bundled orbit_seu
    pages: "/static/" -> "/oseu-static/", "/api/run" -> "/oseu/api/run",
    "/api/import_spenvis" -> "/oseu/api/import_spenvis"."""
    pairs = (("/static/", "/oseu-static/"),
             ("/api/run", "/oseu/api/run"),
             ("/api/devices", "/oseu/api/devices"),
             ("/api/import_spenvis", "/oseu/api/import_spenvis"))
    if isinstance(text, bytes):
        for old, new in pairs:
            ob, nb = old.encode(), new.encode()
            for q in (b'"', b"'"):
                text = text.replace(q + ob, q + nb)
        return text
    for old, new in pairs:
        for q in ('"', "'"):
            text = text.replace(q + old, q + new)
    return text


_BANNER = (
    '<div style="padding:6px 14px;font:12px \'Segoe UI\',\'Microsoft YaHei\';'
    'background:rgba(10,20,36,.92);border-bottom:1px solid #1b3350;'
    'color:#7f93ab">'
    '<a href="/" style="color:#00e5ff;text-decoration:none">打击</a>'
    '&nbsp;|&nbsp;'
    '<a href="/orbit" style="color:#eaf6ff;text-decoration:none">轨道</a>'
    '&nbsp;|&nbsp;'
    '<a href="/effects" style="color:#00e5ff;text-decoration:none">效应总览</a>'
    '&nbsp;&nbsp;·&nbsp;&nbsp;'
    '<a href="/orbit3d" style="color:#00e5ff;text-decoration:none">⛶ 独立 3D 视图</a>'
    '</div>')


def _oseu_page(name):
    from .orbit_env import _roots
    lib, env, _cfg = _roots()
    webapp = os.path.join(lib, "orbit_seu", "webapp")
    with open(os.path.join(webapp, name), "rb") as fh:
        html = fh.read().decode("utf-8")
    html = _rewrite_oseu_prefixes(html)
    html = html.replace("<body>", "<body>" + _BANNER, 1)
    return html.encode("utf-8")


_ORBIT_MISSING = (
    '<html><body style="background:#0a1424;color:#9db4cc;font-family:sans-serif;'
    'padding:40px"><h2>轨道页不可用</h2><p>未找到 orbit_seu：请把仓库 '
    '<code>code/orbit_seu</code> 放在本包旁、设 ORBIT_SEU_ROOT，'
    '或 <code>pip install</code> 包含 orbit_seu 的版本。</p>'
    '<p><a href="/" style="color:#00e5ff">返回打击页</a></p></body></html>')


def make_handler(gui):
    class _FullHandler(gui._Handler):
        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                web = os.path.join(os.path.dirname(gui.__file__), "webapp",
                                   "index.html")
                with open(web, "r", encoding="utf-8") as fh:
                    html = fh.read()
                html = html.replace("__APP_VERSION__", VERSION)
                self._send(200, "text/html; charset=utf-8", html.encode("utf-8"))
                return
            if path in ("/effects", "/effects.html"):
                web = os.path.join(os.path.dirname(gui.__file__), "webapp",
                                   "effects.html")
                with open(web, "r", encoding="utf-8") as fh:
                    html = fh.read()
                html = html.replace("__APP_VERSION__", VERSION)
                self._send(200, "text/html; charset=utf-8", html.encode("utf-8"))
                return
            if path in ("/orbit", "/orbit.html"):
                try:
                    self._send(200, "text/html; charset=utf-8",
                               _oseu_page("index.html"))
                except FileNotFoundError:
                    self._send(503, "text/html; charset=utf-8",
                               _ORBIT_MISSING.encode("utf-8"))
                return
            if path in ("/orbit3d", "/oseu/3d.html", "/3d"):
                try:
                    self._send(200, "text/html; charset=utf-8",
                               _oseu_page("3d.html"))
                except FileNotFoundError:
                    self._send(503, "text/html; charset=utf-8",
                               _ORBIT_MISSING.encode("utf-8"))
                return
            if path.startswith("/oseu-static/"):
                name = os.path.basename(path[len("/oseu-static/"):])
                try:
                    from .orbit_env import _roots
                    lib, _env, _cfg = _roots()
                except FileNotFoundError:
                    self._send(404, "text/plain; charset=utf-8", b"not found")
                    return
                full = os.path.join(lib, "orbit_seu", "webapp", name)
                ext = os.path.splitext(full)[1].lower()
                mime = {".js": "application/javascript; charset=utf-8",
                        ".jpg": "image/jpeg", ".png": "image/png"}.get(ext)
                if name and os.path.isfile(full) and mime:
                    if ext == ".js":
                        with open(full, "rb") as fh:
                            body = _rewrite_oseu_prefixes(fh.read())
                        self._send(200, mime, body)
                    else:
                        with open(full, "rb") as fh:
                            self._send(200, mime, fh.read())
                    return
            if path == "/oseu/api/devices":
                try:
                    from .orbit_env import _roots
                    lib, _env, _cfg = _roots()
                    if lib not in sys.path:
                        sys.path.append(lib)
                    from orbit_seu.device import list_devices
                    self._send(200, "application/json",
                               json.dumps(list_devices(),
                                          ensure_ascii=False).encode("utf-8"))
                except FileNotFoundError as exc:
                    self._send(503, "application/json",
                               json.dumps({"error": str(exc)}).encode("utf-8"))
                return
            super().do_GET()

        def do_POST(self):
            path = self.path.split("?", 1)[0]
            if path == "/oseu/api/import_spenvis":
                self._handle_import_spenvis()
                return
            if path != "/oseu/api/run":
                super().do_POST()
                return
            try:
                n = int(self.headers.get("Content-Length", 0))
                config = json.loads(self.rfile.read(n) or b"{}")
                from .orbit_env import _roots
                lib, env, _cfg = _roots()
                if lib not in sys.path:
                    sys.path.append(lib)
                e = config.get("environment") or {}
                for key in ("let_spectra_files",):
                    for k, rel in list((e.get(key) or {}).items()):
                        e[key][k] = os.path.normpath(os.path.join(env, rel))
                if e.get("proton_file"):
                    e["proton_file"] = os.path.normpath(
                        os.path.join(env, e["proton_file"]))
                bo = e.get("coefficients_csv")
                if bo and not os.path.isabs(bo):
                    e["coefficients_csv"] = os.path.normpath(
                        os.path.join(env, bo))
                from orbit_seu.gui import _safe
                from orbit_seu.mission import run
                self._send(200, "application/json",
                           json.dumps(_safe(run(config))).encode("utf-8"))
            except FileNotFoundError as exc:
                self._send(503, "application/json",
                           json.dumps({"error": str(exc)}).encode("utf-8"))
            except Exception as exc:
                self._send(400, "application/json",
                           json.dumps({"error": f"{type(exc).__name__}: {exc}"}
                                      ).encode("utf-8"))

        def _handle_import_spenvis(self):
            """POST /oseu/api/import_spenvis — drop a SPENVIS export in,
            get a ready-to-use 'files' environment block out. The logic
            lives in orbit_seu.spenvis_import.handle_import (shared with
            the standalone orbit_seu server)."""
            try:
                n = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(n) or b"{}")
                from .orbit_env import _roots
                lib, env, _cfg = _roots()
                if lib not in sys.path:
                    sys.path.append(lib)
                from orbit_seu.spenvis_import import handle_import
                out = handle_import(body)
                self._send(200, "application/json",
                           json.dumps(out).encode("utf-8"))
            except FileNotFoundError as exc:
                self._send(503, "application/json",
                           json.dumps({"error": str(exc)}).encode("utf-8"))
            except Exception as exc:
                self._send(400, "application/json",
                           json.dumps({"error": f"{type(exc).__name__}: {exc}"}
                                      ).encode("utf-8"))

    return _FullHandler


def _prewarm_orbit():
    try:
        from .orbit_env import compute_orbit_payload
        payload = compute_orbit_payload()
        print("[layout-ecc] orbit env prewarmed: device/day="
              f"{payload['rates_per_s']['total_per_device'] * 86400:.4f}")
    except Exception as exc:
        print(f"[layout-ecc] orbit env prewarm skipped: {exc}")


def main(port=0, open_browser=True):
    argv = sys.argv[1:]
    if argv:
        try:
            port = int(argv[0])
        except ValueError:
            pass
    if "--no-browser" in argv:
        open_browser = False
    if "--server-only" in argv:
        open_browser = False
    from layout_ecc import gui  # loads the layout once at import
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(gui))
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{port}/"
    print(f"[layout-ecc] version {VERSION}; server up on {url}; "
          f"sites={gui._LAYOUT['n_sites']}")
    threading.Thread(target=_prewarm_orbit, daemon=True).start()
    if open_browser:
        webbrowser.open(url)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\n[layout-ecc] stopped.")
        srv.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
