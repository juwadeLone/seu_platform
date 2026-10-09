"""v1.2.0 effects coverage table: ids present, no invented TID/SEL numbers."""
import json
import os
import unittest

# out_vx690t_measured/results.json, 2026-09-26 run (corrected chain)
FROZEN_DEVICE_PER_DAY = 46.160314073644855

from layout_ecc.effects_coverage import (
    build_effects_payload,
    load_table,
    required_effect_ids,
    scan_tid_slot,
)

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
_JSON = os.path.join(_ROOT, "layout_ecc", "data", "effects_coverage.json")

# Keys that would mean we invented a mission rate / dose for effects we do not have.
_INVENTED_RATE_KEYS = (
    "dose_krad", "dose_rad", "tid_krad", "tid_rate",
    "sel_rate", "seb_rate", "segr_rate", "tnid_rate",
    "rate", "rate_per_day", "value", "krad",
)


class TestEffectsCoverageTable(unittest.TestCase):
    def setUp(self):
        with open(_JSON, "r", encoding="utf-8") as fh:
            self.table = json.load(fh)

    def test_every_effect_has_short_brief(self):
        for e in self.table["effects"]:
            self.assertIn("brief", e)
            self.assertLessEqual(len(e["brief"]), 18, e["id"])

    def test_utf8_and_version(self):
        self.assertEqual(self.table.get("version"), "1.2.0")
        self.assertTrue(os.path.isfile(_JSON))
        ids = [e["id"] for e in self.table["effects"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_required_ids_present(self):
        have = {e["id"] for e in self.table["effects"]}
        missing = set(required_effect_ids()) - have
        self.assertFalse(missing, f"missing effect ids: {sorted(missing)}")

    def test_status_mapping(self):
        by = {e["id"]: e for e in self.table["effects"]}
        self.assertEqual(by["seu_hi"]["status"], "simulating")
        self.assertEqual(by["mbu"]["status"], "simulating")
        self.assertEqual(by["seu_dsp"]["status"], "data_missing")
        self.assertEqual(by["seu_proton"]["status"], "data_missing")
        self.assertEqual(by["tid"]["status"], "data_missing")
        self.assertEqual(by["sel"]["status"], "data_missing")   # 有实测起始 LET，缺截面
        for eid in ("tnid", "set", "sefi", "seb", "segr"):
            self.assertEqual(by[eid]["status"], "out_of_scope", eid)

    def test_tid_status_data_missing_unless_real_file(self):
        by = {e["id"]: e for e in self.table["effects"]}
        slot = scan_tid_slot()
        if slot["status"] == "MISSING":
            self.assertEqual(by["tid"]["status"], "data_missing")
        else:
            # A real dose file was dropped; still must not invent a number
            # in the static table of record.
            self.assertIsNone(by["tid"].get("source") or None)

    def test_no_numeric_tid_sel_invented_in_table(self):
        for e in self.table["effects"]:
            if e["id"] not in ("tid", "tnid", "sel", "seb", "segr", "set", "sefi"):
                continue
            for k in _INVENTED_RATE_KEYS:
                self.assertNotIn(k, e, f"{e['id']} has invented key {k}")
            self.assertIsNone(e.get("source") if e["id"] in ("tnid", "seb", "segr", "set", "sefi") else e.get("dose_krad"))

    def test_sel_onset_only_no_rate(self):
        sel = next(e for e in self.table["effects"] if e["id"] == "sel")
        self.assertEqual(sel["status"], "data_missing")
        self.assertIn("Lee", sel["source"])
        blob = json.dumps(sel)
        self.assertNotRegex(blob, r"\d+\.\d+e-")
        self.assertNotIn("krad", blob.lower())

    def test_frozen_seu_is_sourced_not_blank(self):
        snap = self.table["frozen_seu_hi"]
        self.assertAlmostEqual(snap["device_events_per_day"], FROZEN_DEVICE_PER_DAY, places=12)
        self.assertIn("out_vx690t_measured", snap["source"])
        # proton must not be mixed into the freeze number
        self.assertIn("质子", snap["note"])

    def test_proton_anchors_match_wirthlin_file(self):
        facts = self.table["proton_anchored_facts"]
        self.assertAlmostEqual(facts["CRAM"]["sigma_cm2_per_bit"], 8.29e-15)
        self.assertAlmostEqual(facts["BRAM"]["sigma_cm2_per_bit"], 8.19e-15)
        self.assertIsNone(facts["FF"])
        self.assertIsNone(facts["DSP"])
        proton_path = os.path.join(_ROOT, "layout_ecc", "data", "proton_7series_sigma_E.json")
        with open(proton_path, "r", encoding="utf-8") as fh:
            proton = json.load(fh)
        cram = proton["per_domain"]["CRAM"]["sigma_cm2_per_bit_vs_E"][0]
        self.assertEqual(cram["sigma_cm2_per_bit"], facts["CRAM"]["sigma_cm2_per_bit"])


class TestEffectsPayload(unittest.TestCase):
    def test_payload_seu_hi_simulating_tid_missing(self):
        payload = build_effects_payload()
        by = {e["id"]: e for e in payload["effects"]}
        self.assertEqual(by["seu_hi"]["status"], "simulating")
        self.assertEqual(by["tid"]["status"], "data_missing")
        self.assertEqual(payload["tid_slot"]["status"], "MISSING")
        self.assertFalse(payload["seu_hi_snapshot"].get("_spectrum_recomputed"))
        self.assertAlmostEqual(
            payload["seu_hi_snapshot"]["device_events_per_day"],
            FROZEN_DEVICE_PER_DAY, places=12)

    def test_load_table_roundtrip(self):
        t = load_table()
        self.assertEqual(t["version"], "1.2.0")
        self.assertEqual(len(t["effects"]), 11)
