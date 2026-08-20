"""WP8 unit conversions and anchored kernel."""
import math
import unittest

from layout_ecc.kernel import kernel_axes, kernel_axes_from_area
from layout_ecc.layout_synth import synthesize
from layout_ecc.strike import run_strike
from layout_ecc.units import (
    A_REF_UM2, LET_REF, RPM_TO_UM, RADAELLI_2005, area_to_grid_b,
    area_um2_from_let, constants_passport, radaelli_fit, radius_um_from_area,
)


class TestRadaelliFit(unittest.TestCase):
    def test_alpha_sublinear(self):
        fit = radaelli_fit()
        self.assertLess(fit["alpha"], 1.0)
        self.assertGreater(fit["alpha"], 0.0)
        # 144/22 MeV = 6.55× energy, 4.613/1.178 = 3.92× area → sublinear

    def test_fit_rmse_recorded(self):
        fit = radaelli_fit()
        self.assertIn("rmse_um2", fit)
        self.assertGreaterEqual(fit["rmse_um2"], 0.0)

    def test_area_monotonic_in_let(self):
        lets = [5, 10, 15, 20, 30]
        areas = [area_um2_from_let(L) for L in lets]
        for a, b in zip(areas, areas[1:]):
            self.assertLess(a, b)
        self.assertAlmostEqual(area_um2_from_let(LET_REF), A_REF_UM2)

    def test_area_to_axes_to_grid(self):
        area = 2.903
        r = radius_um_from_area(area)
        self.assertAlmostEqual(r, math.sqrt(area / math.pi))
        b = area_to_grid_b(area, rpm_to_um=8.0)
        self.assertAlmostEqual(b, r / 8.0)
        a, bb = kernel_axes_from_area(area, theta_deg=0.0, rpm_to_um=8.0)
        self.assertAlmostEqual(a, bb)
        self.assertAlmostEqual(bb, b)
        a60, b60 = kernel_axes_from_area(area, theta_deg=60.0, rpm_to_um=8.0)
        self.assertAlmostEqual(b60, b)
        self.assertGreater(a60, a)

    def test_passport_tags(self):
        p = constants_passport()
        self.assertEqual(p["rpm_to_um"]["source"], "assumption")
        self.assertIn("source:", p["radaelli_2005"]["source"])
        self.assertIn("assumption:", p["let_energy_bridge"])


class TestLegacyDefault(unittest.TestCase):
    def test_legacy_axes_unchanged(self):
        a, b = kernel_axes(15, 0.0, a0=2.0, k_let=0.0)
        self.assertAlmostEqual(a, 2.0)
        self.assertAlmostEqual(b, 2.0)

    def test_legacy_strike_default(self):
        layout = synthesize(ncols=24, nrows=40)
        out = run_strike(layout, 12, 20, 15, 0, 0, a0=2.0, seed=1)
        self.assertEqual(out["kernel_model"], "legacy_linear")
        self.assertEqual(out["flip_model"], "bernoulli")

    def test_anchored_uses_area(self):
        layout = synthesize(ncols=24, nrows=40)
        out = run_strike(layout, 12, 20, 15, 0, 0, a0=12.0, seed=1,
                         kernel_model="anchored")
        self.assertEqual(out["kernel_model"], "anchored")
        self.assertAlmostEqual(out["area_um2"], A_REF_UM2)
        # SRAM-cluster area at 8 µm/RPM is a fraction of one site
        self.assertLess(out["a0_eq_grid"], 1.0)
        self.assertEqual(out["rpm_to_um"], RPM_TO_UM)
