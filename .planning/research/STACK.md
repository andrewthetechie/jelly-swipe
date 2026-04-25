# Technology Stack

**Project:** Jelly Swipe (v1.3 — Unit Tests)
**Researched:** 2026-04-25
**Confidence:** HIGH

## Recommended Stack

### Core Testing Framework
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **pytest** | ^9.0.0 | Testing framework with fixtures and parametrize | Python 3.13 compatible, de facto standard, supports modern pytest.mark.parametrize and fixture-based tests, auto-discovery, rich assertion introspection |
| **pytest-cov** | ^6.0.0 | Coverage measurement | Integrates coverage.py with pytest, provides multiple report formats (term, HTML, XML for CI), append mode for combining unit/integration test coverage |
| **pytest-mock** | ^3.14.0 | Mocking utilities | Thin wrapper around unittest.mock with cleaner API via `mocker` fixture, automatic cleanup, type annotations support, spy/stub utilities |
| **responses** | ^0.25.0 | HTTP request mocking | Mocks requests library calls to external APIs (Jellyfin, TMDB), decorator/context manager patterns, call tracking, dynamic response generation |

### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **pytest-timeout** | ^2.3.0 | Timeout for potentially hanging tests | SSE/generator tests that might hang, ensures CI doesn't stall |
| **pytest-xdist** | ^3.6.0 | Parallel test execution | When test suite grows large, speeds up CI runs (optional for v1.3) |

### Development Tools
| Tool | Purpose | Notes |
|------|---------|-------|
| **pytest** | Test runner | Run with `pytest tests/` for basic, `pytest --cov=jellyswipe tests/` for coverage |
| **coverage.py** (via pytest-cov) | Coverage reporting | Use `--cov-report=html:htmlcov` for detailed reports, `--cov-report=xml:coverage.xml` for CI badges |
| **conftest.py** | Shared fixtures | Define database fixtures, mock fixtures, and test configuration in `tests/conftest.py` |

## Installation

```bash
# Core testing dependencies (add to [project.optional-dependencies] in pyproject.toml)
uv add --dev pytest pytest-cov pytest-mock responses pytest-timeout

# Optional: for parallel test execution when test suite grows
uv add --dev pytest-xdist
```

### Recommended pyproject.toml additions:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=9.0.0",
    "pytest-cov>=6.0.0",
    "pytest-mock>=3.14.0",
    "responses>=0.25.0",
    "pytest-timeout>=2.3.0",
    "pytest-xdist>=3.6.0",  # optional, for parallel execution
]
```

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| **pytest** | unittest (stdlib) | pytest has better fixtures, parametrize, auto-discovery, and community ecosystem |
| **responses** | httpx-mock | App uses `requests` library, not `httpx`; responses is the standard for mocking requests |
| **pytest-mock** | unittest.mock (stdlib) | pytest-mock provides `mocker` fixture with automatic cleanup and cleaner API |
| **in-memory SQLite** | pytest-sqlalchemy | App uses raw sqlite3, not SQLAlchemy ORM; pytest-sqlalchemy adds unnecessary abstraction |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **flask-testing** | Requirement is "framework-agnostic" tests; flask-testing ties tests to Flask request/response cycle | Test db.py and jellyfin_library.py directly with pytest |
| **pytest-flask** | Same as above — framework-agnostic requirement means testing business logic, not Flask integration | Test core modules in isolation, use Flask only for integration tests (out of scope for v1.3) |
| **pytest-asyncio** | App uses gevent for concurrency, not asyncio; pytest-asyncio is for async/await patterns | Standard pytest sync tests; for SSE tests use pytest-timeout to prevent hanging |
| **factory_boy** | Overkill for this codebase — simple test data can be created directly in fixtures or test functions | Create test data in pytest fixtures or inline in tests |

## Stack Patterns by Variant

**If testing db.py (database functions):**
- Use in-memory SQLite databases (`:memory:` connection)
- Create a fixture that sets up DB_PATH, calls init_db(), and yields connection
- Roll back or truncate tables after each test for isolation
- Example:
  ```python
  @pytest.fixture
  def test_db():
      import tempfile
      import os
      fd, path = tempfile.mkstemp(suffix=".db")
      os.close(fd)
      import jellyswipe.db
      jellyswipe.db.DB_PATH = path
      jellyswipe.db.init_db()
      yield path
      os.unlink(path)
  ```

**If testing jellyfin_library.py (Jellyfin API client):**
- Use `responses` library to mock HTTP requests to Jellyfin
- Mock authentication endpoint, `/Items`, `/Users/Me`, etc.
- Use `@responses.activate` decorator or context manager
- Test error handling by returning non-200 status codes
- Example:
  ```python
  @responses.activate
  def test_login_from_env_with_api_key(mocker):
      mocker.patch.dict(os.environ, {"JELLYFIN_API_KEY": "test-key"})
      responses.add(responses.GET, "http://test.com/Items", json={}, status=200)
      provider = JellyfinLibraryProvider("http://test.com")
      provider.ensure_authenticated()
      assert provider._access_token == "test-key"
  ```

**If testing TMDB integration:**
- Use `responses` to mock TMDB API calls (search, videos, credits)
- Test error handling (404, invalid responses)
- Don't call real TMDB API in tests

**If testing with gevent (future SSE tests):**
- Use `pytest-timeout` to prevent hanging tests
- Consider monkey-patching `time.sleep` in generator tests to speed up polling loops
- Note: v1.3 focuses on unit tests (db.py, jellyfin_library.py), not SSE route testing

## Version Compatibility

| Package | Compatible With | Notes |
|-----------|-----------------|-------|
| pytest >= 9.0.0 | Python 3.13+ | pytest 9.x actively maintained, supports Python 3.13 and 3.14 |
| pytest-cov >= 6.0.0 | pytest >= 7.0 | Coverage plugin version aligned with pytest 7+ |
| pytest-mock >= 3.14.0 | pytest >= 7.0 | Current stable, full Python 3.13 support |
| responses >= 0.25.0 | Python 3.8+ | Actively maintained, full Python 3.13 support |
| gevent >= 24.10 | Python 3.13+ | Already in runtime dependencies, confirmed Python 3.13 support in CHANGES.rst |

## Integration Points

### Database Testing
- **Target modules:** `jellyswipe/db.py`
- **Strategy:** Use `:memory:` SQLite or temp file, call `init_db()`, test CRUD operations
- **Isolation:** Each test gets fresh database or rolls back transactions

### External API Testing
- **Target modules:** `jellyswipe/jellyfin_library.py`
- **Strategy:** Use `@responses.activate` to mock all HTTP requests
- **Coverage:** Test success paths, error handling (401, 404, network errors), retry logic
- **TMDB integration:** Mock TMDB search, videos, and credits endpoints

### Framework-Agnostic Testing
- **Avoid:** Flask request/response testing, SSE streaming, session management
- **Focus:** Pure Python functions in `db.py` and `jellyfin_library.py`
- **Future:** Integration tests can use Flask's test client (out of scope for v1.3)

## CI Integration

### GitHub Actions (pytest job)
```yaml
- name: Run tests
  run: |
    uv sync --frozen --extra dev
    uv run pytest --cov=jellyswipe --cov-report=xml --cov-report=term-missing tests/

- name: Upload coverage
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage.xml
```

### Test Commands
```bash
# Run all tests
uv run pytest tests/

# Run with coverage
uv run pytest --cov=jellyswipe --cov-report=html:htmlcov tests/

# Run specific test file
uv run pytest tests/test_db.py

# Run with verbose output
uv run pytest -v tests/

# Run with parallel execution (if using pytest-xdist)
uv run pytest -n auto tests/
```

## Sources

- **pytest-dev/pytest** — Python 3.13 compatibility, fixtures, parametrize (HIGH confidence)
- **pytest-dev/pytest-cov** — Coverage measurement and reporting formats (HIGH confidence)
- **pytest-dev/pytest-mock** — Mocking API, mocker fixture, type annotations (HIGH confidence)
- **getsentry/responses** — HTTP request mocking for requests library, decorator patterns (HIGH confidence)
- **gevent/gevent** — Python 3.13 support confirmed in CHANGES.rst (HIGH confidence)
- **Official pytest docs** (docs.pytest.org) — Fixture parametrization, pytest.mark.parametrize usage (HIGH confidence)

---
*Stack research for: Jelly Swipe v1.3 — Unit Tests*
*Researched: 2026-04-25*
