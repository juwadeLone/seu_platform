"""Tile -> frame bbox tests."""
import unittest

from layout_ecc.a7_frame_map import (
    bbox_of_row, frame_in_bbox, infer_clock_region, parse_tile, tile_class,
)


class TestParse(unittest.TestCase):
    def test_clb_tile(self):
        self.assertEqual(parse_tile("CLBLL_L_X6Y50"), ("CLBLL_L", 6, 50))
        self.assertEqual(tile_class("CLBLL_L"), "CLB")

    def test_bram_dsp(self):
        self.assertEqual(tile_class("BRAM_L"), "BRAM")
        self.assertEqual(tile_class("DSP_R"), "DSP")

    def test_clock_region_from_y(self):
        self.assertEqual(infer_clock_region("CLBLL_L_X6Y10"), "X0Y0")
        self.assertEqual(infer_clock_region("CLBLL_L_X6Y50"), "X0Y1")
        self.assertEqual(
            infer_clock_region("CLBLL_L_X6Y10", clock_region="X1Y0"), "X1Y0")


class TestBbox(unittest.TestCase):
    def test_without_table_has_id_no_frames(self):
        b = bbox_of_row({"tile": "CLBLM_R_X12Y51", "site": "SLICE_X18Y51"})
        self.assertEqual(b["clock_region"], "X0Y1")
        self.assertEqual(b["tile_class"], "CLB")
        self.assertIsNone(b["frame_lo"])
        self.assertIn("X0Y1|CLB|COL12", b["frame_bbox_id"])
        self.assertEqual(b["frame_source"], "clock_region_column")

    def test_with_table(self):
        table = {
            "index": {("X0Y1", "CLB", 12): (100, 135)},
            "source": "unit-test",
        }
        b = bbox_of_row({"tile": "CLBLM_R_X12Y51"}, frame_table=table)
        self.assertEqual((b["frame_lo"], b["frame_hi"]), (100, 135))
        self.assertTrue(frame_in_bbox(120, b))
        self.assertFalse(frame_in_bbox(99, b))
        self.assertFalse(frame_in_bbox(120, {**b, "frame_lo": None}))


if __name__ == "__main__":
    unittest.main()
