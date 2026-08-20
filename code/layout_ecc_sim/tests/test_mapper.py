"""WP3 strike→fault replay."""
import unittest

from layout_ecc.functional import ensure_golden
from layout_ecc.functional_mapper import map_flipped, replay_strike
from layout_ecc.layout_import import load_primitive_map
from layout_ecc.strike import run_strike
import os

_CSV = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "data", "layout", "p1_ooc_win",
    "primitive_map.csv"))


@unittest.skipUnless(os.path.isfile(_CSV), "P1 CSV missing")
class TestMapperReplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layout = load_primitive_map(_CSV)
        cls.golden = ensure_golden()

    def test_seed_replay_identical(self):
        kw = dict(layout=self.layout, x0=self.layout["default_x0"],
                  y0=self.layout["default_y0"], let=15, theta_deg=45,
                  phi_deg=30, a0=12.0, seed=11)
        a = run_strike(**kw)
        b = run_strike(**kw)
        self.assertEqual(
            [(f["unit_id"], f["domain"]) for f in a["flipped"]],
            [(f["unit_id"], f["domain"]) for f in b["flipped"]],
        )
        ra, sa = replay_strike(a["flipped"], golden=self.golden,
                               max_inject=3, strike_id="r")
        rb, sb = replay_strike(b["flipped"], golden=self.golden,
                               max_inject=3, strike_id="r")
        self.assertEqual(sa["outcomes"], sb["outcomes"])
        self.assertEqual(sa["stages"], sb["stages"])
        self.assertTrue(all(r.get("confidence") in ("proxy", "inferred")
                            for r in ra))
        self.assertTrue(any(r.get("confidence") == "inferred" for r in ra))
