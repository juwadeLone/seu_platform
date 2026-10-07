#!/usr/bin/env python3
"""STK 实时链路 CLI：STK Connect -> 位置 -> 辐射参数，逐历元输出 JSONL。

三种模式：

  实时轮询（默认，需要真 STK 开着动画）：
    python tools/stk_live.py --sat "*/Satellite/Sat1" --interval 1.0

  星历文件批量挂载（STK 报告/星历导出的 CSV/空白分列：
  epoch lat_deg lon_deg alt_km，可带 ecef_km 列）：
    python tools/stk_live.py --file ephemeris.csv --out with_rad.jsonl

  内置 mock（无 STK 自测演示）：
    python tools/stk_live.py --mock --sat "*/Satellite/Demo" --epochs 5

输出每行一个 attach() 结果 JSON（见 orbit_attach.attach）。
辐射参数是模型级估计（GCR-only，截止/L 值真实计算）；捕获带与 SAA
通量未包含，见输出 provenance.caveat。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import threading
import time

_SIM = __file__.rsplit("/tools/", 1)[0]
sys.path.insert(0, _SIM)
sys.path.append(_SIM + "/../orbit_seu")   # vendored orbit_seu

from layout_ecc.orbit_attach import RadiationAttacher  # noqa: E402
from layout_ecc.stk_connect import (  # noqa: E402
    StkConnectClient, poll_position)


# ---- mock STK Connect server（文档线协议的镜像实现，用于 --mock 自测） -------

class MockStkServer(threading.Thread):
    """最小 STK Connect 模拟端：ConControl/GetAnimTime/Position。

    位置轨迹用 vendored orbit_seu 的 Kepler 传播（MEO 20200km/55°），
    保证 mock 出的 ECEF/LLA 与平台磁层模型自洽。
    """

    HEADER_LEN = 40

    def __init__(self, port=0, alt_km=20200.0, inc_deg=55.0):
        super().__init__(daemon=True)
        import socket
        from orbit_seu.orbit import OrbitElements
        self.orb = OrbitElements(altitude_km=alt_km,
                                 inclination_deg=inc_deg)
        self.t0 = time.time()
        self._srv = socket.socket()
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind(("127.0.0.1", port))
        self._srv.listen(1)
        self.port = self._srv.getsockname()[1]

    @staticmethod
    def _lla(x, y, z):
        # 地固系 -> 测地（球近似，mock 用足够；attach 本身走 ECEF 分支）
        import math
        r = math.sqrt(x * x + y * y + z * z)
        return (math.degrees(math.asin(z / r)),
                math.degrees(math.atan2(y, x)),
                r - 6378.137)

    def _frame(self, cmd_name, payload):
        data = payload.encode("ascii")
        header = (cmd_name + " " + str(len(data))).encode("ascii")
        header = header.ljust(self.HEADER_LEN, b" ")
        return b"ACK\n" + header + data

    def run(self):
        while True:
            try:
                conn, _ = self._srv.accept()
            except OSError:
                return
            try:
                self._serve(conn)
            finally:
                conn.close()

    def _serve(self, conn):
        buf = b""
        while True:
            try:
                chunk = conn.recv(65536)
            except OSError:
                return
            if not chunk:
                return
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                cmd = line.decode("ascii", "replace").strip()
                if not cmd:
                    continue
                if cmd.startswith("ConControl"):
                    conn.sendall(b"ACK\n")
                elif cmd.startswith("GetAnimTime"):
                    t = time.time() - self.t0
                    payload = f"1 Jan 2025 00:00:{t % 60:06.3f}"
                    conn.sendall(self._frame("GETANIMTIME", payload))
                elif cmd.startswith("Position"):
                    t = time.time() - self.t0
                    x, y, z = self.orb.position_geo_km(t)
                    lat, lon, alt = self._lla(x, y, z)
                    nums = ([lat, lon, alt, 0.0, 0.0, 0.0]
                            + [x, y, z, 0.0, 0.0, 0.0]
                            + [x, y, z, 0.0, 0.0, 0.0])
                    conn.sendall(self._frame(
                        "POSITION", " ".join(f"{v:.6f}" for v in nums)))
                else:
                    conn.sendall(b"NACK unsupported command\n")


# ---- 模式实现 -----------------------------------------------------------------

def _print_json(obj, out):
    out.write(json.dumps(obj, ensure_ascii=False) + "\n")
    out.flush()


def run_live(args, attacher):
    with StkConnectClient(host=args.host, port=args.port) as cli:
        n = 0
        while args.epochs is None or n < args.epochs:
            pos = poll_position(cli, args.sat)
            rec = attacher.attach(ecef_km=pos.ecef_km,
                                  lat_deg=pos.lat_deg,
                                  lon_deg=pos.lon_deg,
                                  alt_km=pos.alt_km,
                                  epoch=pos.epoch)
            _print_json(rec, sys.stdout)
            n += 1
            if args.epochs is None or n < args.epochs:
                time.sleep(args.interval)


def run_file(args, attacher):
    rows = []
    with open(args.file, "r", encoding="utf-8", errors="replace") as fh:
        sample = fh.read(4096)
        fh.seek(0)
        if "," in sample.splitlines()[0]:
            reader = csv.DictReader(fh)
            for r in reader:
                rows.append({
                    "epoch": r.get("epoch") or r.get("time"),
                    "lat_deg": float(r["lat_deg"]),
                    "lon_deg": float(r["lon_deg"]),
                    "alt_km": float(r["alt_km"]),
                })
        else:
            for line in fh:
                parts = line.split()
                if len(parts) < 4 or parts[0].startswith("#"):
                    continue
                # time lat lon alt 或 lat lon alt（无时间列）
                if len(parts) >= 5:
                    rows.append({"epoch": " ".join(parts[:-3]),
                                 "lat_deg": float(parts[-3]),
                                 "lon_deg": float(parts[-2]),
                                 "alt_km": float(parts[-1])})
                else:
                    rows.append({"epoch": None,
                                 "lat_deg": float(parts[0]),
                                 "lon_deg": float(parts[1]),
                                 "alt_km": float(parts[2])})
    out = open(args.out, "w", encoding="utf-8") if args.out else sys.stdout
    for r in rows:
        _print_json(attacher.attach(**r), out)
    if args.out:
        out.close()
        print(f"wrote {len(rows)} records -> {args.out}", file=sys.stderr)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sat", default="*/Satellite/Sat1",
                    help="STK 对象路径（默认 */Satellite/Sat1）")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5001,
                    help="STK Connect 端口（默认 5001）")
    ap.add_argument("--interval", type=float, default=1.0,
                    help="实时轮询间隔秒（默认 1.0）")
    ap.add_argument("--epochs", type=int, default=None,
                    help="采样历元数（默认无限）")
    ap.add_argument("--file", help="星历文件批量挂载（CSV 或空白分列）")
    ap.add_argument("--out", help="输出文件（默认 stdout JSONL）")
    ap.add_argument("--mock", action="store_true",
                    help="起内置 mock STK（无真 STK 的自测）")
    ap.add_argument("--phi-mv", type=float, default=600.0,
                    help="太阳调制势 phi（默认 600 MV，同 mission 默认）")
    args = ap.parse_args(argv)

    attacher = RadiationAttacher(phi_mv=args.phi_mv)

    if args.file:
        run_file(args, attacher)
        return 0

    if args.mock:
        srv = MockStkServer()
        srv.start()
        args.port = srv.port
        print(f"[mock] STK Connect mock on 127.0.0.1:{srv.port} "
              f"(MEO 20200km/55deg Kepler track)", file=sys.stderr)

    run_live(args, attacher)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
