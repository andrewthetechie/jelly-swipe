---
phase: 33-router-extraction-and-endpoint-parity
plan: 01
subsystem: api
tags: [fastapi, router-extraction, config, dependency-injection, jellyfin, tmdb]

# Dependency graph
requires:
  - phase: 32-auth-rewrite-and-dependency-injection
    provides: dependencies.py with require_auth, DBConn, check_rate_limit, get_provider
provides:
  - config.py as single source of truth for shared runtime constants (TMDB_AUTH_HEADERS, JELLYFIN_URL, _token_user_id_cache, CLIENT_ID)
  - routers/auth.py with 6 authentication routes
  - routers/static.py with 4 static file routes
  - routers/media.py with 4 media-related routes (trailer, cast, genres, watchlist)
  - routers/proxy.py with 1 image proxy route with rate limiting
affects:
  - Phase 33 Plan 02 (app factory refactor - will wire these routers into create_app())

# Tech tracking
tech-stack:
  added: [FastAPI APIRouter, dependency injection pattern]
  patterns:
    - Router extraction pattern: domain-specific routers using APIRouter() with no prefix
    - Dependency injection: Depends(require_auth), Depends(check_rate_limit), Depends(get_provider)
    - Shared config: central module (config.py) for all runtime constants

key-files:
  created:
    - jellyswipe/config.py
    - jellyswipe/routers/__init__.py
    - jellyswipe/routers/auth.py
    - jellyswipe/routers/static.py
    - jellyswipe/routers/media.py
    - jellyswipe/routers/proxy.py
  modified: []

key-decisions:
  - "Export JELLYFIN_URL (no underscore) from config.py for router imports - _JELLYFIN_URL remains internal"
  - "Keep XSSSafeJSONResponse in __init__.py and import it into routers (avoids circular import issues)"
  - "Each router defines its own make_error_response and log_exception helpers (copied pattern from monolith)"
  - "All routers use APIRouter() with no prefix (D-14) - prefixing will happen in app factory (Plan 02)"

patterns-established:
  - "Pattern 1: Domain routers extracted from monolith with minimal changes - verbatim handler logic with DI substitutions"
  - "Pattern 2: Shared config module (config.py) initialized at import time, same as original monolith pattern"
  - "Pattern 3: Router-specific helpers (make_error_response, log_exception) defined per-router to avoid shared module complexity"

requirements-completed: [ARCH-01, FAPI-02]

# Metrics
duration: 13min
completed: 2026-05-03T06:55:03Z
---

# Phase 33 Plan 01: Create config.py and extract 4 domain routers

**Shared config module extracted from monolith, plus 4 domain routers (auth, static, media, proxy) with correct DI wiring**

## Performance

- **Duration:** 13 min
- **Started:** 2026-05-03T06:41:59Z
- **Completed:** 2026-05-03T06:55:03Z
- **Tasks:** 2
- **Files modified:** 6 files created

## Accomplishments

- Created `config.py` as the single source of truth for all shared runtime constants (TMDB_AUTH_HEADERS, JELLYFIN_URL, _token_user_id_cache, CLIENT_ID, TOKEN_USER_ID_CACHE_TTL_SECONDS, IDENTITY_ALIAS_HEADERS, _provider_singleton, _RATE_LIMITS)
- Moved env var validation and SSRF validation (validate_jellyfin_url) to config.py
- Extracted 6 auth routes to `routers/auth.py` (provider, server-identity, login, logout, me, jellyfin/server-info)
- Extracted 4 static routes to `routers/static.py` (index, manifest.json, sw.js, favicon.ico)
- Extracted 4 media routes to `routers/media.py` (trailer, cast, genres, watchlist/add)
- Extracted 1 proxy route to `routers/proxy.py` (image proxy with rate limiting and regex validation)
- All routers use APIRouter() with no prefix (D-14)
- All authenticated routes use Depends(require_auth) from dependencies.py (D-14, ARCH-01)
- All rate-limited routes use Depends(check_rate_limit)
- Imported XSSSafeJSONResponse from jellyswipe package (custom class preserved from v1.5)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create config.py and routers/__init__.py** - `73f786b` (feat)
2. **Task 2: Extract auth, static, media, and proxy routers** - `4b54b07` (feat)

**Plan metadata:** (to be added after SUMMARY.md commit)

## Files Created/Modified

- `jellyswipe/config.py` - Shared runtime configuration module with env var validation, SSRF validation, and all module-level constants
- `jellyswipe/routers/__init__.py` - Package init for routers directory
- `jellyswipe/routers/auth.py` - 6 authentication routes (GET /auth/provider, POST /auth/jellyfin-use-server-identity, POST /auth/jellyfin-login, POST /auth/logout, GET /me, GET /jellyfin/server-info)
- `jellyswipe/routers/static.py` - 4 static file routes (GET /, GET /manifest.json, GET /sw.js, GET /favicon.ico)
- `jellyswipe/routers/media.py` - 4 media routes (GET /get-trailer/{movie_id}, GET /cast/{movie_id}, GET /genres, POST /watchlist/add)
- `jellyswipe/routers/proxy.py` - 1 proxy route (GET /proxy with rate limiting and regex path validation)

## Decisions Made

- Export JELLYFIN_URL (no underscore) from config.py for router imports, keeping _JELLYFIN_URL as internal variable
- Keep XSSSafeJSONResponse in __init__.py and import it into routers (avoids circular import issues - routers import from package which exports the class)
- Each router defines its own make_error_response and log_exception helpers (copied pattern from monolith, each with its own _logger)
- All routers use APIRouter() with no prefix (D-14) - prefixing will happen in app factory (Plan 02)
- Use TYPE_CHECKING pattern for _provider_singleton type hint to avoid circular import with jellyfin_library.py

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- config.py is ready as the single source of truth for shared runtime constants
- 4 router modules extracted with correct route counts: auth(6), static(4), media(4), proxy(1)
- All routers use APIRouter() with no prefix
- All authenticated routes use Depends(require_auth) from dependencies.py
- __init__.py is unmodified (Plan 02 will handle app factory refactor to wire these routers)

Ready for Phase 33 Plan 02 (app factory refactor and rooms router extraction).

---
*Phase: 33-router-extraction-and-endpoint-parity*
*Completed: 2026-05-03*

## Self-Check: PASSED

- ✅ SUMMARY.md exists at .planning/phases/33-router-extraction-and-endpoint-parity/33-01-SUMMARY.md
- ✅ Commit 73f786b found: "feat(33-01): create config.py and routers/__init__.py"
- ✅ Commit 4b54b07 found: "feat(33-01): extract auth, static, media, and proxy routers"
- ✅ Commit 56b9cad found: "docs(33-01): complete [create config.py and extract routers] plan"
- ✅ All key files created: config.py, routers/__init__.py, routers/auth.py, routers/static.py, routers/media.py, routers/proxy.py
- ✅ STATE.md updated (Plan 2 of 2, 80% progress)
- ✅ ROADMAP.md updated (1 of 2 summaries, status "In Progress")
- ✅ REQUIREMENTS.md updated (ARCH-01 and FAPI-02 marked complete)
