---
phase: 37-async-database-infrastructure
plan: 03
subsystem: testing
tags: [pytest, alembic, sqlite, sqlalchemy, async, fastapi]

requires:
  - plan: 37-01
    provides: async runtime primitives and canonical sync-to-async database URL handling
  - plan: 37-02
    provides: migration-first bootstrap ordering and runtime disposal on shutdown
provides:
  - shared temp-database bootstrap through Alembic plus async runtime initialization
  - auth low-level tests wired to the shared fixture/runtime seam
  - route cursor helper compatibility across sqlite3 and SQLAlchemy connection shapes
affects: [37, 38, 39]

tech-stack:
  added: []
  patterns: [shared temp-db bootstrap helper, sync DATABASE_URL contract in test_config, explicit runtime disposal before fixture singleton cleanup]

key-files:
  created: []
  modified:
    - tests/conftest.py
    - tests/test_auth.py
    - jellyswipe/routers/rooms.py

key-decisions:
  - "Keep test bootstrap canonical on sync `DATABASE_URL` values and derive the async runtime URL inside the shared helper."
  - "Let low-level auth tests import the shared bootstrap helper from `tests.conftest` instead of repeating Alembic setup in each test."
  - "Preserve the sync/async coexistence window by making room cursor helpers accept both raw sqlite3 connections and SQLAlchemy connections."

patterns-established:
  - "Pattern 1: test fixtures provision temp SQLite files by running `upgrade_to_head(sync_url)` and then `initialize_runtime(async_url)` before app creation."
  - "Pattern 2: fixture teardown disposes the cached async runtime before clearing dependency overrides or provider singletons."
  - "Pattern 3: direct sync assertions in transitional tests reuse bootstrapped `db_connection` state rather than opening a second schema path."

requirements-completed: [VAL-01, ADB-02]

duration: 14 min
completed: 2026-05-06T02:08:18Z
---

# Phase 37 Plan 3: Async Test Bootstrap Summary

**Shared Alembic-backed temp database bootstrap with async runtime rebind coverage for auth and real-auth route tests.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-05-06T01:54:00Z
- **Completed:** 2026-05-06T02:08:18Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Centralized pytest temp-database setup in `tests/conftest.py` so shared fixtures now run Alembic migrations, initialize the async runtime, and dispose that runtime before fixture singleton cleanup.
- Rewired `tests/test_auth.py` onto the shared bootstrap seam, removed repeated per-test migration setup, and added a regression that proves runtime rebinds cleanly across two different temp SQLite files.
- Restored room deck cursor verification under `client_real_auth` by making the room query helpers work with both raw sqlite3 connections and SQLAlchemy connections during the transition.

## Verification

- `python -m compileall tests/conftest.py tests/test_auth.py`
- `uv run pytest tests/test_auth.py tests/test_dependencies.py -q --no-cov`
- `uv run pytest tests/test_auth.py -q --no-cov`
- `rg -n "get_db_dep|DBConn|upgrade_to_head\\(" tests/test_auth.py`
- `uv run pytest tests/test_auth.py tests/test_route_authorization.py tests/test_routes_room.py -q --no-cov`

## Task Commits

Each task was committed atomically:

1. **Task 1: Rebuild the shared test fixtures around Alembic plus sync-URL bootstrap** - `af23df1` (feat)
2. **Task 2: Rewrite low-level auth tests around the new fixture/runtime seam** - `d445d6e` (feat)
3. **Auto-fix: Restore room cursor helpers for sync route paths** - `e5bbef4` (fix)

## Files Created/Modified

- `tests/conftest.py` - added `_bootstrap_temp_db_runtime`, canonical sync `DATABASE_URL` test config wiring, and explicit runtime-first teardown ordering
- `tests/test_auth.py` - switched auth tests to shared bootstrap/db fixtures and added cross-database runtime rebind regression coverage
- `jellyswipe/routers/rooms.py` - widened cursor helper query utilities to support both sqlite3 and SQLAlchemy connection types

## Decisions Made

- Kept `test_config["DATABASE_URL"]` in canonical sync `sqlite:///...` form and passed the derived async URL only to the runtime initializer.
- Reused `db_connection` for sync assertions in auth tests so route and low-level tests share one migration-first bootstrap path.
- Fixed the blocking room cursor regression in-place rather than weakening verification, because plan success requires the updated fixture layer to work under real-auth route coverage.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Restored room cursor helper compatibility for real-auth deck tests**
- **Found during:** Overall verification
- **Issue:** `tests/test_route_authorization.py` deck coverage failed because `jellyswipe/routers/rooms.py` called `exec_driver_sql()` on raw `sqlite3.Connection` objects returned by `get_db_closing()`.
- **Fix:** Added a small dual-mode query helper so `_fetchone()` and `_execute()` work with both sqlite3 and SQLAlchemy connection shapes.
- **Files modified:** `jellyswipe/routers/rooms.py`
- **Verification:** `uv run pytest tests/test_auth.py tests/test_route_authorization.py tests/test_routes_room.py -q --no-cov`
- **Committed in:** `e5bbef4`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** The fix was required to satisfy the plan's real-auth route verification and did not expand the phase boundary beyond compatibility for the updated fixture path.

## Known Stubs

None.

## Issues Encountered

- Final route verification exposed a pre-existing connection-shape mismatch in the room deck cursor helpers. It was fixed inline because the updated fixture layer needs those routes to remain green under `client_real_auth`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 38 can now build auth persistence changes on top of one shared Alembic/runtime bootstrap path across low-level auth and route-level real-auth tests.
- The remaining sync compatibility helpers are now explicitly bounded to bootstrapped databases instead of ad hoc schema setup.
- `.planning/STATE.md` was intentionally left unchanged in this sequential run per execution instructions.

## Self-Check: PASSED

---
*Phase: 37-async-database-infrastructure*
*Completed: 2026-05-06*
