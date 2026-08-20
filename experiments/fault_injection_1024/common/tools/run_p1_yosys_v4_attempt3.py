#!/usr/bin/env python3
"""Execute attempt3 as an audited transformation of the attempt2 runner."""

from __future__ import annotations

import difflib
import hashlib
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "run_p1_yosys_v4_attempt2.py"
WORKSPACE = HERE.parents[3]
RESULTS = (
    HERE.parents[1]
    / "results"
    / "p1_yosys_v4_001"
    / "attempt3"
)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def main() -> int:
    original = SOURCE.read_text(encoding="utf-8")
    transformed = original

    # Isolated attempt labels and unique ASCII temporary-directory prefix.
    transformed = transformed.replace('"attempt2"', '"attempt3"')
    transformed = transformed.replace("attempt2-", "attempt3-")
    transformed = transformed.replace("attempt2_", "attempt3_")
    transformed = transformed.replace("P1V4A2", "P1V4A3")

    # The only flow-logic change authorized by D111.
    needle = '                "write_json P1_hierarchy.json",'
    replacement = (
        '                "proc",\n'
        '                "opt_clean",\n'
        '                "write_json P1_hierarchy.json",'
    )
    occurrence_count = transformed.count(needle)
    if occurrence_count != 2:
        raise RuntimeError(
            f"expected two hierarchy write_json sites, found {occurrence_count}"
        )
    transformed = transformed.replace(needle, replacement)

    # Import as a library; this bootstrap invokes main explicitly.
    marker = '\nif __name__ == "__main__":\n'
    if marker not in transformed:
        raise RuntimeError("attempt2 runner main marker not found")
    transformed = transformed.split(marker, 1)[0] + "\n"

    namespace = {
        "__name__": "p1_yosys_v4_attempt3_expanded",
        "__file__": str(Path(__file__).resolve()),
        "__package__": None,
    }
    exec(compile(transformed, str(Path(__file__).resolve()), "exec"), namespace)
    return_code = int(namespace["main"]())

    RESULTS.mkdir(parents=True, exist_ok=True)
    diff = list(
        difflib.unified_diff(
            original.splitlines(),
            transformed.splitlines(),
            fromfile="run_p1_yosys_v4_attempt2.py",
            tofile="expanded_attempt3_runner.py",
            lineterm="",
        )
    )
    manifest = {
        "schema": "p1-yosys-v4-001-attempt3-runner-transform-v1",
        "source_runner": str(SOURCE.relative_to(WORKSPACE)).replace("\\", "/"),
        "source_sha256": digest(original),
        "expanded_sha256": digest(transformed),
        "write_json_sites_modified": occurrence_count,
        "authorized_flow_change": [
            "insert proc immediately before write_json P1_hierarchy.json",
            "insert opt_clean immediately after proc and before write_json P1_hierarchy.json",
        ],
        "administrative_changes": [
            "attempt2 output labels changed to attempt3",
            "unique ASCII temporary prefix changed from P1V4A2 to P1V4A3",
            "library main guard removed for explicit bootstrap invocation",
        ],
        "unified_diff": diff,
        "runner_exit_code": return_code,
    }
    (RESULTS / "runner_transform.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
