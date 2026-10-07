"""STK 风格轨道定义与二体传播——平台自传播，不需要 STK。

输入：经典开普勒六根数（与 STK Classical/Keplerian 轨道定义面板一致）：
  semimajor_axis_km (或 hp_km+ha_km 近/远点高度)、eccentricity、
  inclination_deg、raan_deg (Ω)、arg_perigee_deg (ω)、true_anomaly_deg (ν)

传播：二体开普勒（Newton 解开普勒方程）+ 地球自转（GMST, J2000 历元）
  → 逐历元 ECEF → WGS84 测地 (lat, lon, alt)。
之后可直接喂 orbit_attach.attach_ephemeris 挂辐射参数。

诚实标注：二体传播器，无 J2/大气阻力/日月三体摄动——
长期弧段会偏离真实星历；用作轨道定义与辐射评估输入足够，
不声称替代 STK HPOP 精密传播。
"""
from __future__ import annotations

import math

# WGS84 / 常数（与 orbit_attach 同一套）
_A_KM = 6378.137
_F = 1.0 / 298.257223563
_E2 = _F * (2 - _F)
_MU = 398600.4418            # km^3/s^2, 地球引力常数
_RE_KM = 6378.137
_SIDEREAL_S = 86164.0905     # 恒星日秒数
_J2000_UNIX = 946728000.0    # 2000-01-01 12:00:00 UTC 的 Unix 秒
_GMST0_DEG = 280.46061837    # J2000 时刻 GMST (deg)，度/日系数 360.98564736629


def _d2r(x):
    return x * math.pi / 180.0


def _r2d(x):
    return x * 180.0 / math.pi


# ---------------------------------------------------------------- 轨道定义

class OrbitElements:
    """经典六根数（角度均 deg，长度 km）。"""

    def __init__(self, a_km, e, inc_deg, raan_deg=0.0, arg_perigee_deg=0.0,
                 true_anomaly_deg=0.0):
        if not (0.0 <= e < 1.0):
            raise ValueError(f"eccentricity must be in [0,1): {e}")
        if a_km * (1 - e) < _RE_KM + 100.0:
            raise ValueError(
                f"perigee radius {a_km*(1-e):.0f} km below 100 km altitude")
        self.a_km = float(a_km)
        self.e = float(e)
        self.inc_deg = float(inc_deg)
        self.raan_deg = float(raan_deg)
        self.arg_perigee_deg = float(arg_perigee_deg)
        self.true_anomaly_deg = float(true_anomaly_deg)

    @classmethod
    def from_altitudes(cls, hp_km, ha_km, inc_deg, raan_deg=0.0,
                       arg_perigee_deg=0.0, true_anomaly_deg=0.0):
        """STK 圆/椭圆轨道面板式输入：近地点高度 hp + 远地点高度 ha。"""
        rp = _RE_KM + float(hp_km)
        ra = _RE_KM + float(ha_km)
        a = (rp + ra) / 2.0
        e = (ra - rp) / (ra + rp)
        return cls(a, e, inc_deg, raan_deg, arg_perigee_deg,
                   true_anomaly_deg)

    @property
    def period_s(self):
        return 2 * math.pi * math.sqrt(self.a_km ** 3 / _MU)

    @property
    def apogee_alt_km(self):
        return self.a_km * (1 + self.e) - _RE_KM

    @property
    def perigee_alt_km(self):
        return self.a_km * (1 - self.e) - _RE_KM

    def summary(self):
        return {
            "semimajor_axis_km": round(self.a_km, 3),
            "eccentricity": self.e,
            "inclination_deg": self.inc_deg,
            "raan_deg": self.raan_deg,
            "arg_perigee_deg": self.arg_perigee_deg,
            "true_anomaly_deg": self.true_anomaly_deg,
            "period_min": round(self.period_s / 60.0, 3),
            "apogee_alt_km": round(self.apogee_alt_km, 1),
            "perigee_alt_km": round(self.perigee_alt_km, 1),
            "propagator": "two-body Kepler + GMST earth rotation "
                          "(no J2/drag/third-body)",
        }


# STK 风格预设（典型公开轨道，参数为名义值）
PRESETS = {
    "iss":      dict(hp_km=415.0, ha_km=425.0, inc_deg=51.64),
    "sso_800":  dict(hp_km=800.0, ha_km=800.0, inc_deg=98.6),
    "gps_meo":  dict(hp_km=20180.0, ha_km=20220.0, inc_deg=55.0),
    "geo":      dict(hp_km=35786.0, ha_km=35786.0, inc_deg=0.05),
    "molniya":  dict(hp_km=600.0, ha_km=39700.0, inc_deg=63.4,
                     arg_perigee_deg=270.0),
}


# ---------------------------------------------------------------- 传播

def _kepler_E(M, e):
    """Newton 解 M = E - e·sinE（椭圆轨道）。"""
    M = math.fmod(M, 2 * math.pi)
    E = M if e < 0.8 else math.pi
    for _ in range(50):
        f = E - e * math.sin(E) - M
        fp = 1 - e * math.cos(E)
        E -= f / fp
        if abs(f) < 1e-12:
            break
    return E


def _eci_at(elements, t_since_epoch_s):
    """t 秒后的 ECI 位置 (x,y,z) km。"""
    a, e = elements.a_km, elements.e
    n = math.sqrt(_MU / a ** 3)
    # 初始真近点角 → 偏近点角 → 平近点角
    nu0 = _d2r(elements.true_anomaly_deg)
    E0 = 2 * math.atan2(math.sqrt(1 - e) * math.sin(nu0 / 2),
                        math.sqrt(1 + e) * math.cos(nu0 / 2))
    M = (E0 - e * math.sin(E0)) + n * t_since_epoch_s
    E = _kepler_E(M, e)
    # 近焦点坐标
    x_orb = a * (math.cos(E) - e)
    y_orb = a * math.sqrt(1 - e * e) * math.sin(E)
    # perifocal → ECI：Rz(-Ω)·Rx(-i)·Rz(-ω)
    Om, i, w = (_d2r(elements.raan_deg), _d2r(elements.inc_deg),
                _d2r(elements.arg_perigee_deg))
    cO, sO = math.cos(Om), math.sin(Om)
    ci, si = math.cos(i), math.sin(i)
    cw, sw = math.cos(w), math.sin(w)
    x = (cO * cw - sO * sw * ci) * x_orb + (-cO * sw - sO * cw * ci) * y_orb
    y = (sO * cw + cO * sw * ci) * x_orb + (-sO * sw + cO * cw * ci) * y_orb
    z = (sw * si) * x_orb + (cw * si) * y_orb
    return x, y, z


def _gmst_deg(unix_s):
    """格林尼治平恒星时（度）。纪元差按 UT1≈UTC。"""
    days = (unix_s - _J2000_UNIX) / 86400.0
    return (_GMST0_DEG + 360.98564736629 * days) % 360.0


def _ecef_to_geodetic(x, y, z):
    """ECEF → WGS84 测地 (lat_deg, lon_deg, alt_km)，两次迭代 km 级精度。"""
    lon = math.atan2(y, x)
    p = math.hypot(x, y)
    lat = math.atan2(z, p * (1 - _E2))
    for _ in range(2):
        n = _A_KM / math.sqrt(1 - _E2 * math.sin(lat) ** 2)
        alt = p / max(math.cos(lat), 1e-12) - n
        lat = math.atan2(z, p * (1 - _E2 * n / max(n + alt, 1e-12)))
    n = _A_KM / math.sqrt(1 - _E2 * math.sin(lat) ** 2)
    alt = p / max(math.cos(lat), 1e-12) - n
    return _r2d(lat), ((_r2d(lon) + 180) % 360) - 180, alt


def propagate(elements, duration_min=100.0, step_s=10.0,
              epoch0_unix=None, epoch0_iso=None):
    """按步长传播轨道，返回逐历元 dict 列表。

    elements: OrbitElements
    epoch0_unix: 起始历元 Unix 秒（默认当前时间）；epoch0_iso 可覆盖字符串显示。
    返回: [{epoch, lat_deg, lon_deg, alt_km, ecef_km}]，
    epoch 为 "T+秒" 与 ISO 字符串双字段。
    """
    import datetime
    if epoch0_unix is None:
        epoch0_unix = epoch0_unix = (
            datetime.datetime.now(datetime.timezone.utc).timestamp())
    n_pts = int(duration_min * 60.0 / step_s) + 1
    if n_pts > 20000:
        raise ValueError(f"too many epochs ({n_pts}); increase step_s")
    out = []
    for k in range(n_pts):
        t = k * step_s
        x, y, z = _eci_at(elements, t)
        gmst = _d2r(_gmst_deg(epoch0_unix + t))
        # ECI → ECEF：绕 z 旋转 -GMST
        xe = x * math.cos(gmst) + y * math.sin(gmst)
        ye = -x * math.sin(gmst) + y * math.cos(gmst)
        lat, lon, alt = _ecef_to_geodetic(xe, ye, z)
        iso = (datetime.datetime.fromtimestamp(
            epoch0_unix + t, datetime.timezone.utc)
            .strftime("%d %b %Y %H:%M:%S"))
        out.append({
            "epoch": iso, "t_s": t,
            "lat_deg": round(lat, 5), "lon_deg": round(lon, 5),
            "alt_km": round(alt, 3),
            "ecef_km": [round(xe, 4), round(ye, 4), round(z, 4)],
        })
    return out


def propagate_and_attach(elements, duration_min=100.0, step_s=10.0,
                         attacher=None, epoch0_unix=None):
    """传播 + 逐历元挂辐射参数（attach_ephemeris 直连）。"""
    from .orbit_attach import attach_ephemeris
    pts = propagate(elements, duration_min, step_s, epoch0_unix)
    return attach_ephemeris(pts, attacher)
