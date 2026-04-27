---
phase: 24-tmdb-security
plan: 01
subsystem: security
tags: [tmdb, bearer-token, auth, headers, credentials]

requires:
  - phase: 23-http-hardening
    provides: "make_http_request with headers param support"
provides:
  - "TMDB API calls use Bearer token via Authorization header"
  - "No api_key query params in any TMDB URL"
  - "Boot validation requires TMDB_ACCESS_TOKEN"
  - "AST-based regression test preventing api_key re-introduction"
affects: [http-client, tmdb, security]

tech-stack:
  added: []
  patterns: ["Bearer token auth via headers for TMDB API", "AST scanning for credential leak prevention"]

key-files:
  created:
    - "tests/test_tmdb_auth.py"
  modified:
    - "jellyswipe/__init__.py"
    - "tests/conftest.py"
    - "tests/test_infrastructure.py"
    - "tests/test_routes_xss.py"

key-decisions:
  - "Keep v3 API paths (/3/search/movie, /3/movie/{id}/videos, /3/movie/{id}/credits) — Bearer tokens work with v3 endpoints"
  - "Hard break: TMDB_API_KEY removed entirely, app requires TMDB_ACCESS_TOKEN"

patterns-established:
  - "TMDB_AUTH_HEADERS dict pattern for Authorization: Bearer header injection"

requirements-completed:
  - TMDB-01
  - TMDB-02
  - HTTP-02

duration: 7min
completed: 2026-04-27
---

# Phase 24 Plan 01: TMDB Bearer Token Auth Summary

**Migrated TMDB API authentication from v3 URL query-string api_key to Bearer token Authorization headers, eliminating credential exposure in URLs, logs, and browser network tabs.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-04-27T04:12:47Z
- **Completed:** 2026-04-27T04:19:19Z
- **Tasks:** 1
- **Files modified:** 5

## Accomplishments
- Removed all `api_key=` from 4 TMDB URL constructions in get_trailer and get_cast routes
- Added `TMDB_AUTH_HEADERS` with `Authorization: Bearer <token>` to all TMDB API calls
- Renamed env var from TMDB_API_KEY to TMDB_ACCESS_TOKEN with boot-time enforcement
- Created 6 AST-based and mock-based security regression tests

## Task Commits

Each task was committed atomically:

1. **Task 1: Migrate TMDB auth to v4 Bearer token** - `8524948` (test) + `33a6892` (feat)

## Files Created/Modified
- `tests/test_tmdb_auth.py` - 6 new tests: AST scan for api_key, Bearer header verification for trailer/cast, URL credential exposure check, TMDB_API_KEY removal verification, boot validation check
- `jellyswipe/__init__.py` - Replaced TMDB_API_KEY with TMDB_ACCESS_TOKEN, added TMDB_AUTH_HEADERS, updated boot validation, removed api_key from 4 URLs
- `tests/conftest.py` - Updated env var defaults from TMDB_API_KEY to TMDB_ACCESS_TOKEN
- `tests/test_infrastructure.py` - Updated env var assertion to TMDB_ACCESS_TOKEN
- `tests/test_routes_xss.py` - Updated env var setup to TMDB_ACCESS_TOKEN

## Decisions Made
- Kept v3 API paths unchanged — TMDB Bearer tokens work with both v3 and v4 endpoints
- Hard break on TMDB_API_KEY — not backwards compatible, operators must set TMDB_ACCESS_TOKEN

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Duplicate code block in get_cast after edit**
- **Found during:** Task 1 (GREEN phase implementation)
- **Issue:** First edit of get_cast URL replacement left a partial duplicate block, causing a code path where `c_res` was never set
- **Fix:** Consolidated duplicate code blocks into single correct implementation
- **Files modified:** jellyswipe/__init__.py
- **Verification:** All 107 tests pass including cast bearer token test
- **Committed in:** 33a6892 (part of feat commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Trivial — edit artifact fixed immediately. No scope creep.

## Issues Encountered
None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- TMDB auth migration complete, all 107 tests pass
- Ready for next plan in phase 24

---
*Phase: 24-tmdb-security*
*Completed: 2026-04-27*
