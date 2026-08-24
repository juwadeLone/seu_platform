"""LayoutECC 桌面版启动器（pywebview 原生窗口，不再开浏览器）。

开发运行：  python desktop/app.py
无头测试：  python desktop/app.py --server-only   （只起 HTTP 服务，打印端口）
打包：      desktop/build_exe.bat （PyInstaller onefile）

窗口加载的页面与引擎全部复用 layout_ecc 包（gui.py / engine.js / strike.py），
数据文件与 webapp 资源由 PyInstaller --add-data 打进 exe：
    data/layout/p1_ooc_win/primitive_map.csv   -> data/layout/p1_ooc_win/
    data/weibull_7series_measured.json         -> data/
    data/rpm_grid_calibration.json             -> data/   （仅溯源展示引用）
    layout_ecc/webapp/*                        -> layout_ecc/webapp/
"""
import json
import os
import sys
import threading

VERSION = "1.0.1"

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG_ROOT = os.path.normpath(os.path.join(_HERE, ".."))
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)


def _log(msg):
    line = f"[layout-ecc-desktop] {msg}\n"
    try:
        with open(os.path.join(os.environ.get("TEMP", "."), "LayoutECC_viewer.log"),
                  "a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError:
        pass
    if sys.stdout:
        try:
            print(line, end="")
        except OSError:
            pass


def _desktop_dir():
    """desktop 资源目录（orbit.html 等）：冻结态在 _MEIPASS，开发态为脚本目录。"""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return _HERE



def _rewrite_oseu_prefixes(text):
    """Rewrite only the path prefixes already used by the bundled orbit_seu pages.

    The pages reference "/static/..." (engine.js, earth.jpg, …) and "/api/run".
    Mapping is exactly:
        "/static/"  -> "/oseu-static/"
        "/api/run"  -> "/oseu/api/run"
    Quote-aware (double or single) so a stray substring is left alone.
    Do not add extra rewrite rules here.
    """
    if isinstance(text, bytes):
        for old, new in ((b"/static/", b"/oseu-static/"),
                         (b"/api/run", b"/oseu/api/run")):
            for q in (b'"', b"'"):
                text = text.replace(q + old, q + new)
        return text
    for old, new in (("/static/", "/oseu-static/"),
                     ("/api/run", "/oseu/api/run")):
        for q in ('"', "'"):
            text = text.replace(q + old, q + new)
    return text


def _make_handler(gui):
    """在网页版查看器之上挂载 orbit_seu 原版仪表盘（/orbit）与其 API。

    原版页面用绝对路径 /static/... 与 /api/run；这里在响应时把它们改写成
    /oseu-static/... 与 /oseu/api/run，避免与打击查看器的同名路由冲突，
    页面本身的渲染、动画、交互零改动——与单独运行 orbit_seu 完全同效。
    """

    def _oseu_dirs():
        from orbit_env import _roots
        lib, env, _cfg = _roots()
        return os.path.join(lib, "orbit_seu", "webapp"), env

    _BANNER = (
        '<div style="padding:6px 14px;font:12px \'Segoe UI\',\'Microsoft YaHei\';'
        'background:rgba(10,20,36,.92);border-bottom:1px solid #1b3350;'
        'color:#7f93ab">'
        '<a href="/" style="color:#00e5ff;text-decoration:none">← 返回打击仿真器</a>'
        '&nbsp;&nbsp;·&nbsp;&nbsp;'
        '<a href="/orbit3d" style="color:#00e5ff;text-decoration:none">⛶ 独立 3D 视图</a>'
        '&nbsp;&nbsp;·&nbsp;&nbsp;orbit_seu 原版界面（打包只读副本，与冻结基线同源）'
        '</div>')

    def _oseu_page(name):
        webapp, _env = _oseu_dirs()
        with open(os.path.join(webapp, name), "rb") as fh:
            html = fh.read().decode("utf-8")
        html = _rewrite_oseu_prefixes(html)
        html = html.replace("<body>", "<body>" + _BANNER, 1)
        return html.encode("utf-8")

    class _DesktopHandler(gui._Handler):
        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                web = os.path.join(os.path.dirname(gui.__file__), "webapp",
                                   "index.html")
                with open(web, "r", encoding="utf-8") as fh:
                    html = fh.read()
                html = html.replace("__APP_VERSION__", VERSION)
                self._send(200, "text/html; charset=utf-8",
                           html.encode("utf-8"))
                return
            if path in ("/orbit", "/orbit.html"):
                self._send(200, "text/html; charset=utf-8", _oseu_page("index.html"))
                return
            if path in ("/orbit3d", "/oseu/3d.html"):
                self._send(200, "text/html; charset=utf-8", _oseu_page("3d.html"))
                return
            if path == "/3d":
                # 原版 popBtn 用 window.open("/3d?alt=…&inc=…")，保住查询串
                self._send(200, "text/html; charset=utf-8", _oseu_page("3d.html"))
                return
            if path.startswith("/oseu-static/"):
                name = os.path.basename(path[len("/oseu-static/"):])
                webapp, _env = _oseu_dirs()
                full = os.path.join(webapp, name)
                ext = os.path.splitext(full)[1].lower()
                mime = {".js": "application/javascript; charset=utf-8",
                        ".jpg": "image/jpeg", ".png": "image/png"}.get(ext)
                if name and os.path.isfile(full) and mime:
                    if ext == ".js":  # engine.js 内部引用 "/static/earth.jpg"
                        with open(full, "rb") as fh:
                            body = _rewrite_oseu_prefixes(fh.read())
                        self._send(200, mime, body)
                    else:
                        with open(full, "rb") as fh:
                            self._send(200, mime, fh.read())
                    return
            super().do_GET()

        def do_POST(self):
            if self.path.split("?", 1)[0] != "/oseu/api/run":
                super().do_POST()
                return
            try:
                n = int(self.headers.get("Content-Length", 0))
                config = json.loads(self.rfile.read(n) or b"{}")
                from orbit_env import _roots
                _lib, env, _cfg = _roots()
                e = config.get("environment") or {}
                for key in ("let_spectra_files",):
                    for k, rel in list((e.get(key) or {}).items()):
                        e[key][k] = os.path.normpath(os.path.join(env, rel))
                if e.get("proton_file"):
                    e["proton_file"] = os.path.normpath(
                        os.path.join(env, e["proton_file"]))
                bo = e.get("coefficients_csv")
                if bo and not os.path.isabs(bo):
                    e["coefficients_csv"] = os.path.normpath(os.path.join(env, bo))

                from orbit_seu.gui import _safe
                from orbit_seu.mission import run
                self._send(200, "application/json",
                           json.dumps(_safe(run(config))).encode("utf-8"))
            except Exception as exc:
                self._send(400, "application/json",
                           json.dumps({"error": f"{type(exc).__name__}: {exc}"}
                                      ).encode("utf-8"))

    return _DesktopHandler


def main() -> int:
    from http.server import ThreadingHTTPServer

    # 冻结态（exe）下，functional.py 自己推算的 experiments 路径指向临时目录外，
    # 这里把打包进去的副本挂回 sys.path（追加即可：functional 插入的路径无效时
    # import 会沿 sys.path 继续搜索到这里的正确副本）。
    if getattr(sys, "frozen", False):
        _exp = os.path.join(sys._MEIPASS, "experiments", "fault_injection_1024")
        if os.path.isdir(_exp) and _exp not in sys.path:
            sys.path.append(_exp)

    if _PKG_ROOT not in sys.path:
        sys.path.insert(0, _PKG_ROOT)  # 使冻结态也能 import desktop 下的 orbit_env
    from layout_ecc import gui  # 模块导入时完成 17 MB 布局加载（一次性）

    srv = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(gui))
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{port}/"
    _log(f"version {VERSION}; server up on {url}; sites={gui._LAYOUT['n_sites']}")

    def _prewarm_orbit():
        try:
            from orbit_env import compute_orbit_payload
            payload = compute_orbit_payload()
            _log("orbit env prewarmed: device/day="
                 f"{payload['rates_per_s']['total_per_device'] * 86400:.4f}")
        except Exception as exc:
            _log(f"orbit env prewarm failed (will retry on request): {exc}")
    threading.Thread(target=_prewarm_orbit, daemon=True).start()

    server_only = "--server-only" in sys.argv or \
        os.environ.get("LAYOUT_ECC_SERVER_ONLY") == "1"
    if server_only:
        _log("server-only mode; Ctrl+C to stop")
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
        return 0

    # WebView2 加速 2D 画布在部分驱动/缩放下会整幅变黑（本工具 3D 视图为
    # 2D canvas 逐帧重绘），改用软件 2D 画布规避；须在 import webview 前设置。
    os.environ.setdefault("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
                          "--disable-accelerated-2d-canvas")
    import webview  # pywebview：Windows 上使用 Edge WebView2 原生窗口
    _log("opening native window")
    webview.create_window(
        f"LayoutECC · 空间辐射打击仿真器 v{VERSION}",
        url,
        width=1560, height=940, min_size=(1180, 760),
        background_color="#04070d",
    )
    webview.start()
    _log("window closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
