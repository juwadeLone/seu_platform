"""The frozen N_SEU replayed by /api/effects must equal a live orbit_seu run
on the same config. Skipped when the orbit_seu tree is not on this machine."""
import json
import os
import sys
import unittest

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _ROOT)

from layout_ecc import orbit_env  # noqa: E402

try:
    orbit_env._roots()
    _HAVE_OSEU = True
except FileNotFoundError:
    _HAVE_OSEU = False


@unittest.skipUnless(_HAVE_OSEU, "orbit_seu tree not available")
class TestFrozenMatchesLiveRun(unittest.TestCase):
    def test_device_and_domain_rates(self):
        live = orbit_env.compute_orbit_payload()
        frozen = live["_frozen_baseline"]
        got = live["rates_per_s"]["total_per_device"] * 86400.0
        self.assertAlmostEqual(got / frozen["device_events_per_day"], 1.0,
                               delta=1e-9)
        for dom, r in frozen["per_domain_rates_day_per_bit"].items():
            self.assertAlmostEqual(
                live["per_domain"][dom]["rate_per_day_per_bit"] / r, 1.0,
                delta=1e-9)

    def test_effects_table_matches_orbit_env(self):
        with open(os.path.join(_ROOT, "layout_ecc", "data", "effects_coverage.json"),
                  encoding="utf-8") as fh:
            table = json.load(fh)
        frozen = orbit_env.compute_orbit_payload()["_frozen_baseline"]
        self.assertEqual(table["frozen_seu_hi"]["device_events_per_day"],
                         frozen["device_events_per_day"])


if __name__ == "__main__":
    unittest.main()
