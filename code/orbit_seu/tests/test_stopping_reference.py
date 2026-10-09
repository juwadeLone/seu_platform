"""Stopping-power anchors, shield transport, the files-mode orbit guard and
an end-to-end check of the XC7VX690T MEO run against Lee 2014 Table 2."""
import copy
import json
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from orbit_seu.stopping import let_si, transport_spectrum  # noqa: E402
from orbit_seu.mission import run  # noqa: E402


def _meo_config():
    with open(os.path.join(ROOT, "orbit_seu", "examples", "xc7vx690t_measured_meo.json"),
              encoding="utf-8") as fh:
        cfg = json.load(fh)
    cfg = copy.deepcopy(cfg)
    files = cfg["environment"]["let_spectra_files"]
    for k, rel in files.items():
        files[k] = os.path.join(ROOT, "orbit_seu", rel)
    cfg["mission"]["sampling"] = {"orbits": 1, "points_per_orbit": 8}
    return cfg


class TestStoppingAnchors(unittest.TestCase):
    def test_min_ionizing_proton(self):
        # ~1.66 MeV cm2/g in Si near beta*gamma ~ 3
        self.assertAlmostEqual(let_si(2000.0, 1) * 1000, 1.66, delta=0.05)

    def test_10mev_proton_vs_pstar(self):
        # NIST PSTAR: 34.7 MeV cm2/g at 10 MeV in Si
        self.assertAlmostEqual(let_si(10.0, 1), 0.0347, delta=0.0347 * 0.05)

    def test_fe_bragg_peak(self):
        peak = max(let_si(0.5 * 1.05 ** k, 26) for k in range(200))
        self.assertGreater(peak, 25.0)
        self.assertLess(peak, 32.0)


class TestTransport(unittest.TestCase):
    @staticmethod
    def f(t):
        return 1e-3 * t ** 0.5 / (1 + (t / 300.0) ** 3.2)

    def setUp(self):
        self.ts = [1.0 * 1.2 ** k for k in range(64)]
        self.fs = [self.f(t) for t in self.ts]

    def test_zero_shield_is_identity(self):
        ts, fs = transport_spectrum(self.ts, self.fs, 26, 0.0)
        self.assertEqual(ts, self.ts)
        self.assertEqual(fs, self.fs)

    def test_shield_removes_low_energy_keeps_high(self):
        ts, fs = transport_spectrum(self.ts, self.fs, 26, 0.686)
        lo = dict(zip(ts, fs))
        # far above the Fe range energy of 0.69 g/cm2 Al: nearly unchanged
        t_hi = min(ts, key=lambda t: abs(t - 5000.0))
        self.assertAlmostEqual(lo[t_hi] / self.f(t_hi), 1.0, delta=0.05)
        # CSDA, no fragmentation: particles are conserved. Everything that
        # exits above 0.5 MeV/n entered above E(R(0.5) + t).
        from orbit_seu.stopping import RangeTable
        rt = RangeTable(26)
        t_min_in = rt.energy_of(rt.range_of(0.5) + 0.686)
        n_out = sum(0.5 * (fs[k] + fs[k + 1]) * (ts[k + 1] - ts[k])
                    for k in range(len(ts) - 1))
        grid = [t_min_in * (self.ts[-1] / t_min_in) ** (k / 3999)
                for k in range(4000)]
        n_in = sum(0.5 * (self.f(grid[k]) + self.f(grid[k + 1]))
                   * (grid[k + 1] - grid[k]) for k in range(len(grid) - 1))
        self.assertAlmostEqual(n_out / n_in, 1.0, delta=0.03)


class TestFilesOrbitGuard(unittest.TestCase):
    def test_other_orbit_is_refused(self):
        cfg = _meo_config()
        cfg["orbit"]["altitude_km"] = 550
        cfg["orbit"]["inclination_deg"] = 97.6
        with self.assertRaises(ValueError) as cm:
            run(cfg)
        self.assertIn("SPENVIS", str(cm.exception))

    def test_source_orbit_runs(self):
        res = run(_meo_config())
        self.assertTrue(res["spectra_manifests"])


class TestLee2014Reference(unittest.TestCase):
    """Same Weibull, same 100 mil Al: the MEO 20200 km / 55 deg per-bit
    rates must land near Lee 2014 Table 2 (GEO, solar min, CREME96). MEO
    sits slightly below GEO (weak geomagnetic shielding). A 1e4 sigma unit
    slip or the old K*Z^2/beta^2 LET map fails this by orders of magnitude."""

    LEE_GEO_SOLMIN = {"CRAM": 1.0e-7, "BRAM": 5.2e-7, "FF": 9.0e-8}

    def test_per_bit_rates_near_lee_table2(self):
        res = run(_meo_config())
        for dom, ref in self.LEE_GEO_SOLMIN.items():
            got = res["per_domain"][dom]["rate_per_day_per_bit"]
            self.assertGreater(got / ref, 0.5, dom)
            self.assertLess(got / ref, 1.5, dom)

    def test_species_breakdown_sums_to_device(self):
        res = run(_meo_config())
        r = res["rates_per_s"]
        self.assertAlmostEqual(sum(r["per_species"].values()),
                               r["total_per_bit"],
                               delta=r["total_per_bit"] * 1e-9)


if __name__ == "__main__":
    unittest.main()
