---
phase: 40-full-migration-validation-and-sync-db-removal
plan: 01
subsystem: testing
tags: [alembic, pytest, sqlite, migrations, VAL-02]

requires:
  - phase: "39-room-swipe-match-and-sse-persistence-conversion"
    provides: Persistence baseline and Alembic revisions available on integration branch.
provides:
  - Alembic env URL resolution preferring DATABASE_URL/DB_PATH for subprocess parity
  - Automated VAL-02 migration tests (fresh file DB, head revision, idempotent subprocess)
affects:
  - phase-40 plan 02–04 (sync DB removal builds on migration confidence)

tech-stack:
  added: []
  patterns:
    - Subprocess `python -m alembic upgrade head` with explicit DATABASE_URL against tmp_path DB

key-files:
  created:
    - tests/test_migrations.py
  modified:
    - alembic/env.py

key-decisions:
  - "Keep alembic.ini as default when DATABASE_URL/DB_PATH unset so operator runs stay unchanged."
  - "Resolve URL via jellyswipe.migrations.get_database_url only when env overrides are present."

patterns-established:
  - "Migration parity tests use isolated tmp_path SQLite and argv-list subprocess (no shell)."

requirements-completed: [VAL-02]

duration: 25min
completed: 2026-05-07
---

# Phase 40 — Plan 01 Summary

**Alembic CLI honors DATABASE_URL for isolated upgrades, with pytest proving empty SQLite reaches head and a second subprocess upgrade is idempotent.**

## Performance

- **Duration:** ~25 min (recorded at summary write; implementation landed in prior session)
- **Tasks:** 2 (single feat commit on branch)
- **Files modified:** 2

## Accomplishments

- `_resolve_url()` in `alembic/env.py` prefers `DATABASE_URL` / `DB_PATH` through `get_database_url()`, else `alembic.ini`, else final fallback.
- `tests/test_migrations.py` asserts core tables and `alembic_version` after `upgrade_to_head`, then runs `alembic upgrade head` twice via subprocess with `check=True`.

## Task Commits

Implementation was delivered as one commit (both tasks together):

1. **Task 1:** Alembic env URL precedence — `fff98f5`
2. **Task 2:** VAL-02 migration parity tests — `fff98f5`

## Files Created/Modified

- `alembic/env.py` — env-driven URL for subprocess tests
- `tests/test_migrations.py` — VAL-02 parity + idempotent subprocess

## Decisions Made

Followed MIG-03: `env.py` imports `jellyswipe.migrations` and models metadata only — no FastAPI app import.

## Deviations from Plan

None — plan executed as written. Tasks were not split into separate commits on this branch.

## Issues Encountered

None.

## User Setup Required

None.

## Next Phase Readiness

VAL-02 automation in place; Plan 02 can decouple tests from sync `jellyswipe.db` helpers.

---
*Phase: 40-full-migration-validation-and-sync-db-removal*
*Completed: 2026-05-07*
