"""stk_connect + orbit_attach 的测试。

- MockStkServer：镜像 STK Connect 文档线协议（ACK + 40 字节头 + 数据体）。
- attach() 与 orbit_seu.mission.run 的交叉核对：同一 MEO 轨道、同一
  BO2020 GCR 模型下，attach 逐点均值的整机 /day 应与 mission 报告一致
  （同一物理模型的两条路径）。
"""
import json
import os
import socket
import sys
import threading
import time
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SIM = os.path.normpath(os.path.join(_HERE, ".."))
_OSEU = os.path.normpath(os.path.join(_SIM, "..", "orbit_seu"))
for p in (_SIM, _OSEU):
    if p not in sys.path:
        sys.path.append(p)

from layout_ecc.orbit_attach import RadiationAttacher, geodetic_to_ecef_km  # noqa: E402
from layout_ecc.stk_connect import (  # noqa: E402
    StkConnectClient, StkConnectError, poll_position)

_MEO_ALT_KM = 20200.0
_MEO_INC_DEG = 55.0


class MockStkServer(threading.Thread):
    """最小 STK Connect mock：ConControl / GetAnimTime / Position。

    Position 的轨迹用 orbit_seu 自己的 Kepler 传播（MEO 20200/55），
    使 mock 出的位置与平台磁层模型自洽，可直接喂给 attach()。
    """

    HEADER_LEN = 40

    def __init__(self):
        super().__init__(daemon=True)
        from orbit_seu.orbit import OrbitElements
        self.orb = OrbitElements(altitude_km=_MEO_ALT_KM,
                                 inclination_deg=_MEO_INC_DEG)
        self.t0 = time.time()
        self._srv = socket.socket()
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind(("127.0.0.1", 0))
        self._srv.listen(1)
        self.port = self._srv.getsockname()[1]

    @staticmethod
    def _lla(x, y, z):
        import math
        r = math.sqrt(x * x + y * y + z * z)
        return (math.degrees(math.asin(z / r)),
                math.degrees(math.atan2(y, x)),
                r - 6378.137)

    @classmethod
    def _frame(cls, cmd_name, payload):
        data = payload.encode("ascii")
        header = (cmd_name + " " + str(len(data))).encode("ascii")
        header = header.ljust(cls.HEADER_LEN, b" ")
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
                    conn.sendall(self._frame(
                        "GETANIMTIME", f"1 Jan 2025 00:{t % 3600:09.3f}"))
                elif cmd.startswith("Position"):
                    t = time.time() - self.t0
                    x, y, z = self.orb.position_geo_km(t)
                    lat, lon, alt = self._lla(x, y, z)
                    nums = ([lat, lon, alt, 0, 0, 0]
                            + [x, y, z, 0, 0, 0]
                            + [x, y, z, 0, 0, 0])
                    conn.sendall(self._frame(
                        "POSITION",
                        " ".join(f"{v:.6f}" for v in nums)))
                else:
                    conn.sendall(b"NACK unsupported\n")


class TestStkConnect(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = MockStkServer()
        cls.srv.start()
        time.sleep(0.05)

    def test_handshake_and_position(self):
        with StkConnectClient(port=self.srv.port) as cli:
            t = cli.get_anim_time()
            self.assertTrue(t)
            pos = cli.get_position("*/Satellite/Demo", t)
            # mock 的轨迹是 MEO 20200 km：alt 应在附近
            self.assertAlmostEqual(pos.alt_km, _MEO_ALT_KM, delta=1500.0)
            self.assertEqual(len(pos.ecef_km), 3)
            self.assertEqual(len(pos.icrf_km), 3)
            import math
            r = math.sqrt(sum(c * c for c in pos.ecef_km))
            self.assertAlmostEqual(r, 6378.137 + _MEO_ALT_KM, delta=1500.0)

    def test_poll_position(self):
        with StkConnectClient(port=self.srv.port) as cli:
            pos = poll_position(cli, "*/Satellite/Demo")
            self.assertTrue(pos.epoch)
            self.assertGreater(pos.alt_km, 18000)

    def test_bad_command_raises(self):
        with StkConnectClient(port=self.srv.port) as cli:
            with self.assertRaises(StkConnectError):
                cli.send("BogusCommand")


class TestOrbitAttach(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.att = RadiationAttacher()

    def test_attach_from_lla_and_ecef_agree(self):
        lat, lon, alt = 10.0, 45.0, _MEO_ALT_KM
        a = self.att.attach(lat_deg=lat, lon_deg=lon, alt_km=alt)
        b = self.att.attach(ecef_km=geodetic_to_ecef_km(lat, lon, alt))
        self.assertAlmostEqual(
            a["geomagnetic"]["cutoff_gv"], b["geomagnetic"]["cutoff_gv"],
            places=3)
        self.assertAlmostEqual(
            a["seu_rate_gcr_only"]["device_total_per_day"],
            b["seu_rate_gcr_only"]["device_total_per_day"], places=6)

    def test_cutoff_equator_vs_pole(self):
        eq = self.att.attach(lat_deg=0, lon_deg=0, alt_km=20200)
        # 磁极上方：截止应显著低于赤道
        poleward = self.att.attach(lat_deg=75, lon_deg=0, alt_km=20200)
        self.assertLess(poleward["geomagnetic"]["cutoff_gv"],
                        eq["geomagnetic"]["cutoff_gv"])

    def test_meo_attach_mean_matches_mission_bo_gcr(self):
        """同一轨道同一模型：attach 逐点均值 ≈ mission.run(bo_gcr) 的 /day。"""
        import copy
        from orbit_seu.mission import run as mission_run
        from orbit_seu.orbit import OrbitElements, propagate_mission

        cfg = json.load(open(os.path.join(
            _OSEU, "examples", "demo_meo_gps.json"), encoding="utf-8"))
        # 换成 bo_gcr（真实模型路径，与 attach 同源）；器件也用同一个
        # measured 三域 Weibull——attach 与 mission 只差平均方式
        cfg["environment"] = {
            "type": "bo_gcr", "phi_mv": 600.0,
            "rigidity_cutoff": {"kappa": 1.0}}
        cfg["device"] = json.load(open(os.path.join(
            _OSEU, "examples", "xc7vx690t_measured_meo.json"),
            encoding="utf-8"))["device"]
        res = mission_run(cfg)
        # rates_per_s.total_per_device 是 events/s/device → /day
        mission_day = res["rates_per_s"]["total_per_device"] * 86400.0
        self.assertGreater(mission_day, 0)

        orb = OrbitElements(altitude_km=cfg["orbit"]["altitude_km"],
                            inclination_deg=cfg["orbit"]["inclination_deg"])
        n_orb = cfg["mission"]["sampling"]["orbits"]
        n_pt = cfg["mission"]["sampling"]["points_per_orbit"]
        samples = propagate_mission(orb, n_orb, n_pt)
        totals, cutoffs = [], []
        for _, xg, yg, zg in samples:
            rec = self.att.attach(ecef_km=(xg, yg, zg))
            totals.append(rec["seu_rate_gcr_only"]["device_total_per_day"])
            cutoffs.append(rec["geomagnetic"]["cutoff_gv"])
        mean_day = sum(totals) / len(totals)
        # mission 的截止按 0.25 GV 量化平均；attach 同样量化——应高度接近
        self.assertAlmostEqual(mean_day, mission_day, delta=mission_day * 0.15)
        mc = res["magnetosphere"]["cutoff_gv"]
        self.assertGreaterEqual(max(cutoffs), mc["min"])
        self.assertLessEqual(min(cutoffs), mc["max"])

    def test_saa_and_belt_flags(self):
        # SAA 多边形内、低高度 → saa_region_approx
        rec = self.att.attach(lat_deg=-30, lon_deg=-45, alt_km=400)
        self.assertEqual(rec["environment_tag"], "saa_region_approx")
        self.assertIn("NOT included", rec["environment_note"])
        # MEO 高 L → gcr_dominant
        rec2 = self.att.attach(lat_deg=0, lon_deg=0, alt_km=20200)
        self.assertEqual(rec2["environment_tag"], "gcr_dominant")

    def test_provenance_marks_model_level(self):
        rec = self.att.attach(lat_deg=0, lon_deg=0, alt_km=800)
        self.assertTrue(rec["provenance"]["model_level"])
        self.assertIn("46.160314073644855", rec["provenance"]["caveat"])


if __name__ == "__main__":
    unittest.main()
