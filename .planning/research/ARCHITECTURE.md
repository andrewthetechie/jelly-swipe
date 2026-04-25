# Architecture Research

**Domain:** Unit testing for Flask application with SQLite and external API integration
**Researched:** 2026-04-25
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Test Suite (pytest)                      │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Unit Tests  │  │Integration   │  │   Shared     │     │
│  │              │  │   Tests      │  │   Fixtures   │     │
│  │  test_db.py  │  │test_routes.py│  │ conftest.py  │     │
│  │test_jellyfin │  │              │  │              │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                 │                  │              │
├─────────┴─────────────────┴──────────────────┴──────────────┤
│                  Test Dependencies Layer                     │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ pytest-mock  │  │   tmp_path   │  │   monkeypatch│     │
│  │  (mocking)   │  │  (temp DB)   │  │  (env vars)  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
├─────────────────────────────────────────────────────────────┤
│                    Production Code Layer                     │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ jellyswipe/  │  │ jellyswipe/  │  │ jellyswipe/  │     │
│  │   db.py      │  │jellyfin_lib  │  │  base.py     │     │
│  │              │  │     .py      │  │              │     │
│  │  get_db()    │  │   Provider   │  │  Abstract    │     │
│  │  init_db()   │  │  (requests)  │  │  Base Class  │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                 │                  │              │
├─────────┴─────────────────┴──────────────────┴──────────────┤
│                  External Dependencies                       │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   SQLite     │  │   Jellyfin   │  │   Flask      │     │
│  │   Database   │  │     API      │  │   Framework  │     │
│  │  (in-memory) │  │  (mocked)    │  │              │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **conftest.py** | Shared fixtures for database, mocks, and test configuration | pytest fixtures with appropriate scopes |
| **test_db.py** | Test database schema, migrations, and CRUD operations | In-memory SQLite with tmp_path fixture |
| **test_jellyfin_library.py** | Test Jellyfin API client logic, error handling, caching | Mock requests library, test provider methods |
| **test_base.py** | Test abstract base class contract | Concrete test subclass or mock |
| **test_routes.py** (optional) | Test Flask route handlers end-to-end | Flask test client, integration-level tests |
| **pytest-mock** | Provide mocker fixture for patching dependencies | Monkeypatch external services and APIs |
| **tmp_path** | Provide isolated temporary directories for each test | In-memory SQLite databases, temporary files |

## Recommended Project Structure

```
tests/
├── conftest.py                    # Shared fixtures (session, module, function scope)
├── unit/
│   ├── __init__.py
│   ├── test_db.py                 # Database functions: get_db(), init_db()
│   ├── test_jellyfin_library.py   # JellyfinLibraryProvider methods
│   └── test_base.py               # LibraryMediaProvider abstraction
└── integration/
    ├── __init__.py
    └── test_routes.py             # Flask routes (optional, for v1.3+)
```

### Structure Rationale

- **conftest.py:** Centralizes shared fixtures (database initialization, provider mocks, environment setup). Pytest automatically discovers fixtures in conftest.py, making them available to all tests without explicit imports.
- **unit/**: Isolates business logic from Flask framework. Tests functions and classes directly without HTTP layer. Matches the requirement for "framework-agnostic tests."
- **integration/**: Tests that verify component interactions (e.g., Flask routes calling provider methods). Can be deferred beyond v1.3 if unit coverage is sufficient.
- **Separation of concerns:** Database tests, provider tests, and route tests are isolated, making it clear what each test validates and enabling parallel test execution.

## Architectural Patterns

### Pattern 1: In-Memory SQLite with tmp_path

**What:** Use pytest's `tmp_path` fixture to create isolated SQLite databases for each test. This prevents tests from sharing state and ensures clean test runs.

**When to use:** All database-related tests (schema, migrations, CRUD operations).

**Trade-offs:**
- **Pros:** Complete isolation, no cleanup required, fast execution, matches production SQLite behavior.
- **Cons:** In-memory database differs from disk-based in some edge cases (file locking, persistence not tested).

**Example:**
```python
# content of tests/conftest.py
import pytest
import sqlite3
from pathlib import Path

@pytest.fixture
def db_path(tmp_path: Path):
    """Provide an isolated database path for each test."""
    db_file = tmp_path / "test.db"
    yield str(db_file)
    # No cleanup needed - tmp_path is automatic

@pytest.fixture
def db_connection(db_path: str):
    """Provide a database connection with schema initialized."""
    import jellyswipe.db
    original_db_path = jellyswipe.db.DB_PATH
    jellyswipe.db.DB_PATH = db_path
    jellyswipe.db.init_db()

    conn = jellyswipe.db.get_db()
    yield conn
    conn.close()

    # Restore original DB_PATH
    jellyswipe.db.DB_PATH = original_db_path
```

### Pattern 2: Mock External API Calls with pytest-mock

**What:** Use pytest-mock's `mocker` fixture to patch the `requests` library, preventing real HTTP calls to Jellyfin during tests.

**When to use:** All JellyfinLibraryProvider tests that make HTTP requests.

**Trade-offs:**
- **Pros:** No external dependencies, fast tests, can simulate error conditions, deterministic.
- **Cons:** Mocks may drift from real API behavior if not updated; doesn't validate integration with real Jellyfin server.

**Example:**
```python
# content of tests/unit/test_jellyfin_library.py
import pytest
from unittest.mock import Mock
from jellyswipe.jellyfin_library import JellyfinLibraryProvider

def test_fetch_deck_with_mocked_api(mocker):
    """Test fetch_deck uses correct API parameters."""
    # Mock the Session class to intercept HTTP requests
    mock_session = mocker.patch('jellyswipe.jellyfin_library.requests.Session')
    mock_response = Mock()
    mock_response.ok = True
    mock_response.json.return_value = {
        "Items": [
            {
                "Id": "movie-123",
                "Name": "Test Movie",
                "Overview": "A test movie",
                "RunTimeTicks": 7200000000,  # 2 hours
                "ProductionYear": 2024,
                "CommunityRating": 8.5
            }
        ]
    }
    mock_session.return_value.request.return_value = mock_response

    provider = JellyfinLibraryProvider("http://test.local")
    provider._access_token = "test-token"
    provider._cached_user_id = "user-123"
    provider._cached_library_id = "lib-123"

    deck = provider.fetch_deck()

    assert len(deck) == 1
    assert deck[0]["id"] == "movie-123"
    assert deck[0]["title"] == "Test Movie"

    # Verify the correct API call was made
    mock_session.return_value.request.assert_called_once()
    call_args = mock_session.return_value.request.call_args
    assert call_args[0][0] == "GET"  # method
    assert "/Items" in call_args[0][1]  # path
    assert call_args[1]["params"]["ParentId"] == "lib-123"
```

### Pattern 3: Environment Variable Monkeypatching

**What:** Use pytest's `monkeypatch` fixture to temporarily set environment variables for tests, then restore original values.

**When to use:** Tests that depend on environment configuration (e.g., JELLYFIN_URL, TMDB_API_KEY).

**Trade-offs:**
- **Pros:** Isolates test configuration from system environment, allows testing different configurations.
- **Cons:** Requires careful restoration (handled by monkeypatch automatically).

**Example:**
```python
# content of tests/conftest.py
import pytest
import os

@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set required environment variables for tests."""
    monkeypatch.setenv("JELLYFIN_URL", "http://test.local")
    monkeypatch.setenv("JELLYFIN_API_KEY", "test-api-key")
    monkeypatch.setenv("TMDB_API_KEY", "test-tmdb-key")
    monkeypatch.setenv("FLASK_SECRET", "test-secret")
    yield
```

### Pattern 4: Parametrized Fixtures for Test Variations

**What:** Use pytest's `@pytest.fixture(params=[...])` to run the same test with different inputs or configurations.

**When to use:** Testing multiple genre filters, error conditions, or API response variants.

**Trade-offs:**
- **Pros:** DRY, comprehensive coverage of variants, clear test organization.
- **Cons:** Can obscure which parameter caused a failure if not careful with test names.

**Example:**
```python
# content of tests/unit/test_jellyfin_library.py
@pytest.fixture(params=[
    "All",
    "Sci-Fi",
    "Recently Added",
    "Action"
])
def genre_param(request):
    """Parametrize genre filter tests."""
    return request.param

def test_fetch_deck_genre_filter(mocker, genre_param):
    """Test fetch_deck with different genre filters."""
    mock_session = mocker.patch('jellyswipe.jellyfin_library.requests.Session')
    mock_response = Mock()
    mock_response.ok = True
    mock_response.json.return_value = {"Items": []}
    mock_session.return_value.request.return_value = mock_response

    provider = JellyfinLibraryProvider("http://test.local")
    provider._access_token = "test-token"
    provider._cached_user_id = "user-123"
    provider._cached_library_id = "lib-123"

    deck = provider.fetch_deck(genre_param)

    # Verify correct genre parameter was passed
    call_args = mock_session.return_value.request.call_args
    params = call_args[1]["params"]
    if genre_param == "Recently Added":
        assert params["SortBy"] == "DateCreated"
    elif genre_param in ("All", "Sci-Fi"):
        assert params["SortBy"] in ("Random", "SortName")
```

## Data Flow

### Test Execution Flow

```
[Test Function]
    ↓ (request fixture)
[conftest.py] → [db_connection fixture] → [create temp DB]
    ↓                                      ↓
[monkeypatch fixture] → [set env vars]   [run schema migrations]
    ↓                                      ↓
[mocker fixture] → [patch requests]       [get_db() returns connection]
    ↓                                      ↓
[Call code under test]                    [assert database state]
    ↓                                      ↓
[Assertions] ←── [Check return values] ←── [Verify side effects]
    ↓
[Test cleanup] ← [mocker undo patches] ← [tmp_path deleted]
```

### Mock Data Flow

```
[Test calls provider.fetch_deck()]
    ↓
[Provider calls self._api()]
    ↓
[Provider calls self._session.request()]
    ↓
[mocker.patch intercepts call] → [Returns mock_response]
    ↓
[Provider processes mock_response] → [Returns deck]
    ↓
[Test asserts deck structure]
```

### Database State Flow

```
[Test starts]
    ↓
[db_connection fixture creates temp DB]
    ↓
[init_db() runs migrations]
    ↓
[Test performs database operations]
    ↓
[Test queries and asserts state]
    ↓
[Test ends]
    ↓
[db_connection fixture closes connection]
    ↓
[tmp_path deletes temp directory]
```

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0-100 tests | Monolithic conftest.py, function-scoped fixtures, in-memory SQLite |
| 100-1000 tests | Split conftest.py by package (unit/conftest.py, integration/conftest.py), module-scoped DB fixture where safe, consider pytest-xdist for parallel execution |
| 1000+ tests | Session-scoped expensive resources (e.g., mock Jellyfin responses), test categorization with markers, separate CI stages (unit → integration) |

### Scaling Priorities

1. **First bottleneck:** Test execution time. Mitigate with: parallel execution (pytest-xdist), smarter fixture scoping (use module/session where safe), mock expensive operations.
2. **Second bottleneck:** Test flakiness from shared state. Mitigate with: fixture isolation, unique temporary resources, explicit teardown.

## Anti-Patterns

### Anti-Pattern 1: Tightly Coupled Tests to Flask Context

**What people do:** Using Flask's test client for all tests, including unit tests of business logic.

**Why it's wrong:** Tests become slow, brittle, and test the framework instead of business logic. Difficult to isolate failures.

**Do this instead:** Test functions and classes directly. Use Flask test client only for integration tests of route handlers.

```python
# BAD - Testing business logic through Flask
def test_fetch_deck_via_flask(client):
    response = client.get("/deck?genre=Sci-Fi")
    assert response.status_code == 200
    # This tests Flask routing, not the provider logic

# GOOD - Testing provider logic directly
def test_fetch_deck_provider_logic(mocker):
    provider = JellyfinLibraryProvider("http://test.local")
    # Mock and test directly
    deck = provider.fetch_deck("Sci-Fi")
    assert deck is not None
```

### Anti-Pattern 2: Not Mocking External Dependencies

**What people do:** Tests make real HTTP calls to Jellyfin or TMDB during test runs.

**Why it's wrong:** Tests are slow, flaky, depend on external services, may hit rate limits, don't test error conditions deterministically.

**Do this instead:** Mock all external API calls with pytest-mock. Use real integration tests only in a separate suite with proper isolation.

```python
# BAD - Real HTTP call
def test_fetch_deck():
    provider = JellyfinLibraryProvider(os.getenv("JELLYFIN_URL"))
    deck = provider.fetch_deck()  # Makes real HTTP call

# GOOD - Mocked HTTP call
def test_fetch_deck(mocker):
    mocker.patch('jellyswipe.jellyfin_library.requests.Session')
    provider = JellyfinLibraryProvider("http://test.local")
    deck = provider.fetch_deck()  # Uses mock
```

### Anti-Pattern 3: Shared Database State Across Tests

**What people do:** Using a single database file for multiple tests without proper isolation.

**Why it's wrong:** Tests interfere with each other, flaky failures, hard to debug, order-dependent behavior.

**Do this instead:** Use tmp_path fixture for per-test databases or in-memory SQLite (:memory:).

```python
# BAD - Shared database
DB_PATH = "/tmp/test.db"  # Shared across all tests

# GOOD - Isolated database
@pytest.fixture
def db_path(tmp_path):
    yield tmp_path / "test.db"  # Unique per test
```

### Anti-Pattern 4: Testing Implementation Details

**What people do:** Testing private methods or internal state instead of public behavior.

**Why it's wrong:** Tests break when implementation changes without behavior change, tests become maintenance burden.

**Do this instead:** Test public interfaces and observable behavior. Use black-box testing principles.

```python
# BAD - Testing private method
def test_private_method(mocker):
    provider = JellyfinLibraryProvider("http://test.local")
    result = provider._auth_headers()  # Private method

# GOOD - Testing public behavior
def test_api_call_uses_auth_headers(mocker):
    provider = JellyfinLibraryProvider("http://test.local")
    # Verify that public method makes authenticated call
    deck = provider.fetch_deck()
    mocker.assert_called_with(headers={"Authorization": ...})
```

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| **Jellyfin API** | Mock requests.Session with pytest-mock | Test error conditions (401, 403, 404, 500), timeout scenarios, malformed responses |
| **TMDB API** | Mock requests library | Same as Jellyfin - this app calls TMDB from routes, not provider |
| **SQLite** | In-memory database with tmp_path fixture | Test schema migrations, constraints, row_factory behavior |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| **db.py ↔ jellyfin_library.py** | No direct communication | Database stores room/swipe/match data; provider supplies movie metadata. Tests are independent. |
| **jellyfin_library.py ↔ base.py** | Inheritance | JellyfinLibraryProvider implements LibraryMediaProvider abstract base. Test both concrete implementation and contract compliance. |
| **Flask routes ↔ jellyswipe modules** | Direct imports | Routes import and call functions from db.py and jellyfin_library.py. Unit tests skip routes; integration tests use Flask test client. |
| **Environment → jellyswipe/** | os.getenv() calls | Use monkeypatch fixture to set/override environment variables per test. |

### New Components vs. Modified Code

**New Components (to be created):**
- `tests/conftest.py` - Shared fixtures
- `tests/unit/test_db.py` - Database tests
- `tests/unit/test_jellyfin_library.py` - Provider tests
- `tests/unit/test_base.py` - Abstract base tests
- `tests/integration/test_routes.py` - Route tests (optional)

**Modified Code (existing, not requiring changes):**
- `jellyswipe/db.py` - Testable as-is with fixture support
- `jellyswipe/jellyfin_library.py` - Testable as-is with mocking
- `jellyswipe/base.py` - Testable via concrete implementation
- `jellyswipe/__init__.py` - Not tested directly in v1.3 (Flask routes deferred)

**Build Order (suggested):**
1. **Phase 1:** Set up test infrastructure (pytest, pytest-mock, conftest.py with basic fixtures)
2. **Phase 2:** Test database module (test_db.py) - lowest level, no dependencies
3. **Phase 3:** Test base abstraction (test_base.py) - defines contract
4. **Phase 4:** Test Jellyfin provider (test_jellyfin_library.py) - depends on base, mocks requests
5. **Phase 5 (deferred):** Integration tests for Flask routes - depends on all above, requires Flask test client

## Sources

- **pytest documentation:** https://docs.pytest.org/en/stable/ (HIGH confidence - official docs)
- **Flask testing guide:** https://flask.palletsprojects.com/en/stable/testing/ (HIGH confidence - official docs)
- **pytest-mock documentation:** https://pytest-mock.readthedocs.io/ (HIGH confidence - official docs)
- **Context7 research:** pytest fixtures, parametrization, mocking patterns (HIGH confidence - curated docs)

---
*Architecture research for: Unit testing architecture for Jelly Swipe Flask application*
*Researched: 2026-04-25*
