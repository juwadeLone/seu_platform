"""WP9 MBU pattern sampling."""
import unittest

from layout_ecc.layout_synth import synthesize
from layout_ecc.mbu_patterns import (
    DEFAULT_TABLE, distribution_table, sample_k, select_k,
)
from layout_ecc.strike import run_strike


class TestDistribution(unittest.TestCase):
    def test_probs_normalized(self):
        s = sum(DEFAULT_TABLE.values())
        self.assertAlmostEqual(s, 1.0)
        tab = distribution_table()
        self.assertAlmostEqual(tab["sum"], 1.0)
        self.assertIn("source:", tab["source"])
        self.assertIn("assumption:", tab["domain_allocation"])

    def test_k1_is_single_flip(self):
        layout = synthesize(ncols=24, nrows=40)
        out = run_strike(layout, 12.5, 20.5, 15, 0, 0, a0=3.0, seed=3,
                         flip_model="pattern", pattern_shape="cluster",
                         p_by_domain={"CFG": 1, "FF_STATE": 1,
                                      "BRAM_STATE": 1, "DSP_STATE": 1})
        self.assertEqual(out["flip_model"], "pattern")
        self.assertEqual(len(out["flipped"]), out["pattern_k"])
        if out["pattern_k"] == 1:
            self.assertEqual(out["n_flipped"], 1)

    def test_seed_replay_pattern(self):
        layout = synthesize(ncols=24, nrows=40)
        kw = dict(layout=layout, x0=12.0, y0=20.0, let=15, theta_deg=0,
                  phi_deg=0, a0=3.0, seed=9, flip_model="pattern",
                  pattern_shape="cluster")
        a = run_strike(**kw)
        b = run_strike(**kw)
        self.assertEqual(
            [(f["unit_id"], f["domain"]) for f in a["flipped"]],
            [(f["unit_id"], f["domain"]) for f in b["flipped"]],
        )
        self.assertEqual(a["pattern_k"], b["pattern_k"])

    def test_bernoulli_default_unchanged(self):
        layout = synthesize(ncols=24, nrows=40)
        kw = dict(layout=layout, x0=12.0, y0=20.0, let=15, theta_deg=45,
                  phi_deg=30, a0=2.0, seed=7)
        a = run_strike(**kw)
        b = run_strike(**kw)
        self.assertEqual(a["flip_model"], "bernoulli")
        self.assertEqual(
            [(f["unit_id"], f["domain"]) for f in a["flipped"]],
            [(f["unit_id"], f["domain"]) for f in b["flipped"]],
        )

    def test_cluster_picks_nearest(self):
        class R:
            def random(self):
                return 0.0
        cands = [
            {"unit_id": "far", "domain": "CFG", "bits": 1,
             "grid_x": 10, "grid_y": 10},
            {"unit_id": "near", "domain": "CFG", "bits": 1,
             "grid_x": 0, "grid_y": 0},
        ]
        picked = select_k(cands, 1, R(), shape="cluster", x0=0.5, y0=0.5)
        self.assertEqual(picked[0]["unit_id"], "near")

    def test_sample_k_range(self):
        class R:
            def __init__(self, u):
                self.u = u
            def random(self):
                return self.u
        self.assertEqual(sample_k(R(0.0)), 1)
        self.assertEqual(sample_k(R(0.699)), 1)
        self.assertEqual(sample_k(R(0.70)), 2)
        self.assertEqual(sample_k(R(0.99)), 2)
