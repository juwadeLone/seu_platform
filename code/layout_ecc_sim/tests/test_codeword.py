"""WP5 codeword tags from P1 hier_cell names."""
import unittest

from layout_ecc.codeword_map import codeword_of, majority_codeword
from layout_ecc.functional_mapper import classify_strike_faults, map_flipped


class TestCodewordNames(unittest.TestCase):
    def test_butterfly_symbol(self):
        rec = codeword_of(
            "u/s5/complete_butterflies[3].pipe_rot.rotate/out_re[31]_i_8__1")
        self.assertEqual(rec["codeword_id"], "s5:arith")
        self.assertEqual(rec["symbol_id"], 3)
        self.assertEqual(rec["confidence"], "inferred")
        self.assertEqual(rec["scheme"], "arithmetic_643")

    def test_two_symbols_same_codeword(self):
        a = codeword_of("u/s4/complete_butterflies[0].x")
        b = codeword_of("u/s4/complete_butterflies[1].x")
        self.assertEqual(a["codeword_id"], b["codeword_id"])
        self.assertNotEqual(a["symbol_id"], b["symbol_id"])

    def test_hold_same_word(self):
        rec = codeword_of("u/s7/hold_r_reg[5][12]")
        self.assertEqual(rec["codeword_id"], "s7:arith")
        self.assertEqual(rec["symbol_id"], 5)

    def test_mem_lane(self):
        rec = codeword_of("u/s3/mem1/g_async_distributed.mem_reg_0_63_0_2")
        self.assertEqual(rec["codeword_id"], "s3:secded:mem1")
        self.assertEqual(rec["scheme"], "memory_secded70")

    def test_replica(self):
        rec = codeword_of("u/s8/replicas[2].u/rot2/out_im_reg[11]")
        self.assertEqual(rec["codeword_id"], "s8:tmr")
        self.assertEqual(rec["symbol_id"], 2)

    def test_cfg_stays_proxy(self):
        rec = codeword_of("u/s1/complete_butterflies[0].x", domain="CFG")
        self.assertEqual(rec["confidence"], "proxy")
        self.assertIsNone(rec["codeword_id"])

    def test_mapper_same_codeword_two_symbols(self):
        flipped = [
            {"unit_id": "a", "domain": "FF_STATE", "stage_id": 5,
             "module_role": "butterfly", "codeword_id": "s5:arith",
             "symbol_id": 0, "codeword_confidence": "inferred",
             "site": "S0", "grid_x": 0},
            {"unit_id": "b", "domain": "FF_STATE", "stage_id": 5,
             "module_role": "butterfly", "codeword_id": "s5:arith",
             "symbol_id": 1, "codeword_confidence": "inferred",
             "site": "S1", "grid_x": 1},
        ]
        recs = map_flipped(flipped, strike_id="t")
        self.assertEqual(recs[0]["codeword_id"], recs[1]["codeword_id"])
        self.assertNotEqual(recs[0]["symbol_id"], recs[1]["symbol_id"])
        self.assertEqual(recs[0]["confidence"], "inferred")
        summary = classify_strike_faults(recs)
        self.assertEqual(summary["same_codeword_multi_symbol"], ["s5:arith"])

    def test_site_majority(self):
        maj = majority_codeword([
            "u/s2/complete_butterflies[0].a",
            "u/s2/complete_butterflies[0].b",
            "u/s2/GND",
        ])
        self.assertEqual(maj["codeword_id"], "s2:arith")
        self.assertEqual(maj["symbol_id"], 0)
        self.assertEqual(maj["confidence"], "inferred")
