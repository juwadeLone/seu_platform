"""A7 CS-256 hier_cell -> (stage_id, module_role) tags.

Unlike P1 (`u/sN/` ten-stage SDF FFT), the Microphase A7 design uses an
*iterative* 256-pt FFT (`fft256_core` with a stage register 0..7). There
are no `s1..s8` hierarchy prefixes. stage_id therefore means:

  1..4  FFT lane  u_fft0..u_fft3  (shared 8 radix stages inside each core)
  5     Hcs/H1 phase gen
  6     Hr/H2 phase gen
  7     Haz/Ha phase gen
  0     other tagged logic (control, ddr, coeff, transpose, comms)
 -1     test_infra / untagged

Rules encode names from `hier_after_fft4.rpt` / `A7_fpga_top`. First match
wins. Do not reuse P1 `stage_tags.py`.
"""
from __future__ import annotations

import csv
import re
from collections import Counter

ROLES = (
    "test_infra", "control", "coeff_build", "fft_core", "phase_gen",
    "fft_ctrl", "ddr_if", "transpose", "comms", "clock", "unknown",
)

_FFT_LANE = re.compile(r"/u_fft([0-3])(?:/|$)")
_PHASE = (
    (re.compile(r"/u_gen_hcs(?:/|$)"), 5, "phase_gen"),
    (re.compile(r"/u_gen_hr(?:/|$)"), 6, "phase_gen"),
    (re.compile(r"/u_gen_ha(?:/|$)"), 7, "phase_gen"),
)

# first-match; more specific prefixes before generic ones
_ROLE_RES = [
    (re.compile(r"(?:^|/)(?:sem_0|sem_monitor_bridge|u_sem_wrapper|"
                r"u_sem_bridge|u_sem)(?:/|$)"),
     "test_infra"),
    (re.compile(r"(?:^|/)(?:u_cmd_seq)(?:/|$)"), "control"),
    (re.compile(r"(?:^|/)(?:u_uart_cmd_if|uart_rx|u_uart_tx(?:_glue)?)(?:/|$)"),
     "control"),
    (re.compile(r"(?:^|/)u_cs_builder(?:/|$)"), "coeff_build"),
    (re.compile(r"(?:^|/)u_fft2d/u_row/u_fft[0-3](?:/|$)"), "fft_core"),
    (re.compile(r"(?:^|/)u_fft2d/u_row/u_gen_h(?:cs|r|a)(?:/|$)"), "phase_gen"),
    (re.compile(r"(?:^|/)u_fft2d/u_row/u_(?:rd|wr)(?:/|$)"), "ddr_if"),
    (re.compile(r"(?:^|/)u_fft2d(?:/|$)"), "fft_ctrl"),
    (re.compile(r"(?:^|/)u_swap(?:/|$)"), "transpose"),
    (re.compile(r"(?:^|/)(?:u_block_design_top|u_mig_7series_0|ddr0_clk_fifo|"
                r"u_dwidth)(?:/|$)"), "ddr_if"),
    (re.compile(r"(?:^|/)(?:udp_eth_rx|u_udp_eth_tx|u_wr_master|u_rd_master|"
                r"u_tx_engine|u_tx_arb|u_tx_fifo|u_rd_fifo|"
                r"u_telem_engine|u_telem_snap|u_telem_uart|"
                r"u_rd_start_cdc|u_tx_done_cdc|"
                r"rgmii_to_gmii|gmii_to_rgmii)(?:/|$)"), "comms"),
    (re.compile(r"(?:^|/)(?:inst1_clk_and_rst|u_eth_rst_sync)(?:/|$)"),
     "clock"),
]


def _normalize(hier_cell: str) -> str:
    h = (hier_cell or "").strip()
    if h.startswith("A7_fpga_top/"):
        h = h[len("A7_fpga_top/"):]
    elif h == "A7_fpga_top":
        h = ""
    return h


def tag(hier_cell: str):
    """Return (stage_id, module_role, replica_id). replica_id is always None."""
    h = _normalize(hier_cell)
    if not h:
        return -1, "unknown", None
    role = "unknown"
    for rx, r in _ROLE_RES:
        if rx.search("/" + h if not h.startswith("/") else h) or rx.search(h):
            role = r
            break
    # search also against a leading-slash form so ^|/ alternatives hit
    if role == "unknown":
        hs = h if h.startswith("/") else "/" + h
        for rx, r in _ROLE_RES:
            if rx.search(hs):
                role = r
                break

    stage = 0 if role != "unknown" else -1
    if role == "test_infra":
        stage = -1
    m = _FFT_LANE.search("/" + h)
    if m:
        stage = int(m.group(1)) + 1
        role = "fft_core"
    else:
        for rx, st, rr in _PHASE:
            if rx.search("/" + h):
                stage, role = st, rr
                break
    return stage, role, None


def majority_site(hier_cells):
    stages = Counter()
    roles = Counter()
    stage_set = set()
    for h in hier_cells:
        st, role, _rep = tag(h)
        stages[st] += 1
        roles[role] += 1
        if st > 0:
            stage_set.add(st)
    stage_id = stages.most_common(1)[0][0] if stages else -1
    role = roles.most_common(1)[0][0] if roles else "unknown"
    return {
        "stage_id": stage_id,
        "module_role": role,
        "replica_id": None,
        "is_shared": len(stage_set) > 1,
        "stages": sorted(stage_set),
        "n_prims": sum(stages.values()),
        "role_counts": dict(roles),
        "stage_counts": dict(stages),
    }


def bucket_of(role: str) -> str:
    """50-sample strata buckets from the campaign plan."""
    if role == "test_infra":
        return "test_infra"
    if role == "control":
        return "control"
    if role in ("fft_core", "phase_gen", "fft_ctrl", "coeff_build"):
        return "fft_datapath"
    if role in ("ddr_if", "transpose"):
        return "bram_dsp_col"
    return "other"


def report_csv(path):
    by_stage = Counter()
    by_role = Counter()
    unk_hier = []
    n = 0
    n_unk_role = 0
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            n += 1
            h = row.get("hier_cell") or ""
            st, role, _rep = tag(h)
            by_stage[st] += 1
            by_role[role] += 1
            if role == "unknown":
                n_unk_role += 1
                if len(unk_hier) < 40:
                    unk_hier.append(h)
    return {
        "n": n,
        "n_unknown_role": n_unk_role,
        "unknown_role_frac": (n_unk_role / n) if n else 0.0,
        "by_stage": dict(sorted(by_stage.items())),
        "by_role": dict(by_role.most_common()),
        "unknown_hier_samples": unk_hier,
    }


def format_report(rep):
    lines = [
        "A7 stage_tags report",
        f"primitives {rep['n']}",
        f"unknown role {rep['n_unknown_role']} "
        f"({100 * rep['unknown_role_frac']:.2f}%)",
        "by_stage " + " ".join(f"s{k}={v}" for k, v in rep["by_stage"].items()),
        "by_role " + " ".join(f"{k}={v}" for k, v in rep["by_role"].items()),
        "unknown hier samples:",
    ]
    for h in rep["unknown_hier_samples"]:
        lines.append("  " + (h or "(empty)"))
    return "\n".join(lines)
