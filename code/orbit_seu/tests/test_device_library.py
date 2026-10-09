"""Device library + user layout upload tests."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "layout_ecc_sim"))

from orbit_seu.device import list_devices, resolve_device
from orbit_seu import mission as mission_mod

PRIM_CSV = (
    "unit_id,hier_cell,ref_name,loc,bel,site,tile,grid_x,grid_y\n"
    "0,u/s1/FF,FDRE,SLICE_X5Y7,AFF,SLICE_X5Y7,CLB_X5Y7,5,7\n"
    "1,u/s1/FF2,FDRE,SLICE_X6Y8,BFF,SLICE_X6Y8,CLB_X6Y8,6,8\n"
)


class TestLibrary(unittest.TestCase):
    def test_list_devices_has_three(self):
        devs = list_devices()
        self.assertIn("xc7vx690t", devs)
        self.assertIn("xc7k325t", devs)
        self.assertIn("xc7z045", devs)
        self.assertTrue(devs["xc7k325t"]["provenance"])
        self.assertEqual(devs["xc7k325t"]["role"], "native_dut")

    def test_load_and_resolve(self):
        spec = resolve_device({"library": "xc7k325t"})
        self.assertEqual(spec["_library"]["id"], "xc7k325t")
        self.assertGreater(spec["bits"], 0)
        self.assertIn("heavy_ion_weibull_by_domain", spec)

    def test_override_wins(self):
        spec = resolve_device({"library": "xc7k325t", "bits": 123})
        self.assertEqual(spec["bits"], 123)

    def test_no_library_passthrough(self):
        spec = resolve_device({"bits": 5, "weibull": {}})
        self.assertNotIn("_library", spec)

    def test_mission_library_entry(self):
        cfg = {
            "mission": {"duration_years": 0.01,
                        "sampling": {"orbits": 2, "points_per_orbit": 8}},
            "orbit": {"altitude_km": 420, "inclination_deg": 51.6,
                      "eccentricity": 0.001},
            "magnetosphere": {"cutoff_eq_gv": 14.9},
            "environment": {"type": "demo_gcr", "phi_mv": 300},
            "device": {"library": "xc7k325t"},
        }
        res = mission_mod.run(cfg)
        self.assertEqual(res["device"]["library"]["id"], "xc7k325t")
        self.assertEqual(res["device"]["bits"], 84727696)

    def test_unknown_library_raises(self):
        with self.assertRaises((KeyError, FileNotFoundError)):
            resolve_device({"library": "nope999"})


class TestLayoutUpload(unittest.TestCase):
    def test_register_and_resolve(self):
        from layout_ecc import gui
        lid, state = gui.register_layout(PRIM_CSV, "user_test")
        self.assertTrue(lid)
        st = gui.layout_for_id(lid)
        self.assertIsNotNone(st["layout"])
        self.assertNotEqual(st["layout"]["design"], gui._LAYOUT.get("design"))

    def test_default_bundled(self):
        from layout_ecc import gui
        st = gui.layout_for_id(None)
        self.assertEqual(st["layout"].get("design"), gui._LAYOUT.get("design"))

    def test_strike_with_layout_id(self):
        from layout_ecc import gui
        lid, _ = gui.register_layout(PRIM_CSV, "user_strike")
        self.assertIsNotNone(gui.layout_for_id(lid))
        self.assertNotEqual(lid, "bundled")


if __name__ == "__main__":
    unittest.main()
