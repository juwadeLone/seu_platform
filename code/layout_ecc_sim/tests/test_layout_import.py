"""Load P1 primitive_map.csv when the DCP export is present."""
import os
import unittest

from layout_ecc.layout_import import load_primitive_map
from layout_ecc.strike import g4_presets, run_strike

_CSV = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "data", "layout", "p1_ooc_win",
    "primitive_map.csv"))


@unittest.skipUnless(os.path.isfile(_CSV), "P1 primitive_map.csv not exported")
class TestP1Import(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layout = load_primitive_map(_CSV)

    def test_sites_and_bbox(self):
        L = self.layout
        self.assertGreater(L["n_sites"], 10000)
        self.assertEqual(L["n_sites"], len(L["tiles"]))
        self.assertGreater(L["ncols"], 100)
        self.assertGreater(L["nrows"], 100)
        for t in L["tiles"]:
            self.assertTrue(t["is_used"])
            self.assertGreaterEqual(t["grid_x"], 0)
            self.assertLess(t["grid_x"], L["ncols"])
            self.assertGreaterEqual(t["grid_y"], 0)
            self.assertLess(t["grid_y"], L["nrows"])

    def test_strike_on_real_sites(self):
        L = self.layout
        out = run_strike(L, L["default_x0"], L["default_y0"],
                         15, 45, 30, a0=L["default_a0"], seed=1)
        self.assertGreater(out["n_candidates"], 0)
        self.assertIn("unit_id", out["candidates"][0])
        self.assertIn("domain", out["candidates"][0])

    def test_domains_present(self):
        ff_sites = 0
        for t in self.layout["tiles"]:
            self.assertIn("domains", t)
            self.assertGreater(t["domains"].get("CFG", 0), 0,
                               msg=t["site"])
            if t["domains"].get("FF_STATE", 0) > 0:
                ff_sites += 1
        self.assertGreater(ff_sites, 0)

    def test_stage_tags_on_sites(self):
        tagged = 0
        shared = 0
        for t in self.layout["tiles"]:
            if t["stage_id"] > 0:
                tagged += 1
            if t.get("is_shared"):
                shared += 1
        self.assertGreater(tagged, 0.9 * self.layout["n_sites"])
        self.assertEqual(shared, self.layout["n_shared_sites"])

    def test_cross_stage_preview_not_placeholder(self):
        L = self.layout
        out = run_strike(L, L["default_x0"], L["default_y0"],
                         15, 45, 30, a0=20.0, seed=1)
        self.assertTrue(any(f["stage_id"] > 0 for f in out["flipped"]))
        # a large kernel at the centroid should usually see >1 stage
        if len(out["stages_hit"]) > 1:
            self.assertEqual(out["preview_class"], "CROSS_STAGE")
        presets = g4_presets(self.layout)
        self.assertIn("center_on_clb", presets)
        self.assertIn("bram_delay", presets)
