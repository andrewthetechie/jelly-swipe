# Phase 14: Test Infrastructure Setup - Context

**Gathered:** 2026-04-25
**Status:** Ready for planning

## Phase Boundary

Configure pytest environment and establish shared fixtures for isolated testing. This phase sets up the foundation for all subsequent testing work (database tests in Phase 15, Jellyfin provider tests in Phase 16, and coverage/CI in Phase 17).

## Implementation Decisions

### Test Directory Structure
- **D-01:** Use flat `tests/` directory — all test files in one place (test_db.py, test_jellyfin_library.py, etc.)
- **Rationale:** Simple and effective for current scope; easy to find all tests; can add subdirectories later if needed as test count grows

### Fixture Organization
- **D-02:** Use single `tests/conftest.py` for all fixtures
- **Rationale:** All fixtures (~4-5 needed) fit comfortably in one file; pytest auto-discovers conftest.py; easy to see all fixtures in one place; can extract domain-specific fixtures later if needed

### pytest Configuration
- **D-03:** Use standard pytest configuration in `pyproject.toml`
- **Rationale:** Better output and control than minimal config without overkill; includes testpaths, verbose output, and cleaner tracebacks
- **Specific settings:**
  - `[tool.pytest.ini_options]` section in pyproject.toml
  - `testpaths = ["tests"]` for explicit discovery
  - `python_files = ["test_*.py"]` for clarity
  - `addopts = "-v --tb=short"` for verbose output and cleaner tracebacks
  - Defer coverage configuration to Phase 17 (COV-01)

### Framework-Agnostic Import Strategy
- **D-04:** Import modules directly with monkeypatch in conftest.py
- **Rationale:** Pragmatic approach that doesn't require code refactoring; allows clean imports of `jellyswipe.db` and `jellyswipe.jellyfin_library.py` without Flask app side effects
- **Specific implementation:**
  - Patch `load_dotenv()` in `jellyswipe/__init__.py` to skip .env file loading
  - Patch `Flask()` call to prevent app initialization
  - Use `monkeypatch` fixture in conftest.py to apply these patches before test imports
  - This allows tests to import submodules without triggering Flask app creation

### the agent's Discretion
- **Environment variable mocking:** Use `monkeypatch` fixture in conftest.py to set test environment variables (JELLYFIN_URL, JELLYFIN_API_KEY, TMDB_API_KEY, etc.) — decide on specific env vars and values based on test needs
- **Fixture scopes:** Decide on function vs module vs session scopes for fixtures based on performance vs isolation tradeoffs — function-scope by default for maximum isolation
- **pytest markers:** Decide whether to use markers (e.g., `@pytest.mark.unit`, `@pytest.mark.integration`) if it becomes useful for organizing tests — defer until test suite grows

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Research Outputs
- `.planning/research/STACK.md` — Testing stack decisions (pytest, pytest-mock, responses, pytest-cov, pytest-timeout)
- `.planning/research/FEATURES.md` — Feature landscape for unit testing (table stakes, differentiators, anti-features)
- `.planning/research/ARCHITECTURE.md` — Fixture patterns and integration points (in-memory SQLite, HTTP mocking, conftest.py organization)
- `.planning/research/PITFALLS.md` — Anti-patterns to avoid (over-mocking, test coupling to implementation details, state leakage)
- `.planning/research/SUMMARY.md` — Executive synthesis with phase implications

### Project Documents
- `.planning/PROJECT.md` — Project context and v1.3 milestone goals
- `.planning/REQUIREMENTS.md` — v1.3 requirements (INFRA-01 through COV-02)
- `.planning/ROADMAP.md` — Phase 14-17 structure and success criteria

### Codebase Maps
- `.planning/codebase/CONVENTIONS.md` — Naming patterns, code style, import organization
- `.planning/codebase/STRUCTURE.md` — Directory layout, package structure (`jellyswipe/` from v1.2)
- `.planning/codebase/TESTING.md` — Existing testing patterns (none established, recommendations for future layout)

### Python Configuration
- `pyproject.toml` — Python 3.13 configuration, dependencies (Flask, gevent, gunicorn, python-dotenv, requests, werkzeug)

## Existing Code Insights

### Reusable Assets
- `pyproject.toml` — Already configured for Python 3.13 with uv dependency management; can add `[tool.pytest.ini_options]` section
- `jellyswipe/` package — Contains modules to test (`db.py`, `jellyfin_library.py`, `base.py`)
- `uv.lock` — Frozen dependency lockfile; pytest and test dependencies will be added here

### Established Patterns
- No existing test framework or patterns — this is a greenfield testing initiative
- Code style: `snake_case` for functions/variables, informal consistent style (no Black/Ruff)
- Package structure: `jellyswipe/` with `__init__.py`, `db.py`, `jellyfin_library.py`, `base.py`
- Import pattern: `jellyswipe/__init__.py` loads `.env` and initializes Flask app on import (needs monkeypatching)

### Integration Points
- **Database:** `jellyswipe/db.py` contains all SQLite operations (get_db, init_db, schema, migrations)
- **Jellyfin API:** `jellyswipe/jellyfin_library.py` contains `JellyfinLibraryProvider` with HTTP calls to Jellyfin/TMDB
- **Base abstraction:** `jellyswipe/base.py` contains `LibraryMediaProvider` abstract base class
- **Flask app:** `jellyswipe/__init__.py` initializes Flask app, routes, and SSE — NOT used in framework-agnostic tests

## Specific Ideas

No specific requirements — open to standard approaches for pytest setup and fixture organization.

## Deferred Ideas

None — discussion stayed within phase scope.
