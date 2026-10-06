"""Local 3D strike viewer: python -m layout_ecc [port]

Stdlib http.server only. Default http://127.0.0.1:8610
"""
import json
import math
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .domains import LABEL, ORDER, summarize
from .effects_coverage import build_effects_payload
from .geom_metrics import stage_bboxes, stage_points
from .layout_import import load_primitive_map
from .layout_synth import bounding_box
from .strike import g4_presets, run_strike
from .strike_effects import classify

_ATTACHER = None


def _attacher():
    """惰性构建 RadiationAttacher（加载 LIS 系数与器件配置需要数十 ms）。"""
    global _ATTACHER
    if _ATTACHER is None:
        from .orbit_attach import RadiationAttacher
        _ATTACHER = RadiationAttacher()
    return _ATTACHER

_WEB = os.path.join(os.path.dirname(__file__), "webapp")
_MIME = {".html": "text/html; charset=utf-8",
         ".js": "application/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8",
         ".json": "application/json",
         ".jpg": "image/jpeg",
         ".png": "image/png"}

_CSV = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "data", "layout", "p1_ooc_win",
    "primitive_map.csv"))
_LAYOUT = load_primitive_map(_CSV)
_PRESETS = g4_presets(_LAYOUT)
_BOX = bounding_box(_LAYOUT)
_STAGE_BBOXES = [
    {"stage": st, **box,
     "color": (_LAYOUT.get("stage_colors") or {}).get(st, "#3d7ec9")}
    for st, box in sorted(stage_bboxes(stage_points(_LAYOUT["tiles"])).items())
]
_BOX.update({
    "n_sites": _LAYOUT["n_sites"],
    "n_placed": _LAYOUT["n_placed"],
    "part": _LAYOUT.get("part"),
})


def _safe(obj):
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe(v) for v in obj]
    return obj


def _layout_payload():
    cells = []
    for t in _LAYOUT["tiles"]:
        cells.append([int(t["grid_x"]), int(t["grid_y"]), t["res_type"],
                      t["site"], t.get("n_prims", 0), t["unit_id"],
                      summarize(t.get("domains") or {}),
                      int(t.get("stage_id") or -1),
                      t.get("module_role") or "unknown",
                      1 if t.get("is_shared") else 0,
                      int(t.get("module_idx", -1))])
    ts = _LAYOUT.get("tag_stats") or {}
    return {
        "domains": list(ORDER),
        "domain_labels": LABEL,
        "source": _LAYOUT["source"],
        "part": _LAYOUT.get("part"),
        "disclaimer": _LAYOUT["disclaimer"],
        "ncols": _LAYOUT["ncols"], "nrows": _LAYOUT["nrows"],
        "n_stages": _LAYOUT.get("n_stages", 0),
        "n_sites": _LAYOUT["n_sites"],
        "n_placed": _LAYOUT["n_placed"],
        "n_shared_sites": _LAYOUT.get("n_shared_sites", 0),
        "tag_stats": {
            "n": ts.get("n"),
            "n_unknown_role": ts.get("n_unknown_role"),
            "unknown_role_frac": ts.get("unknown_role_frac"),
            "by_stage": ts.get("by_stage"),
            "by_role": ts.get("by_role"),
        },
        "stage_colors": [None] + [
            (_LAYOUT.get("stage_colors") or {}).get(i, "#3d7ec9")
            for i in range(1, 11)
        ],
        "resource_colors": _LAYOUT.get("resource_colors") or {},
        "stage_bboxes": _STAGE_BBOXES,
        "box": _BOX,
        "presets": _PRESETS,
        "default_x0": _LAYOUT["default_x0"],
        "default_y0": _LAYOUT["default_y0"],
        "default_a0": _LAYOUT["default_a0"],
        "color_used": _LAYOUT["color_used"],
        "color_unused": _LAYOUT["color_unused"],
        "cells": cells,
        "design": _LAYOUT.get("design"),
        "modules": _LAYOUT.get("modules") or [],
        "module_depth": _LAYOUT.get("module_depth"),
    }


class _Handler(BaseHTTPRequestHandler):

    def _send(self, code, ctype, body):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            with open(os.path.join(_WEB, "index.html"), "rb") as fh:
                self._send(200, "text/html; charset=utf-8", fh.read())
            return
        if path in ("/sar", "/sar.html"):
            with open(os.path.join(_WEB, "sar.html"), "rb") as fh:
                self._send(200, "text/html; charset=utf-8", fh.read())
            return
        if path in ("/effects", "/effects.html"):
            with open(os.path.join(_WEB, "effects.html"), "rb") as fh:
                self._send(200, "text/html; charset=utf-8", fh.read())
            return
        if path in ("/seu", "/seu.html", "/seu_inside.html"):
            with open(os.path.join(_WEB, "seu_inside.html"), "rb") as fh:
                self._send(200, "text/html; charset=utf-8", fh.read())
            return
        if path in ("/live", "/live.html"):
            with open(os.path.join(_WEB, "live.html"), "rb") as fh:
                self._send(200, "text/html; charset=utf-8", fh.read())
            return
        if path == "/api/effects":
            self._send(200, "application/json; charset=utf-8",
                       json.dumps(_safe(build_effects_payload()),
                                  ensure_ascii=False))
            return
        if path == "/api/stk/status":
            import socket as _sk
            host = "127.0.0.1"
            port = 5001
            ok = False
            try:
                _sk.create_connection((host, port), timeout=1.0).close()
                ok = True
            except OSError:
                pass
            self._send(200, "application/json; charset=utf-8",
                       json.dumps({"connect_url": f"{host}:{port}",
                                   "reachable": ok,
                                   "note": "STK Connect TCP listener"},
                                  ensure_ascii=False))
            return
        if path == "/api/layout":
            self._send(200, "application/json",
                       json.dumps(_safe(_layout_payload())))
            return
        if path.startswith("/static/"):
            name = os.path.basename(path)
            full = os.path.join(_WEB, name)
            ext = os.path.splitext(full)[1].lower()
            if os.path.isfile(full) and ext in _MIME:
                with open(full, "rb") as fh:
                    self._send(200, _MIME[ext], fh.read())
                return
        self._send(404, "text/plain; charset=utf-8", b"not found")

    def do_POST(self):
        if self.path in ("/api/stk/sample", "/api/stk/track"):
            self._stk_post()
            return
        if self.path != "/api/strike":
            self._send(404, "text/plain; charset=utf-8", b"not found")
            return
        try:
            n = int(self.headers.get("Content-Length", 0))
            cfg = json.loads(self.rfile.read(n) or b"{}")
            out = run_strike(
                _LAYOUT,
                x0=float(cfg.get("x0", _LAYOUT["default_x0"])),
                y0=float(cfg.get("y0", _LAYOUT["default_y0"])),
                let=float(cfg.get("let", 15)),
                theta_deg=float(cfg.get("theta", 45)),
                phi_deg=float(cfg.get("phi", 30)),
                a0=float(cfg.get("a0", _LAYOUT["default_a0"])),
                seed=int(cfg.get("seed", 1)),
                k_let=float(cfg.get("k_let", 0.25)),
                kernel_model=str(cfg.get("kernel_model") or "anchored"),
                flip_model=str(cfg.get("flip_model") or "weibull"),
                rpm_to_um=float(cfg["rpm_to_um"]) if cfg.get("rpm_to_um") else None,
                pattern_shape=str(cfg.get("pattern_shape") or "cluster"),
            )
            out["effects"] = classify(out, out["let"])
            self._send(200, "application/json", json.dumps(_safe(out)))
        except Exception as exc:
            self._send(400, "application/json",
                       json.dumps({"error": f"{type(exc).__name__}: {exc}"}))

    def _stk_post(self):
        """STK 实时链路：/api/stk/sample（单次轮询）与 /api/stk/track（批量）。"""
        try:
            n = int(self.headers.get("Content-Length", 0))
            cfg = json.loads(self.rfile.read(n) or b"{}")
            att = _attacher()
            if self.path == "/api/stk/sample":
                from .stk_connect import StkConnectClient, poll_position
                host = str(cfg.get("host") or "127.0.0.1")
                port = int(cfg.get("port") or 5001)
                sat = str(cfg.get("sat") or "*/Satellite/Sat1")
                try:
                    with StkConnectClient(host=host, port=port,
                                          timeout=float(cfg.get("timeout", 5))) as cli:
                        pos = poll_position(cli, sat)
                except Exception as exc:
                    self._send(200, "application/json; charset=utf-8",
                               json.dumps({
                                   "error": f"STK Connect: {type(exc).__name__}: {exc}",
                                   "hint": "STK 需开着 scenario 且 Options→Connect 端口监听已启用",
                               }, ensure_ascii=False))
                    return
                rec = att.attach(ecef_km=pos.ecef_km,
                                 lat_deg=pos.lat_deg, lon_deg=pos.lon_deg,
                                 alt_km=pos.alt_km, epoch=pos.epoch)
                rec["stk"] = {"satellite": sat, "host": host, "port": port}
                self._send(200, "application/json; charset=utf-8",
                           json.dumps(_safe(rec), ensure_ascii=False))
                return
            # /api/stk/track：批量历元挂载（不需要 STK）
            pts = cfg.get("points") or []
            results = []
            for p in pts:
                results.append(att.attach(
                    lat_deg=p.get("lat_deg"), lon_deg=p.get("lon_deg"),
                    alt_km=p.get("alt_km"), ecef_km=p.get("ecef_km"),
                    epoch=p.get("epoch")))
            self._send(200, "application/json; charset=utf-8",
                       json.dumps(_safe({"results": results, "n": len(results)}),
                                  ensure_ascii=False))
        except Exception as exc:
            self._send(400, "application/json",
                       json.dumps({"error": f"{type(exc).__name__}: {exc}"}))

    def log_message(self, *args):
        pass


class _Server(ThreadingHTTPServer):
    # http.server enables SO_REUSEADDR by default; on Windows that lets a
    # second instance bind the same port and silently split traffic with a
    # stale server. Fail loudly instead.
    allow_reuse_address = False


def main(port=8610):
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    print(f"[layout_ecc] loaded {_LAYOUT['n_sites']} sites from {_CSV}")
    ts = _LAYOUT.get("tag_stats") or {}
    frac = 100 * float(ts.get("unknown_role_frac") or 0)
    print(f"[layout_ecc] unknown role {ts.get('n_unknown_role')} / "
          f"{ts.get('n')} ({frac:.2f}%)  "
          f"shared sites {_LAYOUT.get('n_shared_sites')}")
    by = ts.get("by_stage") or {}
    print("[layout_ecc] " + " ".join(
        f"s{k}={by[k]}" for k in sorted(by, key=lambda x: int(x) if str(x).lstrip('-').isdigit() else 99)
        if int(k) > 0))
    srv = _Server(("127.0.0.1", port), _Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"[layout_ecc] 3D strike viewer on {url}  (Ctrl+C to stop)")
    print(f"[layout_ecc] SEU inside LUT/FF/BRAM: {url}/seu")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[layout_ecc] stopped.")
    return 0
