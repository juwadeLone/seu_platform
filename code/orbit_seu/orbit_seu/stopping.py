"""Ion stopping in Si (LET) and Al (shield transport), interim model.

Used by scripts/spenvis_to_let.py to turn SPENVIS/CREME96 GCR energy
spectra into LET spectra behind a shield. This is an INTERIM engineering
path: the standard route is SPENVIS's own CREME96 shielded LET spectrum
(TRANS + LETSPEC), which should replace these files once exported.

Physics (textbook, no fitted constants beyond the cited material data):
  - Bethe-Bloch mass stopping power with the full Tmax expression,
    Sternheimer density-effect correction; no shell, Barkas-Andersen or
    Bloch corrections (valid to ~10% above ~1 MeV/n, worse near the
    Bragg peak).
  - Effective charge Z_eff = Z [1 - exp(-125 beta Z^(-2/3))] (Barkas 1963).
  - Material data: mean excitation energies I (Si 173 eV, Al 166 eV) and
    Sternheimer density-effect parameters from Sternheimer, Berger &
    Seltzer, At. Data Nucl. Data Tables 30 (1984) 261 (as tabulated by the
    PDG / NIST ESTAR).
  - Shield transport: continuous slowing down (CSDA) through a spherical
    shell of areal density t (the CREME96 TRANS geometry: every direction
    sees t), flux conserved, nuclear fragmentation neglected (~few % for
    ~1 g/cm2 Al, slightly conservative).

Anchors checked in tests: minimum-ionizing proton in Si ~1.66 MeV cm2/g;
10 MeV proton in Si ~0.0347 MeV cm2/mg (NIST PSTAR); Fe maximum LET in Si
~29 MeV cm2/mg.
"""
import math

ME_MEV = 0.51099895          # electron rest energy
AMU_MEV = 931.49410242       # atomic mass unit
MP_MEV = 938.27208816        # proton rest energy
K_BETHE = 0.307075           # 4 pi N_A r_e^2 m_e c^2, MeV cm2/mol

# Standard atomic weights rounded to mass number, Z = 1..92 (A per ion).
ATOMIC_MASS = [
    1, 4, 7, 9, 11, 12, 14, 16, 19, 20, 23, 24, 27, 28, 31, 32, 35, 40, 39,
    40, 45, 48, 51, 52, 55, 56, 59, 59, 64, 65, 70, 73, 75, 79, 80, 84, 85,
    88, 89, 91, 93, 96, 98, 101, 103, 106, 108, 112, 115, 119, 122, 128, 127,
    131, 133, 137, 139, 140, 141, 144, 145, 150, 152, 157, 159, 163, 165, 167,
    169, 173, 175, 178, 181, 184, 186, 190, 192, 195, 197, 201, 204, 207, 209,
    209, 210, 222, 223, 226, 227, 232, 231, 238,
]

ELEMENTS = [
    'H', 'He', 'Li', 'Be', 'B', 'C', 'N', 'O', 'F', 'Ne', 'Na', 'Mg', 'Al',
    'Si', 'P', 'S', 'Cl', 'Ar', 'K', 'Ca', 'Sc', 'Ti', 'V', 'Cr', 'Mn', 'Fe',
    'Co', 'Ni', 'Cu', 'Zn', 'Ga', 'Ge', 'As', 'Se', 'Br', 'Kr', 'Rb', 'Sr',
    'Y', 'Zr', 'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd', 'In', 'Sn',
    'Sb', 'Te', 'I', 'Xe', 'Cs', 'Ba', 'La', 'Ce', 'Pr', 'Nd', 'Pm', 'Sm',
    'Eu', 'Gd', 'Tb', 'Dy', 'Ho', 'Er', 'Tm', 'Yb', 'Lu', 'Hf', 'Ta', 'W',
    'Re', 'Os', 'Ir', 'Pt', 'Au', 'Hg', 'Tl', 'Pb', 'Bi', 'Po', 'At', 'Rn',
    'Fr', 'Ra', 'Ac', 'Th', 'Pa', 'U',
]


class Material:
    def __init__(self, name, z_over_a, i_ev, cbar, x0, x1, a, m, delta0,
                 density_g_cm3):
        self.name = name
        self.z_over_a = z_over_a
        self.i_mev = i_ev * 1e-6
        self.dens = (cbar, x0, x1, a, m, delta0)
        self.rho = density_g_cm3


SILICON = Material("Si", 14 / 28.0855, 173.0,
                   4.4351, 0.2014, 2.8715, 0.14921, 3.2546, 0.14, 2.329)
ALUMINUM = Material("Al", 13 / 26.9815, 166.0,
                    4.2395, 0.1708, 3.0127, 0.08024, 3.6345, 0.12, 2.699)

MIL_CM = 2.54e-3


def mass_per_nucleon(z):
    return MP_MEV if z == 1 else AMU_MEV


def _density_delta(x, dens):
    cbar, x0, x1, a, m, d0 = dens
    ln10 = math.log(10.0)
    if x >= x1:
        return 2 * ln10 * x - cbar
    if x >= x0:
        return 2 * ln10 * x - cbar + a * (x1 - x) ** m
    return d0 * 10 ** (2 * (x - x0))


def effective_charge(z, beta):
    return z * (1.0 - math.exp(-125.0 * beta * z ** (-2.0 / 3.0)))


def mass_stopping(t_per_n, z, mat, a_ion=None):
    """Electronic mass stopping power [MeV cm2/g] of ion (Z, A) with kinetic
    energy t_per_n [MeV/nucleon] in material mat."""
    a_ion = a_ion or ATOMIC_MASS[z - 1]
    mn = mass_per_nucleon(z)
    gamma = 1.0 + t_per_n / mn
    b2 = 1.0 - 1.0 / (gamma * gamma)
    beta = math.sqrt(b2)
    zeff = effective_charge(z, beta)
    m_ion = a_ion * mn
    r = ME_MEV / m_ion
    tmax = 2 * ME_MEV * b2 * gamma * gamma / (1 + 2 * gamma * r + r * r)
    bg = beta * gamma
    delta = _density_delta(math.log10(bg), mat.dens)
    log_term = 0.5 * math.log(2 * ME_MEV * b2 * gamma * gamma * tmax
                              / (mat.i_mev ** 2))
    bracket = log_term - b2 - delta / 2.0
    return K_BETHE * zeff * zeff * mat.z_over_a / b2 * max(bracket, 0.0)


def let_si(t_per_n, z, a_ion=None):
    """LET in silicon [MeV cm2/mg]."""
    return mass_stopping(t_per_n, z, SILICON, a_ion) / 1000.0


def _log_grid(lo, hi, n):
    return [lo * (hi / lo) ** (k / (n - 1)) for k in range(n)]


class RangeTable:
    """CSDA range R(T) [g/cm2] of one ion species in a material."""

    def __init__(self, z, mat=ALUMINUM, a_ion=None, t_lo=0.1, t_hi=2e5,
                 n=2400):
        self.z = z
        self.a = a_ion or ATOMIC_MASS[z - 1]
        self.mat = mat
        self.ts = _log_grid(t_lo, t_hi, n)
        # dT/dx per nucleon = S_ion / A ; the first step is approximated
        # as a constant-S slab from 0 to t_lo (range of order microns).
        s0 = mass_stopping(self.ts[0], z, mat, self.a) / self.a
        rs = [self.ts[0] / s0]
        for k in range(1, n):
            t0, t1 = self.ts[k - 1], self.ts[k]
            s0 = mass_stopping(t0, z, mat, self.a) / self.a
            s1 = mass_stopping(t1, z, mat, self.a) / self.a
            rs.append(rs[-1] + 0.5 * (1 / s0 + 1 / s1) * (t1 - t0))
        self.rs = rs

    def range_of(self, t):
        return _interp(self.ts, self.rs, t, logy=False)

    def energy_of(self, r):
        if r >= self.rs[-1]:
            return None
        return _interp(self.rs, self.ts, r, logx=False)

    def stopping_per_nucleon(self, t):
        return mass_stopping(t, self.z, self.mat, self.a) / self.a


def _interp(xs, ys, x, logx=True, logy=True):
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    lo, hi = 0, len(xs) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if xs[mid] <= x:
            lo = mid
        else:
            hi = mid
    x0, x1, y0, y1 = xs[lo], xs[lo + 1], ys[lo], ys[lo + 1]
    if logx and x0 > 0:
        f = (math.log(x) - math.log(x0)) / (math.log(x1) - math.log(x0))
    else:
        f = (x - x0) / (x1 - x0)
    if logy and y0 > 0 and y1 > 0:
        return math.exp(math.log(y0) + f * (math.log(y1) - math.log(y0)))
    return y0 + f * (y1 - y0)


def interp_loglog(xs, ys, x):
    """Log-log interpolation inside the table; 0 outside it."""
    if x < xs[0] or x > xs[-1]:
        return 0.0
    return _interp(xs, ys, x)


def transport_spectrum(ts_in, flux_in, z, t_gcm2, t_out_lo=0.5,
                       t_out_hi=None, n_out=400):
    """Differential energy spectrum behind a spherical Al shell of t_gcm2.

    ts_in [MeV/n] strictly increasing, flux_in per (MeV/n) (any area/time/
    solid-angle unit; it is carried through). Returns (ts_out, flux_out).
    t_gcm2 <= 0 returns the input unchanged.
    """
    if t_gcm2 <= 0:
        return list(ts_in), list(flux_in)
    t_out_hi = t_out_hi or ts_in[-1]
    rt = RangeTable(z)
    out_t, out_f = [], []
    for t_out in _log_grid(t_out_lo, t_out_hi, n_out):
        t_in = rt.energy_of(rt.range_of(t_out) + t_gcm2)
        if t_in is None or t_in < ts_in[0] or t_in > ts_in[-1]:
            continue
        f_in = interp_loglog(ts_in, flux_in, t_in)
        # flux conservation: phi_out dT_out = phi_in dT_in,
        # dT_in/dT_out = S(T_in)/S(T_out) along a fixed path
        ratio = rt.stopping_per_nucleon(t_in) / rt.stopping_per_nucleon(t_out)
        out_t.append(t_out)
        out_f.append(f_in * ratio)
    return out_t, out_f
