"""End-to-end mission pipeline and reporting.

run(config) propagates the configured orbit, evaluates the geomagnetic
cutoff along the track, builds/loads the particle environment, integrates
SEU rates against the device cross-section model, and returns a results
dictionary. write_report() renders it as Markdown + JSON with full input
echo and SHA-256 provenance (workspace traceability rule).
"""
import json
import math
import os
import hashlib
from collections import Counter

from .orbit import OrbitElements, propagate_mission
from .magnetosphere import DipoleModel
from .spectra import Spectrum
from .device import (build_device_sigma, resolve_device,
                     WeibullLET, TableSigma)
from .rates import heavy_ion_rate_per_s, proton_rate_per_s, mission_stats
from .environment import (demo_gcr_let_spectra, load_spectrum_file,
                          sha256_of, DEMO_SYNTHETIC)


def _cfg_get(cfg, *keys, default=None):
    node = cfg
    for k in keys:
        if not isinstance(node, dict) or k not in node:
            return default
        node = node[k]
    return node


def run(config):
    # ---- orbit & magnetosphere -------------------------------------------
    orb_cfg = config["orbit"]
    orbit = OrbitElements(
        altitude_km=orb_cfg["altitude_km"],
        inclination_deg=orb_cfg["inclination_deg"],
        eccentricity=_cfg_get(orb_cfg, "eccentricity", default=0.001),
        raan_deg=_cfg_get(orb_cfg, "raan_deg", default=0.0),
        argp_deg=_cfg_get(orb_cfg, "argp_deg", default=0.0),
        mean_anomaly0_deg=_cfg_get(orb_cfg, "mean_anomaly0_deg", default=0.0),
    )
    g10 = _cfg_get(config, "magnetosphere", "g10_nt")
    dip = DipoleModel(
        g10=-29404.8 if g10 is None else g10,
        g11=-1450.9 if _cfg_get(config, "magnetosphere", "g11_nt") is None
            else _cfg_get(config, "magnetosphere", "g11_nt"),
        h11=4652.7 if _cfg_get(config, "magnetosphere", "h11_nt") is None
            else _cfg_get(config, "magnetosphere", "h11_nt"),
        cutoff_eq_gv=_cfg_get(config, "magnetosphere", "cutoff_eq_gv",
                              default=14.9),
    )
    n_orb = _cfg_get(config, "mission", "sampling", "orbits", default=24)
    n_pt = _cfg_get(config, "mission", "sampling", "points_per_orbit",
                    default=96)
    samples = propagate_mission(orbit, n_orb, n_pt)

    cutoffs, lvals = [], []
    for t, x, y, z in samples:
        cutoffs.append(dip.vertical_cutoff_gv(x, y, z))
        lvals.append(dip.mcilwain_l(x, y, z))

    # ---- device -----------------------------------------------------------
    dev_spec = resolve_device(config["device"])
    dev = build_device_sigma(dev_spec)
    bits = dev_spec.get("bits")

    # ---- environment ------------------------------------------------------
    env = config["environment"]
    env_types = env.get("type", "demo_gcr")
    if isinstance(env_types, str):
        env_types = [env_types]
    provenance = {}
    manifests = {}           # manifest.json next to imported LET files
    heavy_spectra = {}       # name -> Spectrum (LET differential)
    proton_spectrum = None
    synthetic = "demo_gcr" in env_types

    def average_over_cutoffs(spectra_by_cutoff):
        """Weighted average of LET spectra across quantized orbit cutoffs."""
        quant = Counter(round(c / 0.25) * 0.25 for c in cutoffs)
        total = sum(quant.values())
        acc = {}
        for cutoff, weight in quant.items():
            for name, sp in spectra_by_cutoff(cutoff).items():
                acc.setdefault(name, []).append((sp, weight / total))
        out = {}
        for name, lst in acc.items():
            lo = min(sp.xs[0] for sp, _ in lst)
            hi = max(sp.xs[-1] for sp, _ in lst)
            xs = [lo * (hi / lo) ** (k / 239.0) for k in range(240)]
            ys = [sum(w * sp(x) for sp, w in lst) for x in xs]
            out[name] = Spectrum(xs, ys)
        return out

    for env_type in env_types:
        if env_type == "demo_gcr":
            kappa = _cfg_get(env, "rigidity_cutoff", "kappa", default=1.0)
            heavy_spectra.update(
                average_over_cutoffs(
                    lambda c: demo_gcr_let_spectra(c, kappa=kappa)))
        elif env_type == "bo_gcr":
            # real model: force-field modulation + LIS coefficient file
            from .gcr_bo import (DEFAULT_COEF_PATH, let_spectra_from_gcr,
                                 load_lis_coefficients)
            kappa = _cfg_get(env, "rigidity_cutoff", "kappa", default=1.0)
            phi = _cfg_get(env, "phi_mv", default=600.0)
            csv_path = env.get("coefficients_csv",
                               os.path.normpath(DEFAULT_COEF_PATH))
            coeffs = load_lis_coefficients(csv_path)
            heavy_spectra.update(average_over_cutoffs(
                lambda c: let_spectra_from_gcr(coeffs, phi, c, kappa)))
            import hashlib as _h
            with open(csv_path, "rb") as fh:
                blob = fh.read()
            provenance["lis_coefficients"] = {
                "path": csv_path, "sha256": _h.sha256(blob).hexdigest(),
                "phi_mv": phi}
        elif env_type == "ae9ap9":
            from .ae9ap9 import build_ae9ap9_environment
            specs, prov2 = build_ae9ap9_environment(config, orbit)
            provenance["ae9ap9"] = prov2
            if "trapped_p" in specs:
                proton_spectrum = specs["trapped_p"]
        elif env_type == "files":
            let_files = _cfg_get(env, "let_spectra_files", default={}) or {}
            for name, rel in let_files.items():
                sp = load_spectrum_file(
                    rel,
                    x_col=_cfg_get(env, "let_columns", "let", default=0),
                    y_col=_cfg_get(env, "let_columns", "diff_flux", default=1))
                heavy_spectra[name] = sp
                provenance[rel] = sha256_of(rel)
            for mpath, man in _spectra_manifests(let_files.values()):
                _check_spectra_orbit(man, orb_cfg, mpath)
                manifests[mpath] = man
            rel = _cfg_get(env, "proton_file", default=None)
            if rel:
                proton_spectrum = load_spectrum_file(
                    rel,
                    x_col=_cfg_get(env, "proton_columns", "energy", default=0),
                    y_col=_cfg_get(env, "proton_columns", "diff_flux",
                                   default=1))
                provenance[rel] = sha256_of(rel)
        else:
            raise ValueError(f"unknown environment type: {env_type}")

    if not heavy_spectra and proton_spectrum is None:
        raise ValueError("environment produced no spectra")

    # ---- chart series (for the GUI) ---------------------------------------
    step = max(1, len(cutoffs) // 256)
    cutoff_series = [[round(k * step * orbit.period / max(len(cutoffs) - 1, 1) / 60.0, 3),
                      round(c, 4)] for k, c in enumerate(cutoffs[::step])]
    # 3D visual track in ECI: one Keplerian period is a closed planar ellipse.
    # Rate sampling stays in ECEF (Earth-fixed) so cutoff/SAA remain geographic.
    # Plotting that ECEF arc as a closed ring is wrong: Earth rotates ~15°/hour,
    # so the endpoints do not meet and stitching them drew a chord jump.
    Re = 6378.137
    track = []
    track_xyz = []
    vis_times = [j * orbit.period / n_pt for j in range(n_pt + 1)]  # include t=T
    for t in vis_times:
        xe, ye, ze = orbit.position_eci_km(t)
        xg, yg, zg = orbit.position_geo_km(t)
        lam = math.degrees(dip.magnetic_latitude_rad(xg, yg, zg))
        r_re = math.sqrt(xe * xe + ye * ye + ze * ze) / Re
        rc = round(dip.vertical_cutoff_gv(xg, yg, zg), 4)
        track.append([round(lam, 2), round(r_re, 4), rc])
        track_xyz.append([round(xe / Re, 4), round(ye / Re, 4),
                          round(ze / Re, 4), rc])

    # ---- rates ------------------------------------------------------------
    from .device import DomainWeibull
    _per_domain = None
    if isinstance(dev, DomainWeibull):
        # domain_rates_day returns /day/bit and Σ bits_d·rate_d,day.
        # rates_per_s and mission_stats expect /s; convert here.
        # Device count uses domain bits only — never divide by a separate
        # top-level device.bits (that field was a 55 Mbit placeholder).
        per_sp_day = dev.species_domain_rates_day(heavy_spectra)
        per_dom_day, heavy_dev_day = dev.domain_rates_day(heavy_spectra)
        domain_bits = sum(int(d["bits"]) for d in dev.domains.values()
                          if d.get("bits"))
        # Per-domain proton contribution: only domains carrying a
        # proton_sigma model participate (/s/bit for that domain).
        proton_per_dom_s = {}
        if proton_spectrum is not None:
            for name, d in dev.domains.items():
                if d.get("proton") is not None:
                    proton_per_dom_s[name] = proton_rate_per_s(
                        proton_spectrum, d["proton"])
        proton_dev_s = sum(proton_per_dom_s[n] *
                           int(dev.domains[n]["bits"] or 0)
                           for n in proton_per_dom_s)
        device_total_day = heavy_dev_day + proton_dev_s * 86400.0
        rate_per_device = device_total_day / 86400.0
        heavy_total = ((heavy_dev_day / 86400.0 / domain_bits)
                       if domain_bits
                       else sum(per_dom_day.values()) / 86400.0)
        proton_total = (proton_dev_s / domain_bits) if domain_bits else 0.0
        rate_per_bit = heavy_total + proton_total
        # per species group, same meaning as the single-group path: events/s
        # per bit (bit-weighted over domains), so x bits = device share
        per_species = {
            name: (sum(r_day * int(dev.domains[d]["bits"] or 0)
                       for d, r_day in row.items()) / 86400.0 / domain_bits)
            for name, row in per_sp_day.items()} if domain_bits else {}
        bits = domain_bits if domain_bits else bits
        _per_domain = {}
        for name, r_day in per_dom_day.items():
            d = dev.domains[name]
            b = int(d["bits"] or 0)
            p_s = proton_per_dom_s.get(name, 0.0)
            _per_domain[name] = {
                "bits": b,
                "rate_per_day_per_bit": r_day,
                "rate_per_s_per_bit": r_day / 86400.0,
                "rate_per_day": r_day * b,
                "rate_per_s": r_day * b / 86400.0,
                "proton_rate_per_s_per_bit": p_s,
                "proton_rate_per_day_per_bit": p_s * 86400.0,
                "proton_rate_per_day": p_s * 86400.0 * b,
                "proton_mode": d.get("proton_mode"),
                "proton_meta": d.get("proton_meta"),
            }
        _per_domain_rates = per_dom_day
    else:
        per_species = {}
        for name, sp in heavy_spectra.items():
            per_species[name] = heavy_ion_rate_per_s(sp, dev)
        heavy_total = sum(per_species.values())
        proton_total = (proton_rate_per_s(proton_spectrum, dev)
                        if proton_spectrum is not None else 0.0)
        rate_per_bit = heavy_total + proton_total
        rate_per_device = rate_per_bit * bits if bits else None
        _per_domain_rates = None

    duration_s = (_cfg_get(config, "mission", "duration_years", default=1.0)
                  * 365.25 * 86400.0)
    stats_bit = mission_stats(rate_per_bit, duration_s)
    stats_dev = (mission_stats(rate_per_device, duration_s)
                 if rate_per_device is not None else None)

    cfg_bytes = json.dumps(config, sort_keys=True).encode()
    return {
        "tool": "orbit_seu", "version": "0.1.0",
        "synthetic_environment": synthetic,
        "environment_type": "+".join(env_types),
        "orbit": {
            "altitude_km": orb_cfg["altitude_km"],
            "inclination_deg": orb_cfg["inclination_deg"],
            "eccentricity": orbit.e, "period_min": orbit.period / 60.0,
            "samples": len(samples),
        },
        "magnetosphere": {
            "pole": dip.pole_description,
            "cutoff_gv": {"min": min(cutoffs), "mean": sum(cutoffs) / len(cutoffs),
                          "max": max(cutoffs)},
            "mcilwain_l": {"min": min(lvals), "max": max(lvals)},
        },
        "device": {"description": dev.describe(), "bits": bits,
                   "library": dev_spec.get("_library")},
        "environment_summary": _environment_summary(heavy_spectra),
        "spectra_manifests": manifests,
        "per_domain_rates_day_per_bit": _per_domain_rates,
        "per_domain": _per_domain,
        "rates_per_s": {"per_species": per_species,
                        "heavy_ion_total": heavy_total,
                        "proton_total": proton_total,
                        "total_per_bit": rate_per_bit,
                        "total_per_device": rate_per_device},
        "mission": {"duration_years": duration_s / 365.25 / 86400.0,
                    "per_bit": stats_bit, "per_device": stats_dev},
        "series": {
            "cutoff_gv_vs_time_min": cutoff_series,
            "let_spectra": _spectra_series(heavy_spectra),
            "orbit_track_meridian": track,
            "orbit_track_xyz_re": track_xyz,
        },
        "provenance": {"config_sha256":
                       hashlib.sha256(cfg_bytes).hexdigest(),
                       "input_files": provenance},
        "notes": _limitations(env_types, manifests),
    }


def _interval_text(rate_per_day):
    days = 1.0 / max(rate_per_day, 1e-30)
    if days >= 1.0:
        return f"{days:.2f} 天"
    if days * 24 >= 1.0:
        return f"{days * 24:.2f} 小时"
    return f"{days * 1440:.1f} 分钟"


def _spectra_manifests(paths):
    """Yield (path, manifest) for each distinct manifest.json that sits next
    to the imported LET files (written by scripts/spenvis_to_let.py)."""
    seen = set()
    for rel in paths:
        mpath = os.path.join(os.path.dirname(os.path.abspath(rel)),
                             "manifest.json")
        if mpath in seen or not os.path.isfile(mpath):
            continue
        seen.add(mpath)
        with open(mpath, encoding="utf-8") as fh:
            yield mpath, json.load(fh)


def _check_spectra_orbit(manifest, orb_cfg, mpath, tol_km=1.0, tol_deg=0.1):
    """Imported spectra carry the geomagnetic shielding of the orbit they
    were generated for; refuse to reuse them for a different orbit."""
    src = manifest.get("source_orbit") or {}
    alt = src.get("apogee_km")
    inc = src.get("inclination_deg")
    if alt is None or inc is None:
        return
    per = src.get("perigee_km", alt)
    ok_alt = (abs(float(orb_cfg["altitude_km"]) - alt) <= tol_km
              and abs(per - alt) <= tol_km)
    ok_inc = abs(float(orb_cfg["inclination_deg"]) - inc) <= tol_deg
    if not (ok_alt and ok_inc):
        raise ValueError(
            f"imported LET spectra were generated for {alt:g} km / {inc:g} deg "
            f"(see {mpath}); the requested orbit is "
            f"{orb_cfg['altitude_km']} km / {orb_cfg['inclination_deg']} deg. "
            "Re-run SPENVIS for this orbit and re-convert; spectra are not "
            "transferable between orbits.")


def _environment_summary(spectra):
    """Particle intensity per species/group: omni integral flux and the
    flux above LET 1 and 10 MeV*cm^2/mg."""
    def above(sp, lmin):
        return sp.integrate_against(lambda L: 1.0 if L >= lmin else 0.0)
    out = {}
    for name, sp in spectra.items():
        out[name] = {"flux_cm2_s": sp.total_flux(),
                     "flux_let_ge_1_cm2_s": above(sp, 1.0),
                     "flux_let_ge_10_cm2_s": above(sp, 10.0),
                     "let_max": sp.xs[-1]}
    return out


def _spectra_series(spectra, n=50):
    out = {}
    for name, sp in spectra.items():
        lo, hi = sp.xs[0], sp.xs[-1]
        if hi <= lo:
            continue
        pts = []
        for k in range(n):
            x = lo * (hi / lo) ** (k / (n - 1))
            y = sp(x)
            if y > 0:
                pts.append([round(x, 6), round(y, 8)])
        if len(pts) >= 2:
            out[name] = pts
    return out


def _limitations(env_types, manifests=None):
    notes = [
        "Centered-dipole Størmer vertical cutoff (±20% vs multi-pole maps).",
        "First-order secular J2 propagation; no short-period terms.",
        ("Effective-LET thin-slab rate approximation (CREME86-era): "
         "R = (φ_omni/2)·<σ(L/cosθ)>, θ over 0–90° with the crossing-angle "
         "density 2cosθ·sinθ; full IRPP, funneling and MBU sharing are "
         "not modelled."),
    ]
    if "demo_gcr" in env_types:
        notes.append("DEMO spectra are SYNTHETIC and must not be used for "
                     "flight estimates; use bo_gcr / ae9ap9 / files modes "
                     "with real data for engineering work.")
    if "bo_gcr" in env_types:
        notes.append("GCR: force-field modulation + LIS coefficient file "
                     "(real model chain); LET mapping omits the Bethe log "
                     "term (low-beta LET underestimated ~2-3x).")
    if "ae9ap9" in env_types:
        notes.append("Trapped radiation from the AE9/AP9-IRENE public "
                     "package run; shielding inside the package defaults "
                     "to 0 mil Al unless configured there.")
    if "files" in env_types:
        notes.append("Environment read from user files; verify orbit/"
                     "shielding matching.")
        for mpath, man in (manifests or {}).items():
            sh = man.get("shielding") or {}
            orb = man.get("source_orbit") or {}
            notes.append(
                f"LET files ({os.path.basename(os.path.dirname(mpath))}): "
                f"{man.get('source_model') or 'SPENVIS'} spectra for "
                f"{orb.get('apogee_km')} km / {orb.get('inclination_deg')}°, "
                f"shield {sh.get('thickness_mil')} mil "
                f"{sh.get('material')} ({sh.get('transport')}); LET model: "
                f"{man.get('let_model')}. Status: {man.get('status')}.")
    notes.append("Environment is GCR only (solar minimum): solar particle "
                 "events (CREME96 worst week/day/5-min) are not included "
                 "unless an imported SPE/proton spectrum covers them.")
    notes.append("Proton contribution requires a measured sigma(E) table or "
                 "a single-energy anchor (reported as lower-bound).")
    return notes


def write_report(results, config, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    synth = ("**⚠ SYNTHETIC-DEMO ENVIRONMENT — 非工程数据，禁止用于任务评估**"
             if results["synthetic_environment"] else
             "Environment: imported files (see provenance).")
    rpb = results["rates_per_s"]
    lines = [
        "# orbit_seu — 芯片在轨 SEU 效应估算报告",
        "",
        f"- 工具版本: {results['tool']} v{results['version']}",
        f"- 环境类型: {results['environment_type']}  {synth}",
        "",
        "## 1. 轨道与磁场",
        f"- 轨道: 高度 {results['orbit']['altitude_km']} km, "
        f"倾角 {results['orbit']['inclination_deg']}°, "
        f"偏心率 {results['orbit']['eccentricity']}, "
        f"周期 {results['orbit']['period_min']:.2f} min, "
        f"采样点 {results['orbit']['samples']}",
        f"- {results['magnetosphere']['pole']}",
        f"- 垂直截止刚度 GV: min {results['magnetosphere']['cutoff_gv']['min']:.2f}"
        f" / mean {results['magnetosphere']['cutoff_gv']['mean']:.2f}"
        f" / max {results['magnetosphere']['cutoff_gv']['max']:.2f}",
        f"- McIlwain L: {results['magnetosphere']['mcilwain_l']['min']:.2f} ~ "
        f"{results['magnetosphere']['mcilwain_l']['max']:.2f}",
        "",
        "## 2. 粒子环境强度（全向积分通量）",
        "",
        "| 离子组 | 通量 /cm²/s | LET≥1 /cm²/s | LET≥10 /cm²/s | 最大 LET |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, row in (results.get("environment_summary") or {}).items():
        lines.append(
            f"| {name} | {row['flux_cm2_s']:.3e} | "
            f"{row['flux_let_ge_1_cm2_s']:.3e} | "
            f"{row['flux_let_ge_10_cm2_s']:.3e} | {row['let_max']:.1f} |")
    lines += [
        "",
        "## 3. 器件",
        f"- {results['device']['description']}",
        f"- 规模: {results['device']['bits']} bit"
        if results['device']['bits'] else "- 规模: 未给出（仅按归一化截面）",
        "",
        "## 4. SEU 事件率",
    ]
    per_domain = results.get("per_domain") or {}
    if per_domain:
        lines += [
            "",
            "器件次数 = Σ_d bits_d × (events/day/bit)_d，不用顶层占位 bits 去除。",
            "",
            "| 域 | bits | events/day/bit | events/day | events/s |",
            "|---|---:|---:|---:|---:|",
        ]
        for name, row in per_domain.items():
            lines.append(
                f"| {name} | {row['bits']:,} | "
                f"{row['rate_per_day_per_bit']:.3e} | "
                f"{row['rate_per_day']:.3e} | "
                f"{row['rate_per_s']:.3e} |")
        d = rpb["total_per_device"]
        tot_bits = results["device"]["bits"]
        lines.append(
            f"| **合计/器件** | **{tot_bits:,}** | "
            f"**{rpb['total_per_bit']*86400:.3e}** (bit 加权均) | "
            f"**{d*86400:.3e}** | **{d:.3e}** |")
        if any(r.get("proton_rate_per_s_per_bit")
               for r in per_domain.values()):
            lines += [
                "",
                "### 4.0a 域级质子贡献（导入谱 × 实测 σ(E)）",
                "",
                "| 域 | 质子 events/day/bit | 质子 events/day | σ(E) 模式 |",
                "|---|---:|---:|---|",
            ]
            for name, row in per_domain.items():
                if not row.get("proton_rate_per_s_per_bit"):
                    lines.append(
                        f"| {name} | — | — | 无实测质子 σ(E)，缺数据未计入 |")
                    continue
                mode = row.get("proton_mode") or "table"
                meta = row.get("proton_meta") or {}
                tag = ("lower-bound 下界" if mode == "lower_bound"
                       else mode)
                if meta.get("source"):
                    tag += f"；{meta['source']}"
                lines.append(
                    f"| {name} | {row['proton_rate_per_day_per_bit']:.3e} | "
                    f"{row['proton_rate_per_day']:.3e} | {tag} |")
            lines.append(
                "lower-bound：域仅有单能点实测 σ，只计入锚点能量以上的通量，"
                "结果为下界（低估）。")
        if rpb.get("per_species"):
            lines += [
                "",
                "### 4.0 分离子组贡献（整片 events/day）",
                "",
                "| 离子组 | events/day | 占比 |",
                "|---|---:|---:|",
            ]
            for name, r in rpb["per_species"].items():
                r_dev = r * tot_bits
                frac = r_dev / d if d else 0.0
                lines.append(f"| {name} | {r_dev*86400:.3e} | {frac*100:.1f}% |")
        dut = _cfg_get(config, "device", "dut_linear_reference")
        if dut and dut.get("bits"):
            lines += [
                "",
                "### 4.1 与 Lee DUT bits 线性对照",
                f"- DUT: {dut.get('part', 'Lee 2014 tested device')}；"
                f"{dut.get('source', '')}",
                "",
                "| 域 | DUT bits | DUT /day | 本器件 bits | 本器件 /day | bits 比 |",
                "|---|---:|---:|---:|---:|---:|",
            ]
            dut_total = 0.0
            for name, row in per_domain.items():
                db = int(dut["bits"].get(name, 0) or 0)
                dut_day = row["rate_per_day_per_bit"] * db
                dut_total += dut_day
                ratio = (row["bits"] / db) if db else float("nan")
                lines.append(
                    f"| {name} | {db:,} | {dut_day:.3e} | "
                    f"{row['bits']:,} | {row['rate_per_day']:.3e} | "
                    f"{ratio:.4f} |")
            vx_day = d * 86400.0
            scale = (vx_day / dut_total) if dut_total else float("nan")
            lines += [
                f"| **合计** | | **{dut_total:.3e}** | | "
                f"**{vx_day:.3e}** | **{scale:.4f}** |",
                "",
                "同一组 Weibull 与同一条谱下，器件次数只随 bits 线性变。",
            ]
        ref = _cfg_get(config, "device", "reference_rates_per_bit_day")
        if ref:
            lines += [
                "",
                "### 4.2 与文献在轨率对照（每 bit）",
                f"- 参照：{ref.get('source', '')}",
                "",
                "| 域 | 本次 /day/bit | 参照 /day/bit | 本次/参照 |",
                "|---|---:|---:|---:|",
            ]
            for name, row in per_domain.items():
                rv = ref.get(name)
                if not rv:
                    continue
                got = row["rate_per_day_per_bit"]
                lines.append(f"| {name} | {got:.3e} | {rv:.2e} | "
                             f"{got / rv:.2f} |")
            if ref.get("note"):
                lines += ["", ref["note"]]
    else:
        lines += [
            "| 来源 | 事件率 (events/s/bit) | (events/day/bit) |",
            "|---|---|---|",
        ]
        for name, r in rpb["per_species"].items():
            lines.append(f"| 重离子 {name} | {r:.3e} | {r*86400:.3e} |")
        if rpb["proton_total"]:
            lines.append(f"| 质子 | {rpb['proton_total']:.3e} | "
                         f"{rpb['proton_total']*86400:.3e} |")
        lines += [
            f"| **合计/bit** | **{rpb['total_per_bit']:.3e}** | "
            f"**{rpb['total_per_bit']*86400:.3e}** |",
        ]
        if rpb["total_per_device"] is not None:
            d = rpb["total_per_device"]
            lines.append(f"| 合计/器件 | {d:.3e} | {d*86400:.3e} |")
    m = results["mission"]
    lines += [
        "",
        "## 5. 任务期统计（泊松）",
        f"- 任务时长: {m['duration_years']:.2f} 年",
        f"- 每 bit 期望事件数: {m['per_bit']['expected_events']:.3e}, "
        f"P(≥1) = {m['per_bit']['prob_at_least_one']:.3e}",
    ]
    if m["per_device"]:
        lines.append(
            f"- 每器件期望事件数: {m['per_device']['expected_events']:.3e}, "
            f"P(≥1) = {m['per_device']['prob_at_least_one']:.3e}, "
            f"即约每 {_interval_text(m['per_device']['rate_per_day'])}一次")
    lines += ["", "## 6. 方法与局限", ""]
    lines += [f"- {n}" for n in results["notes"]]
    excluded = _cfg_get(config, "device", "excluded_domains") or {}
    for name, info in excluded.items():
        reason = info.get("reason", "no cross-section")
        extra = info.get("ds180_dsp_slices")
        slice_note = f"（DS180 DSP slices = {extra}）" if extra else ""
        lines.append(f"- 未计入 {name}{slice_note}: {reason}")
    lines += [
        "",
        "## 7. 溯源",
        f"- config SHA-256: `{results['provenance']['config_sha256']}`",
    ]
    for path, h in results["provenance"]["input_files"].items():
        lines.append(f"- `{path}` SHA-256: `{h}`")
    lines.append("")

    with open(os.path.join(out_dir, "report.md"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    with open(os.path.join(out_dir, "results.json"), "w",
              encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)
    return os.path.join(out_dir, "report.md")
