"""Convert a SPENVIS GCR flux file (spenvis_gcf.txt) into differential-LET
spectrum files behind a shield, for orbit_seu's 'files' environment mode.

INTERIM PATH. The standard route is SPENVIS's own CREME96 shielded LET
spectrum (TRANS + LETSPEC) for the mission orbit and shielding; when that
export is available it replaces these files. This script exists because the
workspace only holds the unshielded CREME96 ion energy spectra.

SPENVIS input layout (see the spenvis_gcf.txt header):
  data rows = Energy [MeV/n], 92x IFlux, 92x DFlux
  DFlux units: particles m^-2 s^-1 sr^-1 (MeV/n)^-1, species Z = 1..92

Per species:
  1. spherical-shell CSDA transport through `--shield-mil` of Al
     (default 100 mil, the CREME96 / Lee 2014 reference shielding);
  2. LET in Si from Bethe-Bloch with effective charge (orbit_seu.stopping);
     the old L = K Z^2 / beta^2 map had no Bragg peak (Fe up to 527
     MeV cm2/mg instead of ~29) and is retired;
  3. histogram into log-spaced LET bins. LET(E) is not monotonic (Bragg
     peak, relativistic rise), so every energy interval deposits its flux
     into the bin of its LET; this is exact in the fine-grid limit.
Omnidirectional flux: DFlux * 4 pi (isotropic) * 1e-4 (m^-2 -> cm^-2).

All 92 species are included and written as groups (H, He, Z3-10, Z11-20,
Z21-28, Z29-92) so the report can still break the rate down. A manifest.json
records the source orbit (parsed from the SPENVIS header), shielding, model
and hashes; orbit_seu.mission refuses to use these files for another orbit.

Usage: python scripts/spenvis_to_let.py [spenvis_gcf.txt] [outdir]
                                        [--shield-mil 100]
"""
import hashlib
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from orbit_seu.stopping import (ATOMIC_MASS, ELEMENTS, MIL_CM, ALUMINUM,  # noqa: E402
                                interp_loglog, let_si, transport_spectrum)

OMNI = 4.0 * math.pi * 1e-4   # sr -> 4pi, m^-2 -> cm^-2
NSP = 92
GROUPS = [("H", 1, 1), ("He", 2, 2), ("Z03-10", 3, 10), ("Z11-20", 11, 20),
          ("Z21-28", 21, 28), ("Z29-92", 29, 92)]
LET_LO, LET_HI, N_BINS = 1.0e-3, 2.0e2, 360     # MeV cm2/mg, ~3.5% bins
T_LO, T_HI, N_FINE = 0.5, 1.0e5, 6000           # MeV/n fine grid


def parse_tokens(path):
    toks = []
    for line in open(path, encoding="utf-8", errors="replace"):
        for piece in re.findall(r"'([^']*)'|([-+]?\d*\.?\d+[eE][-+]?\d+)", line):
            if piece[0]:
                toks.append(("L", piece[0].strip()))
            elif piece[1]:
                toks.append(("N", float(piece[1])))
    return toks


def parse_header(path):
    """Pick 'KEY', n, value lines such as 'ORB_APO',  1, 2.02E+04,'km'."""
    meta = {}
    pat = re.compile(r"^'([A-Z_]{3,8})',\s*-?\d+,\s*([^,]+),")
    for line in open(path, encoding="utf-8", errors="replace"):
        m = pat.match(line.strip())
        if m:
            meta.setdefault(m.group(1), m.group(2).strip().strip("'"))
    return meta


def read_spenvis_gcf(path):
    toks = parse_tokens(path)
    dstart = None
    for i in range(len(toks) - 1, 0, -1):
        if toks[i] == ("L", "SPECIES") and toks[i + 1][0] == "N":
            dstart = i + 1
            break
    if dstart is None:
        raise ValueError("no DFlux data block found")
    row_len = 1 + 2 * NSP
    data = toks[dstart:]
    nrows = len(data) // row_len
    energies, dflux = [], [[] for _ in range(NSP)]
    for r in range(nrows):
        row = data[r * row_len:(r + 1) * row_len]
        energies.append(row[0][1])
        for z in range(NSP):
            dflux[z].append(row[1 + NSP + z][1])
    return energies, dflux


def log_grid(lo, hi, n):
    return [lo * (hi / lo) ** (k / (n - 1)) for k in range(n)]


def species_let_histogram(ts, flux_omni, z, edges):
    """Deposit flux (per cm2 s) of each fine energy interval into LET bins."""
    hist = [0.0] * (len(edges) - 1)
    lo_e, hi_e = math.log(edges[0]), math.log(edges[-1])
    nb = len(hist)
    grid = [t for t in log_grid(max(T_LO, ts[0]), ts[-1], N_FINE)]
    fvals = [interp_loglog(ts, flux_omni, t) for t in grid]
    for k in range(len(grid) - 1):
        t0, t1 = grid[k], grid[k + 1]
        dphi = 0.5 * (fvals[k] + fvals[k + 1]) * (t1 - t0)
        if dphi <= 0:
            continue
        let = let_si(math.sqrt(t0 * t1), z)
        if let <= edges[0] or let >= edges[-1]:
            continue
        b = int((math.log(let) - lo_e) / (hi_e - lo_e) * nb)
        hist[min(max(b, 0), nb - 1)] += dphi
    return hist


def main(src, outdir, shield_mil):
    t_gcm2 = shield_mil * MIL_CM * ALUMINUM.rho
    energies, dflux = read_spenvis_gcf(src)
    meta = parse_header(src)
    edges = log_grid(LET_LO, LET_HI, N_BINS + 1)
    group_hist = {g[0]: [0.0] * N_BINS for g in GROUPS}
    group_flux = {g[0]: 0.0 for g in GROUPS}
    for zi in range(NSP):
        z = zi + 1
        fl = [v * OMNI for v in dflux[zi]]
        if not any(v > 0 for v in fl):
            continue
        # keep strictly positive support for log-log interpolation
        pts = [(e, v) for e, v in zip(energies, fl) if v > 0]
        ts = [p[0] for p in pts]
        fs = [p[1] for p in pts]
        ts_o, fs_o = transport_spectrum(ts, fs, z, t_gcm2)
        if len(ts_o) < 2:
            continue
        hist = species_let_histogram(ts_o, fs_o, z, edges)
        gname = next(g[0] for g in GROUPS if g[1] <= z <= g[2])
        for b in range(N_BINS):
            group_hist[gname][b] += hist[b]
        group_flux[gname] += sum(hist)

    os.makedirs(outdir, exist_ok=True)
    for f in os.listdir(outdir):           # drop stale species files
        if f.startswith("spenvis_") and f.endswith(".let.txt"):
            os.remove(os.path.join(outdir, f))
    written = {}
    for gname, zlo, zhi in GROUPS:
        # piecewise-constant per bin, written as two points per bin so a
        # trapezoid over the table reproduces the histogram (bin-centre
        # points would drop half of every edge bin)
        rows = []
        nz = [b for b in range(N_BINS) if group_hist[gname][b] > 0]
        if nz:
            for b in range(nz[0], nz[-1] + 1):
                y = group_hist[gname][b] / (edges[b + 1] - edges[b])
                rows.append((edges[b], y))
                rows.append((edges[b + 1] * (1 - 1e-6), y))
        if len(rows) < 2:
            continue
        out = os.path.join(outdir, f"spenvis_{gname}.let.txt")
        with open(out, "w", encoding="utf-8") as fh:
            fh.write("# differential LET spectrum from SPENVIS CREME96 GCR "
                     "(orbit_seu interim transport)\n")
            fh.write("# col0: LET in Si [MeV*cm^2/mg], col1: omni differential "
                     "flux [1/(cm^2 s (MeV*cm^2/mg))]; piecewise constant "
                     "per LET bin (two rows per bin)\n")
            fh.write(f"# group={gname} Z={zlo}..{zhi} "
                     f"({ELEMENTS[zlo - 1]}..{ELEMENTS[zhi - 1]})\n")
            fh.write(f"# shield: {shield_mil:g} mil Al spherical shell "
                     f"({t_gcm2:.4f} g/cm2), CSDA, no fragmentation\n")
            fh.write("# LET: Bethe-Bloch + Barkas effective charge + "
                     "Sternheimer density effect (orbit_seu.stopping)\n")
            fh.write(f"# integral omni flux: {group_flux[gname]:.6e} /cm2/s\n")
            for x, y in rows:
                fh.write(f"{x:.6e}  {y:.6e}\n")
        with open(out, "rb") as fh:
            written[gname] = {
                "file": os.path.basename(out), "Z": [zlo, zhi],
                "integral_flux_cm2_s": group_flux[gname],
                "sha256": hashlib.sha256(fh.read()).hexdigest()}

    with open(src, "rb") as fh:
        src_sha = hashlib.sha256(fh.read()).hexdigest()

    def num(key):
        try:
            return float(meta[key])
        except (KeyError, ValueError):
            return None

    manifest = {
        "source_file": os.path.basename(src),
        "source_sha256": src_sha,
        "source_model": meta.get("GCR_MOD"),
        "source_orbit": {
            "apogee_km": num("ORB_APO"), "perigee_km": num("ORB_PER"),
            "inclination_deg": num("ORB_INC"), "raan_deg": num("ORB_RAA"),
            "note": "parsed from the SPENVIS header; the spectra carry this "
                    "orbit's geomagnetic shielding",
        },
        "shielding": {"material": "Al", "thickness_mil": shield_mil,
                      "areal_density_g_cm2": t_gcm2,
                      "geometry": "spherical shell (CREME96 TRANS convention)",
                      "transport": "CSDA, no nuclear fragmentation"},
        "let_model": "Bethe-Bloch in Si, Barkas effective charge, Sternheimer "
                     "density effect; no shell/Bloch corrections",
        "flux_convention": "omnidirectional (4 pi) differential flux per cm2 s",
        "status": "interim; replace with SPENVIS CREME96 shielded LET "
                  "spectrum (TRANS+LETSPEC) when exported",
        "groups": written,
    }
    with open(os.path.join(outdir, "manifest.json"), "w",
              encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    print(f"wrote {len(written)} group spectra + manifest.json to {outdir}")
    for g, rec in written.items():
        print(f"  {g:7s} Z={rec['Z'][0]:2d}..{rec['Z'][1]:2d}  "
              f"flux {rec['integral_flux_cm2_s']:.4e} /cm2/s")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    shield = 100.0
    if "--shield-mil" in args:
        i = args.index("--shield-mil")
        shield = float(args[i + 1])
        del args[i:i + 2]
    src = args[0] if len(args) > 0 else \
        os.path.join(HERE, "..", "orbit_seu", "env_data", "spenvis_gcf.txt")
    outdir = args[1] if len(args) > 1 else \
        os.path.join(HERE, "..", "orbit_seu", "env_data", "spenvis_let")
    main(os.path.normpath(src), os.path.normpath(outdir), shield)
