# Sao Paulo Energy GeoLab

Educational local application. Interface and code in English.

## Windows quick start
1. Extract the ZIP completely to a writable folder (not inside the ZIP).
2. Install Python 3.11 or 3.12 with the Windows Python launcher.
3. Double-click INSTALL.bat once; internet access is required for dependencies.
4. Double-click TEST.bat to run the included 26 backend/API tests.
5. Double-click START.bat and keep the terminal window open.
6. Open http://127.0.0.1:8001 in your browser.
7. Press Ctrl+C in the terminal to stop.

If Windows hides file extensions, enable View > Show > File name extensions.
PyCharm: open this folder and select .venv/Scripts/python.exe as interpreter.
No environment activation is required.

Manual PowerShell commands, from this folder:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest -v
.\.venv\Scripts\python.exe app.py
```

If the port is occupied, use `python app.py --port 8010` with the same interpreter.
Both editions run independently on different ports.

## Included functions
- MapLibre map with OpenStreetMap basemap; plants, substations and line layers.
- Region, state, municipality and generation-source filters.
- Asset details including source date and provenance.
- Five nearest substations, WGS84 ellipsoidal distances using GeographicLib.
- State comparisons, known installed MW and missing-capacity counts.
- GeoJSON import/export, CSV results and JSON report with normalized-dataset SHA-256.
- Strict input validation and 26 unit/API tests.

## Data status
All bundled installations, capacities and routes are SYNTHETIC and fictional.
Geographic locations are illustrative and do not identify actual energy assets.
Demo source_date is the scenario creation date, not an observation date.
No official inventory, automatic feed or electrical topology is bundled.

Only state=SP records are accepted. Nearest searches exclude neighboring states; use the Brazil edition for cross-border studies.

Imports replace the current browser session's dataset. They do not merge records.
Refresh/restart restores the demo. Export loaded GeoJSON to keep a local copy.
Use the exported demo as an import-format template.

## Normalized GeoJSON format
Root: FeatureCollection with a nonempty features array.
Each feature: type=Feature, properties object, geometry object.
Required string properties:
- id: unique identifier
- name
- kind: plant | substation | line
- state: two-letter Brazilian state code
- municipality: name, or "Not supplied" if unavailable
- source: http/https URL for imported records
- source_date: YYYY-MM-DD, source date supplied by importer
- data_status: synthetic | imported

Plants also require fuel (Solar, Hydro, Biomass, Wind, Thermal, Nuclear, etc.).
Optional capacity_mw and voltage_kv: nonnegative number or null.
Use null for missing capacity; never substitute a fabricated zero.
Region is derived from state. Unknown properties are discarded.

Point geometry for plants/substations; LineString geometry for lines.
Coordinates: WGS84 decimal degrees [longitude, latitude], 2D only, no crs member.
Convert projected coordinates before import. Split MultiLineStrings into individual
LineString features with unique IDs and retained source attribution.
Split cross-border lines and label each segment with its state before import.
Line counts count records/segments, not necessarily whole circuits.

Limits: 20 MiB, 20,000 features, 250,000 vertices.
This version loads the dataset into memory; no vector tiling, viewport database
queries or spatial indexing is implemented. Large datasets need preprocessing.
Performance on an 8 GB Windows notebook has not been benchmarked.

## Interpretation
- Installed capacity is not actual generation or available connection capacity.
- Geographic proximity and map intersections do not establish electrical connectivity.
- Every nearest-substation result is labelled Not verified.
- Supplied route geometry is not independently verified.
- All loaded substations are candidates, regardless of visual filters.
- State labels are checked against known codes, not against boundary polygons.
- Different IDs across inventories are not automatically deduplicated.
- Source dates/URLs are validated as metadata, not independently verified.
- No power-flow, congestion, distribution-network or investment-feasibility model.
- National scope does not imply full coverage of the Brazilian electrical network.

## Internet and privacy
Local server binds only to 127.0.0.1. No AI API key or GPU is needed.
MapLibre loads from unpkg and map tiles load from OpenStreetMap; these require
internet and browser WebGL. Their providers receive normal map-resource requests.
Imported datasets are processed locally and are not sent to an AI service.
Backend calculations work after dependencies are installed, without external API calls.
If map resources fail, the tables, import and calculations can still work.

## Official references (not downloaded automatically)
- https://www.ons.org.br/paginas/sobre-o-sin/mapas
- https://www.epe.gov.br/pt/publicacoes-dados-abertos/publicacoes/webmap-epe
- https://dadosabertos.aneel.gov.br/dataset/base-de-dados-geografica-da-distribuidora-bdgd

Review source license, dates, schema and coverage before adapting official data.
See VALIDATION.md for the actual checks performed on this delivery.
