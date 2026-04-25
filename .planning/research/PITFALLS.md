# Pitfalls Research

**Domain:** Python Flask web application (unit testing)
**Researched:** 2026-04-25
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: Over-mocking External Dependencies

**What goes wrong:**
Tests mock out too much of the Jellyfin API, TMDB API, database, or Flask request context, creating tests that pass even when the actual integration fails. Mocks return unrealistic data that doesn't match real API responses, hiding integration bugs.

**Why it happens:**
When adding tests to existing code, it's tempting to mock all external dependencies to avoid network calls and setup complexity. The JellyfinLibraryProvider makes real HTTP requests, so developers mock `requests.Session` or `requests.get()` to avoid testing against a real server. This creates a false sense of security.

**How to avoid:**
- Use **integration tests** for API boundary layers (JellyfinLibraryProvider), not unit tests
- Keep mocks **minimal and realistic** - use autospec to match real method signatures
- Use **monkeypatch** for specific function replacement, not wholesale mocking of modules
- Test with **real fixtures** for simple dependencies (SQLite in-memory databases)
- Prefer **test doubles** over mocks where possible - use fake implementations that behave like the real thing

**Warning signs:**
- Tests never fail when production code changes
- Mock assertions check implementation details (`mock.assert_called_with("GET", ...)`)
- Mock return values are hardcoded to simple values like `{"key": "value"}`
- Tests pass but production fails due to API contract changes

**Phase to address:**
Phase 1 (Test infrastructure setup) - establish clear boundaries between unit and integration tests, create realistic fixtures for Jellyfin/TMDB responses.

---

### Pitfall 2: Test Coupling to Implementation Details

**What goes wrong:**
Tests break when refactoring code that doesn't change behavior. For example, testing that `db.py` calls `conn.execute('SELECT * FROM rooms WHERE pairing_code = ?')` means the test breaks if you switch to an ORM or change the query structure.

**Why it happens:**
When adding tests to existing code, the path of least resistance is to test what the code *does* (implementation) rather than what it *accomplishes* (behavior). The Flask routes in `__init__.py` have complex logic mixed with database queries, making it tempting to test each step rather than the overall outcome.

**How to avoid:**
- Test **behavior, not implementation** - verify outcomes, not how they're achieved
- Use **black-box testing** for routes - given input X, expect output Y
- For database code, test **state changes** (after calling function, database contains Z)
- Avoid mocking private methods - test through the public interface
- Use **parameterized tests** to test multiple scenarios without duplicating implementation assumptions

**Warning signs:**
- Tests import implementation modules directly (`from jellyswipe import db`) rather than using the API
- Assertions check that specific methods were called with specific arguments
- Tests require intimate knowledge of internal function names
- Refactoring causes cascading test failures

**Phase to address:**
Phase 2 (Core module tests) - establish test design patterns that focus on behavior over implementation before writing extensive tests.

---

### Pitfall 3: Flaky Tests from State Leakage

**What goes wrong:**
Tests pass when run individually but fail when run together. One test creates a room in the database, and the next test fails because the room still exists. Session state (`session['active_room']`) persists between tests.

**Why it happens:**
The existing Flask app uses:
- **Global singleton**: `get_provider()` returns a cached `JellyfinLibraryProvider` instance with internal state (`_access_token`, `_cached_user_id`)
- **Flask sessions**: `session['active_room']` and `session['my_user_id']` persist unless explicitly cleared
- **SQLite databases**: File-based databases retain data between test runs

When adding tests, developers don't account for this state because the production code assumes fresh requests.

**How to avoid:**
- Use **pytest fixtures with `yield`** for setup/teardown - ensure each test gets a clean slate
- Reset singletons in fixtures: `provider.reset()` or recreate the provider instance
- Use **in-memory SQLite databases** (`":memory:"`) for tests
- Clear Flask session state in fixtures or use `client.session_transaction()`
- Use **autouse fixtures** to prevent state from leaking between tests
- Run tests with **`pytest-randomly`** to expose hidden dependencies

**Warning signs:**
- Tests pass when run in isolation: `pytest tests/test_db.py::test_create_room` works but `pytest tests/test_db.py` fails
- Test order affects results
- Flaky tests that "sometimes fail" without code changes
- Tests create data but never clean it up

**Phase to address:**
Phase 1 (Test infrastructure) - establish fixture patterns for proper isolation before writing any tests. This is foundational.

---

### Pitfall 4: Testing Libraries Instead of Application Logic

**What goes wrong:**
Tests verify that Flask's `test_client.get()` works, or that `sqlite3.connect()` creates a connection, rather than testing the application's business logic. This provides no value because libraries already have their own tests.

**Why it happens:**
When adding tests to existing code, it's unclear what to test. The Flask routes have database queries, API calls, and response formatting all mixed together. Testing the entire route end-to-end feels like "testing Flask" so developers instead try to test individual lines, which often means testing library calls.

**How to avoid:**
- Test **your code, not libraries** - verify the logic you wrote, not what Flask/SQLite/requests do
- For routes: test the **integration** of all pieces (route handler → database → response)
- For utility functions: test the **transformation logic** (e.g., `_format_runtime()` converting seconds to "1h 30m")
- Use **framework-agnostic tests** for pure Python modules (`db.py`, `jellyfin_library.py`)
- For Flask routes, use the **test client** to test the full HTTP contract, not internal routing

**Warning signs:**
- Tests for Flask's `test_client` behavior (e.g., "test that client.get returns a response")
- Tests for SQLite's `execute()` method
- Tests that don't fail even when you delete all your application code
- Low test coverage despite many tests

**Phase to address:**
Phase 2 (Core module tests) - identify and document which modules need tests vs. which use well-tested libraries.

---

### Pitfall 5: Hard-to-Maintain Test Setups

**What goes wrong:**
Test fixtures become complex hierarchies that are impossible to understand. A test needs a `client` that needs an `app` that needs a `provider` that needs a `database` that needs a `tmdb_api_key`. When one fixture changes, 20 tests break.

**Why it happens:**
The existing app has many implicit dependencies:
- Routes need `get_provider()` which needs `JELLYFIN_URL` env var
- Database operations need `init_db()` which needs `DB_PATH` env var
- TMDB routes need `TMDB_API_KEY` env var

When writing tests, developers create fixtures to set all of this up, leading to fixture chains like `db → provider → app → client`.

**How to avoid:**
- Keep fixtures **simple and focused** - each fixture does one thing
- Use **conftest.py** for shared fixtures, but keep them minimal
- Prefer **function-scoped fixtures** (default) over session/class-scoped to avoid state sharing
- Use **monkeypatch** for env var injection instead of complex fixture setup
- Document fixture dependencies clearly
- Extract complex setup into **helper functions** rather than fixtures

**Warning signs:**
- Fixtures call other fixtures that call other fixtures (3+ levels deep)
- Test functions have 5+ fixture arguments
- Fixtures have conditional logic (`if fixture_a: setup_b()`)
- Changing one fixture causes failures in unrelated tests

**Phase to address:**
Phase 1 (Test infrastructure) - establish fixture design patterns before writing tests. Simple fixtures prevent debt accumulation.

---

## Technical Debt Patterns

Shortcuts that seem reasonable when adding tests but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Mocking everything to avoid setup | Tests write quickly, no external dependencies | Tests don't catch real integration bugs, become fragile | Never - this defeats the purpose of testing |
| Testing routes by calling handler functions directly | Avoids Flask test client setup | Tests don't verify HTTP contract, miss middleware/before_request logic | Only for pure functions extracted from routes |
| Using production database for tests | No test DB setup needed | Tests can corrupt production data, slow, state leakage | Never |
| Skipping tests for "simple" functions | Faster progress initially | Bugs slip through in "trivial" code, no safety net for refactoring | Only for generated code or truly one-liners |
| Hardcoding env vars in test setup | Tests run without configuration management | Tests fail in CI/CD, can't test multiple configurations | Only for temporary debugging, never commit |
| Asserting implementation details (`mock.assert_called_with`) | Easy to write tests by copying code | Tests break on refactoring, discourage code improvements | Only when testing specific side effects that are part of the contract |
| Skipping cleanup in fixtures | Tests pass initially | Flaky tests, state leakage, hard-to-debug failures | Never |

---

## Integration Gotchas

Common mistakes when connecting to external services in tests.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| **Jellyfin API** | Mock `requests.get()` to return fake data; tests don't catch API contract changes | Use integration tests with a real test Jellyfin server or recorded responses (`vcr.py`); unit test only the data transformation logic (`_item_to_card()`, `_format_runtime()`) |
| **TMDB API** | Mock TMDB responses with minimal data; miss edge cases like missing images | Use parameterized tests with realistic TMDB response fixtures (missing fields, null values, unicode characters) |
| **SQLite Database** | Use production database file; tests corrupt data | Use in-memory database (`":memory:"`) or temporary files (`tmp_path`) |
| **Flask Sessions** | Don't clear session between tests; state leaks | Use `client.session_transaction()` fixture or clear session in test teardown |
| **Environment Variables** | Set env vars in global `conftest.py` using `os.environ`; affects all tests | Use `monkeypatch.setenv()` in fixtures to ensure isolation |
| **Singleton Provider** | Use global `get_provider()` in tests; state persists across tests | Create fresh provider instance in fixtures or call `provider.reset()` in teardown |

---

## Performance Traps

Patterns that work for a few tests but fail as the test suite grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| **Network calls in tests** | Each test makes real HTTP requests to Jellyfin/TMDB; suite takes minutes to run | Use mocks/vcr for external APIs; run integration tests separately | At 20+ tests with API calls (~5-10 seconds per test) |
| **File-based databases** | SQLite writes to disk; I/O overhead grows with test count | Use in-memory databases or tmp_path with proper cleanup | At 50+ database tests (~2-3 seconds per test) |
| **Sequential test execution** | Tests run one at a time; unused CPU cores | Use `pytest-xdist` for parallel execution; ensure test isolation | At 100+ tests (>10 seconds total) |
| **Global state initialization** | Provider authenticates with Jellyfin in every test; auth latency accumulates | Cache authenticated provider in session-scoped fixture with proper reset | At 30+ tests needing authenticated provider |
| **Fixture recomputation** | Expensive fixtures (app creation, DB init) run for every test | Use appropriate fixture scope (module/session) for expensive setup | At 50+ tests using same fixtures |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| **Leaking API keys in test output** | Test failures print request headers containing `JELLYFIN_API_KEY` or `TMDB_API_KEY` | Use `pytest-capturelog` to filter sensitive data; mock responses that include keys |
| **Testing with production credentials** | Accidental operations on production Jellyfin server | Require test-specific env vars; fail fast if `TESTING=True` not set |
| **Exposing tokens in assertion messages** | `assert response.json['token'] == expected` prints token on failure | Use custom assertion helpers that redact sensitive fields |
| **Not testing auth failures** | Tests assume valid tokens; unauthenticated paths untested | Parameterize tests with valid/invalid tokens; test 401/403 paths explicitly |
| **Hardcoded secrets in test fixtures** | API keys committed to repository | Use environment variables or pytest config (`pytest.ini`) for test credentials |

---

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| **Tests don't tell you what's broken** | Test output shows "assert 1 == 2" with no context | Use descriptive test names (`test_create_room_returns_4_digit_code`) and custom assertion messages |
| **Flaky tests waste developer time** | Developers re-run tests multiple times, lose trust in test suite | Fix flaky tests immediately; use `pytest-rerunfailures` only as temporary band-aid |
| **Slow feedback loop** | Developers wait 30+ seconds for tests to run before committing | Keep unit test suite under 10 seconds; run fast tests locally, slow tests in CI |
| **Tests hard to run locally** | Complex setup requires Docker, test servers, multiple env vars | Make tests runnable with just `pytest`; document simple setup in README |
| **Test output is noisy** | Hundreds of passing tests obscure the one failure | Use `-v` for verbose output only on failures; pytest shows summary by default |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Test coverage metrics are high, but critical paths are untested:** Verify high-impact paths (authentication, database writes, error handling) have explicit tests, don't rely on coverage from incidental tests
- [ ] **Tests pass locally but fail in CI:** Verify test isolation, environment variable handling, and file paths work in CI environment
- [ ] **All tests mock the same thing:** Verify integration tests exist for mocked components (e.g., at least one test calls real Jellyfin API)
- [ ] **Error handling only tested with mocks:** Verify exception paths are tested with real error conditions (network timeouts, 500 responses, malformed data)
- [ ] **Database tests only test happy paths:** Verify tests for constraint violations, concurrent updates, and edge cases (empty results, null values)
- [ ] **Flask routes only tested with valid input:** Verify tests for missing/invalid headers, malformed JSON, missing required fields

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| **Over-mocked tests** | HIGH | 1. Identify which mocks hide integration bugs by temporarily removing them<br>2. Add integration tests for those boundaries<br>3. Rewrite unit tests to test behavior, not implementation<br>4. Document what should be mocked vs. what should be integration tested |
| **Flaky tests** | MEDIUM | 1. Isolate the failing test (run in isolation until it fails)<br>2. Add logging to identify state leakage<br>3. Add `pytest-randomly` to expose hidden dependencies<br>4. Fix fixture isolation or add explicit cleanup<br>5. Verify fix by running tests in random order 100+ times |
| **Test coupling to implementation** | HIGH | 1. Identify tests that break on refactoring<br>2. Determine the intended behavior being tested<br>3. Rewrite tests to verify behavior through public API<br>4. Consider extracting private methods if they need testing |
| **Slow test suite** | MEDIUM | 1. Profile test execution time (`--durations=10`)<br>2. Identify slow tests and slow fixtures<br>3. Move slow tests to separate `tests/integration/` directory<br>4. Add `pytest-xdist` for parallel execution<br>5. Optimize expensive fixtures (use appropriate scope) |
| **Missing test isolation** | MEDIUM | 1. Identify tests that fail when run together<br>2. Add autouse fixtures to reset global state<br>3. Use in-memory databases for tests<br>4. Ensure all fixtures use function scope by default<br>5. Run with `pytest-randomly` to verify isolation |
| **Tests break in CI but pass locally** | LOW-MEDIUM | 1. Compare local vs. CI environment (Python version, dependencies, env vars)<br>2. Reproduce CI failure locally (Docker, same Python version)<br>3. Check for hardcoded paths or missing `.gitignore` files<br>4. Ensure test dependencies are in `dev-dependencies` of `pyproject.toml`<br>5. Add CI-specific test configuration if needed |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| **Flaky tests from state leakage** | Phase 1 - Establish fixture patterns with proper isolation (yield fixtures, in-memory DB, provider reset) | Run tests with `pytest-randomly` multiple times; verify tests pass in all orders |
| **Hard-to-maintain test setups** | Phase 1 - Design simple, focused fixtures before writing tests; document fixture dependencies | Review fixtures for complexity (>3 levels deep, >5 fixture args per test) |
| **Testing libraries instead of application logic** | Phase 2 - Create test plan identifying which modules need tests vs. library code | Verify test coverage of application code (not stdlib/Flask/requests) |
| **Over-mocking external dependencies** | Phase 1 - Establish boundaries: unit tests for logic, integration tests for APIs | Count mocks vs. real calls; ensure at least one integration test per external service |
| **Test coupling to implementation** | Phase 2 - Establish test design patterns focusing on behavior before writing tests | Refactor production code; verify tests still pass without changes |
| **Performance traps** | Phase 3 - Optimize test suite after coverage is achieved (pytest-xdist, fixture scopes) | Measure test suite runtime; target <10 seconds for unit tests |
| **Security mistakes** | Phase 2 - Add security-focused test cases for auth failures and sensitive data | Run tests with audit for leaked secrets in logs/assertions |

---

## Sources

- **Pytest Documentation**: Official pytest docs on fixtures, monkeypatching, flaky tests, and import modes - HIGH confidence (official source)
- **Flask Testing Documentation**: Official Flask testing guide for fixtures, test client, and testing patterns - HIGH confidence (official source)
- **Google Testing Blog - "Just Say No to More End-to-End Tests"**: Industry best practices on testing pyramid and test strategy - MEDIUM confidence (industry-standard approach)
- **Python unittest.mock Documentation**: Official Python docs on mocking best practices, autospec, and where to patch - HIGH confidence (official source)
- **Existing codebase analysis**: Reviewed `jellyswipe/__init__.py`, `jellyswipe/db.py`, and `jellyswipe/jellyfin_library.py` to identify specific testing challenges - HIGH confidence (direct analysis)

---

*Pitfalls research for: Python Flask web application unit testing*
*Researched: 2026-04-25*
