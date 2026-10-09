"""Unit tests (stdlib unittest): python -m unittest discover -s tests"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from orbit_seu.orbit import OrbitElements
from orbit_seu.magnetosphere import DipoleModel
from orbit_seu.spectra import Spectrum
from orbit_seu.device import WeibullLET, DomainWeibull, build_device_sigma
from orbit_seu.rates import (sigma_effective, heavy_ion_rate_per_s,
                             mission_stats, _direction_quadrature,
                             FLAT_PLATE_FACTOR)
from orbit_seu.environment import demo_gcr_let_spectra


class TestOrbit(unittest.TestCase):
    def test_period_matches_kepler(self):
        orb = OrbitElements(altitude_km=550, inclination_deg=97.6,
                            eccentricity=0.001)
        expect = 2 * math.pi * math.sqrt(orb.a**3 / 3.986004418e14)
        self.assertAlmostEqual(orb.period, expect, delta=expect * 0.01)

    def test_ground_track_radius(self):
        orb = OrbitElements(altitude_km=500, inclination_deg=30)
        x, y, z = orb.position_geo_km(0.0)
        r = math.sqrt(x*x + y*y + z*z)
        self.assertAlmostEqual(r, 6378.137 + 500, delta=5.0)


class TestMagnetosphere(unittest.TestCase):
    def setUp(self):
        self.dip = DipoleModel()

    def test_equatorial_cutoff_at_surface(self):
        # point on the geomagnetic equator at Earth radius
        px, py, pz = self.dip.pole
        # any surface point perpendicular to the pole vector
        v = (1.0, 0.0, 0.0)
        dot = v[0]*px + v[1]*py + v[2]*pz
        r = [v[0]-dot*px, v[1]-dot*py, v[2]-dot*pz]
        n = math.sqrt(sum(c*c for c in r)) / 6378.137
        p = [c / n for c in r]
        rc = self.dip.vertical_cutoff_gv(*p)
        self.assertAlmostEqual(rc, 14.9, delta=0.5)

    def test_pole_cutoff_zero(self):
        px, py, pz = self.dip.pole
        rc = self.dip.vertical_cutoff_gv(6378.137*px, 6378.137*py,
                                         6378.137*pz)
        self.assertLess(rc, 1e-3)

    def test_cutoff_decreases_with_altitude(self):
        px, py, pz = self.dip.pole
        v = (1.0, 0.0, 0.0)
        dot = v[0]*px + v[1]*py + v[2]*pz
        r = [v[0]-dot*px, v[1]-dot*py, v[2]-dot*pz]
        n = math.sqrt(sum(c*c for c in r)) / 6378.137
        p = [c / n for c in r]
        lo = self.dip.vertical_cutoff_gv(*p)
        hi = self.dip.vertical_cutoff_gv(*[2*c for c in p])
        self.assertLess(hi, lo)


class TestDeviceAndRates(unittest.TestCase):
    def test_weibull_bounds(self):
        w = WeibullLET(5.0, 20.0, 1.5, 1e-7)
        self.assertEqual(w.sigma(4.9), 0.0)
        self.assertEqual(w.sigma(5.0), 0.0)  # exactly at threshold
        self.assertGreater(w.sigma(5.1), 0.0)
        self.assertLess(w.sigma(1e6), 1e-7 * (1 + 1e-9))
        self.assertLess(w.sigma(30), w.sigma(60))

    def test_quadrature_normalized(self):
        self.assertAlmostEqual(sum(w for w, _ in _direction_quadrature()),
                               1.0, places=9)
        # effective sigma >= normal-incidence sigma (longer chords)
        dev = WeibullLET(5.0, 20.0, 1.5, 1e-7)
        self.assertGreaterEqual(sigma_effective(6.0, dev), dev.sigma(6.0))

    def test_delta_function_rate(self):
        # narrow rectangular spectrum: integral(phi dL)=1
        # => rate = (1/2) * <sigma(L0/cos)>  (omni flux through a thin plate)
        dev = WeibullLET(5.0, 20.0, 1.5, 1e-7)
        L0 = 15.0
        dL = 0.1
        spec = Spectrum([L0 - dL, L0, L0 + dL],
                        [1/(2*dL), 1/(2*dL), 1/(2*dL)])
        rate = heavy_ion_rate_per_s(spec, dev)
        self.assertAlmostEqual(rate, FLAT_PLATE_FACTOR * sigma_effective(L0, dev),
                               delta=1e-9)

    def test_flat_plate_constant_sigma(self):
        # constant sigma, omni flux phi: plate is crossed by phi*A/2
        class Flat:
            def sigma(self, let):
                return 2e-8
        spec = Spectrum([1.0, 2.0, 3.0], [0.5, 0.5, 0.5])   # phi = 1
        self.assertAlmostEqual(heavy_ion_rate_per_s(spec, Flat()), 1e-8,
                               delta=1e-14)

    def test_lee2014_sigma_is_cm2(self):
        # Lee 2014 Fig. 3 (cm^2/bit): config memory ~1.2e-8 at LET 126.
        # Table 1 prints 'um^2/bit' but A is cm^2/bit.
        cram = WeibullLET(0.4, 338.5, 0.852, 3.34e-08)
        self.assertGreater(cram.sigma(126.1), 0.8e-8)
        self.assertLess(cram.sigma(126.1), 1.6e-8)

    def test_mission_stats(self):
        st = mission_stats(1.0 / 86400.0, 86400.0)  # 1/day for 1 day
        self.assertAlmostEqual(st["expected_events"], 1.0)
        self.assertAlmostEqual(st["prob_at_least_one"],
                               1 - math.exp(-1.0), places=9)


class TestDomainWeibull(unittest.TestCase):
    """Per-domain Weibull (measured 7-series) must not regress the
    single-group fallback, and must reproduce single-domain rates."""
    def _specs(self):
        root = os.path.join(os.path.dirname(__file__), "..")
        from orbit_seu.environment import load_spectrum_file
        sp = {}
        for s in ["H", "He", "Z03-10", "Z11-20", "Z21-28", "Z29-92"]:
            p = os.path.join(root, "orbit_seu", "env_data", "spenvis_let",
                             f"spenvis_{s}.let.txt")
            sp[s] = load_spectrum_file(p, x_col=0, y_col=1)
        return sp

    def test_build_device_single_group_fallback(self):
        dev = build_device_sigma({"heavy_ion_weibull": {
            "let_threshold": 5.0, "width": 20.0, "shape": 1.5,
            "sigma_sat_cm2_per_bit": 1e-7}})
        self.assertIsInstance(dev, WeibullLET)
        self.assertNotIsInstance(dev, DomainWeibull)

    def test_build_device_by_domain(self):
        dev = build_device_sigma({"heavy_ion_weibull_by_domain": {
            "CRAM": {"let_threshold": 0.4, "width": 338.5, "shape": 0.852,
                     "sigma_sat_cm2_per_bit": 3.34e-08, "bits": 67930000}}})
        self.assertIsInstance(dev, DomainWeibull)
        self.assertEqual(dev.domains["CRAM"]["bits"], 67930000)

    def test_domain_rate_matches_single_weibull(self):
        specs = self._specs()
        dw = DomainWeibull({"CRAM": {"let_threshold": 0.4, "width": 338.5,
                                     "shape": 0.852,
                                     "sigma_sat_cm2_per_bit": 3.34e-08,
                                     "bits": 1000}})
        per, total = dw.domain_rates_day(specs)
        lone = WeibullLET(0.4, 338.5, 0.852, 3.34e-08)
        expected = sum(heavy_ion_rate_per_s(sp, lone) * 86400.0
                       for sp in specs.values())
        self.assertAlmostEqual(per["CRAM"], expected, delta=expected * 1e-9)
        self.assertAlmostEqual(total, 1000 * per["CRAM"], delta=1e-12)

    def test_mission_domain_units_match_single_group(self):
        """Domain path must write /s into rates_per_s, matching
        single-group bits × rate_per_s. Top-level placeholder bits
        must not change the device rate."""
        from orbit_seu.mission import run
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        files = {
            s: os.path.join(root, "orbit_seu", "env_data", "spenvis_let",
                            f"spenvis_{s}.let.txt")
            for s in ["H", "He", "Z03-10", "Z11-20", "Z21-28", "Z29-92"]
        }
        wb = {"let_threshold": 0.4, "width": 338.5, "shape": 0.852,
              "sigma_sat_cm2_per_bit": 3.34e-08}
        bits_n = 1000
        common = {
            "mission": {"duration_years": 1.0,
                        "sampling": {"orbits": 1, "points_per_orbit": 8}},
            "orbit": {"altitude_km": 20200, "inclination_deg": 55.0,
                      "eccentricity": 0.001},
            "environment": {
                "type": "files",
                "let_spectra_files": files,
                "let_columns": {"let": 0, "diff_flux": 1},
            },
        }
        r_single = run({**common, "device": {
            "bits": bits_n, "heavy_ion_weibull": wb}})
        r_dom = run({**common, "device": {
            "bits": 55000000,
            "heavy_ion_weibull_by_domain": {
                "CRAM": dict(wb, bits=bits_n)}}})
        expect = r_single["rates_per_s"]["total_per_device"]
        got = r_dom["rates_per_s"]["total_per_device"]
        self.assertIsNotNone(expect)
        self.assertAlmostEqual(got, expect, delta=abs(expect) * 1e-9)
        self.assertEqual(r_dom["device"]["bits"], bits_n)
        per_day = r_dom["per_domain_rates_day_per_bit"]["CRAM"]
        self.assertAlmostEqual(got * 86400.0, bits_n * per_day,
                               delta=abs(bits_n * per_day) * 1e-9)
        # 1-year expectation uses /s, not the old /day-as-/s 86400× error
        mu = r_dom["mission"]["per_device"]["expected_events"]
        self.assertAlmostEqual(
            mu, got * 365.25 * 86400.0, delta=abs(mu) * 1e-9)


class TestDemoEnvironment(unittest.TestCase):
    def test_cutoff_suppresses_flux(self):
        full = demo_gcr_let_spectra(0.0)
        cut = demo_gcr_let_spectra(10.0)
        for name in full:
            self.assertLess(cut[name].total_flux(), full[name].total_flux())

    def test_spectra_valid(self):
        for name, sp in demo_gcr_let_spectra(1.0).items():
            self.assertGreater(sp.total_flux(), 0.0)


if __name__ == "__main__":
    unittest.main()
