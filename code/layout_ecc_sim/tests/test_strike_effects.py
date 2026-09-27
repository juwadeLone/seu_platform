"""Design-agnostic modules and per-strike effect classification."""
import unittest

from layout_ecc.modules import build_modules, pick_depth
from layout_ecc.strike_effects import SEL_ONSET_LET, classify, multi_share


class TestModules(unittest.TestCase):
    def test_depth_skips_single_wrapper(self):
        hiers = ["top/core/a/x", "top/core/b/y", "top/core/c/z"]
        self.assertEqual(pick_depth(hiers), 3)

    def test_p1_like_hierarchy_splits_by_instance(self):
        hiers = [f"u/s{k}/m/r{j}" for k in range(1, 11) for j in range(3)]
        self.assertEqual(pick_depth(hiers), 2)
        site_mod, mods = build_modules({"A": ["u/s2/x", "u/s2/y", "u/s10/z"],
                                        "B": ["u/s10/q"]}, 2)
        self.assertEqual(site_mod, {"A": "u/s2", "B": "u/s10"})
        self.assertEqual([m["name"] for m in mods], ["s2", "s10"])   # natural order


def _strike(flipped=(), cands=()):
    return {"flipped": list(flipped), "candidates": list(cands)}


class TestClassify(unittest.TestCase):
    def test_no_hit(self):
        e = classify(_strike(), 5)
        st = {x["id"]: x["status"] for x in e["effects"]}
        self.assertEqual(st["seu"], "none")
        self.assertEqual(st["set"], "none")
        self.assertEqual(st["sel"], "none")
        self.assertEqual(st["sefi"], "unmodeled")

    def test_single_cram_flip(self):
        c = {"unit_id": "s1", "domain": "CFG", "n_bits": 1, "res_type": "SLICE", "module": "u/s3"}
        e = classify(_strike([c], [c]), 30)
        st = {x["id"]: x["status"] for x in e["effects"]}
        self.assertEqual(st["seu"], "occurred")
        self.assertEqual(st["mcu"], "none")
        self.assertEqual(st["set"], "possible")
        self.assertEqual(e["consequences"][0]["recovery"], "scrub")
        self.assertEqual(e["modules_hit"], [{"module": "u/s3", "bits": 1}])

    def test_mcu_and_sel_threshold(self):
        fl = [{"unit_id": "s1", "domain": "CFG", "n_bits": 2, "res_type": "SLICE"},
              {"unit_id": "s2", "domain": "BRAM_STATE", "n_bits": 1, "res_type": "BRAM"}]
        e = classify(_strike(fl, fl), SEL_ONSET_LET)
        st = {x["id"]: x["status"] for x in e["effects"]}
        self.assertEqual(st["mcu"], "occurred")
        self.assertEqual(st["sel"], "risk")
        self.assertEqual(e["bits"], 3)
        self.assertEqual({c["recovery"] for c in e["consequences"]}, {"scrub", "ecc"})
        self.assertEqual(classify(_strike(), SEL_ONSET_LET - 0.1)["effects"][4]["status"], "none")

    def test_lee_table3_lookup(self):
        self.assertEqual(multi_share(50), (49.3, 0.486))
        self.assertEqual(multi_share(1.0), (1.5, 0.068))


if __name__ == "__main__":
    unittest.main()
