# Phase 14: Test Infrastructure Setup - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-25
**Phase:** 14-Test Infrastructure Setup
**Areas discussed:** Test directory structure, Fixture organization, pytest configuration, Framework-agnostic imports

---

## Test Directory Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Flat tests/ | All test files in tests/ directory (simple, good starting point) | ✓ |
| By module | tests/test_db.py, tests/test_jellyfin_library.py (mirrors jellyswipe/ structure) | |
| unit/integration split | tests/unit/ and tests/integration/ subdirectories (clear separation) | |

**User's choice:** Flat tests/
**Notes:** Simple and effective for current scope; easy to find all tests; can add subdirectories later if needed.

---

## Fixture Organization

| Option | Description | Selected |
|--------|-------------|----------|
| Single conftest.py | All fixtures in tests/conftest.py (simple, pytest auto-discovers) | ✓ |
| Multiple fixture files | Separate files by domain (db_fixtures.py, api_fixtures.py) | |
| You decide | Choose the approach that makes the most sense | |

**User's choice:** Single conftest.py
**Notes:** All fixtures in one place; pytest auto-discovers; easy to see all fixtures; ~4-5 fixtures needed.

---

## pytest Configuration

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal | Just test discovery, use pytest defaults | |
| Standard (Recommended) | testpaths, verbose output, cleaner tracebacks | ✓ |
| Full-featured | Include coverage, markers, custom options | |

**User's choice:** Standard (Recommended)
**Notes:** Include testpaths, verbose output (-v), cleaner tracebacks (--tb=short); defer coverage to Phase 17.

---

## Framework-Agnostic Imports

| Option | Description | Selected |
|--------|-------------|----------|
| Import directly + monkeypatch | Import jellyswipe.db, jellyfin_library.py; patch __init__.py side effects in conftest.py | ✓ |
| Refactor modules | Extract pure logic from Flask-tied code (more work, cleaner long-term) | |
| sys.path manipulation | Bypass __init__.py by importing from jellyswipe/ directory directly | |

**User's choice:** Import directly + monkeypatch
**Notes:** Pragmatic approach without code refactoring; patch load_dotenv() and Flask() call in conftest.py.

### Monkeypatch Target

| Option | Description | Selected |
|--------|-------------|----------|
| Mock Flask app | Patch Flask() call to prevent app creation and .env loading | |
| Mock environment loading | Patch load_dotenv() to skip .env file, allow Flask import but don't run it | |
| You decide | Choose the most pragmatic approach for framework-agnostic tests | ✓ |

**User's choice:** You decide
**Notes:** Agent will mock Flask app — patch Flask() call and load_dotenv() to prevent app initialization.

---

## the agent's Discretion

Areas where user deferred to agent:
- Environment variable mocking — Use monkeypatch fixture for test env vars
- Fixture scopes — Decide function vs module vs session based on needs
- pytest markers — Defer until test suite grows

## Deferred Ideas

None — discussion stayed within phase scope.
