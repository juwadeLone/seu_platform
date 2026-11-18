import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from layout_ecc import campaign


class CampaignTest(unittest.TestCase):
    def test_default_campaign_repeats_and_retains_multibit_and_miss(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            first = campaign.run_campaign(campaign._DEFAULT_SCENARIO, out / "first")
            second = campaign.run_campaign(campaign._DEFAULT_SCENARIO, out / "second")
            self.assertEqual(first, second)
            names = ("events.jsonl", "run_manifest.json")
            for name in names:
                self.assertEqual((out / "first" / name).read_bytes(),
                                 (out / "second" / name).read_bytes())
            data = (out / "first" / "events.jsonl").read_bytes()
            events = [json.loads(line) for line in data.splitlines()]
            self.assertEqual(first["events"]["sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual([e["event_id"] for e in events], ["clb/1", "clb/2", "miss/1"])
            self.assertEqual([e["seed"] for e in events], [1, 2, 1])
            self.assertEqual(events[0]["n_bits_flipped"], 3)
            self.assertEqual(events[0]["flipped"][0]["n_bits"], 3)
            self.assertEqual(events[-1]["n_candidates"], 0)
            self.assertEqual(events[-1]["flipped"], [])
            self.assertEqual(first["counts"]["events"], 3)
            self.assertEqual(first["counts"]["no_candidates"], 1)
            self.assertEqual(first["orbit"]["source"], "frozen_snapshot")
            self.assertAlmostEqual(first["orbit"]["rates"]["device_bit_upsets_per_day"],
                                   46.160314073644855)
            self.assertIn("golden_vector", first["inputs"])
            self.assertNotIn(tmp, (out / "first" / "run_manifest.json").read_text("utf-8"))

    def test_duplicate_seeds_are_rejected(self):
        case = dict(id="clb", x0=1, y0=2, a0=1, let=60, theta_deg=45, phi_deg=30, seeds=[1, 1])
        with patch.object(campaign, "g4_presets", return_value={}):
            with self.assertRaisesRegex(ValueError, "seeds must be unique"):
                list(campaign._cases({"cases": [case]}, {}))

    def test_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            path.write_text("keep", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                campaign.run_campaign(campaign._DEFAULT_SCENARIO, tmp)
            self.assertEqual(path.read_text("utf-8"), "keep")

    def test_live_mode_requires_explicit_upstream(self):
        env = dict(os.environ)
        env.pop("ORBIT_SEU_ROOT", None)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "run"
            cmd = [sys.executable, "-m", "layout_ecc.campaign", "--live-orbit", "--out", str(out)]
            proc = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("requires ORBIT_SEU_ROOT", proc.stderr)
            self.assertFalse(out.exists())

    def test_live_mode_rejects_wrong_or_modified_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp) / "orbit_seu"
            package.mkdir()
            (package / "mission.py").touch()
            rev = campaign._ORBIT_REV.read_text("ascii").strip()
            with patch.dict(os.environ, ORBIT_SEU_ROOT=tmp):
                for actual, dirty in [("0" * 40, ""), (rev, " M orbit_seu/mission.py")]:
                    with self.subTest(actual=actual, dirty=dirty):
                        with patch.object(campaign, "_git", side_effect=[actual, dirty]):
                            with self.assertRaisesRegex(ValueError, "requires clean .*" + rev):
                                campaign._orbit_snapshot(live=True)
