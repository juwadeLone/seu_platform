# Roadmap

Positioning: **SPENVIS tells you what radiation is on your orbit; this platform tells you what that radiation does to your design.** We build the downstream layer SPENVIS never had — layout, modules, functional consequences — and ingest SPENVIS outputs rather than re-deriving its environment models.

Principle that does not change: every number carries provenance; missing data is marked "gap", never invented.

## Phase 0 — packaging ✅ (this release)

- `pip install .` + `seu-platform` console script; all five pages served locally
- `orbit_seu` vendored into `code/orbit_seu` — no second clone or env var needed
- English-first README (中文 folded), MIT LICENSE, CI (unittest matrix Ubuntu + Windows, Python 3.10–3.13)
- Static demo on GitHub Pages: precomputed snapshots of all five pages

## Phase 1 — environment coverage

- **SPENVIS importer**: upload an orbit's `.let.txt` / proton spectrum exports → mission config → full consequence chain. Overnight, coverage = every orbit SPENVIS covers.
- **LEO proton chain**: wire the partially-filled `proton_7series_sigma_E.json` (Wirthlin K7 anchors) to AP8/AE9 trapped-proton flux. Biggest physics gap today; LEO/SAA is the most common real orbit.
- First new orbits: LEO (ISS-class) and GEO, alongside the current MEO.

## Phase 2 — device and design coverage

- Device library: second family (UltraScale or RTG4) + user-supplied σ(LET)/σ(E) tables.
- Design import: drop in your own `primitive_map.csv` (Vivado design checkpoint parse) instead of the bundled P1 FFT.
- English UI toggle for the five pages; docs site beyond README.

## Phase 3 — the layer SPENVIS doesn't have

- **Mitigation decision engine**: given a reliability target, recommend where TMR / ECC / scrubbing goes and at what rate — validated against `experiments/fault_injection_1024` (7 FFT architectures, frozen dataset).
- **Generic consequence engine**: user describes their design; flip → module → mission-outcome probability, not just SAR.
- Fault-injection as a product surface ("validate your ECC scheme").
- RHA-style report export: orbit → rates → strike consequences in one PDF/HTML document.

## Phase 4 — visibility

- PyPI release, landing page, benchmark comparisons vs winning-category tools, demo video.

## Honest scope

We do not aim to re-implement AP8/AE9, CREME96, SHIELDOSE inside this repo — SPENVIS exports flow in through the importer. The platform's contribution is everything after the spectrum.
