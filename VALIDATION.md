# Delivery validation — 2026-11-18

Edition: sao-paulo-energy-geolab
Environment: Linux, Python 3.12.14.

- 26/26 unit and HTTP API tests passed in each edition.
- Tested using the exact primary package versions in requirements.txt.
- Resolved dependency versions are recorded in requirements-lock.txt.
- JavaScript syntax checked with node --check (shared script for both editions).
- Tests include geodesic reference distance, identity, symmetry, measurement
  endpoints, ranking, empty candidates, cross-state candidates, provenance,
  scope rejection, invalid geometry, missing capacity, duplicates, request size,
  content type and API response checks.
- ZIP member CRCs verified after packaging.

Limitations:
- Browser automation was attempted but Chromium could not start because this
  execution environment disallowed a required process socket. Visual rendering,
  live map tile access and interactive browser flows were not validated here.
- Windows BAT launchers are supplied but were not executed on Windows here.
- No real national energy inventory, electrical topology or field validation.
- Demo assets and routes are synthetic.

Run TEST.bat locally after installation to repeat backend/API tests.
