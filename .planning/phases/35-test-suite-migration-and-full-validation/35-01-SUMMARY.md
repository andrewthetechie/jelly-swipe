---
phase: 35-test-suite-migration-and-full-validation
plan: 01
subsystem: testing
tags: [FastAPI, TestClient, pytest, conftest, session, middleware]

# Dependency graph
requires:
  - phase: 33
    provides: FastAPI app factory and domain routers
provides:
  - FastAPI TestClient infrastructure in tests/conftest.py
  - set_session_cookie() helper for session injection
  - app and client fixtures with dependency_overrides for auth mocking
  - app_real_auth and client_real_auth fixtures for real auth testing
  - SECRET_KEY wiring in create_app() for test session signing
affects: [36, 37, 38, 39, 40]

# Tech tracking
tech-stack:
  added: [itsdangerous.TimestampSigner]
  patterns: [FastAPI TestClient fixture pattern, dependency_overrides for mocking, set_session_cookie helper]

key-files:
  created: []
  modified: [jellyswipe/__init__.py, tests/conftest.py]

key-decisions:
  - "Use itsdangerous.TimestampSigner (not URLSafeTimedSerializer) to match Starlette 1.0.0 SessionMiddleware format"
  - "Preserve SECRET_KEY in test_config to match FLASK_SECRET, ensuring set_session_cookie cookies are accepted"
  - "Separate app_real_auth fixture for real auth path tests (no dependency_overrides[require_auth])"

patterns-established:
  - "Pattern 1: FastAPI app fixture with tmp_path database and dependency_overrides.clear() teardown"
  - "Pattern 2: set_session_cookie helper uses TimestampSigner with b64encode(json_payload)"
  - "Pattern 3: Separate fixtures for mocked auth (app/client) vs real auth (app_real_auth/client_real_auth)"

requirements-completed: [TST-01, FAPI-01]

# Metrics
duration: 2min
completed: 2026-05-03T20:59:48Z
---

# Phase 35 Plan 1: Test Suite Foundation Summary

**FastAPI TestClient infrastructure with set_session_cookie helper, SECRET_KEY wiring, and real-auth fixture variants**

## Performance

- **Duration:** 2 min
- **Started:** 2026-05-03T20:56:56Z
- **Completed:** 2026-05-03T20:59:48Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- SessionMiddleware now reads SECRET_KEY from test_config when provided, enabling tests to control session signing
- FastAPI TestClient fixtures replace broken Flask test_client() calls
- set_session_cookie() helper creates Starlette-compatible signed cookies using TimestampSigner
- Framework-agnostic tests (test_db.py, test_auth.py, test_dependencies.py) continue to pass
- Both mocked auth (dependency_overrides) and real auth paths available for testing

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire SECRET_KEY into create_app() SessionMiddleware** - `ee3bc96` (feat)
2. **Task 2: Rewrite conftest.py with FastAPI TestClient infrastructure** - `10bb937` (feat)

**Plan metadata:** (pending final commit)

## Files Created/Modified

- `jellyswipe/__init__.py` - Modified create_app() to read SECRET_KEY from test_config for SessionMiddleware
- `tests/conftest.py` - Complete rewrite: added FastAPI TestClient imports, set_session_cookie helper, new app/client fixtures, app_real_auth/client_real_auth fixtures; preserved framework-agnostic fixtures and FakeProvider class

## Decisions Made

- Used itsdangerous.TimestampSigner (not URLSafeTimedSerializer) to exactly match Starlette 1.0.0 SessionMiddleware format
- Kept SECRET_KEY in test_config equal to FLASK_SECRET env var so set_session_cookie cookies are accepted
- Created separate app_real_auth fixture that does NOT set dependency_overrides[require_auth] for real auth path testing

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all acceptance criteria met. Pre-existing test failures in TestCleanupExpiredTokens class are documented in RESEARCH.md Pitfall 6 and were expected.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

FastAPI TestClient foundation complete. Ready for Wave 2 test migrations that will:
- Migrate route tests to use new TestClient fixtures
- Replace session_transaction() calls with set_session_cookie helper
- Verify all 178 route tests pass after migration
- Migrate SSE and static route tests

## Self-Check: PASSED

**Files created:**
- ✓ .planning/phases/35-test-suite-migration-and-full-validation/35-01-SUMMARY.md

**Commits verified:**
- ✓ ee3bc96 (Task 1: Wire SECRET_KEY into create_app() SessionMiddleware)
- ✓ 10bb937 (Task 2: Rewrite conftest.py with FastAPI TestClient infrastructure)
- ✓ a2f363c (Plan metadata: SUMMARY.md, STATE.md, ROADMAP.md, REQUIREMENTS.md)

**Acceptance criteria:**
- ✓ jellyswipe/__init__.py contains session_secret = test_config["SECRET_KEY"]
- ✓ jellyswipe/__init__.py contains secret_key=session_secret (not os.environ)
- ✓ Module-level app = create_app() still exists unchanged
- ✓ uv run python -c "from jellyswipe import app" exits 0
- ✓ tests/conftest.py contains from fastapi.testclient import TestClient
- ✓ tests/conftest.py contains def set_session_cookie(client, data: dict, secret_key: str)
- ✓ tests/conftest.py contains itsdangerous.TimestampSigner
- ✓ tests/conftest.py contains fast_app.dependency_overrides.clear()
- ✓ tests/conftest.py contains def app_real_auth( and def client_real_auth(
- ✓ tests/conftest.py does NOT contain app.test_client()
- ✓ tests/conftest.py does NOT contain from flask
- ✓ Framework-agnostic fixtures (mocker, mock_env_vars, db_path, db_connection) still present
- ✓ FakeProvider class still present with all methods
- ✓ tests pass (65 passed, 3 pre-existing failures in TestCleanupExpiredTokens)

---
*Phase: 35-test-suite-migration-and-full-validation*
*Completed: 2026-05-03*
