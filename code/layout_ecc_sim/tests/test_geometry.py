"""Geometry unit tests for the M3 ellipse kernel (guide 9.3)."""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from layout_ecc.geometry import ellipse_intersects_rect, point_in_ellipse, classify_hits
from layout_ecc.kernel import kernel_axes
from layout_ecc.layout_synth import synthesize
from layout_ecc.strike import g4_presets, run_strike


class TestKernel(unittest.TestCase):
    def test_normal_incidence_is_circle(self):
        a, b = kernel_axes(15, 0.0, a0=2.0, k_let=0.0)
        self.assertAlmostEqual(a, b)
        self.assertAlmostEqual(a, 2.0)

    def test_oblique_stretches_along_track(self):
        a0, b0 = kernel_axes(15, 0.0, a0=2.0, k_let=0.0)
        a, b = kernel_axes(15, 60.0, a0=2.0, k_let=0.0)
        self.assertAlmostEqual(b, b0)
        self.assertGreater(a, a0)


class TestEllipseRect(unittest.TestCase):
    def test_center_on_resource(self):
        self.assertTrue(ellipse_intersects_rect(0.5, 0.5, 0.8, 0.8, 0, 0, 0, 1, 1))

    def test_far_miss(self):
        self.assertFalse(ellipse_intersects_rect(10, 10, 0.5, 0.5, 0, 0, 0, 1, 1))

    def test_point_in_rotated_ellipse(self):
        phi = math.pi / 4
        self.assertTrue(point_in_ellipse(1, 0, 0, 0, 2, 0.4, 0))
        self.assertFalse(point_in_ellipse(0, 1, 0, 0, 2, 0.4, 0))
        self.assertTrue(point_in_ellipse(0.7, 0.7, 0, 0, 2, 0.4, phi))


class TestStrikeReplay(unittest.TestCase):
    def setUp(self):
        self.layout = synthesize(ncols=24, nrows=40)

    def test_seed_replay(self):
        kw = dict(layout=self.layout, x0=12.0, y0=20.0, let=15, theta_deg=45,
                  phi_deg=30, a0=2.0, seed=7)
        a = run_strike(**kw)
        b = run_strike(**kw)
        self.assertEqual([t["unit_id"] for t in a["flipped"]],
                         [t["unit_id"] for t in b["flipped"]])
        self.assertEqual(a["n_candidates"], b["n_candidates"])

    def test_larger_kernel_monotonic_candidates(self):
        small = run_strike(self.layout, 12, 20, 15, 0, 0, a0=1.0, seed=1)
        big = run_strike(self.layout, 12, 20, 15, 0, 0, a0=3.0, seed=1)
        self.assertGreaterEqual(big["n_candidates"], small["n_candidates"])

    def test_g4_presets_run(self):
        presets = g4_presets(self.layout)
        for name, p in presets.items():
            out = run_strike(self.layout, p["x0"], p["y0"], 15, 30, 0,
                             a0=p["a0"], seed=1)
            self.assertIn("n_candidates", out, msg=name)

    def test_unused_region_can_be_no_effect(self):
        edge = run_strike(self.layout, 0.3, 0.3, 15, 0, 0, a0=0.6, seed=1,
                          p_by_domain={"CFG": 0, "FF_STATE": 0,
                                       "BRAM_STATE": 0, "DSP_STATE": 0})
        self.assertEqual(classify_hits(edge["flipped"]), "NO_EFFECT")

    def test_one_site_yields_multiple_domains(self):
        # a CLB tile carries CFG + FF_STATE at the same (x, y)
        out = run_strike(self.layout, 12.5, 20.5, 15, 0, 0, a0=1.0, seed=3,
                         p_by_domain={"CFG": 1.0, "FF_STATE": 1.0,
                                      "BRAM_STATE": 0.0, "DSP_STATE": 0.0})
        by_site = {}
        for f in out["flipped"]:
            by_site.setdefault(f["unit_id"], set()).add(f["domain"])
        self.assertTrue(any({"CFG", "FF_STATE"} <= d for d in by_site.values()))
        self.assertEqual(out["by_domain"]["BRAM_STATE"]["flip"], 0)
        self.assertEqual(out["by_domain"]["DSP_STATE"]["flip"], 0)

    def test_domain_probability_zero_disables_domain(self):
        out = run_strike(self.layout, 12.5, 20.5, 15, 0, 0, a0=2.0, seed=5,
                         p_by_domain={"CFG": 0.0, "FF_STATE": 1.0,
                                      "BRAM_STATE": 1.0, "DSP_STATE": 1.0})
        self.assertTrue(out["by_domain"]["CFG"]["cand"] > 0)
        self.assertEqual(out["by_domain"]["CFG"]["flip"], 0)


if __name__ == "__main__":
    unittest.main()
