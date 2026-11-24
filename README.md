# Sao Paulo Energy GeoLab

Version 1.1.1 — SQLite persistence and independent map loading. Educational local application. Interface and code in English.

## Windows quick start
1. Extract the ZIP completely to a writable folder (not inside the ZIP).
2. Install Python 3.11 or 3.12 with the Windows Python launcher.
3. Double-click INSTALL.bat once; internet access is required for dependencies.
4. Double-click TEST.bat to run the included 42 backend/API/persistence tests.
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
- Strict input validation and 42 unit/API/persistence tests.

## Data status
All bundled installations, capacities and routes are SYNTHETIC and fictional.
Geographic locations are illustrative and do not identify actual energy assets.
Demo source_date is the scenario creation date, not an observation date.
No official inventory, automatic feed or electrical topology is bundled.

Only state=SP records are accepted. Nearest searches exclude neighboring states; use the Brazil edition for cross-border studies.

Imports are validated and saved as immutable snapshots in local SQLite. They do not merge records.
The last active dataset is restored after browser refresh or server restart.
Use Saved datasets > Open saved dataset to reopen earlier snapshots.
Exact reimports reuse the existing normalized-content hash and retain the original name/date.
Changed data creates a new snapshot, even if the uploaded filename is the same.
Source labels and synthetic/imported status are preserved, not independently verified.
Use the exported demo as an import-format template.

## Persistence and history
- Database: `data/energy_geolab.sqlite3`, created automatically on first use.
- Each successful Find nearest substations calculation saves a new history entry.
- Saved analysis history > Open selected analysis reopens the original result and dataset.
- History is paginated in groups of 50; Refresh history picks up other local-tab activity.
- Open synthetic demo switches the active dataset; it does not delete imports/history.
- The active dataset is shared by local browser tabs. This is a single-user local application.
- Failed validation does not replace the active dataset or create a dataset record.
- Storage failures are displayed; the application does not claim to save when writes fail.
- Existing `/api/nearest` and `/api/validate` endpoints remain stateless for compatibility.
  Persistent UI actions use `/api/datasets` and `/api/analyses`.
- Dataset snapshots and historical reports are immutable through the API; deletion is not exposed.

### Update and backup
Stop START.bat with Ctrl+C before updating or backing up.
Extract this version into the same project folder without deleting the existing `data` folder.
For a manual backup with the application stopped, copy `data/energy_geolab.sqlite3`
to a separate location. The ZIP and Git repository exclude all local databases.
Restore a backup only with the application stopped. Keep your original backup.
Moving the app to a new folder does not automatically move its database: copy the data folder too.
`ENERGY_DB_PATH` can override the database path; tests use temporary databases.
SQLite is part of Python: no database server or extra database package is required.

### Schema
`datasets` stores normalized GeoJSON, source status counts, creation time and SHA-256.
`analyses` references datasets with a foreign key and stores the original report and UTC creation time.
`settings` stores the last active dataset. Schema version is 1.
Browser dates display in the local timezone; exports preserve UTC timestamps.

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

## Startup fix in 1.1.1
MapLibre JavaScript and CSS load dynamically after local datasets/history. A slow or unavailable CDN cannot block the local-data startup. API requests time out after 20 seconds and map-library loading after 12 seconds. A startup status appears under the title; caught errors also appear in the browser console. Local HTML/JavaScript use no-store headers and the script URL is versioned.
