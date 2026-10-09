"""Tests for the real-environment modules (gcr_bo, ae9ap9).

Coefficient-dependent tests use a clearly-labeled TEST fixture (not flight
data); the loader error path is verified for the missing-file case.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from orbit_seu.gcr_bo import (load_lis_coefficients, lis_rigidity,
                              modulated_spectrum, let_spectra_from_gcr,
                              LisCoefficientError)
from orbit_seu.ae9ap9 import write_ephemeris, parse_flux_file, Ae9Ap9Error
from orbit_seu.orbit import OrbitElements

FIXTURE = os.path.join(os.path.dirname(__file__), "fixture_lis.csv")


class TestLisLoader(unittest.TestCase):
    def test_missing_file_raises_with_hint(self):
        with self.assertRaises(LisCoefficientError) as cm:
            load_lis_coefficients("nope/missing.csv")
        self.assertIn("README", str(cm.exception))

    def test_fixture_loads(self):
        coefs = load_lis_coefficients(FIXTURE)
        self.assertIn(1, coefs)
        self.assertIn(26, coefs)


class TestBoPhysics(unittest.TestCase):
    """Uses TEST fixture coefficients (placeholder numbers, clearly labeled)."""

    def setUp(self):
        self.coefs = load_lis_coefficients(FIXTURE)

    def test_lis_monotone_decreasing(self):
        c = self.coefs[26]
        vals = [lis_rigidity(c, r) for r in (1.0, 2.0, 5.0, 10.0, 100.0)]
        self.assertTrue(all(vals[i] > vals[i + 1] for i in range(len(vals) - 1)))

    def test_modulation_reduces_flux(self):
        c = dict(self.coefs[1])
        ts, j_low = modulated_spectrum(c, 400.0)
        _, j_high = modulated_spectrum(c, 1200.0)
        # higher solar activity (larger phi) -> stronger modulation -> less flux
        self.assertGreater(j_low[5], j_high[5])

    def test_let_spectra_transmitted(self):
        specs = let_spectra_from_gcr(self.coefs, 600.0, 0.0)
        self.assertIn("H", specs)
        self.assertIn("Fe", specs)
        for sp in specs.values():
            self.assertGreater(sp.total_flux(), 0.0)
        cut = let_spectra_from_gcr(self.coefs, 600.0, 10.0)
        self.assertLess(cut["Fe"].total_flux(), specs["Fe"].total_flux())


class TestAe9Ap9(unittest.TestCase):
    def test_ephemeris_written(self):
        orbit = OrbitElements(550, 51.6, 0.001)
        path = write_ephemeris(orbit, os.path.join(
            os.path.dirname(__file__), "fixture_ephem.txt"), n_points=9)
        lines = open(path).read().strip().splitlines()
        self.assertEqual(len(lines), 9)
        parts = lines[0].split()
        self.assertEqual(len(parts), 6)     # YYYY DDD HHMMSS lat lon alt
        float(parts[3]); float(parts[4]); float(parts[5])
        os.remove(path)

    def test_parse_layout_a(self):
        path = os.path.join(os.path.dirname(__file__), "fixture_flux_a.txt")
        with open(path, "w") as fh:
            fh.write("# test fixture layout A\n10 1e4\n30 3e3\n100 5e2\n")
        sp = parse_flux_file(path)
        self.assertAlmostEqual(sp.total_flux(), 0.5 * ((1e4 + 3e3) * 20 +
                                                       (3e3 + 5e2) * 70))
        os.remove(path)

    def test_parse_layout_b_time_major(self):
        path = os.path.join(os.path.dirname(__file__), "fixture_flux_b.txt")
        with open(path, "w") as fh:
            fh.write("0 10 30 100\n")       # header: time + 3 energies
            fh.write("1 2 4 8\n")           # two epochs -> averaged
            fh.write("2 4 6 10\n")
        sp = parse_flux_file(path)
        self.assertEqual(len(sp.xs), 3)
        rows = dict(sp.as_rows())
        self.assertAlmostEqual(rows[10], 3.0)   # avg(2,4)
        self.assertAlmostEqual(rows[30], 5.0)   # avg(4,6)
        os.remove(path)


if __name__ == "__main__":
    unittest.main()
