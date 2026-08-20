"""Parameterized strike-kernel proxy: (LET, theta) -> ellipse (a, b).

This is NOT a calibrated charge-collection radius. Guide 1.3: until beam or
TCAD calibration, a and b are layout-proxy lengths in tile units. LET does
not blindly inflate the ellipse; the default map is a weak, explicit scale
that the GUI can freeze at 1.0 for geometry debugging.
"""
import math


def kernel_axes(let, theta_deg, a0, let_ref=15.0, k_let=0.25, theta_max=75.0):
    """Return (a, b) in the same length unit as a0.

    b  — across-track half-width (almost independent of incidence)
    a  — along-track half-width, stretched as 1/cos(theta) for a thin slab
         (longer chord at oblique incidence). Cap theta so a stays finite.

    phi is applied later as the ellipse rotation; it does not change a, b.
    """
    th = math.radians(min(max(float(theta_deg), 0.0), theta_max))
    scale = 1.0 + k_let * (max(float(let), 0.0) / let_ref)
    b = max(float(a0), 1e-6) * scale
    a = b / max(math.cos(th), math.cos(math.radians(theta_max)))
    return a, b


def kernel_axes_from_area(area_um2, theta_deg, rpm_to_um, theta_max=75.0):
    """Anchored kernel: A (µm²) → (a, b) in RPM grid units.

    Normal incidence is a circle of area A; oblique stretch is 1/cos(θ)
    along-track, same as the legacy kernel.
    """
    from .units import area_to_grid_b
    th = math.radians(min(max(float(theta_deg), 0.0), theta_max))
    b = max(area_to_grid_b(area_um2, rpm_to_um), 1e-9)
    a = b / max(math.cos(th), math.cos(math.radians(theta_max)))
    return a, b
