# Technology Stack

**Project:** Jelly Swipe - v1.5 Route Test Coverage
**Researched:** 2026-04-26
**Domain:** Flask web application with route testing and app factory pattern
**Confidence:** HIGH

## Recommended Stack

### Core Framework
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **Flask** | >=3.1.3 | Web framework with built-in test client | Flask provides native test client that doesn't require additional plugins. The app factory pattern is a standard Flask pattern for testability and configuration management. |
| **Python** | >=3.13,<3.14 | Runtime environment | Current LTS with uv lockfile; matches existing project configuration |

### Testing Framework
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **pytest** | >=9.0.0 | Test framework and runner | Modern pytest with excellent fixture support, parametrization, and discovery. Already in use with 48 tests. |
| **pytest-cov** | >=7.1.0 | Coverage measurement and enforcement | Provides `--cov-fail-under=70` threshold enforcement for CI. Terminal-only reporting (`term-missing`) already configured. |
| **pytest-mock** | >=3.14.0 | Mocking utilities | Lightweight mocker fixture already used in existing tests. Cleaner than unittest.mock for pytest suites. |
| **responses** | >=0.25.0 | HTTP request mocking | Mock external HTTP calls (Jellyfin, TMDB) in route tests without hitting real APIs. |

### Infrastructure
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **uv** | latest | Dependency management | Already adopted in v1.2; provides fast, reproducible installs with frozen lockfile. |
| **Gunicorn** | >=25.3.0 | WSGI server with gevent workers | Production server; supports SSE streaming without SystemExit errors (shipped v1.2). |

### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **werkzeug** | >=3.1.8 | HTTP utilities and test client | Underpins Flask's test client; no direct usage needed in tests. |
| **python-dotenv** | >=1.2.2 | Environment variable loading | Already monkeypatched in conftest.py for framework-agnostic tests. |

## Stack Changes for v1.5

### No New Dependencies Required

The existing stack has all necessary components for Flask route testing with app factory pattern:

1. **Flask 3.1.3+** provides:
   - Built-in `test_client()` for making HTTP requests without a live server
   - `create_app(test_config=None)` pattern for application factories
   - Session management via `client.session_transaction()`
   - Request context via `app.test_request_context()`

2. **pytest 9.0.0+** provides:
   - Fixture system for app/client/database setup
   - Parametrization for testing multiple scenarios
   - Already configured with `--cov=jellyswipe --cov-report=term-missing`

3. **pytest-cov 7.1.0+** provides:
   - `--cov-fail-under=70` for coverage threshold enforcement
   - Terminal reporting with missing line indicators
   - Integration with pytest's exit code

### Configuration Changes Only

**Update `pyproject.toml` pytest.ini_options:**

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-v --tb=short --cov=jellyswipe --cov-report=term-missing --cov-fail-under=70"
```

This single change enforces 70% coverage in CI while maintaining existing test behavior.

### App Factory Pattern Implementation

**Refactor `jellyswipe/__init__.py`:**

```python
def create_app(test_config=None):
    app = Flask(__name__,
                template_folder=os.path.join(_APP_ROOT, 'templates'),
                static_folder=os.path.join(_APP_ROOT, 'static'))

    # Configuration
    if test_config is None:
        app.secret_key = os.environ["FLASK_SECRET"]
    else:
        app.config.update(test_config)

    # Routes, extensions, etc.
    # ... (move all route definitions and setup here)

    return app

# For backwards compatibility with Gunicorn and local dev
app = create_app()
```

**Add fixtures to `tests/conftest.py`:**

```python
@pytest.fixture
def app(db_path, monkeypatch):
    """Create and configure a test app instance."""
    # Import here to avoid side effects at module load time
    import jellyswipe

    # Patch DB_PATH before importing the app module
    import jellyswipe.db
    monkeypatch.setattr(jellyswipe.db, 'DB_PATH', db_path)

    # Create app with test config
    test_app = jellyswipe.create_app({
        'TESTING': True,
        'SECRET_KEY': 'test-secret-key',
    })

    # Initialize database
    with test_app.app_context():
        jellyswipe.db.init_db()

    return test_app

@pytest.fixture
def client(app):
    """Create a test client for making HTTP requests."""
    return app.test_client()
```

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| **Flask test client** | Built-in `app.test_client()` | pytest-flask plugin | pytest-flask adds a dependency but provides minimal benefit: the built-in client already has all needed features (session, headers, JSON, redirects). Existing tests already use the built-in client successfully. |
| **Coverage reporting** | `--cov-report=term-missing` | `--cov-report=html` | HTML reports require generating files and directories; terminal-only is simpler and meets v1.3 requirements. Can add HTML in v2 if needed. |
| **Mocking approach** | pytest-mock + responses | unittest.mock + custom mocks | pytest-mock provides a cleaner API (`mocker.patch()` vs `patch()` context managers). Responses is specifically designed for HTTP mocking and matches existing test patterns. |
| **Test isolation** | Function-scoped fixtures with tmp_path | Session-scoped fixtures with shared DB | Function-scoped ensures complete test isolation—no state leaks between tests. The 48 existing tests prove this approach works well. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **pytest-flask** | Adds unnecessary dependency; built-in Flask test client is sufficient. Existing `test_route_authorization.py` already demonstrates successful route testing without pytest-flask. | Use Flask's built-in `app.test_client()` with custom fixtures in conftest.py. |
| **pytest-xdist** (parallel test execution) | Not needed for initial test suite; adds complexity and potential ordering issues. Parallel execution can be added later when test count grows significantly. | Run tests sequentially; add xdist in v2 if test time becomes a bottleneck. |
| **Hypothesis** (property-based testing) | Nice to have, not critical for v1.5 milestone. Property-based tests are valuable for complex business logic but overkill for route happy paths. | Use parametrized tests for multiple scenarios; consider Hypothesis for v2 when testing edge cases. |
| **Selenium / Playwright** (browser automation) | Overkill for unit/integration route testing. These are for end-to-end UI testing, which is a separate concern. | Use test client for route testing; add browser automation in v2 if needed for E2E tests. |
| **Flask-Testing** | Deprecated/abandoned; last release 2016. Not compatible with modern Flask 3.x. | Use Flask's built-in test client. |
| **Live server** (`live_server` fixture) | Not needed for route testing; test client doesn't require a running server. Only needed for JavaScript integration or external HTTP clients. | Use `app.test_client()`; only use live server if testing SSE with actual HTTP clients. |

## Stack Patterns by Variant

**If testing routes with session state:**
- Use `with client.session_transaction() as session:` to modify session before requests
- Because Flask's session is encrypted; session_transaction() handles the encryption/decryption

**If testing routes that require authentication:**
- Set session with `session['active_room']` and `session['my_user_id']` via session_transaction
- Or set headers with `client.post(..., headers={'Authorization': 'Token="..."'})`
- Because the app checks both session and Authorization header for identity

**If testing SSE endpoints (`/room/stream`):**
- Use generator pattern: `response = client.get('/room/stream'); data = list(response.response)`
- Or use pytest-flask's `live_server` if testing with actual HTTP clients
- Because SSE returns a streaming generator; test client provides access to the generator

**If testing routes that depend on app context:**
- Use `with app.app_context():` to push context for database initialization
- Because database extensions require active app context for queries

**If mocking external HTTP calls (Jellyfin, TMDB):**
- Use `@responses.activate` decorator or `responses.start()` context manager
- Because responses intercepts requests at the urllib3 level, matching how requests library makes calls

## Installation

```bash
# No new installations required for v1.5
# All dependencies already in pyproject.toml

# To sync the lockfile after adding --cov-fail-under to pytest.ini_options:
uv sync

# To verify the stack works:
pytest --cov=jellyswipe --cov-fail-under=70
```

## Integration with Existing Test Infrastructure

The new route tests will integrate seamlessly with the existing 48 tests:

1. **Shared fixtures**: The new `app` and `client` fixtures will coexist with existing `db_connection`, `mock_env_vars`, and `mocker` fixtures in conftest.py.

2. **Framework-agnostic module tests remain unchanged**: Tests for `jellyswipe/db.py` and `jellyswipe/jellyfin_library.py` continue to mock Flask entirely, as they test pure Python functions without Flask dependencies.

3. **Route tests use app factory**: New route test files (test_routes_auth.py, test_routes_xss.py, etc.) will use the `app` and `client` fixtures to make actual HTTP requests to Flask routes.

4. **Coverage enforcement applies to all tests**: The `--cov-fail-under=70` threshold applies to the entire test suite, ensuring combined coverage from both module-level and route-level tests meets the threshold.

5. **CI workflow unchanged**: The existing GitHub Actions workflow (`.github/workflows/test.yml`) continues to run tests on every push/PR; the new `--cov-fail-under=70` will cause the workflow to fail if coverage drops below 70%.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| Flask 3.1.3+ | pytest 9.0.0+ | Flask's test client works seamlessly with modern pytest fixtures. |
| pytest-cov 7.1.0+ | pytest 9.0.0+ | Compatible; `--cov-fail-under` is supported in pytest-cov 6.0+. |
| pytest-mock 3.14.0+ | pytest 9.0.0+ | Fully compatible; the `mocker` fixture integrates with pytest's fixture system. |
| responses 0.25.0+ | pytest 9.0.0+ | Compatible; `@responses.activate` decorator works with pytest test functions. |
| Python 3.13 | All packages | All dependencies support Python 3.13; uv lockfile uses Python 3.13. |

## Sources

- **Context7: /pallets/flask** — Application factory pattern, test client usage, session management
- **Context7: /pytest-dev/pytest-flask** — Fixture patterns for app factory testing (used for comparison, not adoption)
- **Context7: /pytest-dev/pytest-cov** — `--cov-fail-under` threshold enforcement
- **Flask Official Docs (Testing)** — https://flask.palletsprojects.com/en/stable/testing/ — HIGH confidence
- **Flask Official Docs (Application Factory)** — https://flask.palletsprojects.com/en/stable/tutorial/factory/ — HIGH confidence
- **Existing test suite** — `tests/test_route_authorization.py` demonstrates successful route testing without pytest-flask
- **Project pyproject.toml** — Confirms current versions: pytest >=9.0.0, pytest-cov >=6.0.0, pytest-mock >=3.14.0, responses >=0.25.0
- **uv.lock** — Confirms pytest-cov version 7.1.0 is locked

---
*Stack research for: Flask route testing with app factory pattern*
*Researched: 2026-04-26*
