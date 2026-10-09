"""P3 tests: consequence engine, mitigation advisor, report builder."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from layout_ecc import gui
from layout_ecc.consequence import assess, module_domain_bits, default_domain_rates
from layout_ecc.mitigation import advise
from layout_ecc.report import build_report


class TestConsequence(unittest.TestCase):
    def setUp(self):
        self.layout = gui.layout_state()["layout"]

    def test_module_bits(self):
        mbits = module_domain_bits(self.layout)
        self.assertGreater(len(mbits), 0)
        total = sum(sum(d.values()) for d in mbits.values())
        self.assertGreater(total, 0)

    def test_assess_all_critical(self):
        out = assess(self.layout, None, None, 365.0)
        self.assertGreater(out["critical_rate_per_day"], 0)
        self.assertGreater(out["p_fail"], 0.9)
        self.assertTrue(out["assumptions"])

    def test_subset_lower(self):
        all_ = assess(self.layout, None, None, 365.0)
        one = assess(self.layout, [0], None, 365.0)
        self.assertLessEqual(one["critical_rate_per_day"],
                             all_["critical_rate_per_day"])

    def test_rate_override(self):
        out = assess(self.layout, None, {"CFG": 1e-6, "FF_STATE": 0,
                                         "BRAM_STATE": 0}, 365.0)
        cfg_bits = sum(m["bits"]["CFG"] for m in out["per_module"])
        self.assertAlmostEqual(out["critical_rate_per_day"], cfg_bits * 1e-6)


class TestMitigation(unittest.TestCase):
    def test_advise(self):
        out = advise({"CFG": 1.0, "FF_STATE": 0.5, "BRAM_STATE": 2.0,
                      "DSP_STATE": None},
                     {"CFG": 1e8, "FF_STATE": 1e6, "BRAM_STATE": 1e7},
                     target_rate_per_day=0.01, duration_days=365)
        self.assertIn("DSP_STATE", out["gap_domains"])
        self.assertLess(out["residual_total_per_day"], 3.5)
        self.assertTrue(out["assumptions"])

    def test_tmr_residual_model(self):
        out = advise({"FF_STATE": 1.0}, {"FF_STATE": 1e6}, 0.001,
                     duration_days=365)
        rec = out["recommendations"][0]
        self.assertEqual(rec["option"], "tmr")
        self.assertLess(rec["residual_per_day"], 1.0)


class TestReport(unittest.TestCase):
    def test_build(self):
        st = gui.layout_state()
        out = build_report(st["layout"], st, 365.0)
        self.assertIn("p_fail", out)
        self.assertTrue(out["html"].startswith("<!doctype"))
        import os
        self.assertTrue(os.path.isfile(out["path"]))
        os.remove(out["path"])


if __name__ == "__main__":
    unittest.main()
