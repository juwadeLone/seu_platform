"""WP6 lifetime mapping from P1 SDF depths."""
import unittest

from layout_ecc.functional import inject_and_classify
from layout_ecc.lifetime import (
    STAGE_DEPTH, delay_table, map_cycle, masked_by_lifetime,
)


class TestLifetime(unittest.TestCase):
    def test_depth_table_matches_rtl(self):
        self.assertEqual(STAGE_DEPTH[1], 128)
        self.assertEqual(STAGE_DEPTH[7], 2)
        self.assertEqual(STAGE_DEPTH[10], 2)
        t = delay_table()
        self.assertIn("top_p1_kernel.sv", t["source"])

    def test_stage1_cycle0_is_frame0_sample(self):
        ident = map_cycle(1, 0, address=0, lane=0)
        self.assertEqual(ident["frame"], 0)
        self.assertEqual(ident["sample"], 0)
        self.assertEqual(ident["depth"], 128)
        life = masked_by_lifetime(ident, role="delay")
        self.assertEqual(life["lifetime_class"], "OBSERVED")

    def test_just_written_will_be_read(self):
        ident = map_cycle(3, 10, address=0, lane=1)
        self.assertEqual(ident["lane"], 1)
        self.assertGreater(ident["cycles_until_read"], 0)
        self.assertEqual(masked_by_lifetime(ident, "delay")["lifetime_class"],
                         "OBSERVED")

    def test_overwrite_before_read_is_masked(self):
        ident = {
            "cycles_until_read": 8, "cycles_until_overwrite": 1, "depth": 32,
        }
        life = masked_by_lifetime(ident, role="delay")
        self.assertEqual(life["lifetime_class"], "MASKED")

    def test_tmr_register_observed_next_cycle(self):
        ident = map_cycle(8, 5, lane=2)
        self.assertEqual(ident["depth"], 1)
        self.assertEqual(masked_by_lifetime(ident, "replica")["lifetime_class"],
                         "OBSERVED")

    def test_inject_records_frame_sample(self):
        out = inject_and_classify(
            {"stage_id": 1, "module_role": "butterfly", "domain": "FF_STATE",
             "bit": 0, "symbol": 0, "cycle": 0, "lane": 0},
        )
        self.assertIn("frame", out)
        self.assertIn("sample", out)
        self.assertEqual(out["lifetime_class"], "OBSERVED")
        self.assertEqual(out["outcome"], "CORRECTED")
