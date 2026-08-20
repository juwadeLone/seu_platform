#!/usr/bin/env python3
"""Independent attempt2 after the attempt1 qualification-field mismatch."""

from __future__ import annotations

import run_p2_yosys_no_framebuf_v1_attempt1 as attempt1


attempt1.base.RESULTS = (
    attempt1.EXPERIMENT
    / "results"
    / "p2_yosys_no_framebuf_v1_001"
    / "attempt2"
)
attempt1.base.LOGS = (
    attempt1.EXPERIMENT
    / "logs"
    / "p2_yosys_no_framebuf_v1_001"
    / "attempt2"
)
attempt1.base.BUILD = (
    attempt1.EXPERIMENT
    / "build"
    / "p2_yosys_no_framebuf_v1_001"
    / "attempt2"
)


if __name__ == "__main__":
    raise SystemExit(attempt1.main())
