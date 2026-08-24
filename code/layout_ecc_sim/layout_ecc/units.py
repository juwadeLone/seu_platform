"""Physical unit conversions for the strike kernel (WP8).

Every constant here is tagged ``source:`` or ``assumption:``. Callers must
import from this file; do not copy the numbers elsewhere.
"""
import math

# ---------------------------------------------------------------------------
# RPM grid → micrometres (calibrated 2026-08-22, replaces the 8 µm assumption)
# ---------------------------------------------------------------------------
# Xilinx publishes no µm/RPM figure, but UG475 v1.9 gives official die
# dimensions per device and the open Project X-Ray database gives the exact
# tile-array extents. Two devices (XC7K70T 117x209 tiles on a 5.99x9.68 mm
# die; XC7A200T 265x261 tiles on 11.10x12.05 mm) fix the 7-series lattice:
# 34.53 µm per tile column, 45.58 µm per tile row (independent check on
# XC7K325T reproduces its DS160 25,400 CLBs within ~1.5%).
# On this repo's primitive_map the CSV grid is grid_x = 2*SLICE_X+5 and
# grid_y = 2*SLICE_Y (verified over all 139,826 placed slice rows), and a
# Vivado CLB tile column hosts the adjacent slice pair SLICE_X(2k)/(2k+1)
# while SLICE_Y maps 1:1 to tile rows. Hence one CSV grid unit is half a
# tile row (22.79 µm) in Y and a quarter CLB column (8.63 µm) in X.
RPM_TO_UM_Y = 22.79          # µm per CSV grid unit, Y axis (calibrated)
RPM_TO_UM_X_IN_CLB = 8.63    # µm per CSV grid unit, X axis within one CLB
RPM_TO_UM_LEGACY = 8.0       # pre-calibration assumption, kept for old scans
RPM_TO_UM = RPM_TO_UM_Y
RPM_TO_UM_RANGE_UM = (21.8, 23.8)
RPM_TO_UM_NOTE = (
    "calibrated: UG475 v1.9 official die dimensions (Fig. 4-5/4-7/4-12/4-15) "
    "x Project X-Ray tilegrid extents -> 34.53 µm/tile column, 45.58 µm/tile "
    "row; CSV grid unit = half tile row in Y (22.79 µm, used as the default "
    "scalar) and quarter CLB column in X (8.63 µm within a CLB). X is NOT "
    "uniform: neighbouring CLB columns are ~3 tile columns apart, so "
    "cross-column distances are understated ~5x by the uniform lattice. "
    "Full derivation, SHA-256 and cross-checks: "
    "data/rpm_grid_calibration.json. Was 8 µm assumption before 2026-08-22."
)
RPM_TO_UM_SOURCE = "calibrated"

# ---------------------------------------------------------------------------
# Radaelli 2005 SRAM MBU cluster area vs neutron energy
# (copied via Ebrahimi DAC'13 Table 1, as specified in the handbook)
# ---------------------------------------------------------------------------
RADAELLI_2005 = (
    {"energy_mev": 22.0, "area_um2": 1.178},
    {"energy_mev": 47.0, "area_um2": 1.902},
    {"energy_mev": 95.0, "area_um2": 2.903},
    {"energy_mev": 144.0, "area_um2": 4.613},
)
RADAELLI_SOURCE = (
    "source: Radaelli et al. 2005 SRAM MBU weighted-mean affected area, "
    "as tabulated in Ebrahimi et al., DAC 2013 Table 1 "
    "(22/47/95/144 MeV → 1.178/1.902/2.903/4.613 µm²). "
    "These are neutron-energy → SRAM-cluster-area numbers, not LET."
)

# Track-core / charge-sharing qualitative anchors (not used as numbers in the fit)
MARTIN_GHONIEM_1987 = {
    "core_radius_um": (0.3, 0.6),
    "source": "source: Martin & Ghoniem, IEEE TNS 1987; radial density "
              "decays exponentially outside the track core; funneling "
              "feeds MBU. The ellipse is a coarse proxy for that tail.",
}
BLACK_TNS_2005 = {
    "source": "source: Black et al., IEEE TNS 2005; minimum design-rule "
              "spacing is not enough to stop multi-node charge sharing.",
}

# ---------------------------------------------------------------------------
# Neutron energy is not LET. Explicit bridge (assumption, not a silent skip).
# ---------------------------------------------------------------------------
# Fit A ∝ E^α on Radaelli, then reuse the same exponent on LET by pinning
# A(LET_REF) to the 95 MeV Radaelli point (middle of the four energies).
# LET_REF = 15 matches the legacy GUI default. This does *not* claim that
# 15 MeV·cm²/mg ≡ 95 MeV neutrons.
LET_REF = 15.0
A_REF_UM2 = 2.903  # Radaelli 95 MeV
LET_ENERGY_BRIDGE = (
    "assumption: neutron energy E and heavy-ion LET are different physics. "
    "A(LET) = A_ref · (LET/LET_ref)^α with α from the Radaelli E-fit, "
    "LET_ref=15 (legacy default), A_ref=2.903 µm² (Radaelli 95 MeV). "
    "The exponent is transferred; the energy↔LET identification is not."
)


def fit_radaelli_power_law():
    """Least-squares log-log fit A = c · E^α. Returns dict with residuals."""
    xs = [p["energy_mev"] for p in RADAELLI_2005]
    ys = [p["area_um2"] for p in RADAELLI_2005]
    n = len(xs)
    lx = [math.log(x) for x in xs]
    ly = [math.log(y) for y in ys]
    mx = sum(lx) / n
    my = sum(ly) / n
    num = sum((x - mx) * (y - my) for x, y in zip(lx, ly))
    den = sum((x - mx) ** 2 for x in lx)
    alpha = num / den
    log_c = my - alpha * mx
    c = math.exp(log_c)
    pred = [c * (x ** alpha) for x in xs]
    resid = [p - y for p, y in zip(pred, ys)]
    rmse = math.sqrt(sum(r * r for r in resid) / n)
    e_span = xs[-1] / xs[0]
    a_span = ys[-1] / ys[0]
    return {
        "alpha": alpha,
        "c": c,
        "rmse_um2": rmse,
        "residuals_um2": resid,
        "predicted_um2": pred,
        "energy_ratio": e_span,
        "area_ratio": a_span,
        "source": RADAELLI_SOURCE,
        "model": "A = c * E^alpha, E in MeV, A in µm²",
    }


_FIT = None


def radaelli_fit():
    global _FIT
    if _FIT is None:
        _FIT = fit_radaelli_power_law()
    return _FIT


def area_um2_from_energy_mev(energy_mev):
    """Radaelli power-law A(E). Energy in MeV."""
    fit = radaelli_fit()
    return fit["c"] * (float(energy_mev) ** fit["alpha"])


def area_um2_from_let(let):
    """Bridged A(LET). See LET_ENERGY_BRIDGE."""
    fit = radaelli_fit()
    let = max(float(let), 1e-12)
    return A_REF_UM2 * ((let / LET_REF) ** fit["alpha"])


# Discrete LET → A table used by WP8 scans (same bridge, explicit rows)
def let_to_area_table(lets=(5.0, 10.0, 15.0, 20.0, 30.0)):
    fit = radaelli_fit()
    rows = []
    for let in lets:
        rows.append({
            "let": let,
            "area_um2": area_um2_from_let(let),
            "source": LET_ENERGY_BRIDGE,
            "alpha": fit["alpha"],
            "a_ref_um2": A_REF_UM2,
            "let_ref": LET_REF,
        })
    return rows


def radius_um_from_area(area_um2):
    """Circle equivalent: a = sqrt(A/π) at normal incidence."""
    return math.sqrt(max(float(area_um2), 0.0) / math.pi)


def area_to_grid_b(area_um2, rpm_to_um=None):
    """Normal-incidence half-axis in RPM grid units."""
    rpm = float(RPM_TO_UM if rpm_to_um is None else rpm_to_um)
    return radius_um_from_area(area_um2) / max(rpm, 1e-12)


def constants_passport():
    fit = radaelli_fit()
    return {
        "rpm_to_um": {
            "value": RPM_TO_UM,
            "range_um": list(RPM_TO_UM_RANGE_UM),
            "source": RPM_TO_UM_SOURCE,
            "note": RPM_TO_UM_NOTE,
            "axis_detail": {
                "y_um_per_grid_unit": RPM_TO_UM_Y,
                "x_um_per_grid_unit_within_clb": RPM_TO_UM_X_IN_CLB,
                "legacy_assumption_um": RPM_TO_UM_LEGACY,
                "tile_column_pitch_um": 34.53,
                "tile_row_pitch_um": 45.58,
            },
            "calibration_file": "data/rpm_grid_calibration.json",
        },
        "radaelli_2005": {
            "points": [dict(p) for p in RADAELLI_2005],
            "source": RADAELLI_SOURCE,
            "fit": {
                "alpha": fit["alpha"],
                "c": fit["c"],
                "rmse_um2": fit["rmse_um2"],
                "residuals_um2": fit["residuals_um2"],
                "energy_ratio": fit["energy_ratio"],
                "area_ratio": fit["area_ratio"],
            },
        },
        "let_energy_bridge": LET_ENERGY_BRIDGE,
        "let_ref": LET_REF,
        "a_ref_um2": A_REF_UM2,
        "martin_ghoniem_1987": MARTIN_GHONIEM_1987,
        "black_tns_2005": BLACK_TNS_2005,
    }
