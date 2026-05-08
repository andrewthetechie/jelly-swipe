---
phase: 40-full-migration-validation-and-sync-db-removal
plan: 02
subsystem: testing
tags: [db_paths, migrations, pytest, VAL-03, ADB-03]

requires:
  - plan: "40-01"
    provides: VAL-02 migration parity tests and Alembic env URL precedence.
provides:
  - Neutral `jellyswipe/db_paths.application_db_path` for default/on-disk SQLite path without importing legacy db module for URL fallback
  - `jellyswipe/migrations.get_database_url` decoupled from `jellyswipe.db` import for defaults
  - Test suite migrated off `jellyswipe.db.get_db` / `get_db_closing` toward temp-file sqlite3 reads and async/UoW paths where needed
affects:
  - plan: "40-03"
    note: Enables shrinking `db.py` without breaking URL resolution or fixtures.

tech-stack:
  added: []
  patterns:
    - Import-time and factory-time wiring of `application_db_path.path` from `DB_PATH`

key-files:
  created:
    - jellyswipe/db_paths.py
  modified:
    - jellyswipe/migrations.py
    - jellyswipe/__init__.py
    - tests/conftest.py
    - Multiple route/SSE/error tests per 40-RESEARCH inventory

key-decisions:
  - "Hold default path in `db_paths.application_db_path` instead of importing `jellyswipe.db` from `migrations.py`."

patterns-established:
  - "Tests patch `application_db_path` during bootstrap and use direct sqlite3 only against the temp file path."

requirements-completed: [VAL-03, ADB-03]

duration: ~45min
completed: 2026-05-07
---

# Phase 40 — Plan 02 Summary

**Decouple migration URL defaults and the pytest harness from synchronous `jellyswipe.db` helpers so Plan 03 can remove raw `sqlite3` from the operational package.**

## Performance

- **Commit:** `ee7a835`
- **Scope:** migrations, app factory path wiring, widespread test fixture/assertion adjustments

## Accomplishments

- Introduced **`jellyswipe/db_paths.py`** with **`application_db_path`** and **`default_database_file_path()`**.
- **`jellyswipe/migrations.py`** resolves URLs using **`application_db_path.path`** plus env without importing **`jellyswipe.db`** for **`DB_PATH`** fallback.
- **`jellyswipe/__init__.py`** assigns **`application_db_path.path`** when **`create_app`** receives **`DB_PATH`**.
- **`tests/conftest.py`** patches **`db_paths`** in **`_bootstrap_temp_db_runtime`**; **`db_connection`** and related helpers no longer use **`get_db`**.
- Route, SSE, XSS, and error-handling tests updated to hit the temp SQLite file directly or async paths instead of legacy sync helpers.

## Deviations / notes

Per VAL-03, **`sqlite3`** could remain **in tests only** until Plan 03 removed app-layer **`sqlite3`**.

---

*Phase: 40-full-migration-validation-and-sync-db-removal · Completed: 2026-05-07*
