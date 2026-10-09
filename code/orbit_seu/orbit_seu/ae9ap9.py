"""AE9/AP9-IRENE public package runner (trapped radiation, real data).

The US AFRL/SET distributes the AE9/AP9-IRENE model (v1.50.x) as a public
package containing the `ae9ap9` executable plus binary data files. This
module drives that executable in "RunOnDemand" mode:

  1. propagate the configured orbit into an ephemeris text file
     (time, geodetic lat/lon/alt);
  2. invoke the executable once per requested species (protons/electrons)
     with configurable CLI arguments;
  3. parse the output flux files into Spectrum objects (energy-differential
     trapped flux, orbit-averaged or time-resolved).

No flux numbers are bundled or invented here: everything comes from the
user-provided public package. Paths and column formats are configurable
because package minor versions differ; defaults follow the v1.50
RunOnDemand documentation.
"""
import os
import re
import shutil
import subprocess

from .spectra import Spectrum


class Ae9Ap9Error(RuntimeError):
    pass


def find_executable(search_paths):
    for p in search_paths:
        if p and os.path.isfile(p):
            return p
    found = shutil.which("ae9ap9") or shutil.which("ae9ap9.exe")
    if found:
        return found
    raise Ae9Ap9Error(
        "ae9ap9 executable not found. Install the public AE9/AP9-IRENE "
        "package (v1.50, AFRL/SET) and set environment.ae9ap9.exe_path "
        "in the mission config. See env_data/README.md.")


def write_ephemeris(orbit, path, n_points=721, duration_s=None):
    """Write an AE9/AP9 RunOnDemand ephemeris: YYYY DDD HHMMSS  lat  lon  alt.

    One full orbital period by default (n_points samples), which the model
    orbit-averages. Geodetic approximated as geocentric (documented).
    """
    duration = duration_s or orbit.period
    lines = []
    epoch_day = 1
    for k in range(n_points):
        t = duration * k / (n_points - 1)
        x, y, z = orbit.position_geo_km(t)
        r = (x * x + y * y + z * z) ** 0.5
        lat = 90.0 - _safe_deg_acos(z / r)
        lon = _wrap180(_safe_deg_atan2(y, x))
        alt = r - 6378.137
        sec = t
        hh = int(sec // 3600)
        mm = int((sec % 3600) // 60)
        ss = sec % 60
        lines.append(f"2026 {epoch_day:03d} {hh:02d}{mm:02d}{ss:07.4f} "
                     f"{lat:9.5f} {lon:9.5f} {alt:11.5f}")
    with open(path, "w", encoding="ascii") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


def _safe_deg_acos(v):
    v = max(-1.0, min(1.0, v))
    import math
    return math.degrees(math.acos(v))


def _safe_deg_atan2(y, x):
    import math
    return math.degrees(math.atan2(y, x))


def _wrap180(lon):
    while lon > 180.0:
        lon -= 360.0
    while lon < -180.0:
        lon += 360.0
    return lon


def run_species(exe_path, ephem_path, out_dir, species, config_env):
    """Run the executable once. CLI default follows v1.50 RunOnDemand:
    ae9ap9 -c 1 (RunOnDemand) -p <ephem file> -t <species p/e>
             -o <output prefix> ... configurable via extra_args.
    Returns the first flux file produced (sorted, .txt/.flux).
    """
    os.makedirs(out_dir, exist_ok=True)
    prefix = os.path.join(out_dir, f"ae9ap9_{species}")
    args = [exe_path] + config_env.get("ae9ap9", {}).get("cli_args", [
        "-c", "1",
        "-p", ephem_path,
        "-t", species,
        "-o", prefix,
    ])
    try:
        proc = subprocess.run(args, capture_output=True, text=True,
                              timeout=config_env.get("ae9ap9", {}).get(
                                  "timeout_s", 900),
                              cwd=os.path.dirname(exe_path) or None)
    except FileNotFoundError as exc:
        raise Ae9Ap9Error(f"failed to launch {exe_path}: {exc}")
    if proc.returncode != 0:
        raise Ae9Ap9Error(
            f"ae9ap9 exited {proc.returncode}: "
            f"{(proc.stderr or proc.stdout)[-400:]}")
    produced = sorted(
        f for f in os.listdir(out_dir)
        if f.startswith(f"ae9ap9_{species}") and
        os.path.splitext(f)[1].lower() in (".txt", ".flux", ".csv", ".dat"))
    if not produced:
        raise Ae9Ap9Error(f"no output files produced in {out_dir}")
    return os.path.join(out_dir, produced[0])


_NUM = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


def parse_flux_file(path, energy_col=0, flux_col=1):
    """Parse an AE9/AP9 flux output table.

    Two supported layouts (auto-detected):
      A) simple two+ column table: energy [MeV], flux [1/cm2 s MeV]  -> Spectrum
      B) time-major table with a header row of energy bin centers:
         first data column = time tag, following columns = fluxes at
         energies; the table is averaged over rows into a single Spectrum.
    """
    rows = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            s = line.strip()
            if not s or s[0] in "#%!;":
                continue
            vals = [float(m.group()) for m in _NUM.finditer(
                s.replace(",", " "))]
            if vals:
                rows.append(vals)
    if not rows:
        raise Ae9Ap9Error(f"no numeric rows in {path}")
    # Layout B detection: header energies strictly increasing, col0 looks
    # like a monotonically increasing time tag with many duplicates col-wise
    header = rows[0]
    if (len(header) >= 3 and all(header[i] < header[i + 1]
                                 for i in range(1, len(header) - 1))
            and len(rows) > 1 and all(r[0] >= rows[0][0] - 1e-9
                                      for r in rows)):
        energies = header[1:]
        n = len(energies)
        sums = [0.0] * n
        cnt = 0
        for r in rows[1:]:
            if len(r) < n + 1:
                continue
            for i in range(n):
                sums[i] += r[i + 1]
            cnt += 1
        if cnt:
            xs, ys = [], []
            for i in range(n):
                if energies[i] > 0 and sums[i] >= 0:
                    xs.append(energies[i])
                    ys.append(sums[i] / cnt)
            return Spectrum(xs, ys)
    # Layout A: filter to rows with enough columns
    xs = [r[energy_col] for r in rows if len(r) > max(energy_col, flux_col)]
    ys = [r[flux_col] for r in rows if len(r) > max(energy_col, flux_col)]
    pairs = sorted((x, y) for x, y in zip(xs, ys) if x > 0 and y >= 0)
    if len(pairs) < 2:
        raise Ae9Ap9Error(f"cannot parse flux table {path}")
    return Spectrum([p[0] for p in pairs], [p[1] for p in pairs])


def build_ae9ap9_environment(config, orbit):
    """Run trapped-proton (+optional electron) fluxes for the mission orbit.

    config.environment keys:
      ae9ap9: {exe_path, work_dir, species: ["p"], extra_args per run if
               provided via cli_args, timeout_s}
      proton_energy_col / proton_flux_col: output table column indices.
    Returns ({"trapped_p": Spectrum, ...}, provenance dict).
    """
    import hashlib
    env = config["environment"]
    cfg = env.get("ae9ap9", {})
    exe = find_executable([cfg.get("exe_path", ""),
                           os.path.join(os.path.dirname(__file__),
                                        "env_data", "ae9ap9", "ae9ap9.exe")])
    work = cfg.get("work_dir", os.path.join(
        os.path.dirname(__file__), "env_data", "ae9ap9", "runs"))
    work = os.path.normpath(work)
    os.makedirs(work, exist_ok=True)
    ephem = write_ephemeris(orbit, os.path.join(work, "ephem.txt"),
                            n_points=cfg.get("ephem_points", 721))
    species_list = cfg.get("species", ["p"])
    out = {}
    prov = {"exe": exe, "ephemeris": ephem, "sha256": {}}
    for sp in species_list:
        f = run_species(exe, ephem, work, sp, env)
        spec = parse_flux_file(
            f,
            energy_col=env.get("proton_energy_col", 0),
            flux_col=env.get("proton_flux_col", 1))
        out[f"trapped_{sp}"] = spec
        with open(f, "rb") as fh:
            prov["sha256"][os.path.basename(f)] = \
                hashlib.sha256(fh.read()).hexdigest()[:16]
    return out, prov
