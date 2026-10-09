"""Tilted centered-dipole geomagnetic model.

Provides the geomagnetic (dipole) latitude, McIlwain L (dipole approx.) and
the Størmer vertical cutoff rigidity Rc = Rc_eq * (Re/r)^2 * cos^4(lat_m).
The centered-dipole cutoff is accurate to roughly +/-20% against multi-pole
cutoff maps (Smart & Shea; AE9/AP9 magnetic coordinates) -- the report
carries this caveat explicitly.
"""
import math
from .constants import (R_EARTH_KM, G10_2020, G11_2020, H11_2020,
                        CUTOFF_EQ_GV_DEFAULT)


class DipoleModel:
    def __init__(self, g10=G10_2020, g11=G11_2020, h11=H11_2020,
                 cutoff_eq_gv=CUTOFF_EQ_GV_DEFAULT):
        m = math.sqrt(g10*g10 + g11*g11 + h11*h11)
        # Geographic unit vector of the NORTH geomagnetic pole (= -m_vec/M).
        self.pole = (-g11 / m, -h11 / m, -g10 / m)
        self.cutoff_eq_gv = cutoff_eq_gv
        pole_lat = math.degrees(math.asin(self.pole[2]))
        pole_lon = math.degrees(math.atan2(self.pole[1], self.pole[0]))
        self.pole_description = (f"north dipole pole {pole_lat:.2f} deg, "
                                 f"{pole_lon:.2f} deg lon (from g/h inputs)")

    def magnetic_latitude_rad(self, x, y, z):
        r = math.sqrt(x*x + y*y + z*z)
        px, py, pz = self.pole
        return math.asin(max(-1.0, min(1.0, (x*px + y*py + z*pz) / r)))

    def mcilwain_l(self, x, y, z):
        r = math.sqrt(x*x + y*y + z*z) / R_EARTH_KM
        lam = self.magnetic_latitude_rad(x, y, z)
        c2 = math.cos(lam)**2
        return r / c2 if c2 > 1e-9 else float("inf")

    def vertical_cutoff_gv(self, x, y, z):
        r = math.sqrt(x*x + y*y + z*z) / R_EARTH_KM
        lam = self.magnetic_latitude_rad(x, y, z)
        return self.cutoff_eq_gv * (1.0 / r)**2 * math.cos(lam)**4


def magnetic_latitude(x, y, z, model=None):
    return (model or DipoleModel()).magnetic_latitude_rad(x, y, z)


def vertical_cutoff_gv(x, y, z, model=None):
    return (model or DipoleModel()).vertical_cutoff_gv(x, y, z)
