"""Event-rate integrators.

Heavy ions (direct ionization): the classic "effective LET" thin-slab
approximation. An isotropic differential LET flux phi(L) (omnidirectional,
integrated over 4*pi) crosses a thin sensitive slab whose response sigma(L)
was measured with effective LET and effective (plate-normal) fluence, the
usual heavy-ion test convention. A particle at polar angle theta to the slab
normal deposits along a chord L/cos(theta). Particles cross unit slab area
from direction dOmega at the rate I*|cos(theta)|*dOmega with I = phi/(4*pi),
from both hemispheres, so

    R = phi * int_0^{pi/2} sigma(L / cos(theta)) cos(theta) sin(theta) dtheta
      = (phi / 2) * <sigma(L / cos(theta))>,

where <.> averages over the crossing-angle density 2*cos(theta)*sin(theta)
on [0, pi/2]. For a constant sigma this gives R = phi * sigma / 2, the
flat-plate result (a plate of area A in an isotropic field is crossed by
phi*A/2 particles per unit time). sigma_effective() returns the average
<.>; FLAT_PLATE_FACTOR carries the 1/2.

This is the CREME86-era effective-flux treatment (Petersen): adequate for
thin sensitive volumes, optimistic-to-fair vs full IRPP; stated in the
report. Proton rate is the direct integral phi_p(E) * sigma_p(E) dE.
"""
import math

# Omni flux crossing a thin plate (both faces): phi * A / 2.
FLAT_PLATE_FACTOR = 0.5


def _direction_quadrature(n_angles=64, max_deg=90.0):
    """Returns list of (weight, 1/cos(theta)) with weights summing to 1,
    midpoint rule over theta with the crossing-angle density
    2 cos(theta) sin(theta). The full hemisphere is covered by default;
    the grazing tail is bounded because sigma saturates."""
    pts = []
    total = 0.0
    a, b = 0.0, math.radians(max_deg)
    for j in range(n_angles):
        th = a + (b - a) * (j + 0.5) / n_angles
        w = math.cos(th) * math.sin(th)
        total += w
        pts.append((w, 1.0 / math.cos(th)))
    return [(w / total, inv_cos) for w, inv_cos in pts]


_QUAD = _direction_quadrature()


def sigma_effective(let, device):
    """Direction-averaged cross-section <sigma(L/cos(theta))> over the
    crossing-angle density (not yet multiplied by FLAT_PLATE_FACTOR)."""
    s = 0.0
    for w, inv_cos in _QUAD:
        s += w * device.sigma(let * inv_cos)
    return s


def heavy_ion_rate_per_s(let_spectrum, device):
    """R = (1/2) int phi(L) * <sigma(L/cos)> dL  [events/s, per bit or per
    device following the sigma normalization]; phi is omnidirectional."""
    return FLAT_PLATE_FACTOR * let_spectrum.integrate_against(
        lambda L: sigma_effective(L, device))


def proton_rate_per_s(energy_spectrum, sigma_model):
    return energy_spectrum.integrate_against(lambda E: sigma_model.sigma(E))


def mission_stats(rate_per_s, duration_s):
    """Expected count and P(>=1 event) for a Poisson process."""
    mu = rate_per_s * duration_s
    p = 1.0 - math.exp(-mu)
    return {"expected_events": mu, "prob_at_least_one": p,
            "rate_per_day": rate_per_s * 86400.0}
