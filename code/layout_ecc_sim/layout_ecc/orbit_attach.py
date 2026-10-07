"""把辐射参数挂到任意轨道位置上（STK 实时链路的核心算子）。

每个历元：(lat,lon,alt) 或 ECEF (x,y,z) →
  1. DipoleModel（IGRF-13 2020 偶极）→ 磁纬度 λm、McIlwain L、Størmer 截止刚度 Rc
  2. Badhwar-O'Neill 2020 GCR 模型 + O'Neill LIS 系数（vendored env_data）
     → 该截止下透射的 LET 微分谱（按 0.25 GV 量化缓存，1 Hz 轮询足够快）
  3. XC7VX690T 三域 Weibull σ(LET)（examples/xc7vx690t_measured_meo.json）
     → GCR-only 模型级 SEU 率估计（per domain /day/bit 与整机 /day）

诚实标注（与仓库 source:/assumption: 惯例一致）：
- 冻结证据 46.160314073644855 upsets/day 只对 20200 km / 55° MEO 有效；
  本模块对任意轨道给出的是**模型级估计**，非冻结证据。
- 捕获带（内带质子/外带电子）与 SAA 通量**未包含**：需要 AE9/AP9-IRENE
  可执行包或 SPENVIS 轨道平均谱，见 env_data/README.md。
  environment_tag 只给出区域判别，不编造通量。
- L = K·Z²/β² 近似（无 Bethe 对数项，低 β 时 LET 低估），同 README。
"""
from __future__ import annotations

import math
import os

_PKG = os.path.dirname(os.path.abspath(__file__))
_ORBIT_SEU_ROOT = os.path.normpath(
    os.path.join(_PKG, "..", "..", "orbit_seu"))
_DEFAULT_DEVICE_CFG = os.path.join(
    _ORBIT_SEU_ROOT, "examples", "xc7vx690t_measured_meo.json")
_DEFAULT_LIS_CSV = os.path.join(
    _ORBIT_SEU_ROOT, "env_data", "oneill_lis_coefficients.csv")

# WGS84
_A_KM = 6378.137          # semi-major axis
_F = 1.0 / 298.257223563  # flattening
_E2 = _F * (2 - _F)

# SAA 多边形近似（南大西洋异常区，文献常用粗略范围；标注 approximate）。
# 实际边界由捕获带模型给出；这里仅作"位于该区域"的粗略标记。
_SAA_LAT_MIN, _SAA_LAT_MAX = -55.0, 5.0
_SAA_LON_MIN, _SAA_LON_MAX = -100.0, 25.0
_SAA_ALT_MAX_KM = 1500.0     # 只在低高度标记，高度越高边界越不准

# 内带候选判据：L 与高度都低 → 位置在捕获带影响区内
_INNER_BELT_L_MAX = 3.0
_INNER_BELT_ALT_MAX_KM = 6000.0

_CUTOFF_QUANT_GV = 0.25      # 与 mission.average_over_cutoffs 同量化步长


def geodetic_to_ecef_km(lat_deg, lon_deg, alt_km):
    """WGS84 测地坐标 → ECEF (km)。返回 (x, y, z)。"""
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    s = math.sin(lat)
    n = _A_KM / math.sqrt(1.0 - _E2 * s * s)
    x = (n + alt_km) * math.cos(lat) * math.cos(lon)
    y = (n + alt_km) * math.cos(lat) * math.sin(lon)
    z = (n * (1 - _E2) + alt_km) * s
    return x, y, z


def _dipole():
    from orbit_seu.magnetosphere import DipoleModel
    return DipoleModel()


class RadiationAttacher:
    """一次构造，多次 attach()。GCR 谱按量化截止刚度缓存。"""

    def __init__(self, device_cfg_path=None, lis_csv=None,
                 phi_mv=600.0, kappa=1.0):
        import json
        import sys
        if _ORBIT_SEU_ROOT not in sys.path:
            sys.path.append(_ORBIT_SEU_ROOT)
        from orbit_seu.device import build_device_sigma
        from orbit_seu.gcr_bo import load_lis_coefficients
        self._dip = _dipole()
        cfg_path = device_cfg_path or _DEFAULT_DEVICE_CFG
        with open(cfg_path, "r", encoding="utf-8") as fh:
            dev_cfg = json.load(fh)["device"]
        self.device = build_device_sigma(dev_cfg)
        self.device_name = dev_cfg.get("name", "device")
        self._lis = load_lis_coefficients(
            lis_csv or _DEFAULT_LIS_CSV)
        self.phi_mv = float(phi_mv)
        self.kappa = float(kappa)
        self._spectrum_cache = {}   # quantized cutoff -> {species: Spectrum}
        self.provenance = {
            "cutoff_model": "IGRF-13 2020 tilted centered dipole, "
                            "Stoermer vertical (orbit_seu.magnetosphere)",
            "gcr_model": "Badhwar-O'Neill 2020 + O'Neill LIS coefficients "
                         f"(phi_mv={self.phi_mv})",
            "device": f"{self.device_name} Weibull domains, Lee 2014 "
                      "(examples/xc7vx690t_measured_meo.json)",
            "model_level": True,
            "caveat": ("model-level estimate for arbitrary orbits; "
                       "frozen 46.160314073644855/day applies only to "
                       "20200 km / 55 deg MEO; trapped-belt and SAA flux "
                       "not included (needs AE9/AP9 or SPENVIS)"),
        }

    # ---- internals ---------------------------------------------------------
    def _spectra_at_cutoff(self, cutoff_gv):
        from orbit_seu.gcr_bo import let_spectra_from_gcr
        q = round(cutoff_gv / _CUTOFF_QUANT_GV) * _CUTOFF_QUANT_GV
        key = round(q, 4)
        if key not in self._spectrum_cache:
            self._spectrum_cache[key] = let_spectra_from_gcr(
                self._lis, self.phi_mv, q, self.kappa)
        return self._spectrum_cache[key]

    @staticmethod
    def _environment_tag(mag_lat_deg, l_shell, lat_deg, lon_deg, alt_km):
        in_saa_box = (_SAA_LAT_MIN <= lat_deg <= _SAA_LAT_MAX
                      and _SAA_LON_MIN <= lon_deg <= _SAA_LON_MAX
                      and alt_km <= _SAA_ALT_MAX_KM)
        in_belt = (l_shell <= _INNER_BELT_L_MAX
                   and alt_km <= _INNER_BELT_ALT_MAX_KM)
        if in_saa_box:
            return ("saa_region_approx",
                    "SAA polygon approximation; trapped flux NOT included")
        if in_belt:
            return ("inner_belt_candidate",
                    "L-shell/altitude inside inner belt region; "
                    "trapped proton flux NOT included (needs AE9/AP9)")
        return ("gcr_dominant", "GCR-dominated regime")

    # ---- public -------------------------------------------------------------
    def attach(self, lat_deg=None, lon_deg=None, alt_km=None,
               ecef_km=None, epoch=None):
        """一个历元 → 辐射参数 dict。

        输入二选一：WGS84 测地 (lat_deg, lon_deg, alt_km) 或 ECEF ecef_km=(x,y,z)。
        STK Position 返回的 ECF 坐标直接走 ecef_km（已是地固系）。
        """
        if ecef_km is None:
            if lat_deg is None or lon_deg is None or alt_km is None:
                raise ValueError("need (lat_deg, lon_deg, alt_km) or ecef_km")
            x, y, z = geodetic_to_ecef_km(lat_deg, lon_deg, alt_km)
        else:
            x, y, z = ecef_km
            if lat_deg is None:
                # ECEF → 测地（迭代两次足够 km 级精度）
                lon_deg = math.degrees(math.atan2(y, x))
                p = math.hypot(x, y)
                lat_deg = math.degrees(math.atan2(z, p * (1 - _E2)))
                n = _A_KM / math.sqrt(1 - _E2 * math.sin(
                    math.radians(lat_deg)) ** 2)
                alt_km = p / max(math.cos(math.radians(lat_deg)), 1e-9) - n
        lam = math.degrees(self._dip.magnetic_latitude_rad(x, y, z))
        l_shell = self._dip.mcilwain_l(x, y, z)
        rc = self._dip.vertical_cutoff_gv(x, y, z)
        spectra = self._spectra_at_cutoff(rc)
        tag, tag_note = self._environment_tag(lam, l_shell,
                                              lat_deg, lon_deg, alt_km)
        out = {
            "epoch": epoch,
            "position": {
                "lat_deg": lat_deg, "lon_deg": lon_deg, "alt_km": alt_km,
                "ecef_km": [x, y, z],
            },
            "geomagnetic": {
                "mag_lat_deg": round(lam, 4),
                "mcilwain_l": round(l_shell, 4) if math.isfinite(l_shell)
                else "inf",
                "cutoff_gv": round(rc, 4),
            },
            "environment_tag": tag,
            "environment_note": tag_note,
            "gcr_species": sorted(spectra.keys()),
            "seu_rate_gcr_only": None,
            "provenance": self.provenance,
        }
        if spectra and hasattr(self.device, "domain_rates_day"):
            per_dom, total_day = self.device.domain_rates_day(spectra)
            out["seu_rate_gcr_only"] = {
                "per_domain_per_day": {
                    k: {
                        "rate_per_day_per_bit": per_dom[k],
                        "rate_per_day": per_dom[k] * int(
                            self.device.domains[k]["bits"] or 0),
                        "bits": self.device.domains[k]["bits"],
                    }
                    for k in per_dom
                },
                "device_total_per_day": total_day,
            }
        return out


def attach_ephemeris(rows, attacher=None):
    """批量模式：对 [{epoch,lat_deg,lon_deg,alt_km} 或含 ecef_km] 逐条 attach。

    rows: iterable of dicts。返回同序 dicts。"""
    att = attacher or RadiationAttacher()
    out = []
    for r in rows:
        out.append(att.attach(
            lat_deg=r.get("lat_deg"), lon_deg=r.get("lon_deg"),
            alt_km=r.get("alt_km"), ecef_km=r.get("ecef_km"),
            epoch=r.get("epoch")))
    return out
