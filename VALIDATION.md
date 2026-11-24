# Validation — SQLite edition 1.1

42/42 automated tests passed on Linux / Python 3.12, using the pinned primary dependencies.
26 existing calculation/input/API tests and 16 new SQLite persistence/API tests.

New checks: imported dataset recovery in a fresh Python process; analysis recovery
in a fresh process; immutable historical snapshots after another import; rollback
and foreign keys; exact reimport deduplication; changed-content snapshots; demo
switch preserves history; unknown IDs; invalid import leaves active data intact;
pagination; mismatched hash rejection; SQL-like names stored literally; visible
database failure; cross-origin writes rejected.

JavaScript syntax passed node --check. Browser automation was attempted, but
Chromium could not start because the environment disallowed a process socket.
The new browser controls and Windows BAT launchers still require local confirmation.
The previous edition's map and Campinas export flow were confirmed by the user's
screenshots and exported CSV/JSON. That does not validate the new history controls.

No real official dataset or electrical connection validation is included.
No local database or imported user data is included in the ZIP or repository.
