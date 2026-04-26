# Phase 21: App Factory Refactor - Context

**Gathered:** 2026-04-26
**Status:** Ready for planning

## Phase Boundary

Refactor `jellyswipe/__init__.py` from side-effecting module body to an explicit `create_app(test_config=None)` factory function. This enables test isolation by allowing route tests to create fresh Flask app instances with test-specific configuration. The refactor must maintain full backwards compatibility with existing imports (Dockerfile, Gunicorn CMD, existing code patterns) and preserve all current functionality.

## Implementation Decisions

### Factory Function Signature
- **D-01:** Factory function must be named `create_app(test_config=None)` exactly as specified in FACTORY-01
- **D-02:** Factory returns Flask app instance configured for production or test use
- **D-03:** When test_config is None, factory uses environment variables (current production behavior)
- **D-04:** When test_config is provided (dict), factory merges it with default config to override database path, secret key, etc. for test isolation

### Environment Validation
- **D-05:** Keep environment variable validation (JELLYFIN_URL, TMDB_API_KEY, FLASK_SECRET) at module import time for early failure in production
- **D-06:** Tests will mock or set required env vars before calling `create_app()` (already done in conftest.py)

### Backwards Compatibility
- **D-07:** Global `app` instance must still exist at module level for `jellyswipe:app` import (Dockerfile CMD uses this)
- **D-08:** Global `app` is created by calling `app = create_app()` at module level after factory is defined
- **D-09:** All existing imports and code patterns continue to work without changes

### Database Initialization
- **D-10:** Database initialization (`init_db()`) happens during factory execution, not at module import
- **D-11:** This ensures each test can have a fresh database by overriding DB_PATH in test_config
- **D-12:** Production behavior unchanged: database initializes on app startup

### Provider Singleton
- **D-13:** Keep `_provider_singleton` pattern as is (module-level singleton with `get_provider()` function)
- **D-14:** No changes needed to provider instantiation or caching logic

### Route Registration
- **D-15:** All routes remain defined in `jellyswipe/__init__.py` with decorators
- **D-16:** Routes are registered on the app instance returned by factory function (no change to route definitions)

### the agent's Discretion
- Exact order of operations within `create_app()` (env validation vs app creation vs route registration)
- How test_config is merged with default config (dict.update() vs Flask's config.from_mapping() or config.update())
- Whether to extract route registration into a separate `register_routes(app)` function for clarity

## Canonical References

### Flask App Factory Pattern
- `https://flask.palletsprojects.com/en/stable/tutorial/factory/` — Official Flask tutorial on factory pattern, shows standard `create_app(test_config=None)` implementation

### Flask Configuration
- `https://flask.palletsprojects.com/en/stable/config/` — Flask config object documentation, test_config merging approaches

### Testing with Factories
- `https://flask.palletsprojects.com/en/stable/testing/` — Flask testing guide, shows how to use app factory with test client

### Research Findings
- `.planning/research/SUMMARY.md` — v1.5 research confirms no new dependencies needed, Flask's built-in test client is sufficient
- `.planning/research/STACK.md` — Stack research confirms Flask 3.1.3+ and pytest 9.0.0+ provide all needed capabilities

## Existing Code Insights

### Reusable Assets
- `tests/conftest.py` — Existing environment setup and monkeypatching patterns (mock_load_dotenv, mock_env_vars, db_connection)
- `tests/test_route_authorization.py` — Example of route testing that could use app factory pattern (if exists)
- `jellyswipe/db.py` — Database module with `init_db()` and `get_db()` functions, already has DB_PATH global that can be overridden

### Established Patterns
- **Framework-agnostic testing**: Tests mock Flask entirely via `conftest.py` to avoid side effects
- **Function-scoped fixtures**: All test fixtures use function scope for complete isolation (db_connection, mock_env_vars)
- **Global singleton pattern**: Provider uses module-level singleton with `get_provider()` accessor (should be preserved)
- **Environment-driven configuration**: Current app reads all config from environment variables (test_config dict will override these for tests)

### Integration Points
- **Dockerfile CMD**: `jellyswipe:app` imports global `app` instance from module — must be preserved
- **Gunicorn startup**: Loads app via WSGI entry point `jellyswipe:app` — unchanged by refactor
- **Route definitions**: All routes currently use `@app.route()` decorators on global app — routes register on factory-returned app instead
- **Database module**: `jellyswipe.db.DB_PATH` is set at module import time in current code — tests will override this via monkeypatch before calling `create_app()`

## Specific Ideas

No specific requirements — open to standard Flask factory pattern approaches.

## Deferred Ideas

None — discussion stayed within phase scope.

---
*Phase: 21-app-factory-refactor*
*Context gathered: 2026-04-26*
