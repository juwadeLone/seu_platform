"""CLI wrapper for orbit_seu.spenvis_import.convert_gcf.

The conversion itself lives in the package (orbit_seu.spenvis_import) so the
web importer (/oseu/api/import_spenvis) and this script share one code path.

Usage: python scripts/spenvis_to_let.py [spenvis_gcf.txt] [outdir]
                                        [--shield-mil 100]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from orbit_seu.spenvis_import import convert_gcf  # noqa: E402


def main(src, outdir, shield_mil):
    manifest = convert_gcf(src, outdir, shield_mil)
    written = manifest["groups"]
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
