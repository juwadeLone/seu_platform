# orbit_seu (vendored)

Orbit-environment engine: mission sampling → geomagnetic cutoff → LET spectra
per species → per-domain and whole-device upset rates. Vendored from
[juwadeLone/tcas](https://github.com/juwadeLone/tcas) `code/orbit_seu` so this
platform installs and runs standalone.

Layout after vendoring (package-internal resources, so a wheel stays
self-contained):

```
orbit_seu/
  orbit_seu/            the package
    env_data/           bundled environment data (spenvis_let/, ae9ap9/, gcr/, ...)
    examples/           mission configs (xc7vx690t_measured_meo.json, ...)
    webapp/             orbit dashboard + 3D pages
  scripts/              spectrum conversion / coefficient tooling
  tests/                34 unit tests
```

`layout_ecc.orbit_env` resolves this copy first (before `ORBIT_SEU_ROOT`, an
installed package, or the original tcas path), so from a source checkout no
configuration is needed. `downloads/` from the source tree (22 MB of fetched
references) is not vendored.
