# Changelog

## 1.1 — SQLite persistence
- Persist validated dataset snapshots and the active dataset in local SQLite.
- Save every UI analysis with its original dataset, timestamp, report and SHA-256.
- Reopen datasets and paginated analysis history from the English UI.
- Preserve saved history when opening the synthetic demo.
- Reuse identical normalized datasets; retain new snapshots when content changes.
- Keep old stateless calculation/validation endpoints for compatibility.
- Add persistence/restart tests and Windows update/backup instructions.

Database location: data/energy_geolab.sqlite3. Preserve the data folder during updates.
Stop the server before copying the database for backup.
