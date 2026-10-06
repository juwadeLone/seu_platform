"""Kepler orbit with first-order J2 secular rates.

Propagates classical elements (a, e, i, RAAN, argp, M0) with the standard
first-order secular J2 rates (Vallado, Fundamentals of Astrodynamics) and
returns ECI and rotating geographic (geocentric) positions. Short-period J2
oscillations are neglected: for radiation-environment sampling (km-scale
accuracy over many orbits) this is adequate and is stated in the report.
"""
import math
from .constants import MU_EARTH, R_EARTH_KM, J2, OMEGA_EARTH


class OrbitElements:
    def __init__(self, altitude_km, inclination_deg, eccentricity=0.0,
                 raan_deg=0.0, argp_deg=0.0, mean_anomaly0_deg=0.0,
                 gmst0_deg=0.0):
        self.a = (R_EARTH_KM + altitude_km) * 1e3      # m (circularized alt)
        self.e = float(eccentricity)
        self.i = math.radians(inclination_deg)
        self.raan0 = math.radians(raan_deg)
        self.argp0 = math.radians(argp_deg)
        self.M0 = math.radians(mean_anomaly0_deg)
        self.gmst0 = math.radians(gmst0_deg)

        self.n = math.sqrt(MU_EARTH / self.a**3)       # rad/s mean motion
        self.period = 2 * math.pi / self.n
        p = self.a * (1 - self.e**2)
        f = 1.5 * J2 * (R_EARTH_KM * 1e3 / p)**2 * self.n
        # first-order secular rates (rad/s)
        self.raan_dot = -f * math.cos(self.i)
        self.argp_dot = 0.5 * f * (5 * math.cos(self.i)**2 - 1)
        self.M_dot = self.n + f * math.sqrt(1 - self.e**2) * (3 * math.cos(self.i)**2 - 1) * 0.5

    def elements_at(self, t_s):
        return (self.raan0 + self.raan_dot * t_s,
                self.argp0 + self.argp_dot * t_s,
                self.M0 + self.M_dot * t_s)

    def _eccentric_anomaly(self, M):
        E = M if self.e < 0.8 else math.pi
        for _ in range(64):
            dE = (E - self.e * math.sin(E) - M) / (1 - self.e * math.cos(E))
            E -= dE
            if abs(dE) < 1e-12:
                break
        return E

    def position_eci_km(self, t_s):
        raan, argp, M = self.elements_at(t_s)
        M = math.fmod(M, 2 * math.pi)
        E = self._eccentric_anomaly(M)
        xv = self.a * (math.cos(E) - self.e) / 1e3
        yv = self.a * math.sqrt(1 - self.e**2) * math.sin(E) / 1e3
        cO, sO = math.cos(raan), math.sin(raan)
        cw, sw = math.cos(argp), math.sin(argp)
        ci, si = math.cos(self.i), math.sin(self.i)
        x = (cO*cw - sO*sw*ci)*xv + (-cO*sw - sO*cw*ci)*yv
        y = (sO*cw + cO*sw*ci)*xv + (-sO*sw + cO*cw*ci)*yv
        z = (sw*si)*xv + (cw*si)*yv
        return x, y, z

    def position_geo_km(self, t_s):
        """ECI -> rotating geographic frame via GMST(t) = gmst0 + omega*t."""
        x, y, z = self.position_eci_km(t_s)
        th = self.gmst0 + OMEGA_EARTH * t_s
        c, s = math.cos(th), math.sin(th)
        return x*c + y*s, -x*s + y*c, z


def propagate_mission(orbit, n_orbits, points_per_orbit):
    """Sample the orbit: yields (t_s, x_geo, y_geo, z_geo) covering n_orbits
    starting anomalies spread uniformly so the sweep is phase-unbiased."""
    out = []
    for k in range(n_orbits):
        t0 = k * orbit.period / n_orbits
        for j in range(points_per_orbit):
            t = t0 + j * orbit.period / points_per_orbit
            out.append((t,) + orbit.position_geo_km(t))
    return out
