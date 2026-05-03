---
phase: 32-auth-rewrite-and-dependency-injection-layer
plan: 01
subsystem: auth
tags: [fastapi, dependency-injection, authentication, rate-limiting]

# Dependency graph
requires:
  - phase: 31-fastapi-app-factory-and-session-middleware
    provides: "FastAPI app factory with SessionMiddleware, de-Flaskified auth.py"
provides:
  - jellyswipe/dependencies.py module with FastAPI DI callables
  - AuthUser dataclass for type-safe auth dependency
  - require_auth() - Depends()-compatible auth guard returning AuthUser or raising 401
  - get_db_dep() - yield dependency for database connections
  - DBConn - Annotated type alias for sqlite3.Connection with auto-cleanup
  - check_rate_limit() - Depends()-compatible rate limiter with path inference
  - destroy_session_dep() - Depends()-compatible session destroyer
  - get_provider() - Depends()-compatible JellyfinLibraryProvider singleton accessor
affects: [33-domain-routers-and-dependency-wiring, 34-sse-migration, 35-test-migration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "FastAPI Depends() pattern for dependency injection"
    - "yield dependencies for resource lifecycle management"
    - "Annotated type aliases for reusable dependencies"
    - "Path inference for rate limit configuration"
    - "Lazy import pattern to avoid circular dependencies"

key-files:
  created:
    - jellyswipe/dependencies.py - New FastAPI DI module
    - tests/test_dependencies.py - Comprehensive tests for DI callables
  modified:
    - tests/test_auth.py - Rewritten with FastAPI TestClient, removed all Flask imports

key-decisions:
  - "AuthUser dataclass in dependencies.py (not auth.py) - FastAPI DI concept"
  - "_RATE_LIMITS duplicated in dependencies.py to avoid circular import with __init__.py (per RESEARCH.md recommendation)"
  - "get_provider() uses lazy import inside function body to avoid circular import"
  - "get_db_dep() wraps get_db_closing() contextmanager for guaranteed connection cleanup"

patterns-established:
  - "Pattern 1: Depends() with Annotated Type Alias - DBConn = Annotated[sqlite3.Connection, Depends(get_db_dep)]"
  - "Pattern 2: Yield Dependency for Resource Cleanup - with get_db_closing() as conn: yield conn"
  - "Pattern 3: Dependency That Raises HTTPException - require_auth() and check_rate_limit() guard patterns"
  - "Pattern 4: Cross-Module Dependency - get_provider() accesses __init__py global via lazy import"

requirements-completed: [ARCH-03]

# Metrics
duration: 8 min
completed: 2026-05-03T04:32:21Z
---

# Phase 32 Plan 01: Auth Rewrite and Dependency Injection Layer Summary

**FastAPI dependency injection module with AuthUser dataclass, require_auth() guard, DB connection yield dependency, rate limiter with path inference, and provider singleton - all tested with FastAPI TestClient replacing Flask-based tests.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-05-03T04:23:23Z
- **Completed:** 2026-05-03T04:32:21Z
- **Tasks:** 2 (both TDD)
- **Files modified:** 3

## Accomplishments

- Created `jellyswipe/dependencies.py` with 7 exports (AuthUser, require_auth, get_db_dep, DBConn, check_rate_limit, destroy_session_dep, get_provider)
- Implemented `require_auth()` that returns `AuthUser(jf_token, user_id)` or raises HTTPException(401)
- Implemented `get_db_dep()` yield dependency wrapping `get_db_closing()` for automatic connection cleanup
- Implemented `check_rate_limit()` with path inference against `_RATE_LIMITS` dict
- Implemented `destroy_session_dep()` wrapping `auth.destroy_session()`
- Implemented `get_provider()` with lazy import to avoid circular import with `__init__.py`
- Rewrote `tests/test_auth.py` from Flask to FastAPI TestClient (14 tests, all passing)
- Created `tests/test_dependencies.py` with 11 tests for DI callables
- Zero Flask imports in both dependencies.py and test_auth.py

## Task Commits

Each task was committed atomically following TDD RED-GREEN-REFACTOR cycle:

1. **Task 1: Create dependencies.py with all DI callables** - `2bb5059` (test), `3f356a9` (feat)
2. **Task 2: Rewrite tests/test_auth.py with FastAPI TestClient** - `dcee6cd` (feat)

**Plan metadata:** `2bb5059` + `3f356a9` + `dcee6cd` = plan work

## Files Created/Modified

- `jellyswipe/dependencies.py` - New FastAPI dependency injection module with 7 exports and all DI callables
- `tests/test_dependencies.py` - New test file with 11 tests for DI callables
- `tests/test_auth.py` - Completely rewritten from Flask to FastAPI TestClient, 14 tests all passing

## Decisions Made

None - followed plan as specified. All design decisions from CONTEXT.md (D-01 through D-10) were implemented exactly as specified.

## Deviations from Plan

None - plan executed exactly as written. All TDD gates (RED → GREEN → REFACTOR) passed correctly:

- **Task 1 TDD Gates:**
  - RED: Created test_dependencies.py with failing tests (NotImplementedError)
  - GREEN: Implemented all DI callables to pass tests
  - REFACTOR: No cleanup needed - implementation was clean from the start

- **Task 2 TDD Gates:**
  - RED: Original tests were already failing (ModuleNotFoundError: no module named 'flask')
  - GREEN: Rewrote with FastAPI TestClient, all 14 tests passing
  - REFACTOR: Added teardown_method() to reset rate limiter state between tests

## Issues Encountered

None - all issues were self-corrected during TDD cycle:

- **Rate limiter state sharing between tests:** Fixed by adding `teardown_method()` to reset rate limiter in both test_dependencies.py and test_auth.py
- **Import path patching in get_provider tests:** Fixed by changing approach to test actual singleton behavior rather than mocking internal imports

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- **dependencies.py complete** with all DI callables ready for Phase 33 router extraction
- **auth.py unchanged** (as per D-09) - routes continue using `_require_login()` until Phase 33
- **__init__.py unchanged** (as per D-09) - `_provider_singleton` stays in __init__.py until Phase 33
- **Test suite passing** - 14 auth tests + 11 dependencies tests = 25 tests for DI layer
- **Ready for Phase 33** (domain-routers-and-dependency-wiring) - DI module can now be wired into extracted routers

---

*Phase: 32-Auth Rewrite and Dependency Injection Layer*
*Completed: 2026-05-03*
