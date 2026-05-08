---
phase: 36-alembic-baseline-and-sqlalchemy-models
plan: 02
subsystem: persistence
tags: [Alembic, migrations, baseline-schema, SQLite]

requires:
  - plan: 36-01
    provides: declarative metadata and side-effect-free model import path
provides:
  - Alembic environment and bootstrap helper
  - hand-authored Phase 36 baseline revision
  - migration-focused DB regression tests
affects: [36, 37, 38, 39, 40]

tech-stack:
  added: [alembic command API]
  patterns: [programmatic upgrade_to_head helper, hand-authored baseline revision, migration-first DB tests]

key-files:
  created:
    - alembic.ini
    - alembic/env.py
    - alembic/script.py.mako
    - alembic/versions/0001_phase36_baseline.py
    - jellyswipe/migrations.py
  modified:
    - tests/test_db.py

key-decisions:
  - "Use a hand-authored baseline revision instead of trusting autogenerate for the initial cut"
  - "Keep `matches.room_code` free of a DB FK because archived rows still move to `HISTORY`"
  - "Introduce `get_database_url()` with early `DATABASE_URL` support but keep SQLite path derivation for the current sync phase"

patterns-established:
  - "Pattern 1: Alembic env imports `target_metadata` from `jellyswipe.models.metadata` and nothing from app startup"
  - "Pattern 2: temp DB migration in tests uses `upgrade_to_head(build_sqlite_url(path))`"
  - "Pattern 3: schema assertions stay PRAGMA-driven even after the bootstrap path changes"

requirements-completed: [MIG-01, MIG-02, MIG-03, SCH-02]
completed: 2026-05-05T19:35:00Z
---

# Phase 36 Plan 2 Summary

Added the Alembic baseline infrastructure and replaced the old schema assertions in `tests/test_db.py` with migration-driven verification. A blank SQLite file can now reach the Phase 36 schema entirely through Alembic, and the baseline captures the bounded rename to `auth_sessions`.

## Verification

- `uv run python -c "from jellyswipe.migrations import get_database_url; print(get_database_url('/tmp/jellyswipe-test.db'))"`
- `uv run pytest tests/test_db.py -q --no-cov`

## Notes

- `alembic/env.py` imports `jellyswipe.models.metadata`, not `jellyswipe.__init__`.
- The baseline revision includes real FKs for `swipes` and deliberately omits a room FK for `matches`.
- `tests/test_db.py` is now centered on `upgrade_to_head(...)` instead of `init_db()`.
