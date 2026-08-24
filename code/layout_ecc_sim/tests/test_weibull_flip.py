"""M9: Lee Weibull σ(LET) drives strike flips; official bit counts."""
import math
import unittest

from layout_ecc.domains import (
    BRAM_BITS, CFG_BITS_PER_CLB, CFG_BITS_PER_SLICE, DSP_BITS,
    DS180_SLICES_VX690T, UG470_BITSTREAM_VX690T, build_domains,
)
from layout_ecc.layout_synth import synthesize
from layout_ecc.strike import run_strike
from layout_ecc.weibull import mu_upsets, p_at_least_one, sigma_cm2, sigma_cm2_from_params


class TestOfficialBits(unittest.TestCase):
    def test_cfg_is_bitstream_share_not_400(self):
        self.assertEqual(UG470_BITSTREAM_VX690T, 229_878_496)
        self.assertEqual(DS180_SLICES_VX690T, 108_300)
        self.assertEqual(CFG_BITS_PER_SLICE, 2122)
        self.assertEqual(CFG_BITS_PER_CLB, 4244)
        self.assertEqual(build_domains("SLICE")["CFG"], 2122)
        self.assertNotIn("CFG", build_domains("BRAM"))
        self.assertEqual(build_domains("BRAM")["BRAM_STATE"], 36 * 1024)
        self.assertEqual(BRAM_BITS, 36864)
        self.assertEqual(DSP_BITS, 169)
        self.assertEqual(build_domains("SLICE", n_ff=4)["FF_STATE"], 4)

    def test_n_prims_no_longer_inflates_cfg(self):
        self.assertEqual(build_domains("SLICE", n_prims=50)["CFG"],
                         build_domains("SLICE", n_prims=0)["CFG"])


class TestLeeSigma(unittest.TestCase):
    def test_below_threshold_is_zero(self):
        self.assertEqual(sigma_cm2("CFG", 0.4), 0.0)
        self.assertGreater(sigma_cm2("CFG", 0.41), 0.0)

    def test_approaches_sat(self):
        sat = 3.34e-12
        hi = sigma_cm2_from_params(1e6, 0.4, 338.5, 0.852, sat)
        self.assertAlmostEqual(hi / sat, 1.0, places=6)

    def test_dsp_is_gap(self):
        self.assertIsNone(sigma_cm2("DSP_STATE", 15))

    def test_mu_units_cm2(self):
        mu = mu_upsets(1000, 1e-12, 1e-9)
        self.assertAlmostEqual(mu, 1.0)
        self.assertAlmostEqual(p_at_least_one(1.0), 1.0 - math.exp(-1.0))


class TestWeibullStrike(unittest.TestCase):
    def test_dsp_never_flips(self):
        layout = synthesize(ncols=24, nrows=40)
        out = run_strike(
            layout, 12.5, 20.5, 80, 0, 0, a0=8.0, seed=1,
            kernel_model="legacy_linear", flip_model="weibull")
        self.assertEqual(out["flip_model"], "weibull")
        self.assertFalse(out["proxy"])
        self.assertEqual(
            sum(1 for f in out["flipped"] if f["domain"] == "DSP_STATE"), 0)

    def test_seed_replay(self):
        layout = synthesize(ncols=24, nrows=40)
        kw = dict(layout=layout, x0=12.0, y0=20.0, let=15, theta_deg=0,
                  phi_deg=0, a0=1.0, seed=11, kernel_model="anchored",
                  flip_model="weibull")
        a = run_strike(**kw)
        b = run_strike(**kw)
        self.assertEqual(
            [(f["unit_id"], f["domain"], f["n_bits"]) for f in a["flipped"]],
            [(f["unit_id"], f["domain"], f["n_bits"]) for f in b["flipped"]],
        )

    def test_anchored_area_is_radaelli_scale(self):
        layout = synthesize(ncols=24, nrows=40)
        out = run_strike(
            layout, 12.0, 20.0, 15, 0, 0, a0=12.0, seed=1,
            kernel_model="anchored", flip_model="weibull")
        self.assertIsNotNone(out["area_um2"])
        self.assertLess(out["area_um2"], 20.0)
        self.assertGreater(out["area_cm2"], 0.0)
        self.assertAlmostEqual(out["area_cm2"], out["area_um2"] * 1e-8)

    def test_bernoulli_default_still_legacy_api(self):
        layout = synthesize(ncols=24, nrows=40)
        out = run_strike(layout, 12.0, 20.0, 15, 45, 30, a0=2.0, seed=7)
        self.assertEqual(out["flip_model"], "bernoulli")
        self.assertTrue(out["proxy"])


if __name__ == "__main__":
    unittest.main()
