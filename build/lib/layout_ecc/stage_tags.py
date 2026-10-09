"""hier_cell -> (stage_id, module_role, replica_id) for P1 netlist names.

Rules only encode hierarchy strings that actually appear in
``data/layout/p1_ooc_win/primitive_map.csv``, cross-checked against
``experiments/※seven_arch_rtl/P1/hdl/rtl/top_p1_kernel.sv``.
Anything that does not match is ``unknown`` and counted; do not guess.
Changing ``_ROLE_KEYS`` requires re-running the unknown report.

Priority (first match wins)
---------------------------
Nested ``complete_butterflies[n].pipe_rot.rotate`` is a twiddle rotator
inside a butterfly instance (handbook 2.2). Twiddle keys therefore come
*before* ``complete_butterflies``. Nested ``replicas[i].u/rot2`` is the
same: twiddle before replica. ``u_apply`` / ``sy*`` / ``res*`` are the
arithmetic-ECC apply path, not butterfly arithmetic.
"""
import colorsys
import csv
import re
from collections import Counter

N_STAGES = 10
COLOR_UNUSED = "#14181e"
RESOURCE_COLORS = {
    "SLICE": "#3d7ec9", "CLB": "#3d7ec9",
    "DSP": "#c9893d", "BRAM": "#3dc98a",
    "OTHER": "#6b7c8d", "unused": COLOR_UNUSED,
}


def stage_hex(stage_id):
    if not stage_id or int(stage_id) < 1:
        return COLOR_UNUSED
    h = (int(stage_id) - 1) / N_STAGES
    r, g, b = colorsys.hsv_to_rgb(h, 0.58, 0.86)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


STAGE_COLORS = {i: stage_hex(i) for i in range(1, N_STAGES + 1)}
_STAGE = re.compile(r"^u/s(\d+)/")
_REPLICA = re.compile(r"replicas\[(\d+)\]")

# first-match; order is the priority documented above.
# Short tokens (au/al/qu) MUST be numbered (au0, qu4) so they do not
# match ``valid`` / ``request``.
_ROLE_RES = [
    (re.compile(r"pipe_rot"), "twiddle"),
    (re.compile(r"rot2"), "twiddle"),
    (re.compile(r"\.rotate"), "twiddle"),
    (re.compile(r"complete_butterflies"), "butterfly"),
    (re.compile(r"g_(?:a)?sync_distributed"), "delay"),
    (re.compile(r"mem[0-3]"), "delay"),
    (re.compile(r"hold_[ri]"), "control"),
    (re.compile(r"bnd_[riv]"), "control"),
    (re.compile(r"u_apply"), "ecc"),
    (re.compile(r"sy[01]"), "ecc"),
    (re.compile(r"res[01]"), "ecc"),
    (re.compile(r"app_[ri]"), "ecc"),
    (re.compile(r"replicas\["), "replica"),
    (re.compile(r"mul_[ri]"), "twiddle"),
    (re.compile(r"c[ab][0-3][ri]"), "butterfly"),
    (re.compile(r"q[ul][0-5][ri]"), "butterfly"),
    (re.compile(r"[ah][ul][0-5][ri]"), "ecc"),
    (re.compile(r"[xy][ul][0-3][ri]"), "ecc"),
    (re.compile(r"pending"), "ecc"),
    (re.compile(r"out[0-3]_(?:re|im)"), "butterfly"),
    (re.compile(r"out_(?:count|valid|last)"), "control"),
    (re.compile(r"phase|primed|request_|work2|pair_phase|go_"), "control"),
    (re.compile(r"/[abcd][01][ri]"), "butterfly"),
    (re.compile(r"/q[0-3][ri]"), "delay"),
    # Flattened real/imag LUT cones at stage top. Observed only on s2–s7,
    # which are the stages with generic twiddle multipliers; s1 (trivial
    # rotate) and s8–s10 have none. Not tagged butterfly: those LUTs sit
    # under complete_butterflies/.
    (re.compile(r"(?:^|/)(?:ii|rr)_s"), "twiddle"),
    (re.compile(r"res_v|syn_v"), "ecc"),
    (re.compile(r"last_(?:bf|res|syn)|pair_last"), "control"),
]


def tag(hier_cell):
    """Return (stage_id, module_role, replica_id). stage_id is -1 if unknown."""
    h = hier_cell or ""
    m = _STAGE.match(h)
    if not m:
        return -1, "unknown", None
    stage = int(m.group(1))
    role = "unknown"
    for rx, r in _ROLE_RES:
        if rx.search(h):
            role = r
            break
    # s8/s9 top-level q* registers are TMR voters, not delay-line taps
    if stage in (8, 9) and role == "delay" and "replicas[" not in h:
        role = "replica"
    rep = _REPLICA.search(h)
    return stage, role, (int(rep.group(1)) if rep else None)


def majority_site(hier_cells):
    """Site-level tag from the primitives sharing one Site.

    Majority ``stage_id`` among tagged prims. ``is_shared`` if more than one
    positive stage is present. Majority ``module_role`` among all prims.
    """
    stages = Counter()
    roles = Counter()
    stage_set = set()
    replicas = Counter()
    for h in hier_cells:
        st, role, rep = tag(h)
        stages[st] += 1
        roles[role] += 1
        if st > 0:
            stage_set.add(st)
        if rep is not None:
            replicas[rep] += 1
    stage_id = stages.most_common(1)[0][0] if stages else -1
    role = roles.most_common(1)[0][0] if roles else "unknown"
    replica_id = replicas.most_common(1)[0][0] if replicas else None
    return {
        "stage_id": stage_id,
        "module_role": role,
        "replica_id": replica_id,
        "is_shared": len(stage_set) > 1,
        "stages": sorted(stage_set),
        "n_prims": sum(stages.values()),
        "role_counts": dict(roles),
        "stage_counts": dict(stages),
    }


def report_csv(path):
    """Count stages / roles / unknown ref_name for a primitive_map.csv."""
    by_stage = Counter()
    by_role = Counter()
    unk_ref = Counter()
    unk_hier = []
    n = 0
    n_unk_role = 0
    n_unk_stage = 0
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            n += 1
            h = row.get("hier_cell") or ""
            st, role, _rep = tag(h)
            by_stage[st] += 1
            by_role[role] += 1
            if st < 1:
                n_unk_stage += 1
            if role == "unknown":
                n_unk_role += 1
                unk_ref[row.get("ref_name") or "(empty)"] += 1
                if len(unk_hier) < 12:
                    unk_hier.append(h)
    return {
        "n": n,
        "n_unknown_stage": n_unk_stage,
        "n_unknown_role": n_unk_role,
        "unknown_role_frac": (n_unk_role / n) if n else 0.0,
        "by_stage": dict(sorted(by_stage.items())),
        "by_role": dict(by_role.most_common()),
        "unknown_ref_top20": unk_ref.most_common(20),
        "unknown_hier_samples": unk_hier,
    }


def format_report(rep):
    lines = [
        f"primitives {rep['n']}",
        f"unknown stage {rep['n_unknown_stage']}",
        f"unknown role {rep['n_unknown_role']} "
        f"({100 * rep['unknown_role_frac']:.2f}%)",
        "by_stage " + " ".join(
            f"s{k}={v}" for k, v in rep["by_stage"].items() if k > 0),
        "by_role " + " ".join(f"{k}={v}" for k, v in rep["by_role"].items()),
        "unknown ref_name top 20:",
    ]
    for name, c in rep["unknown_ref_top20"]:
        lines.append(f"  {c:6d}  {name}")
    lines.append("unknown hier samples:")
    for h in rep["unknown_hier_samples"]:
        lines.append("  " + h)
    return "\n".join(lines)


if __name__ == "__main__":
    import os
    csv_path = os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "data", "layout", "p1_ooc_win",
        "primitive_map.csv"))
    print(format_report(report_csv(csv_path)))
