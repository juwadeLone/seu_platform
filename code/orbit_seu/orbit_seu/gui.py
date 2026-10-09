"""Local web GUI: python -m orbit_seu.gui [port]

Serves a single-page dashboard on 127.0.0.1 (stdlib http.server only).
The browser form POSTs a mission config to /api/run and renders rates,
mission statistics and charts. Offline, no external CDNs.
"""
import json
import math
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .mission import run

_INDEX = os.path.join(os.path.dirname(__file__), "webapp", "index.html")
_STATIC_DIR = os.path.join(os.path.dirname(__file__), "webapp")
_STATIC_MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".png": "image/png", ".svg": "image/svg+xml",
                ".js": "application/javascript", ".html": "text/html"}


def _safe(obj):
    """Recursively replace non-finite floats (JSON.parse would choke)."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe(v) for v in obj]
    return obj


class _Handler(BaseHTTPRequestHandler):

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            with open(_INDEX, "rb") as fh:
                self._send(200, "text/html; charset=utf-8", fh.read())
            return
        if path in ("/3d", "/3d.html"):
            p3 = os.path.join(_STATIC_DIR, "3d.html")
            with open(p3, "rb") as fh:
                self._send(200, "text/html; charset=utf-8", fh.read())
            return
        if path == "/api/devices":
            try:
                from .device import list_devices
                self._send(200, "application/json",
                           json.dumps(list_devices(),
                                      ensure_ascii=False).encode("utf-8"))
            except Exception as exc:
                self._send(500, "application/json",
                           json.dumps({"error": str(exc)}).encode("utf-8"))
            return
        if path.startswith("/static/"):
            name = os.path.basename(path[len("/static/"):])
            full = os.path.join(_STATIC_DIR, name)
            ext = os.path.splitext(full)[1].lower()
            if name and os.path.isfile(full) and ext in _STATIC_MIME:
                with open(full, "rb") as fh:
                    self._send(200, _STATIC_MIME[ext], fh.read())
                return
        self._send(404, "text/plain; charset=utf-8", b"not found")

    def do_POST(self):
        if self.path == "/api/import_spenvis":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length) or b"{}")
                from .spenvis_import import handle_import
                self._send(200, "application/json",
                           json.dumps(handle_import(body)).encode("utf-8"))
            except Exception as exc:
                self._send(400, "application/json",
                           json.dumps({"error": f"{type(exc).__name__}: {exc}"}
                                      ).encode("utf-8"))
            return
        if self.path != "/api/run":
            self._send(404, "text/plain; charset=utf-8", b"not found")
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            config = json.loads(self.rfile.read(length) or b"{}")
            results = _safe(run(config))
            self._send(200, "application/json",
                       json.dumps(results).encode("utf-8"))
        except Exception as exc:  # surface config errors to the page
            self._send(400, "application/json",
                       json.dumps({"error": f"{type(exc).__name__}: {exc}"}
                                  ).encode("utf-8"))

    def log_message(self, *args):
        pass


def main(port=8600):
    srv = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"[orbit_seu] GUI serving on {url}  (Ctrl+C to stop)")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[orbit_seu] GUI stopped.")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8600)
