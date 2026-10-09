"""Honest radiation-effects coverage (v1.1.0).

Loads data/effects_coverage.json, attaches the existing MEO SEU freeze
(without recomputing a spectrum), proton single-energy anchors (not a
rate), and a TID file slot. Never invents TID/TNID/SEL numbers.
"""
from __future__ import annotations

import json
import os

from .paths import data_dir as _data_dir

_DATA = _data_dir()
_TABLE_NAME = "effects_coverage.json"
_PROTON_NAME = "proton_7series_sigma_E.json"
_TID_DIRNAME = "tid"
_TID_SKIP = {"readme.md", "readme.txt", ".gitkeep"}
_TID_EXTS = {".json", ".txt", ".dat", ".dose"}


def data_dir() -> str:
    return _DATA


def table_path() -> str:
    return os.path.join(_DATA, _TABLE_NAME)


def load_table() -> dict:
    with open(table_path(), "r", encoding="utf-8") as fh:
        return json.load(fh)


def _frozen_seu_snapshot(table: dict) -> dict:
    """Replay freeze numbers already in orbit_env; do not call mission.run()."""
    origin = "effects_coverage.json"
    snap = dict(table.get("frozen_seu_hi") or {})
    try:
        import orbit_env  # optional; desktop path only
    except Exception:
        orbit_env = None
    payload = getattr(orbit_env, "_ORBIT_PAYLOAD", None) if orbit_env else None
    if isinstance(payload, dict):
        frozen = payload.get("_frozen_baseline")
        if isinstance(frozen, dict) and frozen.get("device_events_per_day") is not None:
            bits = snap.get("bits_by_domain")
            snap = dict(frozen)
            if bits and "bits_by_domain" not in snap:
                snap["bits_by_domain"] = bits
            origin = "orbit_env._ORBIT_PAYLOAD._frozen_baseline"
    snap["_origin"] = origin
    snap["_spectrum_recomputed"] = False
    return snap


def _proton_facts(table: dict) -> dict:
    facts = dict(table.get("proton_anchored_facts") or {})
    path = os.path.join(_DATA, _PROTON_NAME)
    facts["_file_present"] = os.path.isfile(path)
    facts["_file"] = _PROTON_NAME if facts["_file_present"] else None
    if not facts["_file_present"]:
        return facts
    try:
        with open(path, "r", encoding="utf-8") as fh:
            proton = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        facts["_file_read_error"] = f"{type(exc).__name__}: {exc}"
        return facts
    per = (proton.get("per_domain") or {})
    for dom in ("CRAM", "BRAM"):
        pts = ((per.get(dom) or {}).get("sigma_cm2_per_bit_vs_E")) or []
        if pts and isinstance(pts[0], dict):
            facts[dom] = {
                "E_mev": pts[0].get("E_mev"),
                "sigma_cm2_per_bit": pts[0].get("sigma_cm2_per_bit"),
                "source": pts[0].get("source"),
            }
    return facts


def _parse_tid_json(obj):
    """Return the object as-is; pick up dose-like keys only if they exist."""
    found = []

    def walk(node, prefix=""):
        if isinstance(node, dict):
            for k, v in node.items():
                key = f"{prefix}.{k}" if prefix else str(k)
                kl = str(k).lower()
                if isinstance(v, (int, float)) and any(
                    tok in kl for tok in ("dose", "krad", "gray", "gy", "rad")
                ):
                    found.append({"key": key, "value": v, "from_file": True})
                else:
                    walk(v, key)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{prefix}[{i}]")

    walk(obj)
    return found


def parse_tid_file(path: str) -> dict:
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()
    out = {
        "file": name,
        "parsed": False,
        "reason": None,
        "records": [],
        "note": "numbers copied from the file; units left as written; not converted; not computed from LET",
    }
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            raw = fh.read()
    except OSError as exc:
        out["reason"] = f"{type(exc).__name__}: {exc}"
        return out
    if ext == ".json":
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            out["reason"] = f"json: {exc}"
            return out
        out["parsed"] = True
        out["json"] = obj
        out["records"] = _parse_tid_json(obj)
        return out
    header_hit = any(s in raw.upper() for s in ("SHIELDOSE", "SPENVIS", "DOSE"))
    rows = []
    for line in raw.splitlines():
        s = line.strip()
        if not s or s[:1] in "*#!;":
            continue
        parts = s.replace(",", " ").split()
        nums = []
        for p in parts:
            try:
                nums.append(float(p))
            except ValueError:
                continue
        if len(nums) >= 2:
            rows.append({"raw": s, "numbers_from_file": nums})
    if rows:
        out["parsed"] = True
        out["records"] = rows
        out["header_hit"] = header_hit
    else:
        out["reason"] = "no numeric table rows found"
        out["header_hit"] = header_hit
    return out


def scan_tid_slot() -> dict:
    tid_dir = os.path.join(_DATA, _TID_DIRNAME)
    slot = {
        "dir": "data/tid/",
        "status": "MISSING",
        "files": [],
        "parsed": [],
        "note": "no SPENVIS/SHIELDOSE json/txt under data/tid/; TID remains data_missing. Do not compute krad from LET files.",
    }
    if not os.path.isdir(tid_dir):
        return slot
    names = []
    for name in sorted(os.listdir(tid_dir)):
        if name.lower() in _TID_SKIP or name.startswith("."):
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext in _TID_EXTS:
            names.append(name)
    if not names:
        return slot
    parsed = [parse_tid_file(os.path.join(tid_dir, n)) for n in names]
    any_ok = any(p.get("parsed") for p in parsed)
    slot["files"] = names
    slot["parsed"] = parsed
    slot["status"] = "file_present" if any_ok else "unparsed_file"
    slot["note"] = (
        "dose numbers below are copied from the dropped file(s); "
        "software still does not simulate TID damage."
    )
    return slot


def build_effects_payload() -> dict:
    table = load_table()
    tid_slot = scan_tid_slot()
    effects = []
    for row in table.get("effects") or []:
        row = dict(row)
        if row.get("id") == "tid":
            row["tid_slot"] = {
                "status": tid_slot["status"],
                "files": tid_slot["files"],
            }
            # A dropped dose file is display-only; never upgrade to simulating.
            row["status"] = "data_missing"
        effects.append(row)
    return {
        "version": table.get("version") or "1.1.0",
        "schema": table.get("schema"),
        "honesty": table.get("honesty"),
        "effects": effects,
        "seu_hi_snapshot": _frozen_seu_snapshot(table),
        "proton_anchored_facts": _proton_facts(table),
        "tid_slot": tid_slot,
    }


def required_effect_ids():
    return (
        "tid", "tnid", "seu_hi", "seu_dsp", "seu_proton",
        "mbu", "set", "sefi", "sel", "seb", "segr",
    )
