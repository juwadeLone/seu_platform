"""Convert a SPENVIS GCR flux export (spenvis_gcf.txt) into differential-LET
spectrum files behind a shield, for orbit_seu's 'files' environment mode.

INTERIM PATH. The standard route is SPENVIS's own CREME96 shielded LET
spectrum (TRANS + LETSPEC) for the mission orbit and shielding; when that
export is available it replaces these files. This module exists because the
workspace only holds the unshielded CREME96 ion energy spectra.

SPENVIS input layout (see the spenvis_gcf.txt header):
  data rows = Energy [MeV/n], 92x IFlux, 92x DFlux
  DFlux units: particles m^-2 s^-1 sr^-1 (MeV/n)^-1, species Z = 1..92

Per species:
  1. spherical-shell CSDA transport through `shield_mil` of Al
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
"""
import hashlib
import json
import math
import os
import re

from .stopping import (ATOMIC_MASS, ELEMENTS, MIL_CM, ALUMINUM,  # noqa: F401
                       interp_loglog, let_si, transport_spectrum)

OMNI = 4.0 * math.pi * 1e-4   # sr -> 4pi, m^-2 -> cm^-2
NSP = 92
GROUPS = [("H", 1, 1), ("He", 2, 2), ("Z03-10", 3, 10), ("Z11-20", 11, 20),
          ("Z21-28", 21, 28), ("Z29-92", 29, 92)]
LET_LO, LET_HI, N_BINS = 1.0e-3, 2.0e2, 360     # MeV cm2/mg, ~3.5% bins
T_LO, T_HI, N_FINE = 0.5, 1.0e5, 6000           # MeV/n fine grid


def parse_tokens(path):
    toks = []
    with open(path, encoding="utf-8", errors="replace") as _fh:
        lines = _fh.readlines()
    for line in lines:
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
    with open(path, encoding="utf-8", errors="replace") as _fh:
        lines = _fh.readlines()
    for line in lines:
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


def convert_gcf(src, outdir, shield_mil):
    """Convert one SPENVIS GCR export into LET-group spectra + manifest.

    Returns the manifest dict (also written to <outdir>/manifest.json).
    """
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
    return manifest


# ---------------------------------------------------------------------------
# Web-upload path: drop file texts in, get a ready-to-use 'files' environment
# block out. Shared by layout_ecc.serve (/oseu/api/import_spenvis) and the
# standalone orbit_seu.gui server (/api/import_spenvis).

MAX_UPLOAD_CHARS = 60_000_000   # ~60 MB of text per request part


def default_upload_root():
    return os.path.join(os.path.expanduser("~"),
                        ".seu_platform", "uploads")


def handle_import(body, upload_root=None):
    """Process one import request and return the response dict.

    body (JSON-decoded dict):
      gcf_text:   full SPENVIS GCR export text (spenvis_gcf.txt), or
      let_files:  {group_name: file_text} already-converted LET spectra
                  (requires 'orbit' + optional 'shield_mil' for the manifest),
      shield_mil: Al shielding for the GCF conversion (default 100),
      proton_text: optional differential proton spectrum file text,
      proton_columns: {"energy": 0, "diff_flux": 1} (optional),
      orbit:      {altitude_km, inclination_deg, raan_deg?} — only for the
                  manifest when raw let_files are given
    Returns {upload_dir, let_spectra_files(abs), proton_file(abs?),
             manifest, source_orbit, environment} — 'environment' splices
    straight into the mission config posted to the run endpoint.
    """
    from .environment import load_spectrum_file

    if not isinstance(body, dict):
        raise ValueError("body must be a JSON object")
    gcf_text = body.get("gcf_text")
    let_files = body.get("let_files") or {}
    proton_text = body.get("proton_text")
    shield_mil = float(body.get("shield_mil") or 100.0)
    if not gcf_text and not let_files and not proton_text:
        raise ValueError(
            "nothing to import: give gcf_text, let_files or proton_text")
    for tag, blob in (("gcf_text", gcf_text), ("proton_text", proton_text)):
        if blob and len(blob) > MAX_UPLOAD_CHARS:
            raise ValueError(f"{tag} exceeds size limit")

    import time as _time
    up = os.path.join(
        upload_root or default_upload_root(),
        _time.strftime("%Y%m%d-%H%M%S") + "_" +
        hashlib.sha256(os.urandom(8)).hexdigest()[:8])
    os.makedirs(up, exist_ok=True)

    environment = {"type": "files",
                   "let_spectra_files": {},
                   "let_columns": {"let": 0, "diff_flux": 1}}
    manifest = None
    source_orbit = None

    if gcf_text:
        gcf_path = os.path.join(up, "spenvis_gcf.txt")
        with open(gcf_path, "w", encoding="utf-8") as fh:
            fh.write(gcf_text)
        let_dir = os.path.join(up, "spenvis_let")
        manifest = convert_gcf(gcf_path, let_dir, shield_mil)
        source_orbit = manifest.get("source_orbit")
        for gname in manifest["groups"]:
            environment["let_spectra_files"][gname] = os.path.join(
                let_dir, f"spenvis_{gname}.let.txt")
    elif let_files:
        # raw per-group LET files; orbit must be stated so the manifest can
        # guard against orbit/spectra mismatch
        orb = body.get("orbit") or {}
        if (orb.get("altitude_km") is None
                or orb.get("inclination_deg") is None):
            raise ValueError(
                "let_files import needs 'orbit': {altitude_km, "
                "inclination_deg} of the orbit the spectra were made for")
        for gname, text in let_files.items():
            safe = "".join(c for c in str(gname)
                           if c.isalnum() or c in "._-")
            if not safe or len(text) > MAX_UPLOAD_CHARS:
                raise ValueError(f"bad let_files entry: {gname!r}")
            fp = os.path.join(up, f"{safe}.let.txt")
            with open(fp, "w", encoding="utf-8") as fh:
                fh.write(text)
            environment["let_spectra_files"][safe] = fp
        manifest = {
            "source_file": "user-uploaded let files",
            "source_orbit": {
                "apogee_km": float(orb["altitude_km"]),
                "perigee_km": float(orb["altitude_km"]),
                "inclination_deg": float(orb["inclination_deg"]),
                "raan_deg": orb.get("raan_deg"),
            },
            "shielding": {"thickness_mil": shield_mil,
                          "note": "user-declared; not verified"},
            "status": "uploaded via import endpoint",
        }
        source_orbit = manifest["source_orbit"]
        with open(os.path.join(up, "manifest.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(manifest, fh, ensure_ascii=False, indent=2)

    if proton_text:
        pp = os.path.join(up, "proton_spectrum.txt")
        with open(pp, "w", encoding="utf-8") as fh:
            fh.write(proton_text)
        environment["proton_file"] = pp
        pc = body.get("proton_columns") or {}
        environment["proton_columns"] = {
            "energy": int(pc.get("energy", 0)),
            "diff_flux": int(pc.get("diff_flux", 1))}

    # sanity: spectra must parse before paths go back to the client
    for name, fp in environment["let_spectra_files"].items():
        try:
            load_spectrum_file(fp)
        except Exception as exc:
            raise ValueError(f"LET file '{name}' failed to parse: {exc}")
    if environment.get("proton_file"):
        pc = environment["proton_columns"]
        load_spectrum_file(environment["proton_file"],
                           x_col=pc["energy"], y_col=pc["diff_flux"])

    return {
        "upload_dir": up,
        "let_spectra_files": environment["let_spectra_files"],
        "proton_file": environment.get("proton_file"),
        "manifest": manifest,
        "source_orbit": source_orbit,
        "environment": environment,
    }
