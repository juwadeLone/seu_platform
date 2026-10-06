"""orbit_seu: chip SEU-rate estimation for arbitrary Earth orbits.

Chain: orbit elements -> J2-secular propagation -> tilted-dipole geomagnetic
cutoff -> particle/LET environment (file-imported or clearly-labeled SYNTHETIC
demo spectra) -> device cross-section (Weibull or table) -> event rates and
mission probabilities. See README.md for scope and limitations.
"""

__version__ = "0.1.0"

from .orbit import OrbitElements, propagate_mission
from .magnetosphere import DipoleModel, magnetic_latitude, vertical_cutoff_gv
from .spectra import Spectrum
from .device import WeibullLET, TableSigma
from .rates import (heavy_ion_rate_per_s, proton_rate_per_s, mission_stats,
                    sigma_effective)
from .environment import (
    DEMO_SPECIES,
    demo_gcr_let_spectra,
    load_spectrum_file,
)
from .mission import run, write_report
from .gcr_bo import load_lis_coefficients, let_spectra_from_gcr
from .ae9ap9 import write_ephemeris, parse_flux_file

__all__ = [
    "OrbitElements", "propagate_mission",
    "DipoleModel", "magnetic_latitude", "vertical_cutoff_gv",
    "Spectrum", "WeibullLET", "TableSigma",
    "heavy_ion_rate_per_s", "proton_rate_per_s", "sigma_effective",
    "mission_stats",
    "DEMO_SPECIES", "demo_gcr_let_spectra", "load_spectrum_file",
    "load_lis_coefficients", "let_spectra_from_gcr",
    "write_ephemeris", "parse_flux_file",
    "run", "write_report", "__version__",
]
