"""Physical constants and model defaults (SI unless noted).

Sources: WGS-84/EMG2008 standard values for the gravitational parameters and
Earth rotation; IGRF-13 (2020.0) main-field dipole coefficients g10/g11/h11.
The dipole coefficients and the equatorial cutoff normalization are user
overridable in the mission config so newer IGRF epochs can be substituted.
"""

MU_EARTH = 3.986004418e14        # m^3/s^2
R_EARTH_KM = 6378.137            # km (equatorial, WGS-84)
J2 = 1.08262668e-3
OMEGA_EARTH = 7.2921158553e-5    # rad/s

# IGRF-13 dipole terms at epoch 2020.0 [nT]
G10_2020 = -29404.8
G11_2020 = -1450.9
H11_2020 = 4652.7

# Centered-dipole Størmer vertical-cutoff normalization at the geomagnetic
# equator, sea level, for the 2020.0 dipole (~14.9 GV). Real multi-pole
# cutoff maps (Smart & Shea, AE9/AP9) differ by up to ~+/-20%.
CUTOFF_EQ_GV_DEFAULT = 14.9

# Stopping-power constant for the demo LET approximation:
# L [MeV*cm^2/mg] ~= Z^2 * K / beta^2 with K = 1.66e-3 (minimum-ionizing
# proton LET in silicon ~ 0.00166 MeV*cm^2/mg). Demo environment only;
# engineering runs must import real LET spectra.
LET_K_DEMO = 1.66e-3
