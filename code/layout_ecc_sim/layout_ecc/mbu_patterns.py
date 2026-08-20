"""MBU pattern sampling (WP9).

Distributions are copied from literature and tagged ``source:``. Domain
allocation among CFG/FF/BRAM/DSP is an explicit assumption.
"""
from .domains import ORDER

# Perez-Celis & Wirthlin, IEEE TNS 2021 (doi:10.1109/TNS.2021.3071704):
# neutron test, MCU events are 30% of upset *events* → SBU 70%.
# That paper does not publish a 2/3/4-bit split. All MCU events are
# injected as k=2 (lower bound on clustering; k>=2 by definition).
P_K_NEUTRON_FPGA = {
    1: 0.70,
    2: 0.30,
}
P_K_NEUTRON_FPGA_SOURCE = (
    "source: Pérez-Celis & Wirthlin, IEEE TNS 2021, "
    "'Emulating Radiation-Induced Multicell Upset Patterns in SRAM FPGAs "
    "With Fault Injection'. Neutron test: MCU = 30% of upset events "
    "(hence P(k=1)=0.70). MCU size split is not in that paper; every MCU "
    "event is stored as k=2 (lower bound)."
)

# Mayo et al., IEEE TNS 2025 (doi:10.1109/TNS.2025.3531510), Versal 7 nm
# CRAM, LET=62.4 MeV·cm²/mg: σ_SBU = 5.73e-11 cm², σ_2bit = 5.97e-11 cm².
# Max observed multiplicity 4. Default scan uses the 7-series neutron table
# above; this table is the high-LET 1-vs-2 mix only (3- and 4-bit counts
# were not copied as a full histogram from Table III).
P_K_VERSAL_HIGHLET_1AND2 = {
    1: 5.73 / (5.73 + 5.97),
    2: 5.97 / (5.73 + 5.97),
}
P_K_VERSAL_SOURCE = (
    "source: Mayo et al., IEEE TNS 2025, Versal 7 nm CRAM heavy ions, "
    "σ_SBU=(5.73±0.67)·10⁻¹¹ cm² and σ_2-bit MCU=(5.97±0.70)·10⁻¹¹ cm² "
    "at 62.4 MeV·cm²/mg; normalised over {1,2} only. Max MCU size 4."
)

DEFAULT_TABLE = P_K_NEUTRON_FPGA
DEFAULT_TABLE_SOURCE = P_K_NEUTRON_FPGA_SOURCE

# Domain mix among the k selected (site × domain) candidates.
# assumption: a particle does not prefer a fault *domain*; given the kernel
# already selected candidate rows, pick proportional to that row's bit count.
DOMAIN_ALLOCATION_NOTE = (
    "assumption: P(domain | candidate in kernel) ∝ bits on that "
    "(site × domain) row. Charge sharing is geometric; bit count is a "
    "proxy for how much of the site belongs to each domain. Not measured."
)


def distribution_table():
    s = sum(DEFAULT_TABLE.values())
    return {
        "p_k": {str(k): v for k, v in sorted(DEFAULT_TABLE.items())},
        "sum": s,
        "source": DEFAULT_TABLE_SOURCE,
        "alternate_versal_1and2": {
            "p_k": {str(k): v for k, v in sorted(P_K_VERSAL_HIGHLET_1AND2.items())},
            "source": P_K_VERSAL_SOURCE,
        },
        "domain_allocation": DOMAIN_ALLOCATION_NOTE,
        "domains": list(ORDER),
    }


def sample_k(rng, table=None):
    table = DEFAULT_TABLE if table is None else table
    items = sorted(table.items())
    u = rng.random()
    acc = 0.0
    for k, p in items:
        acc += p
        if u < acc:
            return int(k)
    return int(items[-1][0])


def _dist2(entry, x0, y0):
    x = float(entry.get("grid_x", 0)) + 0.5
    y = float(entry.get("grid_y", 0)) + 0.5
    return (x - x0) ** 2 + (y - y0) ** 2


def bit_weight(entry):
    """Domain-allocation weight. See DOMAIN_ALLOCATION_NOTE."""
    return max(int(entry.get("bits") or 1), 1)


def select_k(candidates, k, rng, shape="cluster", x0=0.0, y0=0.0):
    """Pick k (site × domain) rows from the kernel coverage set.

    cluster: nearest to the strike centre first (aggregated MBU shape).
    uniform: random distinct rows (control).
    If k exceeds the candidate count, return all of them.
    """
    if k <= 0 or not candidates:
        return []
    k = min(int(k), len(candidates))
    if shape == "uniform":
        # weighted by bits, without replacement
        pool = list(candidates)
        picked = []
        for _ in range(k):
            weights = [bit_weight(c) for c in pool]
            total = sum(weights)
            u = rng.random() * total
            acc = 0.0
            idx = len(pool) - 1
            for i, w in enumerate(weights):
                acc += w
                if u <= acc:
                    idx = i
                    break
            picked.append(pool.pop(idx))
        return picked
    ranked = sorted(candidates, key=lambda e: (_dist2(e, x0, y0), -bit_weight(e),
                                               e.get("domain") or ""))
    return ranked[:k]
