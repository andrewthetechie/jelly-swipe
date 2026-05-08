---
phase: 37-async-database-infrastructure
plan: 02
subsystem: database
tags: [sqlite, alembic, sqlalchemy, async, bootstrap, uvicorn]

requires:
  - plan: 37-01
    provides: async runtime primitives, canonical sync-to-async URL handling, and the database unit-of-work seam
provides:
  - migration-first bootstrap wrapper before Uvicorn startup
  - app lifespan shutdown that only disposes async runtime and clears provider state
  - async runtime maintenance as the primary startup-safe cleanup path with bounded sync compatibility wrappers
  - Docker and README startup flows aligned to the bootstrap wrapper
affects: [37, 38, 39]

tech-stack:
  added: []
  patterns: [pre-uvicorn migration bootstrap, async-first runtime maintenance with sync compatibility wrappers]

key-files:
  created:
    - jellyswipe/bootstrap.py
    - tests/test_bootstrap.py
  modified:
    - jellyswipe/__init__.py
    - jellyswipe/db.py
    - jellyswipe/db_runtime.py
    - Dockerfile
    - README.md
    - tests/test_infrastructure.py
    - tests/test_db.py

key-decisions:
  - "Keep Alembic on the canonical sync `sqlite:///...` URL and derive the async runtime URL separately before server startup."
  - "Initialize the async runtime before `uvicorn.run(...)`, then let the FastAPI lifespan own shutdown-time disposal only."
  - "Make startup-safe maintenance async-first, while keeping `cleanup_expired_auth_sessions()` sync-safe for the current auth request flow."

patterns-established:
  - "Pattern 1: `python -m jellyswipe.bootstrap` resolves one sync database target, migrates it, initializes async runtime from the derived URL, then launches `jellyswipe:app`."
  - "Pattern 2: `prepare_runtime_database_async()` owns startup-safe cleanup and WAL pragmas, while sync wrappers exist only for compatibility during the Phase 37/38 transition."

requirements-completed: [MIG-04, ADB-01, ADB-04]

duration: 6 min
completed: 2026-05-06T02:00:47Z
---

# Phase 37 Plan 2: Bootstrap Startup Summary

**Migration-first bootstrap startup with pre-Uvicorn Alembic upgrade, explicit async runtime initialization, and compatibility-bounded DB maintenance.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-05-06T01:54:00Z
- **Completed:** 2026-05-06T02:00:47Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- Added `jellyswipe/bootstrap.py` so normal startup now resolves one sync database target, runs `upgrade_to_head(...)`, initializes the async runtime, and only then hands off to Uvicorn.
- Removed in-process startup DB work from `jellyswipe/__init__.py`, leaving lifespan responsible for app teardown, provider cleanup, and `dispose_runtime()` on shutdown.
- Moved startup-safe maintenance onto the async runtime path in `jellyswipe/db.py`, while keeping the current auth-session cleanup wrapper sync-safe for existing request handlers.

## Verification

- `uv run pytest tests/test_bootstrap.py tests/test_infrastructure.py -q --no-cov`
- `uv run pytest tests/test_db.py tests/test_infrastructure.py -q --no-cov`
- `uv run pytest tests/test_bootstrap.py tests/test_infrastructure.py tests/test_db.py -q --no-cov`
- `rg -n "prepare_runtime_database\\(" jellyswipe/__init__.py`
- `rg -n "python -m jellyswipe.bootstrap|uv run python -m jellyswipe$|uv run gunicorn" README.md`

## Task Commits

Each task was committed atomically:

1. **Task 1: Introduce the migration-first bootstrap runner and thin app lifespan** - `930c2af` (feat)
2. **Task 2: Move runtime maintenance onto the async path while keeping legacy sync helpers bounded** - `f1178f4` (feat)

## Files Created/Modified

- `jellyswipe/bootstrap.py` - migration-first startup entrypoint that migrates, initializes runtime, and launches Uvicorn
- `jellyswipe/__init__.py` - thin FastAPI lifespan with shutdown-only runtime disposal and test-config runtime URL override wiring
- `jellyswipe/db_runtime.py` - runtime URL override support for app-factory test configuration
- `jellyswipe/db.py` - async-first maintenance helpers plus bounded sync compatibility wrappers
- `Dockerfile` - final container entrypoint switched to `python -m jellyswipe.bootstrap`
- `README.md` - local development and smoke instructions routed through the bootstrap wrapper
- `tests/test_bootstrap.py` - bootstrap ordering and fail-fast coverage
- `tests/test_infrastructure.py` - startup contract assertions for dependencies, Docker, and README
- `tests/test_db.py` - compatibility and async-maintenance regression coverage

## Decisions Made

- Keep the bootstrap runner responsible for migration and runtime initialization so the app factory can assume schema readiness.
- Preserve `DB_PATH` only as a compatibility input for sync helpers and older tests, while allowing `DATABASE_URL` to override the runtime target explicitly.
- Keep `cleanup_expired_auth_sessions()` sync-safe because `auth.create_session()` still runs from current sync callsites inside async route handlers.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Broke a `db.py`/`migrations.py` import cycle while moving maintenance onto the async path**
- **Found during:** Task 2 (Move runtime maintenance onto the async path while keeping legacy sync helpers bounded)
- **Issue:** `jellyswipe.db` imported `get_database_url` at module import time, while `jellyswipe.migrations` still imported `jellyswipe.db`, which broke pytest collection with a circular import.
- **Fix:** Replaced the module-level import with a local helper lookup so `db.py` can resolve the canonical sync URL without creating an import cycle.
- **Files modified:** `jellyswipe/db.py`
- **Verification:** `uv run pytest tests/test_db.py tests/test_infrastructure.py -q --no-cov`
- **Committed in:** `f1178f4`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** The fix was required to load the package at all after the maintenance refactor. No scope creep beyond correctness.

## Issues Encountered

- The first Task 2 test run exposed the circular import between `db.py` and `migrations.py`; resolving the lookup lazily fixed collection and kept the sync/async URL contract intact.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Normal container and local startup now share the same migration-first bootstrap contract.
- Phase 38 can migrate more sync callsites onto async repositories without reworking startup or maintenance again.
- `STATE.md` was intentionally left unchanged in this sequential execution mode.

## Self-Check: PASSED

---
*Phase: 37-async-database-infrastructure*
*Completed: 2026-05-06*
