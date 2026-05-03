---
phase: 33-router-extraction-and-endpoint-parity
plan: 02
subsystem: api
tags: [fastapi, sqlite, apiRouter, dependency-injection, sse, transaction]

# Dependency graph
requires:
  - phase: 33-01
    provides: config.py, auth/static/media/proxy routers, dependencies.py
  - phase: 32
    provides: require_auth, AuthUser, DBConn, dependency injection layer
provides:
  - jellyswipe/routers/rooms.py with 11 room routes and BEGIN IMMEDIATE swipe transaction
  - Thin jellyswipe/__init__.py app factory mounting all 5 domain routers
  - Endpoint parity verified: all original URL paths present, /plex/server-info deleted
affects: [34-sse-migration, 35-test-migration, router-imports]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "BEGIN IMMEDIATE transaction preserved verbatim in swipe handler (D-12)"
    - "DBConn dependency injection for connection lifecycle management (D-13)"
    - "Thin app factory: all domain routes in routers/, SSE stays inline until Phase 34"
    - "Re-export _provider_singleton/_JELLYFIN_URL from __init__.py for dependencies.py compatibility"

key-files:
  created:
    - jellyswipe/routers/rooms.py
  modified:
    - jellyswipe/__init__.py

key-decisions:
  - "SSE route /room/{code}/stream stays inline in __init__.py per D-15 (Phase 34 migrates it)"
  - "Dead /plex/server-info route deleted per D-10"
  - "DBConn dependency used for swipe handler (CR-01 fix) — non-swipe routes keep get_db_closing() per D-13"
  - "_provider_singleton and _JELLYFIN_URL re-exported in __init__.py because dependencies.py reads them via import jellyswipe"
  - "SSE identity helpers kept inline alongside SSE route until Phase 34 migration"

patterns-established:
  - "All room route handlers use Depends(require_auth) — no _require_login() bridge"
  - "Swipe handler is the only route using DBConn; all others use get_db_closing() context manager"
  - "app.include_router() with no prefix — routes define full paths (D-14)"

requirements-completed: [ARCH-01, FAPI-02]

# Metrics
duration: 15min
completed: 2026-05-03
---

# Phase 33 Plan 02: Rooms Router and Thin App Factory Summary

**Rooms domain extracted (11 routes, BEGIN IMMEDIATE swipe transaction) and __init__.py refactored from 924-line monolith to 353-line thin app factory mounting 5 domain routers**

## Performance

- **Duration:** 15 min
- **Started:** 2026-05-03T00:00:00Z
- **Completed:** 2026-05-03T00:15:00Z
- **Tasks:** 2 (Task 1 pre-completed; Task 2 executed)
- **Files modified:** 2

## Accomplishments

- Created `jellyswipe/routers/rooms.py` with 11 routes including the swipe handler preserving BEGIN IMMEDIATE transaction verbatim (D-12) and using DBConn dependency for connection leak fix (D-13, CR-01)
- Refactored `jellyswipe/__init__.py` from 924 lines to 353 lines — all domain routes removed, 5 routers mounted via `app.include_router()`
- Deleted dead `/plex/server-info` route (D-10); SSE route `/room/{code}/stream` stays inline (D-15)
- 32 total routes registered on app; all original URL paths verified present

## Task Commits

Each task was committed atomically:

1. **Task 1: Create rooms router with swipe transaction integrity** - `cda056d` (feat)
2. **Task 2: Refactor __init__.py into thin app factory** - `846a436` (refactor)

**Plan metadata:** (committed with SUMMARY.md)

## Files Created/Modified

- `jellyswipe/routers/rooms.py` — 11 room routes: create/solo/join/swipe/matches/quit/delete-match/undo/deck/genre/status; swipe uses DBConn dependency and BEGIN IMMEDIATE transaction
- `jellyswipe/__init__.py` — Thin app factory (353 lines, down from 924): mounts auth/rooms/media/proxy/static routers, SSE route inline, middleware, XSSSafeJSONResponse class

## Decisions Made

- SSE route stays in `__init__.py` per D-15; Phase 34 will migrate it with proper async handling
- `_provider_singleton` and `_JELLYFIN_URL` are imported from `config.py` into `__init__.py` and re-exported at module level — required because `dependencies.py` accesses them as `jellyswipe._provider_singleton` and `jellyswipe._JELLYFIN_URL`
- SSE identity helpers (`_jellyfin_user_token_from_request`, `_resolve_user_id_from_token_cached`, etc.) kept inline alongside SSE route until Phase 34

## Deviations from Plan

None — plan executed exactly as written. The `__init__.py` line count (353) is above the 200-250 target because the SSE identity helpers (~65 lines) are required to remain inline until Phase 34.

## Issues Encountered

None — all verifications passed on first run.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Phase 34 (SSE migration): SSE route and its identity helpers are clearly isolated in `__init__.py`, ready for extraction
- Phase 35 (test migration): All route handlers now in domain routers; TestClient can target individual routers or the full app
- ARCH-01 (router split from __init__.py) is satisfied — all 21 domain routes in routers/
- FAPI-02 (endpoint parity) is satisfied — 32 routes registered, all original paths present, dead plex route removed

---
*Phase: 33-router-extraction-and-endpoint-parity*
*Completed: 2026-05-03*
