"""Protection off vs on from one campaign fault list (events.jsonl).

    python -m layout_ecc.compare --events campaign-p1-ff/events.jsonl

Writes comparison.json next to the events file (or --out) with per-outcome
counts for both settings. ``outcomes`` classifies whole events (any CFG /
unmapped bit -> UNMAPPED); ``mapped_outcomes`` classifies the same events
on their FF/BRAM bits only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from .joint_replay import compare_protection

_SCHEMA = "layout_ecc.compare.v1"
_SCOPE = ("Functional replay of prescribed strikes on the P1 1024-point "
          "workload; bit positions inside a word sampled per seed; no "
          "lifetime masking; not an on-orbit error rate.")


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_compare(events, out=None):
    events = Path(events)
    lines = [json.loads(line) for line in
             events.read_text(encoding="utf-8").splitlines() if line.strip()]
    cmp = compare_protection(lines)
    report = {
        "schema": _SCHEMA,
        "scope": _SCOPE,
        "events": {"path": events.name, "sha256": _sha256(events)},
        "n_events": len(lines),
        "n_events_with_mapped_bits": sum(
            1 for e in cmp["fault_list"] if e["n_mapped"]),
        "off": cmp["off"]["summary"],
        "on": cmp["on"]["summary"],
        "per_event": [
            {"event_id": off["event_id"], "n_bits": off["n_bits"],
             "n_mapped": off["n_mapped"],
             "off": off["outcome"], "on": on["outcome"],
             "off_mapped": off["mapped_outcome"],
             "on_mapped": on["mapped_outcome"]}
            for off, on in zip(cmp["off"]["results"], cmp["on"]["results"])],
    }
    out = Path(out) if out else events.parent / "comparison.json"
    out.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True,
                              indent=1) + "\n", encoding="utf-8", newline="\n")
    return report


def table(report):
    keys = ["NO_FAULT", "MASKED", "CORRECTED", "DUE", "SDC", "UNMAPPED"]
    rows = [f"n_events={report['n_events']} "
            f"(with mapped bits: {report['n_events_with_mapped_bits']})",
            "view            prot " + " ".join(f"{k:>9}" for k in keys)]
    for view in ("outcomes", "mapped_outcomes"):
        for prot in ("off", "on"):
            c = report[prot][view]
            rows.append(f"{view:<15} {prot:>4} "
                        + " ".join(f"{c.get(k, '-'):>9}" for k in keys))
    return "\n".join(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    print(table(run_compare(args.events, args.out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
