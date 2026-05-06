---
phase: 38-auth-persistence-conversion
plan: 02
subsystem: auth
tags: [fastapi, sqlalchemy, auth, cookies, testing]
requires:
  - phase: 38-01
    provides: async auth-session service helpers, request-scoped DBUoW auth dependency seam
provides:
  - auth router delegation to async auth service helpers for login, logout, and /me room compatibility
  - route-level stale-session and logout parity coverage for signed session cookie clearing
affects: [phase-39, auth-routes, protected-route-contracts]
tech-stack:
  added: []
  patterns: [auth routes call the auth service only, flagged 401 auth failures delete the signed session cookie]
key-files:
  created: []
  modified:
    [
      jellyswipe/__init__.py,
      jellyswipe/auth.py,
      jellyswipe/dependencies.py,
      jellyswipe/routers/auth.py,
      tests/conftest.py,
      tests/test_route_authorization.py,
    ]
key-decisions:
  - "Protected auth failures mark the request for cookie deletion and let one app-level HTTPException handler preserve the existing 401 detail contract."
  - "The /me active-room compatibility check stays in auth.py behind DBUoW.run_sync instead of reintroducing direct route SQL."
patterns-established:
  - "Auth router handlers await create_session, destroy_session, and resolve_active_room rather than reaching into persistence directly."
  - "Route-level auth parity tests assert visible cookie clearing and 401/logout contracts; deeper cleanup semantics stay in lower-level auth tests."
requirements-completed: [MVC-01, PAR-01]
duration: 5 min
completed: 2026-05-05
---

# Phase 38 Plan 02: Auth Route Delegation and Cookie-Parity Summary

**Auth routes now stay on the async auth/UoW seam while stale-session 401s and logout responses aggressively clear the signed session cookie with unchanged JSON contracts.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-05T23:42:35-05:00
- **Completed:** 2026-05-06T04:47:33Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Rewired `/auth/jellyfin-use-server-identity`, `/auth/jellyfin-login`, `/auth/logout`, and `/me` to use async auth-service helpers with `DBUoW`.
- Added `resolve_active_room()` in `jellyswipe/auth.py` so `/me` keeps room-compatibility behavior without route-level DB access.
- Locked route-visible stale-session and logout parity with cookie-clearing assertions and full route authorization coverage.

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewire the auth routes to the async auth service/UoW seam** - `0e001df` (`test`), `1960eb0` (`feat`)
2. **Task 2: Lock in route-level stale-session and logout parity** - `b80967d` (`test`), `eda15ce` (`fix`)

## Files Created/Modified

- `jellyswipe/auth.py` - Added `resolve_active_room()` behind `DatabaseUnitOfWork.run_sync()`.
- `jellyswipe/routers/auth.py` - Routed logout and `/me` through auth-service helpers and explicit cookie deletion on logout.
- `jellyswipe/dependencies.py` - Flagged stale-session auth failures for response-time cookie deletion while preserving the existing 401 payload.
- `jellyswipe/__init__.py` - Added one app-level `HTTPException` handler that deletes the signed session cookie for flagged auth failures.
- `tests/conftest.py` - Aligned injected session cookies with the app's host-scoped cookie domain so TestClient observes real delete behavior.
- `tests/test_route_authorization.py` - Added TDD seam tests plus stale-session/logout parity assertions.

## Decisions Made

- Used a flagged `HTTPException` handler instead of widening route logic so protected auth paths keep the exact `{"detail": "Authentication required"}` contract while still deleting cookies.
- Kept the active-room compatibility query as a focused `run_sync()` bridge in `auth.py`; broader room persistence migration remains out of scope for Phase 38.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Deleted the signed session cookie on stale-session 401s and logout responses**
- **Found during:** Task 2 (Lock in route-level stale-session and logout parity)
- **Issue:** Clearing `request.session` alone left the client-side `session` cookie present after `/me` stale-session failures and logout responses.
- **Fix:** Marked stale auth failures for cookie deletion in `require_auth`, added an app-level `HTTPException` handler to emit the unchanged 401 payload plus `delete_cookie`, and deleted the cookie explicitly on logout responses.
- **Files modified:** `jellyswipe/__init__.py`, `jellyswipe/dependencies.py`, `jellyswipe/routers/auth.py`
- **Verification:** `./.venv/bin/pytest tests/test_route_authorization.py -q`
- **Committed in:** `eda15ce`

**2. [Rule 3 - Blocking] Fixed the shared session-cookie test helper to use the app's host-scoped cookie domain**
- **Found during:** Task 2 (Lock in route-level stale-session and logout parity)
- **Issue:** `set_session_cookie()` injected hostless cookies, so TestClient could not observe the app's cookie-deletion headers reliably.
- **Fix:** Updated the helper to seed cookies with the same effective host scope as real app-issued session cookies.
- **Files modified:** `tests/conftest.py`
- **Verification:** `./.venv/bin/pytest tests/test_route_authorization.py -q -k "clears_stale_session_cookie or logout_clears_session_cookie"`
- **Committed in:** `eda15ce`

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** Both fixes were required to prove the user-visible stale-session and logout contract without expanding Phase 38 into broader persistence work.

## Issues Encountered

- Session-clearing semantics were already correct in server memory, but TestClient exposed that the signed cookie was not being observably removed under the stale-session/logout paths until response-side deletion and helper-domain alignment were added.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Auth routes now rely only on the async auth-service/UoW seam and keep the locked Phase 38 response contracts.
- Later persistence phases can reuse the same route-level pattern without reopening auth cookie/session parity.

## Self-Check: PASSED

- Verified summary file exists on disk.
- Verified task commits `0e001df`, `1960eb0`, `b80967d`, and `eda15ce` exist in git history.

---
*Phase: 38-auth-persistence-conversion*
*Completed: 2026-05-05*
