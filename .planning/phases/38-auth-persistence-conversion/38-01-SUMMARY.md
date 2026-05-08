---
phase: 38-auth-persistence-conversion
plan: 01
subsystem: auth
tags: [fastapi, sqlalchemy, alembic, auth, async]
requires:
  - phase: 37-async-database-infrastructure
    provides: async SQLAlchemy runtime, request-scoped unit of work, Alembic-backed test bootstrap
provides:
  - async auth session repository CRUD via DatabaseUnitOfWork
  - async auth service lifecycle with cleanup-on-create and best-effort destroy
  - async require_auth and logout dependency contract with stale-session clearing
affects: [38-02, phase-39, auth-routes]
tech-stack:
  added: []
  patterns: [thin repository plus thin service auth boundary, request-scoped async uow for auth routes]
key-files:
  created: [jellyswipe/auth_types.py]
  modified:
    [
      jellyswipe/auth.py,
      jellyswipe/db_uow.py,
      jellyswipe/dependencies.py,
      jellyswipe/routers/auth.py,
      tests/test_auth.py,
      tests/test_dependencies.py,
    ]
key-decisions:
  - "Auth persistence now returns a shared AuthRecord instead of tuples or ORM entities."
  - "Stale persisted-session misses clear the full Starlette session before the dependency raises the unchanged 401 contract."
  - "Auth routes now pass request-scoped DBUoW instances into the async auth service to preserve runtime compatibility."
patterns-established:
  - "Auth services own opaque session_id generation, created_at generation, and request-driven cleanup."
  - "Dependencies translate AuthRecord objects into AuthUser and own stale-session clearing at the request boundary."
requirements-completed: [MVC-01, PAR-01]
duration: 7 min
completed: 2026-05-05
---

# Phase 38 Plan 01: Auth Persistence Boundary Summary

**Async auth-session persistence now flows through a typed AuthRecord, request-scoped SQLAlchemy UoW, and unchanged FastAPI auth dependency contracts.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-05-05T23:32:47-05:00
- **Completed:** 2026-05-06T04:39:37Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Added `AuthRecord` plus async auth-session repository CRUD on `DatabaseUnitOfWork`.
- Converted the auth service to async create/lookup/destroy flows with 14-day cleanup on creation and best-effort persisted delete after local session clearing.
- Preserved the `AuthUser` and `401 {"detail": "Authentication required"}` dependency contract while clearing stale session state and updating auth routes to pass request-scoped UoWs.

## Task Commits

Each task was committed atomically:

1. **Task 1: Build the async auth repository/service boundary** - `ddafe56` (`test`), `676b0c4` (`feat`)
2. **Task 2: Preserve the auth dependency contract on top of the async service** - `8a2cb1b` (`test`), `2041b65` (`feat`)

## Files Created/Modified

- `jellyswipe/auth_types.py` - Shared typed auth-session record for repository and service layers.
- `jellyswipe/auth.py` - Async auth lifecycle helpers with cleanup-on-create and best-effort destroy logging.
- `jellyswipe/db_uow.py` - Async auth-session CRUD methods returning `AuthRecord`.
- `jellyswipe/dependencies.py` - Async `require_auth` and `destroy_session_dep` preserving the existing 401 contract.
- `jellyswipe/routers/auth.py` - Auth routes updated to pass request-scoped UoWs through the async service boundary.
- `tests/test_auth.py` - Service-focused async auth persistence coverage.
- `tests/test_dependencies.py` - Async dependency coverage for valid sessions, stale-session clearing, and awaited logout delegation.

## Decisions Made

- Used `AuthRecord` as the neutral record contract so `db_uow.py` does not depend on `auth.py`.
- Kept persisted auth records as the request-time source of truth; no per-request Jellyfin revalidation was added.
- Cleared the full Starlette session dict for stale or destroyed sessions rather than popping only `session_id`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Swapped the auth test runtime bootstrap to native async setup**
- **Found during:** Task 1 (Build the async auth repository/service boundary)
- **Issue:** The shared sync helper uses `asyncio.run()`, which fails inside the new anyio-backed auth service tests.
- **Fix:** Reused the same Alembic/runtime bootstrap path but initialized the async runtime directly inside the fixture.
- **Files modified:** `tests/test_auth.py`
- **Verification:** `./.venv/bin/pytest tests/test_auth.py -q`
- **Committed in:** `676b0c4`

**2. [Rule 3 - Blocking] Updated auth routes to pass request-scoped UoWs**
- **Found during:** Task 2 (Preserve the auth dependency contract on top of the async service)
- **Issue:** The new async auth service signatures would have broken login, server-identity, and logout routes if they kept calling the old sync helpers.
- **Fix:** Injected `DBUoW` into the auth routes and delegated logout through the async dependency helper.
- **Files modified:** `jellyswipe/routers/auth.py`
- **Verification:** `./.venv/bin/pytest tests/test_route_authorization.py -q`
- **Committed in:** `2041b65`

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both fixes were required to keep the async conversion executable and to avoid leaving the app with broken auth routes.

## Issues Encountered

- `caplog` did not reliably capture the module logger inside the async destroy-failure test, so the test asserts directly on the logger call while still verifying the `auth_session_delete_failed` emission.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 38-02 can build on a proven async auth repository/service pattern.
- Auth routes and dependency boundaries are already running through request-scoped UoWs, so later persistence conversions can mirror this shape.

## Self-Check: PASSED

- Verified summary file exists on disk.
- Verified task commits `ddafe56`, `676b0c4`, `8a2cb1b`, and `2041b65` exist in git history.
