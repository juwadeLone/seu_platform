"""Design-agnostic module grouping from Vivado hierarchy names.

The strike viewer must not assume what the design is (FFT stages, a SAR
processor, a CPU ...). Modules are taken from the netlist hierarchy itself:
the shallowest hierarchy depth that splits the placed primitives into
2..32 groups. Each Site gets the majority module of its primitives.
"""
import colorsys
import re
from collections import Counter


def natural_key(s):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s or "")]


def pick_depth(hiers, max_depth=4, lo=2, hi=32):
    """Shallowest depth whose prefixes give lo..hi distinct modules."""
    for d in range(1, max_depth + 1):
        c = Counter(prefix(h, d) for h in hiers if h)
        c.pop("(top)", None)
        if lo <= len(c) <= hi:
            return d
    return 1


def prefix(hier, depth):
    parts = (hier or "").split("/")
    return "/".join(parts[:depth]) if len(parts) > depth else "(top)"


def module_color(i, n):
    r, g, b = colorsys.hsv_to_rgb((i / max(n, 1)) % 1.0, 0.56, 0.88)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def build_modules(site_hiers, depth):
    """site_hiers: {site_key: [hier_cell, ...]} -> (site_key -> path, list)."""
    site_mod = {}
    counts = Counter()
    for key, hiers in site_hiers.items():
        c = Counter(prefix(h, depth) for h in hiers if h)
        path = c.most_common(1)[0][0] if c else "(top)"
        site_mod[key] = path
        counts[path] += 1
    paths = sorted(counts, key=natural_key)
    names = [p.split("/")[-1] for p in paths]
    dup = {n for n, k in Counter(names).items() if k > 1}
    mods = []
    for i, p in enumerate(paths):
        name = p if p.split("/")[-1] in dup else p.split("/")[-1]
        mods.append({"id": i, "path": p, "name": name, "n_sites": counts[p],
                     "color": module_color(i, len(paths))})
    return site_mod, mods
