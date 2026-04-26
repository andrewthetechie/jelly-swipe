# Phase 22: Test Infrastructure Setup - Context

**Gathered:** 2026-04-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Add shared `app` and `client` fixtures to `tests/conftest.py` that use the Phase 21 `create_app(test_config=None)` factory pattern. These fixtures enable all subsequent route test phases (23-27) to create fresh Flask app instances with test-specific configuration. No test files are written in this phase — only fixture infrastructure in conftest.py.

</domain>

<decisions>
## Implementation Decisions

### Fixture Design
- **D-01:** Add function-scoped `app` fixture that calls `create_app(test_config={})` with a test config dict overriding database path to `tmp_path`-based temp file
- **D-02:** Add function-scoped `client` fixture that returns `app.test_client()` — depends on `app` fixture
- **D-03:** `app` fixture must initialize a fresh database via `init_db()` after patching DB_PATH — tests need schema present
- **D-04:** Fixtures compose with existing `db_connection` fixture pattern — route tests use `client`, direct DB tests continue using `db_connection`

### Provider Mocking
- **D-05:** `app` fixture includes a default `FakeProvider` mock for the provider singleton — most route tests need this
- **D-06:** Individual tests can override the provider mock if they need specific behavior (e.g., auth failure scenarios)

### Existing Test Compatibility
- **D-07:** Existing `test_route_authorization.py` keeps its local `app_module` / `client` fixtures — no migration in this phase (minimize churn, those tests work)
- **D-08:** New shared fixtures live in conftest.py alongside existing fixtures — no conflicts since they have different names
- **D-09:** Existing framework-agnostic tests (test_db.py, test_jellyfin_library.py) are unaffected — they don't use Flask fixtures

### Session Isolation
- **D-10:** `app` fixture uses `app.config['TESTING'] = True` for Flask test mode
- **D-11:** Each `app` instance gets a unique secret key to prevent session leakage between tests

### the agent's Discretion
- Exact test_config dict contents beyond DB_PATH override
- Whether to add helper fixtures for common test setup patterns (e.g., seeded room, authenticated session)
- FakeProvider class placement (in conftest.py vs separate test_helpers.py)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 21 Context (factory pattern)
- `.planning/phases/21-app-factory-refactor/21-CONTEXT.md` — Factory function decisions (D-01 through D-16), especially D-04 (test_config merging) and D-12 (DB init during factory)

### Existing Test Patterns
- `tests/conftest.py` — Current fixture patterns: mock_env_vars, db_path, db_connection, mocker, setup_test_environment
- `tests/test_route_authorization.py` — Existing route test patterns: FakeProvider, app_module fixture, client fixture, session helpers

### Research
- `.planning/research/SUMMARY.md` — v1.5 research: Flask test client patterns, fixture isolation, pitfalls to avoid
- `.planning/codebase/TESTING.md` — Testing patterns analysis for the codebase

### Flask Documentation
- `https://flask.palletsprojects.com/en/stable/testing/` — Flask testing guide with app factory and test client patterns

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `jellyswipe/__init__.py:create_app()` — Factory function from Phase 21, accepts test_config dict to override app.config
- `tests/conftest.py:db_connection` — Function-scoped fixture that patches DB_PATH, calls init_db(), yields connection — route tests will use similar DB setup
- `tests/test_route_authorization.py:FakeProvider` — Provider mock class with methods for auth testing — reusable for new shared fixtures

### Established Patterns
- **Function-scoped isolation**: All test fixtures use function scope (db_connection, mock_env_vars)
- **tmp_path for databases**: Each test gets its own temp SQLite file via pytest's tmp_path
- **monkeypatch for DB_PATH**: Patch `jellyswipe.db.DB_PATH` before calling init_db()
- **Provider singleton patching**: Patch `_provider_singleton` on the module object

### Integration Points
- **conftest.py** — New fixtures added here; existing fixtures untouched
- **jellyswipe/__init__.py:create_app()** — Factory function called by new `app` fixture
- **jellyswipe/db.py** — DB_PATH patching and init_db() call in `app` fixture
- **Phase 23-27 test files** — Will import `client` fixture from conftest.py

</code_context>

<specifics>
## Specific Ideas

No specific requirements — standard Flask testing infrastructure following official documentation patterns.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---
*Phase: 22-test-infrastructure-setup*
*Context gathered: 2026-04-26*
