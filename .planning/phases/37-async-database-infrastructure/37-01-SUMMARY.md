---
phase: 37-async-database-infrastructure
plan: 01
subsystem: database
tags: [sqlite, alembic, sqlalchemy, async, fastapi]

requires:
  - plan: 36-03
    provides: runtime-only sync SQLite helpers and Alembic-backed test bootstrap
provides:
  - canonical sync `DATABASE_URL` resolution for Alembic/bootstrap
  - async SQLAlchemy engine and sessionmaker runtime
  - request-scoped `DatabaseUnitOfWork` dependency
  - `BEGIN IMMEDIATE` swipe bridge over `AsyncSession.run_sync`
affects: [37, 38, 39]

tech-stack:
  added: [aiosqlite, greenlet]
  patterns: [canonical sync-to-async URL derivation, function-scoped async UoW dependency, sync SQLite bridge over AsyncSession.run_sync]

key-files:
  created:
    - jellyswipe/db_runtime.py
    - jellyswipe/db_uow.py
    - tests/test_db_runtime.py
  modified:
    - pyproject.toml
    - uv.lock
    - jellyswipe/migrations.py
    - jellyswipe/dependencies.py
    - jellyswipe/routers/rooms.py
    - tests/test_dependencies.py
    - tests/test_auth.py

key-decisions:
  - "Keep `DATABASE_URL` canonical in sync `sqlite:///...` form and derive the async runtime URL from that one contract."
  - "Make the FastAPI DB seam a function-scoped `DatabaseUnitOfWork` so commit, rollback, and close are owned in one place."
  - "Preserve SQLite `BEGIN IMMEDIATE` locking by running the legacy swipe transaction body through `AsyncSession.run_sync` without inner commit or rollback."

patterns-established:
  - "Pattern 1: Alembic/bootstrap consumes `jellyswipe.migrations.get_database_url()`, while runtime code converts that same target through `build_async_database_url()`."
  - "Pattern 2: `get_db_uow()` yields one `DatabaseUnitOfWork`, commits on success, rolls back on failure, and closes the session in `finally`."
  - "Pattern 3: legacy sync SQLite transaction bodies can run inside async request handling through `DatabaseUnitOfWork.run_sync()` as long as the helper does not own final commit or rollback."

requirements-completed: [ADB-01, ADB-02, ADB-04]

duration: 8 min
completed: 2026-05-06T01:52:17Z
---

# Phase 37 Plan 1: Async Runtime Foundation Summary

**Canonical sync `DATABASE_URL` resolution with an async SQLAlchemy runtime, request-scoped unit of work, and a preserved `BEGIN IMMEDIATE` swipe bridge.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-05-06T01:44:00Z
- **Completed:** 2026-05-06T01:52:17Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments

- Added `aiosqlite` and `greenlet`, then introduced `jellyswipe.db_runtime` as the single async engine/sessionmaker boundary for SQLite.
- Made `jellyswipe.migrations` the canonical sync `DATABASE_URL` resolver so Alembic/bootstrap always consume `sqlite:///...` and runtime code derives `sqlite+aiosqlite:///...` from the same target.
- Replaced the old sync request dependency with `get_db_uow()` / `DBUoW` and moved the room swipe path onto an async bridge that keeps `BEGIN IMMEDIATE` locking semantics intact.

## Verification

- `uv run pytest tests/test_db_runtime.py -q --no-cov`
- `uv run pytest tests/test_db_runtime.py tests/test_dependencies.py -q --no-cov`
- `uv run pytest tests/test_auth.py -q --no-cov --collect-only`
- `rg -n 'get_db_dep|DBConn' jellyswipe/dependencies.py tests/test_dependencies.py`
- `rg -n 'get_db_dep|DBConn' tests/test_auth.py`

## Task Commits

Each task was committed atomically:

1. **Task 1: Add the async runtime and unit-of-work contracts** - `477f13b` (feat)
2. **Task 2: Replace the sync DB dependency surface with the async UoW seam** - `5025d4b` (feat)

## Files Created/Modified

- `pyproject.toml` - added `aiosqlite` and `greenlet` runtime dependencies
- `uv.lock` - regenerated lockfile for the async runtime stack
- `jellyswipe/migrations.py` - canonical sync SQLite URL normalization and Alembic URL resolution
- `jellyswipe/db_runtime.py` - async engine/sessionmaker lifecycle helpers and SQLite connect hooks
- `jellyswipe/db_uow.py` - typed async unit of work plus maintenance repositories
- `jellyswipe/dependencies.py` - function-scoped async UoW dependency with commit/rollback ownership
- `jellyswipe/routers/rooms.py` - `BEGIN IMMEDIATE` swipe bridge over `AsyncSession.run_sync`
- `tests/test_db_runtime.py` - async runtime lifecycle and URL contract coverage
- `tests/test_dependencies.py` - async dependency lifecycle and bridge ownership tests
- `tests/test_auth.py` - removed coverage for the retired sync DB dependency API

## Decisions Made

- Keep `DATABASE_URL` canonical in sync form even when callers accidentally provide `sqlite+aiosqlite:///...`; this keeps Alembic and bootstrap isolated from runtime-driver details.
- Let the dependency boundary own final commit and rollback so routes and sync bridge helpers cannot double-commit or double-rollback a managed SQLAlchemy session.
- Preserve the existing swipe lock behavior by issuing `BEGIN IMMEDIATE` inside the sync bridge helper before any write statements run.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added `greenlet` for SQLAlchemy asyncio session operations**
- **Found during:** Task 1 (Add the async runtime and unit-of-work contracts)
- **Issue:** The first runtime test run failed because `AsyncSession.execute()` and engine disposal require `greenlet` in this environment.
- **Fix:** Added `greenlet>=3.2.4` to the runtime dependencies and regenerated `uv.lock`.
- **Files modified:** `pyproject.toml`, `uv.lock`
- **Verification:** `uv run pytest tests/test_db_runtime.py -q --no-cov`
- **Committed in:** `477f13b`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** The fix was required for the async runtime to execute real SQLAlchemy session work. No scope creep beyond runtime correctness.

## Issues Encountered

- SQLAlchemy asyncio could initialize the engine without `greenlet`, but real session execution and disposal failed immediately. The dependency was added before continuing so the runtime tests covered actual behavior instead of a stubbed path.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Later Phase 37 plans can now wire startup/test bootstrap into the async runtime and migrate more persistence callsites onto `DatabaseUnitOfWork`.
- The room swipe path already proves the legacy sync SQL can cross the async boundary without losing SQLite lock semantics.
- `STATE.md` and `ROADMAP.md` were intentionally left unchanged in this sequential run per executor instructions.

## Self-Check: PASSED
