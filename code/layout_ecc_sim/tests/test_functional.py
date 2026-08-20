"""WP2 functional wrapper tests — known injection → known outcome."""
import unittest

from layout_ecc.functional import ensure_golden, inject_and_classify


class TestGolden(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.golden = ensure_golden()

    def test_zero_fault_matches_stored_output(self):
        self.assertTrue(self.golden["sha256"])
        self.assertEqual(len(self.golden["result"].output), 1024)


class TestKnownOutcomes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.golden = ensure_golden()

    def test_single_arithmetic_bit_corrected(self):
        out = inject_and_classify(
            {"stage_id": 1, "module_role": "butterfly", "domain": "FF_STATE",
             "bit": 0, "symbol": 0},
            golden=self.golden,
        )
        self.assertEqual(out["outcome"], "CORRECTED")
        self.assertTrue(out["detected"] and out["corrected"] and out["match"])

    def test_tmr_one_replica_masked(self):
        out = inject_and_classify(
            {"stage_id": 8, "module_role": "replica", "domain": "FF_STATE",
             "bit": 0, "replica": 0},
            golden=self.golden,
        )
        self.assertEqual(out["outcome"], "MASKED")

    def test_two_symbol_arithmetic_due(self):
        out = inject_and_classify(
            {"stage_id": 4, "module_role": "ecc", "domain": "FF_STATE",
             "bit": 3, "symbol": 0, "n_faults": 2},
            golden=self.golden,
        )
        self.assertEqual(out["outcome"], "DUE")

    def test_open_loop_is_sdc(self):
        out = inject_and_classify(
            {"stage_id": 10, "module_role": "butterfly", "domain": "FF_STATE",
             "bit": 0, "protection": "off"},
            golden=self.golden,
        )
        self.assertEqual(out["outcome"], "SDC")
        self.assertGreater(out["max_output_deviation"], 0)
