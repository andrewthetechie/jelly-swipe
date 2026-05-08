---
phase: 36-alembic-baseline-and-sqlalchemy-models
plan: 03
subsystem: persistence
tags: [sqlite, runtime-bootstrap, auth-sessions, test-fixtures]

requires:
  - plan: 36-02
    provides: Alembic baseline and upgrade helper
provides:
  - runtime-only `db.py`
  - app startup free of schema creation
  - auth/session SQL aligned to `auth_sessions`
  - test/bootstrap path migrated off `init_db()`
affects: [36, 37, 38, 39, 40]

tech-stack:
  added: [runtime PRAGMA helpers]
  patterns: [Alembic-first test bootstrap, runtime-only db module, root-logger structured error emission]

key-files:
  modified:
    - jellyswipe/db.py
    - jellyswipe/__init__.py
    - jellyswipe/auth.py
    - jellyswipe/dependencies.py
    - jellyswipe/http_client.py
    - jellyswipe/routers/media.py
    - jellyswipe/routers/rooms.py
    - tests/conftest.py
    - tests/test_auth.py
    - tests/test_dependencies.py
    - tests/test_db.py
    - tests/test_error_handling.py
    - tests/test_infrastructure.py
    - tests/test_route_authorization.py
    - tests/test_routes_room.py

key-decisions:
  - "Replace `init_db()` with explicit runtime helpers plus Alembic bootstrap instead of keeping a compatibility wrapper"
  - "Enforce `foreign_keys=ON` on every sync connection so the new swipe/session constraints are real in SQLite"
  - "Keep root-logger structured logging for media/room/http helper paths because the suite expects those records to be observable"

patterns-established:
  - "Pattern 1: temp DB fixtures run `upgrade_to_head(build_sqlite_url(path))` before opening connections or apps"
  - "Pattern 2: startup uses `prepare_runtime_database()` for WAL + maintenance only"
  - "Pattern 3: tests that seed swipe rows with session_id must also seed an auth_sessions row"

requirements-completed: [MIG-02, SCH-02]
completed: 2026-05-05T20:10:00Z
---

# Phase 36 Plan 3 Summary

Removed schema creation from the runtime path and moved the sync test stack to Alembic-backed temp databases. `db.py` is now runtime-only, `auth.py` reads and writes `auth_sessions`, and app startup no longer creates tables.

## Verification

- `uv run pytest tests/test_db.py tests/test_auth.py tests/test_dependencies.py tests/test_route_authorization.py tests/test_error_handling.py tests/test_infrastructure.py -q --no-cov`
- `uv run pytest -q --no-cov`
- `rg -n "init_db\\(" jellyswipe tests` returned no matches

## Notes

- SQLite runtime setup now explicitly enables WAL, `synchronous=NORMAL`, and `foreign_keys=ON`.
- A couple of route tests needed real `auth_sessions` seed rows once the new FK became enforceable.
- Media, room, and HTTP helper logging now emits structured fields through the root logger so the suite can observe them reliably.
