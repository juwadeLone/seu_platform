"""Protection off vs on from one events.jsonl fault list."""
import json
import os
import tempfile
import unittest

from layout_ecc.compare import run_compare, table


def row(cw, sym=0, domain="FF_STATE", n=1):
    return dict(domain=domain, stage_id=int(cw.split(":")[0][1:]),
                codeword_id=cw, symbol_id=sym, codeword_confidence="inferred",
                n_bits=n)


class TestCompare(unittest.TestCase):
    def test_off_vs_on_counts(self):
        lines = [
            {"event_id": "a/1", "seed": 1, "flipped": [row("s3:secded:mem1")]},
            {"event_id": "a/2", "seed": 2,
             "flipped": [row("s3:secded:mem1"), row("s3:arith", domain="CFG")]},
            {"event_id": "b/1", "seed": 1, "flipped": []},
        ]
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "events.jsonl")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("".join(json.dumps(x) + "\n" for x in lines))
            rep = run_compare(path)
            self.assertTrue(os.path.isfile(os.path.join(d, "comparison.json")))
        self.assertEqual(rep["n_events"], 3)
        self.assertEqual(rep["n_events_with_mapped_bits"], 2)
        self.assertEqual(rep["off"]["outcomes"]["SDC"], 2)
        self.assertEqual(rep["on"]["outcomes"],
                         dict(NO_FAULT=1, MASKED=0, CORRECTED=1, DUE=0, SDC=0,
                              UNMAPPED=1))
        self.assertEqual(rep["on"]["mapped_outcomes"]["CORRECTED"], 2)
        self.assertEqual([e["event_id"] for e in rep["per_event"]],
                         ["a/1", "a/2", "b/1"])
        self.assertIn("n_events=3", table(rep))


if __name__ == "__main__":
    unittest.main()
