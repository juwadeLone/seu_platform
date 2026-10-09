"""Per-domain proton sigma(E) chain: AnchorSigma bound-mode, TableSigma,
proton_file + heavy_ion_weibull_by_domain integration through mission.run.

All spectra below are tiny SYNTHETIC test fixtures — never shipped as
environment data.
"""
import json
import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from orbit_seu.device import (AnchorSigma, TableSigma, DomainWeibull,
                              build_proton_sigma)
from orbit_seu.rates import proton_rate_per_s
from orbit_seu.spectra import Spectrum
from orbit_seu.mission import run as mission_run
from orbit_seu.spenvis_import import (convert_gcf, read_spenvis_gcf,
                                      parse_header, GROUPS, NSP)


class TestAnchorSigma(unittest.TestCase):
    def test_step_behavior(self):
        a = AnchorSigma(180.0, 8.29e-15)
        self.assertEqual(a.sigma(50.0), 0.0)
        self.assertEqual(a.sigma(180.0), 8.29e-15)
        self.assertEqual(a.sigma(500.0), 8.29e-15)

    def test_is_lower_bound_vs_rising_table(self):
        # a real sigma(E) rises above the anchor; the anchor bound must
        # under-count any spectrum with flux there
        anchor = AnchorSigma(100.0, 1e-12)
        table = TableSigma([50, 100, 500], [5e-13, 1e-12, 3e-12])
        spec = Spectrum([10, 100, 300, 700], [1e-3, 1e-3, 1e-3, 1e-3])
        self.assertLess(proton_rate_per_s(spec, anchor),
                        proton_rate_per_s(spec, table))

    def test_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            AnchorSigma(0.0, 1e-12)
        with self.assertRaises(ValueError):
            AnchorSigma(100.0, -1e-12)


class TestBuildProtonSigma(unittest.TestCase):
    def test_anchor_shape(self):
        m, mode, meta = build_proton_sigma(
            {"anchor_E_mev": 180.0, "sigma_cm2_per_bit": 8.29e-15,
             "source": "test"})
        self.assertIsInstance(m, AnchorSigma)
        self.assertEqual(mode, "lower_bound")
        self.assertEqual(meta["source"], "test")

    def test_inline_table(self):
        m, mode, _ = build_proton_sigma({"table": [[10, 1e-12], [100, 2e-12]]})
        self.assertIsInstance(m, TableSigma)
        self.assertEqual(mode, "table")

    def test_file_shape(self):
        with tempfile.NamedTemporaryFile(
                "w", suffix=".txt", delete=False) as fh:
            fh.write("# comment\n10 1e-12\n100 2e-12\n")
            path = fh.name
        try:
            m, mode, meta = build_proton_sigma({"file": path})
            self.assertIsInstance(m, TableSigma)
            self.assertEqual(meta["file"], path)
        finally:
            os.unlink(path)

    def test_empty_and_bad(self):
        self.assertEqual(build_proton_sigma(None), (None, None, None))
        with self.assertRaises(ValueError):
            build_proton_sigma({"nonsense": 1})


def _iss_cfg(proton_path):
    return {
        "mission": {"duration_years": 1.0,
                    "sampling": {"orbits": 8, "points_per_orbit": 48}},
        "orbit": {"altitude_km": 420, "inclination_deg": 51.6,
                  "eccentricity": 0.001},
        "magnetosphere": {"cutoff_eq_gv": 14.9},
        "environment": {"type": "files",
                        "proton_file": proton_path,
                        "proton_columns": {"energy": 0, "diff_flux": 1}},
        "device": {
            "name": "XC7VX690T", "bits": 284934976,
            "heavy_ion_weibull_by_domain": {
                "CRAM": {"let_threshold": 0.4, "width": 338.5, "shape": 0.852,
                         "sigma_sat_cm2_per_bit": 3.34e-08,
                         "bits": 229878496,
                         "proton_sigma": {"anchor_E_mev": 180.0,
                                          "sigma_cm2_per_bit": 8.29e-15}},
                "BRAM": {"let_threshold": 0.1, "width": 87.5, "shape": 0.893,
                         "sigma_sat_cm2_per_bit": 3.82e-08,
                         "bits": 54190080,
                         "proton_sigma": {"anchor_E_mev": 180.0,
                                          "sigma_cm2_per_bit": 8.19e-15}},
                "FF": {"let_threshold": 1.1, "width": 271.3, "shape": 1.090,
                       "sigma_sat_cm2_per_bit": 1.47e-07,
                       "bits": 866400},
            }},
    }


class TestDomainProtonMission(unittest.TestCase):
    """ISS orbit + synthetic trapped-proton spectrum + Wirthlin anchors."""

    def _proton_file(self, tmp):
        # flat-ish spectrum: no flux below the 180 MeV anchor contributes
        path = os.path.join(tmp, "proton.txt")
        with open(path, "w") as fh:
            fh.write("# synthetic test spectrum (NOT environment data)\n")
            fh.write("1.0   1.0\n10.0  1.0\n50.0  1.0\n"
                     "100.0 1.0\n200.0 0.8\n400.0 0.4\n1000.0 0.1\n")
        return path

    def test_domain_proton_rates_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            res = mission_run(_iss_cfg(self._proton_file(tmp)))
        dom = res["per_domain"]
        # anchored domains carry a nonzero lower-bound proton rate
        for name in ("CRAM", "BRAM"):
            self.assertGreater(dom[name]["proton_rate_per_s_per_bit"], 0.0)
            self.assertEqual(dom[name]["proton_mode"], "lower_bound")
        # FF has no measured proton sigma -> contributes zero, flagged
        self.assertEqual(dom["FF"]["proton_rate_per_s_per_bit"], 0.0)
        # totals add up: device rate includes proton part
        self.assertGreater(res["rates_per_s"]["proton_total"], 0.0)
        self.assertEqual(
            res["rates_per_s"]["total_per_bit"],
            res["rates_per_s"]["heavy_ion_total"]
            + res["rates_per_s"]["proton_total"])
        # hand check: proton_dev/day = sum bits_d * rate_d
        expect = (229878496 * dom["CRAM"]["proton_rate_per_day_per_bit"]
                  + 54190080 * dom["BRAM"]["proton_rate_per_day_per_bit"])
        self.assertAlmostEqual(
            sum(d["proton_rate_per_day"] for d in dom.values()), expect)

    def test_bound_uses_only_flux_above_anchor(self):
        # spectrum entirely below 180 MeV -> zero proton rate
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "low.txt")
            with open(path, "w") as fh:
                fh.write("1.0 1.0\n50.0 1.0\n100.0 1.0\n150.0 1.0\n")
            res = mission_run(_iss_cfg(path))
        self.assertEqual(res["rates_per_s"]["proton_total"], 0.0)


def _tiny_gcf(path):
    """Minimal-but-valid SPENVIS GCF: header + SPECIES marker + 2 data rows
    of (E, 92xIFlux, 92xDFlux)."""
    with open(path, "w", encoding="ascii") as fh:
        fh.write("'ORB_APO',  1, 4.200000E+02,'km'\n")
        fh.write("'ORB_PER',  1, 4.200000E+02,'km'\n")
        fh.write("'ORB_INC',  1, 5.160000E+01,'deg'\n")
        fh.write("'GCR_MOD', -1,'CREME96'\n")
        fh.write("'SPECIES'\n")
        for e in (10.0, 100.0):
            iflux = [1.0 + 0.01 * z for z in range(NSP)]
            dflux = [1e-6 * (z + 1) ** -1.5 for z in range(NSP)]
            row = [e] + iflux + dflux
            fh.write(" ".join(f"{v:.6e}" for v in row) + "\n")


class TestSpenvisImport(unittest.TestCase):
    def test_convert_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "gcf.txt")
            _tiny_gcf(src)
            outdir = os.path.join(tmp, "out")
            man = convert_gcf(src, outdir, 100.0)
            self.assertEqual(man["source_orbit"]["apogee_km"], 420.0)
            self.assertEqual(man["source_orbit"]["inclination_deg"], 51.6)
            self.assertTrue(os.path.isfile(
                os.path.join(outdir, "manifest.json")))
            groups = man["groups"]
            self.assertIn("H", groups)
            for g, rec in groups.items():
                fp = os.path.join(outdir, rec["file"])
                self.assertTrue(os.path.isfile(fp), g)
                self.assertGreater(rec["integral_flux_cm2_s"], 0.0, g)


if __name__ == "__main__":
    unittest.main()
