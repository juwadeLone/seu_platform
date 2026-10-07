"""orbit_propagate：STK 风格轨道定义 + 二体传播的几何正确性测试。"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from layout_ecc.orbit_propagate import (  # noqa: E402
    OrbitElements, PRESETS, propagate, propagate_and_attach,
)


def test_circular_orbit_period_and_altitude():
    """圆轨道：周期 ≈ 2π√(a³/μ)，高度全程恒定。"""
    el = OrbitElements.from_altitudes(420.0, 420.0, 51.6)
    assert abs(el.period_s - 2 * math.pi * math.sqrt(
        (6378.137 + 420.0) ** 3 / 398600.4418)) < 0.01
    pts = propagate(el, duration_min=el.period_s / 60, step_s=30,
                    epoch0_unix=946728000.0)
    # 地心半径恒定（圆轨）；测地高度随纬度在扁椭球上变化 ±15km
    rs = [math.hypot(*p["ecef_km"][:2], p["ecef_km"][2]) for p in pts]
    assert max(rs) - min(rs) < 0.01
    assert abs(sum(rs) / len(rs) - (6378.137 + 420.0)) < 0.01
    alts = [p["alt_km"] for p in pts]
    assert max(alts) - min(alts) < 20.0
    assert abs(sum(alts) / len(alts) - 420.0) < 8.0


def test_ground_track_repeats_with_earth_rotation_drift():
    """一整圈后回到同一惯性位置，但星下点因地球自转而西移。"""
    el = OrbitElements.from_altitudes(420.0, 420.0, 51.6, raan_deg=0.0)
    T = el.period_s
    pts = propagate(el, duration_min=T / 60, step_s=T,
                    epoch0_unix=946728000.0)
    p0, p1 = pts[0], pts[-1]
    # 一圈后惯性位置相同 → 地心经度差 = 地球自转角 ≈ 360.9856° × T/86400
    drift = (p1["lon_deg"] - p0["lon_deg"] + 180) % 360 - 180
    expected = -(360.98564736629 * T / 86400.0) % 360
    expected = (expected + 180) % 360 - 180
    assert abs(drift - expected) < 0.5
    # 纬度回到倾角峰值或相反相位（ν=0 出发则同相）
    assert abs(p1["lat_deg"] - p0["lat_deg"]) < 0.5


def test_inclination_bounds_latitude():
    """最大星下点纬度 ≈ min(i, 180-i)。"""
    el = OrbitElements.from_altitudes(550.0, 550.0, 97.6)
    pts = propagate(el, duration_min=200, step_s=20,
                    epoch0_unix=946728000.0)
    latmax = max(p["lat_deg"] for p in pts)
    latmin = min(p["lat_deg"] for p in pts)
    assert latmax <= 82.4 + 0.5 and latmin >= -82.4 - 0.5
    assert abs(latmax - 82.4) < 1.0 and abs(latmin + 82.4) < 1.0


def test_elliptical_perigee_apogee():
    """Molniya 类：近/远地点高度与输入一致。"""
    el = OrbitElements.from_altitudes(600.0, 39700.0, 63.4,
                                      arg_perigee_deg=270.0)
    pts = propagate(el, duration_min=el.period_s / 60, step_s=60,
                    epoch0_unix=946728000.0)
    alts = [p["alt_km"] for p in pts]
    assert abs(min(alts) - 600.0) < 20.0
    assert abs(max(alts) - 39700.0) < 20.0
    # ω=270° → 近地点在南半球
    perigee_pt = pts[alts.index(min(alts))]
    assert perigee_pt["lat_deg"] < 0


def test_presets_valid():
    for name, kw in PRESETS.items():
        el = OrbitElements.from_altitudes(**kw)
        assert el.period_s > 0
        pts = propagate(el, duration_min=10, step_s=60,
                        epoch0_unix=946728000.0)
        assert len(pts) == 11


def test_propagate_and_attach_integration():
    """传播 → attach 全链路：每个历元都有辐射参数。"""
    el = OrbitElements.from_altitudes(420.0, 420.0, 51.6)
    recs = propagate_and_attach(el, duration_min=30, step_s=60,
                                epoch0_unix=946728000.0)
    assert len(recs) == 31
    for r in recs:
        assert -90 <= r["position"]["lat_deg"] <= 90
        assert r["geomagnetic"]["cutoff_gv"] >= 0
        assert r["environment_tag"] in (
            "gcr_dominant", "inner_belt_candidate", "saa_region_approx")
        rate = r["seu_rate_gcr_only"]
        assert rate and rate["device_total_per_day"] > 0
