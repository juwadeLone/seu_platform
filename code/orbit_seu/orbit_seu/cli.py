"""Command line interface: python -m orbit_seu <config.json> [-o outdir]."""
import argparse
import json
import sys

from .mission import run, write_report


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="orbit_seu",
        description="Estimate chip SEU rates for an arbitrary Earth orbit.")
    ap.add_argument("config", help="mission configuration JSON")
    ap.add_argument("-o", "--out", default=None,
                    help="output directory (default: ./orbit_seu_out)")
    args = ap.parse_args(argv)

    with open(args.config, "r", encoding="utf-8") as fh:
        config = json.load(fh)

    results = run(config)
    out_dir = args.out or "orbit_seu_out"
    report = write_report(results, config, out_dir)

    rpb = results["rates_per_s"]
    print(f"[orbit_seu] environment: {results['environment_type']}"
          + ("  **SYNTHETIC-DEMO **" if results["synthetic_environment"] else ""))
    print(f"[orbit_seu] SEU rate: {rpb['total_per_bit']:.3e} /s/bit "
          f"({rpb['total_per_bit']*86400:.3e} /day/bit)")
    if rpb["total_per_device"] is not None:
        print(f"[orbit_seu] per device: {rpb['total_per_device']*86400:.3e} /day")
    print(f"[orbit_seu] report: {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
