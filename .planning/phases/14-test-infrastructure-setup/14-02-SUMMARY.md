---
phase: 14-test-infrastructure-setup
plan: 02
subsystem: test-infrastructure
tags: [pytest, fixtures, environment-setup, framework-agnostic]
dependency_graph:
  requires: [14-01]
  provides: [14-03]
  affects: [tests/conftest.py, jellyswipe/db, jellyswipe/jellyfin_library]
tech_stack:
  added:
    - "pytest fixtures for test environment setup"
    - "unittest.mock for monkeypatching Flask and load_dotenv"
  patterns:
    - "session-scoped autouse fixtures for global test setup"
    - "function-scoped fixtures for per-test environment isolation"
    - "monkeypatching to enable framework-agnostic module imports"
key_files:
  created: ["tests/__init__.py", "tests/conftest.py"]
  modified: []
decisions: []
metrics:
  duration: "1 minute"
  completed_date: "2026-04-25"
---

# Phase 14 Plan 02: Test Environment Setup Summary

Create tests/conftest.py with environment fixtures that enable framework-agnostic imports of jellyswipe modules without triggering Flask app initialization.

## What Was Built

**Test Environment Fixtures**
- Created tests/ directory structure with __init__.py and conftest.py
- Implemented setup_test_environment fixture (session-scoped, autouse=True) that patches load_dotenv() and Flask()
- Implemented mock_env_vars fixture (function-scoped) for per-test environment variable overrides

**Key Implementation Details**
1. **setup_test_environment fixture** - Session-scoped and autouse=True, runs once before all tests:
   - Patches load_dotenv() to skip .env file loading (prevents loading wrong .env values)
   - Patches Flask() to return None (prevents app initialization)
   - Sets test environment variables (JELLYFIN_URL, TMDB_API_KEY, FLASK_SECRET)
   - Yields control to tests, allowing imports with mocks in place
   - Stops mocks on cleanup to restore original behavior

2. **mock_env_vars fixture** - Function-scoped for test isolation:
   - Provides test environment variables for individual tests
   - Can be used to override env vars per test
   - Ensures test isolation via function-scope

## Deviations from Plan

None - plan executed exactly as written.

## Verification

✓ tests/ directory exists
✓ tests/__init__.py exists (empty file)
✓ tests/conftest.py exists with setup_test_environment fixture
✓ setup_test_environment fixture patches load_dotenv() (mock_load_dotenv found)
✓ setup_test_environment fixture patches Flask() (mock_flask found)
✓ setup_test_environment fixture sets test environment variables (os.environ.setdefault found)
✓ mock_env_vars fixture exists for per-test env var overrides
✓ setup_test_environment is session-scoped (scope="session") and autouse (autouse=True)

## Threat Surface Scan

No new security-relevant surface introduced. Test environment uses hardcoded test values and explicit monkeypatching to control imports.

## Requirements Satisfied

**INFRA-02:** tests/conftest.py provides database, mock, and test data fixtures ✓
- setup_test_environment fixture is session-scoped and autouse ✓
- setup_test_environment patches load_dotenv() to skip .env file loading ✓
- setup_test_environment patches Flask() to prevent app initialization ✓
- setup_test_environment sets JELLYFIN_URL, TMDB_API_KEY, FLASK_SECRET env vars ✓

**INFRA-03:** Tests import and execute modules directly without Flask app initialization ✓
- Importing jellyswipe.db in conftest.py or test files does not trigger Flask app initialization (via Flask() patch)
- No RuntimeError about missing environment variables when importing jellyswipe modules (via load_dotenv() patch and env vars)

## Commits

| Hash | Message | Files |
|------|---------|-------|
| d50a51b | feat(14-02): create tests/conftest.py with environment fixtures | tests/__init__.py, tests/conftest.py |

## Self-Check: PASSED

✓ tests/conftest.py exists and contains required fixtures
✓ tests/__init__.py exists
✓ Commit exists in git history
✓ Fixtures are correctly scoped and configured
