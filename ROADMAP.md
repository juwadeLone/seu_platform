# Roadmap

Positioning: **SPENVIS tells you what radiation is on your orbit; this platform tells you what that radiation does to your design.** We build the downstream layer SPENVIS never had — layout, modules, functional consequences — and ingest SPENVIS outputs rather than re-deriving its environment models.

Principle that does not change: every number carries provenance; missing data is marked "gap", never invented.

## Phase 0 — packaging ✅ (this release)

- `pip install .` + `seu-platform` console script; all five pages served locally
- `orbit_seu` vendored into `code/orbit_seu` — no second clone or env var needed
- English-first README (中文 folded), MIT LICENSE, CI (unittest matrix Ubuntu + Windows, Python 3.10–3.13)
- Static demo on GitHub Pages: precomputed snapshots of all five pages

## Phase 1 — environment coverage ✅ (in progress → mostly done)

- ✅ **SPENVIS importer** (`orbit_seu.spenvis_import` + `POST /oseu/api/import_spenvis` + orbit-page import panel): drop `spenvis_gcf.txt` / per-group `.let.txt` / a proton spectrum → files land under `~/.seu_platform/uploads`, orbit elements lock from the manifest, and the returned environment block splices straight into a mission run. Coverage = every orbit SPENVIS covers.
- ✅ **LEO proton chain wired**: `DomainWeibull` now takes per-domain `proton_sigma` models — `anchor_E_mev` (measured single-energy point → labelled *lower bound*), `table`, or `file`. CRAM/BRAM carry Wirthlin JINST 2014 180 MeV anchors; FF/DSP stay honest gaps. Per-domain proton rates join the mission totals and the report's new "域级质子贡献" section.
- ✅ Orbit presets cover SSO / ISS-class LEO / MEO / GEO; `examples/xc7vx690t_leo_iss_proton_template.json` is the fill-in ISS mission.
- ⚠️ Remaining P1 gap: a *citable* ISS-class trapped-proton spectrum is not bundled (no fabricated data — import your own SPENVIS AP8/TRP export), and energy-resolved proton σ(E) beyond the 180 MeV anchor is still open.

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
