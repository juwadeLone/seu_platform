"""Run a deterministic headless strike campaign on the P1 baseline."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from .layout_import import load_primitive_map
from .strike import g4_presets, run_strike

_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_SCENARIO = _ROOT / "data" / "campaign_p1_smoke.json"
_BASELINE = _ROOT / "out_vx690t_measured" / "results.json"
_ORBIT_REV = _ROOT / "orbit-seu.rev"
_ORBIT_CONFIG = Path("examples/xc7vx690t_measured_meo.json")
_SCHEMA = "layout_ecc.campaign.v1"
_SCOPE = "Prescribed strikes, not draws from the orbit spectrum; no functional replay."
_MODELS = {
    "kernel_model": ("anchored", "legacy_linear"),
    "flip_model": ("weibull", "bernoulli", "pattern"),
}
_STRIKE_FIELDS = (
    "x0", "y0", "a0", "let", "theta_deg", "phi_deg", "k_let", "a", "b",
    "kernel_model", "area_um2", "rpm_to_um", "flip_model", "pattern_shape",
)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _file_info(path, label=None):
    with path.open("rb") as fh:
        digest = hashlib.sha256()
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return {"path": label or path.name, "sha256": digest.hexdigest()}


def _git(path, *args):
    return subprocess.check_output(
        ["git", "-C", str(path), *args], text=True, stderr=subprocess.DEVNULL,
    ).strip()


def _platform_revision():
    try:
        return {
            "commit": _git(_ROOT, "rev-parse", "HEAD"),
            "dirty": bool(_git(_ROOT, "status", "--porcelain", "--untracked-files=no")),
        }
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}


def _rate_snapshot(result):
    domains = result["per_domain_rates_day_per_bit"]
    return {
        "device_bit_upsets_per_day": result["rates_per_s"]["total_per_device"] * 86400,
        "per_domain_upsets_per_bit_day": {d: domains[d] for d in ("CRAM", "BRAM", "FF")},
    }


def _verify_rates(expected, computed):
    def values(snapshot):
        return [snapshot["device_bit_upsets_per_day"],
                *snapshot["per_domain_upsets_per_bit_day"].values()]

    if not all(math.isclose(a, b, rel_tol=1e-9) for a, b in
               zip(values(expected), values(computed), strict=True)):
        raise ValueError("live orbit rates do not match the frozen MEO baseline")


def _orbit_snapshot(live):
    rev = _ORBIT_REV.read_text(encoding="ascii").strip()
    frozen = _rate_snapshot(_read(_BASELINE))
    provenance = {
        "source": "frozen_snapshot",
        "orbit_seu_commit": rev,
        "baseline": _file_info(_BASELINE, "out_vx690t_measured/results.json"),
    }
    if not live:
        return {"rates": frozen, **provenance}

    root_arg = os.environ.get("ORBIT_SEU_ROOT")
    if not root_arg:
        raise ValueError("--live-orbit requires ORBIT_SEU_ROOT pointing at tcas/code/orbit_seu")
    root = Path(root_arg).resolve()
    if not (root / "orbit_seu" / "mission.py").is_file():
        raise ValueError("ORBIT_SEU_ROOT must point at tcas/code/orbit_seu")
    try:
        actual_rev = _git(root, "rev-parse", "HEAD")
        dirty = _git(root, "status", "--porcelain", "--untracked-files=all", "--", ".")
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("live orbit requires a Git checkout of the pinned tcas commit") from exc
    if actual_rev != rev or dirty:
        raise ValueError(f"live orbit requires clean tcas/code/orbit_seu at {rev}; got {actual_rev}")

    config_path = root / _ORBIT_CONFIG
    config = _read(config_path)
    spectra = [Path(p) for p in config["environment"]["let_spectra_files"].values()]
    manifests = sorted({p.parent / "manifest.json" for p in spectra})
    with tempfile.TemporaryDirectory() as temp:
        # Isolate upstream imports and its CWD-relative spectrum paths.
        cmd = [sys.executable, "-I", "-B", "-c",
               "import runpy, sys; sys.path.insert(0, '.'); "
               "runpy.run_module('orbit_seu', run_name='__main__', alter_sys=True)",
               _ORBIT_CONFIG.as_posix(), "-o", temp]
        proc = subprocess.run(cmd, cwd=root, capture_output=True, check=False)
        if proc.returncode != 0:
            raise ValueError(f"pinned orbit_seu exited with status {proc.returncode}")
        computed = _rate_snapshot(_read(Path(temp) / "results.json"))
    _verify_rates(frozen, computed)
    return {
        **provenance,
        "source": "live_verified",
        "rates": computed,
        "inputs": [_file_info(root / p, p.as_posix())
                   for p in [_ORBIT_CONFIG, *spectra, *manifests]],
    }


def _number(obj, key, lower=-math.inf, upper=math.inf):
    value = obj.get(key)
    if type(value) not in (int, float) or not math.isfinite(value) or not lower <= value <= upper:
        raise ValueError(f"invalid numeric field: {key}")
    return value


def _fields(obj, allowed):
    if not isinstance(obj, dict):
        raise ValueError("scenario and cases must be JSON objects")
    extra = obj.keys() - allowed
    if extra:
        raise ValueError(f"unknown fields: {', '.join(sorted(extra))}")


def _cases(config, layout):
    presets = g4_presets(layout)
    cases = config.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("cases must be a nonempty list")
    seen = set()
    for case in cases:
        _fields(case, {"id", "preset", "x0", "y0", "a0", "let", "theta_deg", "phi_deg", "seeds"})
        case_id = case.get("id")
        if not isinstance(case_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", case_id) or case_id in seen:
            raise ValueError("case id must be unique and use only letters, digits, _ and -")
        seen.add(case_id)
        if "preset" in case:
            preset = case["preset"]
            if (not isinstance(preset, str) or preset not in presets
                    or case.keys() & {"x0", "y0", "a0"}):
                raise ValueError(f"case {case_id}: provide a known preset or x0, y0 and a0")
            center = {k: presets[preset][k] for k in ("x0", "y0", "a0")}
        else:
            center = {"x0": _number(case, "x0"), "y0": _number(case, "y0"),
                      "a0": _number(case, "a0", lower=1e-6)}
        seeds = case.get("seeds")
        if (not isinstance(seeds, list) or not seeds
                or any(type(s) is not int or s < 0 for s in seeds)
                or len(seeds) != len(set(seeds))):
            raise ValueError(f"case {case_id}: seeds must be unique nonnegative integers")
        yield case_id, seeds, {
            **center, "let": _number(case, "let", lower=0),
            "theta_deg": _number(case, "theta_deg", 0, 75),
            "phi_deg": _number(case, "phi_deg", 0, 360),
        }


def run_campaign(scenario, out, *, live_orbit=False):
    scenario, out = Path(scenario), Path(out)
    config = _read(scenario)
    _fields(config, {"schema", "layout_csv", "golden_vector", "cases", *_MODELS})
    if config.get("schema") != _SCHEMA:
        raise ValueError(f"scenario schema must be {_SCHEMA}")
    models = {key: config.get(key) for key in _MODELS}
    for key, choices in _MODELS.items():
        if models[key] not in choices:
            raise ValueError(f"{key} must be one of {', '.join(choices)}")
    inputs = {"scenario": _file_info(scenario)}
    for name in ("layout_csv", "golden_vector"):
        value = config.get(name)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{name} must be a file path")
        path = scenario.parent / value
        inputs[name] = _file_info(path, path.name)
    if models["flip_model"] == "weibull":
        inputs["strike_cross_section"] = _file_info(
            _ROOT / "data" / "weibull_7series_measured.json")
    if models["kernel_model"] == "anchored":
        inputs["grid_calibration_reference"] = _file_info(
            _ROOT / "data" / "rpm_grid_calibration.json")
    layout = load_primitive_map(scenario.parent / config["layout_csv"])
    cases = list(_cases(config, layout))
    orbit = _orbit_snapshot(live_orbit)
    platform = _platform_revision()

    out.mkdir(parents=True, exist_ok=False)
    events_path = out / "events.jsonl"
    counts = dict(events=0, no_candidates=0, events_with_flips=0, bit_flips=0)
    with events_path.open("w", encoding="utf-8", newline="\n") as fh:
        for case_id, seeds, strike_args in cases:
            for seed in seeds:
                result = run_strike(layout, seed=seed, **strike_args, **models)
                event = {
                    "event_id": f"{case_id}/{seed}",
                    "case_id": case_id,
                    "seed": seed,
                    "strike": {k: result[k] for k in _STRIKE_FIELDS},
                    "n_candidates": result["n_candidates"],
                    "n_bits_flipped": result["n_bits_flipped"],
                    "flipped": result["flipped"],
                }
                fh.write(_json(event) + "\n")
                counts["events"] += 1
                counts["no_candidates"] += result["n_candidates"] == 0
                counts["events_with_flips"] += result["n_bits_flipped"] > 0
                counts["bit_flips"] += result["n_bits_flipped"]

    manifest = {
        "schema": _SCHEMA,
        "scope": _SCOPE,
        "platform": platform,
        "python_version": sys.version.split()[0],
        "device_part": layout["part"],
        "inputs": inputs,
        "models": models,
        "orbit": orbit,
        "counts": counts,
        "events": _file_info(events_path),
    }
    (out / "run_manifest.json").write_text(_json(manifest) + "\n", encoding="utf-8", newline="\n")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=Path, default=_DEFAULT_SCENARIO)
    parser.add_argument("--out", type=Path, required=True, help="new output directory")
    parser.add_argument("--live-orbit", action="store_true",
                        help="require pinned ORBIT_SEU_ROOT and verify the frozen rates")
    args = parser.parse_args(argv)
    try:
        manifest = run_campaign(args.scenario, args.out, live_orbit=args.live_orbit)
    except (OSError, KeyError, ValueError) as exc:
        parser.exit(2, f"campaign: {exc}\n")
    rates = manifest["orbit"]["rates"]["device_bit_upsets_per_day"]
    print(f"{manifest['orbit']['source']}: {rates:.6f} bit upsets/day; "
          f"{manifest['counts']['events']} prescribed strikes; {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
