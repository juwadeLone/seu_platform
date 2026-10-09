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

_WEB = os.path.join(os.path.dirname(__file__), "webapp")
_MIME = {".html": "text/html; charset=utf-8",
         ".js": "application/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8",
         ".json": "application/json",
         ".jpg": "image/jpeg",
         ".png": "image/png"}

from .paths import data_dir as _data_dir

_CSV = os.path.join(_data_dir(), "layout", "p1_ooc_win",
                    "primitive_map.csv")


def _build_state(path):
    """One layout's derived structures, keyed by csv path."""
    layout = load_primitive_map(path)
    if os.path.abspath(path) != _CSV:
        # loader's disclaimer text is written for the bundled P1 FFT
        layout["disclaimer"] = (
            f"User-uploaded primitive_map: {layout['n_placed']} placed "
            f"primitives on {layout['n_sites']} sites, "
            f"{layout.get('n_shared_sites', 0)} sites mix more than one "
            f"hierarchy. Colour-by-stage uses hierarchy-derived modules; "
            f"black = empty in the used bounding box. RPM_X/Y are "
            f"architecture units, not microns.")
        name_file = os.path.join(os.path.dirname(os.path.abspath(path)),
                                 "name.txt")
        layout["design"] = (open(name_file, encoding="utf-8").read().strip()
                            if os.path.isfile(name_file) else
                            os.path.basename(os.path.dirname(
                                os.path.abspath(path))))
    presets = g4_presets(layout)
    box = bounding_box(layout)
    sb = [
        {"stage": st, **b,
         "color": (layout.get("stage_colors") or {}).get(st, "#3d7ec9")}
        for st, b in sorted(
            stage_bboxes(stage_points(layout["tiles"])).items())
    ]
    box.update({"n_sites": layout["n_sites"],
                "n_placed": layout["n_placed"],
                "part": layout.get("part")})
    return {"layout": layout, "presets": presets, "box": box,
            "stage_bboxes": sb}


_LAYOUT_STATES = {}


def layout_state(path=None):
    """Bundled layout by default; a user-uploaded csv path otherwise.
    Results are cached so repeats are free."""
    key = os.path.abspath(path) if path else _CSV
    if key not in _LAYOUT_STATES:
        _LAYOUT_STATES[key] = _build_state(key)
    return _LAYOUT_STATES[key]


_LAYOUTS_BY_ID = {}
_LAYOUTS_ROOT = os.path.join(os.path.expanduser("~"),
                             ".seu_platform", "layouts")


def register_layout(csv_text, name="primitive_map.csv"):
    """Save user csv_text under the data dir, build its state, return
    (layout_id, state). Raises ValueError when the csv won't parse."""
    import hashlib, time
    lid = time.strftime("%Y%m%d-%H%M%S") + "_" + \
        hashlib.sha256(csv_text.encode("utf-8")[:4096]).hexdigest()[:8]
    d = os.path.join(_LAYOUTS_ROOT, lid)
    os.makedirs(d, exist_ok=True)
    fp = os.path.join(d, "primitive_map.csv")
    with open(fp, "w", encoding="utf-8", newline="") as fh:
        fh.write(csv_text)
    disp = os.path.splitext(os.path.basename(name))[0] or lid
    with open(os.path.join(d, "name.txt"), "w", encoding="utf-8") as fh:
        fh.write(disp)
    st = _build_state(fp)          # parses or raises
    _LAYOUTS_BY_ID[lid] = fp
    return lid, st


def layout_for_id(layout_id):
    """layout_id -> state; 'bundled'/None -> default P1 layout."""
    if not layout_id or layout_id == "bundled":
        return layout_state()
    path = _LAYOUTS_BY_ID.get(layout_id)
    if not path:
        cand = os.path.join(_LAYOUTS_ROOT, layout_id, "primitive_map.csv")
        ok = layout_id and ".." not in layout_id and \
            "/" not in layout_id and "\\" not in layout_id
        if ok and os.path.isfile(cand):
            path = cand
            _LAYOUTS_BY_ID[layout_id] = path
    if not path:
        raise ValueError(f"unknown layout_id {layout_id!r} — upload it first")
    return layout_state(path)


def _known_layouts():
    """Uploaded layouts on disk (survives restarts), merged with
    anything registered this process."""
    found = {}
    if os.path.isdir(_LAYOUTS_ROOT):
        for lid in os.listdir(_LAYOUTS_ROOT):
            fp = os.path.join(_LAYOUTS_ROOT, lid, "primitive_map.csv")
            nf = os.path.join(_LAYOUTS_ROOT, lid, "name.txt")
            if os.path.isfile(fp):
                design = (open(nf, encoding="utf-8").read().strip()
                          if os.path.isfile(nf) else lid)
                found[lid] = {"layout_id": lid, "design": design}
    for lid in _LAYOUTS_BY_ID:
        found.setdefault(lid, {"layout_id": lid, "design": lid})
    return [found[k] for k in sorted(found)]


_LAYOUT = layout_state()["layout"]
_PRESETS = _LAYOUT_STATES[_CSV]["presets"]
_BOX = _LAYOUT_STATES[_CSV]["box"]
_STAGE_BBOXES = _LAYOUT_STATES[_CSV]["stage_bboxes"]


def _safe(obj):
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe(v) for v in obj]
    return obj


def _layout_payload(state=None):
    st = state or _LAYOUT_STATES[_CSV]
    layout = st["layout"]
    cells = []
    for t in layout["tiles"]:
        cells.append([int(t["grid_x"]), int(t["grid_y"]), t["res_type"],
                      t["site"], t.get("n_prims", 0), t["unit_id"],
                      summarize(t.get("domains") or {}),
                      int(t.get("stage_id") or -1),
                      t.get("module_role") or "unknown",
                      1 if t.get("is_shared") else 0,
                      int(t.get("module_idx", -1))])
    ts = layout.get("tag_stats") or {}
    return {
        "domains": list(ORDER),
        "domain_labels": LABEL,
        "source": layout["source"],
        "part": layout.get("part"),
        "disclaimer": layout["disclaimer"],
        "ncols": layout["ncols"], "nrows": layout["nrows"],
        "n_stages": layout.get("n_stages", 0),
        "n_sites": layout["n_sites"],
        "n_placed": layout["n_placed"],
        "n_shared_sites": layout.get("n_shared_sites", 0),
        "tag_stats": {
            "n": ts.get("n"),
            "n_unknown_role": ts.get("n_unknown_role"),
            "unknown_role_frac": ts.get("unknown_role_frac"),
            "by_stage": ts.get("by_stage"),
            "by_role": ts.get("by_role"),
        },
        "stage_colors": [None] + [
            (layout.get("stage_colors") or {}).get(i, "#3d7ec9")
            for i in range(1, 11)
        ],
        "resource_colors": layout.get("resource_colors") or {},
        "stage_bboxes": st["stage_bboxes"],
        "box": st["box"],
        "presets": st["presets"],
        "default_x0": layout["default_x0"],
        "default_y0": layout["default_y0"],
        "default_a0": layout["default_a0"],
        "color_used": layout["color_used"],
        "color_unused": layout["color_unused"],
        "cells": cells,
        "design": layout.get("design"),
        "modules": layout.get("modules") or [],
        "module_depth": layout.get("module_depth"),
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
        if path == "/api/effects":
            self._send(200, "application/json; charset=utf-8",
                       json.dumps(_safe(build_effects_payload()),
                                  ensure_ascii=False))
            return
        if path == "/api/layout":
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            lid = (q.get("layout_id") or [None])[0]
            try:
                self._send(200, "application/json",
                           json.dumps(_safe(_layout_payload(
                               layout_for_id(lid)))))
            except ValueError as exc:
                self._send(400, "application/json",
                           json.dumps({"error": str(exc)}))
            return
        if path == "/api/layouts":
            self._send(200, "application/json",
                       json.dumps(_safe({
                           "bundled": {"layout_id": "bundled",
                                       "n_sites": _LAYOUT["n_sites"],
                                       "design": _LAYOUT.get("design")},
                           "uploaded": _known_layouts()})))
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
        if self.path == "/api/upload_layout":
            try:
                n = int(self.headers.get("Content-Length", 0))
                cfg = json.loads(self.rfile.read(n) or b"{}")
                csv_text = cfg.get("csv_text")
                if not csv_text:
                    raise ValueError("body needs csv_text (primitive_map.csv)")
                lid, st = register_layout(csv_text, cfg.get("name") or
                                          "primitive_map.csv")
                lay = st["layout"]
                self._send(200, "application/json", json.dumps(_safe({
                    "layout_id": lid,
                    "n_sites": lay["n_sites"],
                    "n_placed": lay["n_placed"],
                    "n_stages": lay.get("n_stages"),
                    "n_modules": len(lay.get("modules") or []),
                    "disclaimer": lay["disclaimer"],
                })))
            except Exception as exc:
                self._send(400, "application/json",
                           json.dumps({"error": f"{type(exc).__name__}: {exc}"}))
            return
        if self.path != "/api/strike":
            self._send(404, "text/plain; charset=utf-8", b"not found")
            return
        try:
            n = int(self.headers.get("Content-Length", 0))
            cfg = json.loads(self.rfile.read(n) or b"{}")
            st = layout_for_id(cfg.get("layout_id"))
            lay = st["layout"]
            out = run_strike(
                lay,
                x0=float(cfg.get("x0", lay["default_x0"])),
                y0=float(cfg.get("y0", lay["default_y0"])),
                let=float(cfg.get("let", 15)),
                theta_deg=float(cfg.get("theta", 45)),
                phi_deg=float(cfg.get("phi", 30)),
                a0=float(cfg.get("a0", lay["default_a0"])),
                seed=int(cfg.get("seed", 1)),
                k_let=float(cfg.get("k_let", 0.25)),
                kernel_model=str(cfg.get("kernel_model") or "anchored"),
                flip_model=str(cfg.get("flip_model") or "weibull"),
                rpm_to_um=float(cfg["rpm_to_um"]) if cfg.get("rpm_to_um") else None,
            )
            out["effects"] = classify(out, out["let"])
            self._send(200, "application/json", json.dumps(_safe(out)))
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
