"""P0 joint injection: one strike = one event, unmapped never corrected."""
import os
import unittest

from layout_ecc.functional import ensure_golden
from layout_ecc.functional_mapper import replay_strike
from layout_ecc.joint_replay import (
    build_event, compare_protection, replay_event, replay_events)


def row(cw, sym=0, n=1, stage=None, domain="FF_STATE", conf="inferred", **kw):
    stage = stage if stage is not None else int(cw.split(":")[0][1:])
    return dict(domain=domain, stage_id=stage, codeword_id=cw, symbol_id=sym,
                codeword_confidence=conf, n_bits=n, unit_id=f"u{cw}{sym}",
                **kw)


class TestJointReplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.golden = ensure_golden()

    def replay(self, flipped, prot="on", eid="e", seed=0):
        return replay_event(flipped, event_id=eid, seed=seed,
                            protection=prot, golden=self.golden)

    def test_fault_free_is_golden(self):
        for prot in ("on", "off"):
            r = self.replay([], prot)
            self.assertEqual(r["outcome"], "NO_FAULT")
            self.assertTrue(r["output_match"])
            self.assertEqual(r["max_output_deviation"], 0)

    def test_single_error_recovers(self):
        cases = [row("s3:secded:mem1"), row("s5:arith", sym=2),
                 row("s10:arith:lower", sym=1), row("s8:tmr", sym=1)]
        for flipped in cases:
            with self.subTest(cw=flipped["codeword_id"]):
                on = self.replay([flipped], "on")
                self.assertTrue(on["output_match"])
                self.assertIn(on["outcome"], ("CORRECTED", "MASKED"))
                off = self.replay([flipped], "off")
                self.assertEqual(off["outcome"], "SDC")
                self.assertGreater(off["max_output_deviation"], 0)

    def test_explicit_bit_position_is_used(self):
        ev = build_event([row("s4:arith", sym=0, bit_positions=[7])], "x")
        self.assertEqual([b["bit"] for b in ev["bits"]], [7])
        self.assertEqual(ev["bits"][0]["bit_source"], "explicit")

    def test_double_in_one_codeword_not_split(self):
        for flipped in ([row("s3:secded:mem0", n=2)],
                        [row("s6:arith", sym=0), row("s6:arith", sym=3)]):
            with self.subTest(cw=flipped[0]["codeword_id"]):
                r = self.replay(flipped, "on")
                self.assertEqual(len(r["codewords"]), 1)
                self.assertEqual(r["codewords"][0]["n_bits"], 2)
                self.assertEqual(r["outcome"], "DUE")
                self.assertNotEqual(r["outcome"], "CORRECTED")
        # the legacy per-row replay calls the same two-symbol hit corrected
        _, legacy = replay_strike(
            [row("s6:arith", sym=0), row("s6:arith", sym=3)],
            golden=self.golden)
        self.assertEqual(legacy["outcomes"], ["CORRECTED", "CORRECTED"])

    def test_cross_codeword_keeps_event_id(self):
        flipped = [row("s2:secded:mem2"), row("s5:arith", sym=1),
                   row("s9:tmr", sym=0)]
        r = self.replay(flipped, "on", eid="case7/3")
        self.assertEqual(len(r["codewords"]), 3)
        self.assertEqual({c["event_id"] for c in r["codewords"]}, {"case7/3"})
        self.assertTrue(all(b["event_id"] == "case7/3"
                            for b in r["event"]["bits"]))
        self.assertEqual(r["outcome"], "CORRECTED")
        self.assertEqual(self.replay(flipped, "off")["outcome"], "SDC")

    def test_unmapped_never_corrected(self):
        cfg = dict(domain="CFG", stage_id=1, codeword_id="s1:arith",
                   symbol_id=0, codeword_confidence="inferred", n_bits=3)
        proxy = row("s4:arith", conf="proxy")
        decoder = row("s10:arith:decoder", sym=None)
        r = self.replay([cfg])
        self.assertEqual(r["outcome"], "UNMAPPED")
        self.assertEqual(r["mapping_rate"], 0.0)
        self.assertEqual(r["unmapped_reasons"], ["cfg_no_essential_bit_map"])
        self.assertEqual(r["codewords"], [])
        self.assertTrue(all(b["bit"] is None for b in r["event"]["bits"]))
        # a correctable FF bit next to unmapped bits is still not CORRECTED
        mixed = self.replay([row("s3:secded:mem1"), cfg, proxy, decoder])
        self.assertEqual(mixed["mapped_outcome"], "CORRECTED")
        self.assertEqual(mixed["outcome"], "UNMAPPED")
        self.assertAlmostEqual(mixed["mapping_rate"], 1 / 6)
        lines = [{"event_id": "a", "seed": 1, "flipped": [cfg]},
                 {"event_id": "b", "seed": 1,
                  "flipped": [row("s5:arith", sym=0)]},
                 {"event_id": "c", "seed": 1, "flipped": []}]
        _, summary = replay_events(lines, golden=self.golden)
        self.assertEqual(summary["outcomes"]["UNMAPPED"], 1)
        self.assertEqual(summary["outcomes"]["CORRECTED"], 1)
        self.assertEqual(summary["outcomes"]["NO_FAULT"], 1)
        self.assertAlmostEqual(summary["mapping_rate"], 1 / 4)

    def test_fault_list_replays_identically(self):
        lines = [{"event_id": f"k/{s}", "seed": s,
                  "flipped": [row("s3:secded:mem1", n=2),
                              row("s7:arith", sym=4, n=2)]}
                 for s in range(3)]
        a = compare_protection(lines, golden=self.golden)
        b = compare_protection(lines, golden=self.golden)
        self.assertEqual(a["fault_list"], b["fault_list"])
        for prot in ("on", "off"):
            self.assertEqual([r["outcome"] for r in a[prot]["results"]],
                             [r["outcome"] for r in b[prot]["results"]])
        # off and on replay the very same bits
        self.assertEqual([r["event"] for r in a["on"]["results"]],
                         [r["event"] for r in a["off"]["results"]])


_CSV = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "data", "layout", "p1_ooc_win",
    "primitive_map.csv"))


@unittest.skipUnless(os.path.isfile(_CSV), "P1 CSV missing")
class TestLayoutStrike(unittest.TestCase):
    def test_real_strike_reports_mapping_rate(self):
        from layout_ecc.layout_import import load_primitive_map
        from layout_ecc.strike import run_strike
        layout = load_primitive_map(_CSV)
        golden = ensure_golden()
        res = run_strike(layout, x0=layout["default_x0"],
                         y0=layout["default_y0"], let=15, theta_deg=45,
                         phi_deg=30, a0=12.0, seed=11)
        r = replay_event(res["flipped"], event_id="real/11", seed=11,
                         golden=golden)
        self.assertEqual(r["n_bits"], res["n_bits_flipped"])
        self.assertIsNotNone(r["mapping_rate"])
        if r["n_unmapped"]:
            self.assertNotIn(r["outcome"], ("CORRECTED", "MASKED"))


if __name__ == "__main__":
    unittest.main()
