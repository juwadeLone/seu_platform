"""K7 CSA-2048 hier_cell -> (stage_id, module_role) tags.

K7 is a single-master chain: k7_udp_ddr_top/u_core contains the seven-pass
CSA application (u_cs_app) beside the UDP/DDR plumbing.  The chain itself is
csa_cs_chain_top at u_cs_app/u_dut with four coefficient pass engines
(u_p1, u_p3, u_p4, u_p6) and one transpose engine (u_swap, serves P0/P2/P5).

stage_id semantics:
  1,3,4,6  coefficient pass engines (u_pN -> pass N)
  -2       u_swap -- shared by transposes P0/P2/P5
  0        other tagged logic (control, comms, ddr, coeff, clock)
  -1       test_infra / untagged

module_role feeds the paper's five fault domains at join time:
  control -> CONTROL, coeff_build -> BRAM_COEFF,
  fft_core/transpose/fft_ctrl -> DATAPATH, ddr_if/comms -> DDR_IF.
"""
from __future__ import annotations

import csv
import re
from collections import Counter

ROLES = (
    "test_infra", "control", "coeff_build", "fft_core", "transpose",
    "fft_ctrl", "ddr_if", "comms", "clock", "unknown",
)

_PASS = re.compile(r"/u_p([0-9])(?:/|$)")

# first-match; more specific prefixes before generic ones
_ROLE_RES = [
    (re.compile(r"(?:^|/)(?:sem_0|u_sem_wrapper|u_sem_bridge|u_sem_cdc|"
                r"sem_monitor_bridge|sem_cmd_cdc)(?:/|$)"),
     "test_infra"),
    (re.compile(r"(?:^|/)(?:u_cmd_seq|u_uart_cmd_if|u_uart_rx|u_telem_uart|"
                r"u_glue)(?:/|$)"), "control"),
    (re.compile(r"(?:^|/)u_cs_app/u_seed_engine_f64(?:/|$)"), "coeff_build"),
    (re.compile(r"(?:^|/)u_cs_app/u_seeds(?:/|$)"), "coeff_build"),
    (re.compile(r"(?:^|/)u_cs_app/u_dut/u_swap(?:/|$)"), "transpose"),
    (re.compile(r"(?:^|/)u_cs_app/u_dut/u_p[0-9](?:/|$)"), "fft_core"),
    (re.compile(r"(?:^|/)u_cs_app(?:/|$)"), "fft_ctrl"),
    (re.compile(r"(?:^|/)(?:u_mig|u_axi_cdc|u_mux|u_wr_gear|u_rd_gear|"
                r"u_wr|u_rd)(?:/|$)"), "ddr_if"),
    (re.compile(r"(?:^|/)(?:u_eth_rx|u_eth_tx|u_tx_engine|udp_eth_rx|"
                r"udp_eth_tx|rgmii_to_gmii|gmii_to_rgmii|u_rx|u_tx)(?:/|$)"),
     "comms"),
    (re.compile(r"(?:^|/)(?:u_clk|u_rst|u_icap_bufg)(?:/|$)"), "clock"),
]


def _normalize(hier_cell: str) -> str:
    h = (hier_cell or "").strip()
    if h.startswith("k7_udp_ddr_top/"):
        h = h[len("k7_udp_ddr_top/"):]
    elif h == "k7_udp_ddr_top":
        h = ""
    return h


def tag(hier_cell: str):
    """Return (stage_id, module_role, replica_id). replica_id is always None."""
    h = _normalize(hier_cell)
    if not h:
        return -1, "unknown", None
    role = "unknown"
    hs = h if h.startswith("/") else "/" + h
    for rx, r in _ROLE_RES:
        if rx.search(hs):
            role = r
            break

    stage = 0 if role != "unknown" else -1
    if role == "test_infra":
        stage = -1
    m = _PASS.search(hs)
    if m and "fft_core" == role:
        stage = int(m.group(1))
    elif role == "transpose":
        stage = -2
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
    """Paper fault-domain buckets from the campaign plan."""
    if role == "test_infra":
        return "test_infra"
    if role == "control":
        return "CONTROL"
    if role == "coeff_build":
        return "BRAM_COEFF"
    if role in ("fft_core", "transpose", "fft_ctrl"):
        return "DATAPATH"
    if role in ("ddr_if", "comms"):
        return "DDR_IF"
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
        "K7 stage_tags report",
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
