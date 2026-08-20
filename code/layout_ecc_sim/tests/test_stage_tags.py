"""hier_cell tag parser tests — handbook 2.2 samples plus P1 RTL names."""
import os
import unittest

from layout_ecc.stage_tags import majority_site, report_csv, tag

_CSV = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "data", "layout", "p1_ooc_win",
    "primitive_map.csv"))


class TestHandbookExamples(unittest.TestCase):
    def test_stage1_gnd_is_unknown_role(self):
        st, role, rep = tag("u/s1/GND")
        self.assertEqual(st, 1)
        self.assertEqual(role, "unknown")
        self.assertIsNone(rep)

    def test_stage1_syndrome(self):
        st, role, _ = tag("u/s1/sy0r[11]_i_7")
        self.assertEqual((st, role), (1, "ecc"))

    def test_nested_pipe_rot_is_twiddle_not_butterfly(self):
        st, role, _ = tag(
            "u/s5/complete_butterflies[3].pipe_rot.rotate/out_re[31]_i_8__1")
        self.assertEqual((st, role), (5, "twiddle"))

    def test_hold_is_control(self):
        st, role, _ = tag("u/s7/hold_r_reg[5][12]")
        self.assertEqual((st, role), (7, "control"))

    def test_replica_rot2_is_twiddle_with_replica_id(self):
        st, role, rep = tag("u/s8/replicas[0].u/rot2/out_im_reg[11]")
        self.assertEqual((st, role, rep), (8, "twiddle", 0))

    def test_mem_async_is_delay(self):
        st, role, _ = tag(
            "u/s3/mem1/g_async_distributed.mem_reg_0_63_0_2")
        self.assertEqual((st, role), (3, "delay"))

    def test_residual_is_ecc(self):
        st, role, _ = tag("u/s2/res1r[15]_i_5")
        self.assertEqual((st, role), (2, "ecc"))

    def test_no_stage_prefix(self):
        st, role, _ = tag("toplevel/foo")
        self.assertEqual((st, role), (-1, "unknown"))


class TestSiteMajority(unittest.TestCase):
    def test_shared_two_stages(self):
        maj = majority_site(["u/s3/mem0/x", "u/s3/mem0/y", "u/s4/mem0/z"])
        self.assertTrue(maj["is_shared"])
        self.assertEqual(maj["stage_id"], 3)
        self.assertEqual(maj["stages"], [3, 4])


@unittest.skipUnless(os.path.isfile(_CSV), "P1 CSV missing")
class TestUnknownBudget(unittest.TestCase):
    def test_unknown_role_under_5_percent(self):
        rep = report_csv(_CSV)
        self.assertLess(rep["unknown_role_frac"], 0.05)
        self.assertEqual(rep["n_unknown_stage"], 0)
        for s in range(1, 11):
            self.assertIn(s, rep["by_stage"])
            self.assertGreater(rep["by_stage"][s], 1000)
