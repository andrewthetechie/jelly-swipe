# Feature Research

**Domain:** Unit Testing for Flask/Python Application
**Researched:** 2026-04-25
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features developers assume exist in a professional test suite. Missing these = testing feels incomplete/unprofessional.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **pytest framework** | Industry standard for Python testing; modern, powerful, widely adopted | LOW | Core requirement - provides test discovery, fixtures, and assertions |
| **Fixtures** | Reusable test setup/teardown logic prevents code duplication | LOW-MEDIUM | Essential for database setup, mock configuration, test data |
| **Test discovery** | Automatic test file/function discovery is standard behavior | LOW | Built-in to pytest - no manual test runner configuration needed |
| **Parametrization** | Testing multiple scenarios with one test function is expected | LOW-MEDIUM | @pytest.mark.parametrize for data-driven testing |
| **Mocking/patching** | Isolating units from external dependencies is fundamental | MEDIUM | monkeypatch fixture or pytest-mock for HTTP calls, database, etc. |
| **Temporary resources** | Tests must not interfere with each other or system state | LOW | tmp_path fixture for temporary files/directories |
| **conftest.py** | Shared fixtures and configuration across test modules is expected | LOW | Standard pattern for organizing test infrastructure |
| **Coverage reporting** | Measuring test completeness is basic quality metric | LOW | pytest-cov for coverage percentage and missing lines |
| **CI integration** | Tests should run automatically in CI/CD pipelines | LOW | JUnit XML output, coverage thresholds, exit codes |
| **Clear failure messages** | Developers need to understand why tests failed quickly | LOW | Built-in pytest assertion introspection |

### Differentiators (Competitive Advantage)

Features that set the test suite apart. Not required, but valuable for long-term maintainability.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Framework-agnostic testing** | Tests modules in isolation, not tied to Flask app lifecycle | MEDIUM | Matches TEST-01 requirement - test db.py and jellyfin_library.py without Flask |
| **Module-scoped fixtures** | Efficient resource sharing across tests in same module | LOW-MEDIUM | One database setup per module vs. per test |
| **Session-scoped fixtures** | One-time expensive setup (e.g., test data generation) | MEDIUM | Cache test data that's expensive to generate |
| **pytest-mock integration** | Cleaner mock API than unittest.mock | LOW | mocker fixture with Mock, MagicMock, AsyncMock, ANY, call |
| **Coverage thresholds** | Enforce minimum coverage in CI to prevent regression | LOW | --cov-fail-under=85 ensures quality gate |
| **Multiple coverage reports** | HTML for local review, XML for CI, terminal for quick feedback | LOW | Generate term-missing, html, and xml simultaneously |
| **Parametrized fixtures** | Test multiple configurations without test code duplication | MEDIUM | @pytest.fixture(params=[...]) for exhaustive testing |
| **Test isolation guarantees** | Each test gets fresh instances - no state leakage | LOW | Built-in pytest behavior for class-based tests |
| **Flaky test detection** | Identify tests that fail intermittently due to timing/state | MEDIUM | Split unit vs integration tests; use --cache-clear in CI |
| **Monkeypatch fixture safety** | Automatic cleanup prevents test pollution | LOW | All changes undone after test completes |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Shared test state** | Avoid recreating resources for each test | Causes test order dependency, flaky failures | Use fixtures with appropriate scope (function/module/session) |
| **Business logic in tests** | Tests that "verify" complex scenarios | Makes tests brittle, hard to debug when failing | Keep tests simple - test one thing, use multiple simple tests |
| **Over-mocking** | Isolate everything to avoid dependencies | Tests pass but don't verify real behavior | Mock only external dependencies (HTTP, DB), test real code paths |
| **Integration tests as gate** | Comprehensive end-to-end validation | Slow, flaky, blocks development | Use fast unit tests as merge gate, run integration tests separately |
| **Global fixtures** | One setup for all tests | Breaks test isolation, causes pollution | Use conftest.py hierarchically with scoped fixtures |
| **Testing private methods** | "Need to verify internal logic" | Tests implementation, not behavior; breaks on refactoring | Test public API only; private methods are implementation details |
| **Hard-coded test data** | "Just need a few test cases" | Brittle, doesn't catch edge cases | Use parametrize with diverse test cases |
| **Database state sharing** | Avoid creating fresh DB for each test | Tests interfere with each other | Use tmp_path for isolated databases per test/module |
| **Sleep-based synchronization** | "Wait for async operation" | Flaky tests, slow execution | Use mocks/stubs to control timing, event loops |
| **Exception catching in tests** | "Test should pass even with errors" | Masks real failures | Test expected exceptions with pytest.raises() |

## Feature Dependencies

```
[pytest framework]
    └──requires──> [test discovery]
    └──enables──> [fixtures]
                    └──requires──> [conftest.py]
                    └──enables──> [module-scoped fixtures]
                                    └──enhances──> [database testing]
                    └──enables──> [mocking/patching]
                                    └──enhances──> [framework-agnostic testing]

[pytest-cov]
    └──requires──> [pytest framework]

[pytest-mock]
    └──requires──> [pytest framework]
    └──enhances──> [mocking/patching]

[framework-agnostic testing]
    └──requires──> [mocking/patching]
    └──requires──> [fixtures]
    └──enables──> [test db.py]
    └──enables──> [test jellyfin_library.py]

[CI integration]
    └──requires──> [pytest framework]
    └──requires──> [coverage reporting]
    └──enhances──> [coverage thresholds]

[parametrization]
    └──requires──> [pytest framework]

[temporary resources]
    └──requires──> [pytest framework]
    └──enables──> [database testing]

[database testing]
    └──requires──> [temporary resources]
    └──requires──> [fixtures]
    └──requires──> [test isolation]
```

### Dependency Notes

- **pytest framework enables fixtures**: Pytest's fixture system is built on the framework's test discovery and execution model
- **fixtures enhance mocking/patching**: Fixtures provide clean setup/teardown for mock objects and monkeypatches
- **framework-agnostic testing requires mocking**: To test db.py and jellyfin_library.py without Flask, HTTP requests must be mocked
- **database testing requires temporary resources**: SQLite databases must be isolated using tmp_path to prevent test interference
- **CI integration requires coverage reporting**: Quality gates depend on measuring coverage and enforcing thresholds
- **parametrization requires pytest framework**: @pytest.mark.parametrize is a pytest-specific feature
- **module-scoped fixtures enhance database testing**: One database setup per test module is more efficient than per-test setup
- **test isolation prevents flaky tests**: Shared state causes order-dependent failures; each test must be independent

## MVP Definition

### Launch With (v1.3 - Current Milestone)

Minimum viable test suite to improve reliability when making changes.

- [ ] **pytest framework** — Core testing engine for test discovery and execution
- [ ] **Fixtures for database setup** — Temporary SQLite database with schema initialization (db.py testing)
- [ ] **Mocking for HTTP requests** — Isolate Jellyfin API calls (jellyfin_library.py testing)
- [ ] **Framework-agnostic test structure** — Test modules directly, not through Flask routes
- [ ] **conftest.py organization** — Shared fixtures for database, mocks, test data
- [ ] **Basic coverage reporting** — pytest-cov with terminal output to measure test completeness
- [ ] **CI configuration** — GitHub Actions workflow to run tests on push/PR

### Add After Validation (v1.3+)

Features to add once core testing is working.

- [ ] **Coverage thresholds** — Enforce minimum coverage (e.g., 80-85%) in CI
- [ ] **Multiple coverage reports** — HTML for local development, XML for CI tools
- [ ] **pytest-mock integration** — Cleaner mock API than unittest.mock
- [ ] **Parametrized fixtures** — Test multiple Jellyfin API response scenarios
- [ ] **Module-scoped database fixture** — Optimize database setup across tests
- [ ] **Flaky test detection** — Identify and isolate intermittent test failures

### Future Consideration (v2+)

Features to defer until test suite is mature.

- [ ] **Parallel test execution** — pytest-xdist for faster test runs (requires test isolation verification)
- [ ] **Integration test suite** — End-to-end tests with real Jellyfin server (separate from unit tests)
- [ ] **Performance benchmarking** — pytest-benchmark to detect performance regressions
- [ ] **Test data factories** — factory_boy or similar for complex test data generation
- [ ] **Property-based testing** — Hypothesis for edge case discovery

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| pytest framework | HIGH | LOW | P1 |
| Database fixtures | HIGH | MEDIUM | P1 |
| HTTP mocking | HIGH | MEDIUM | P1 |
| Framework-agnostic tests | HIGH | MEDIUM | P1 |
| conftest.py | HIGH | LOW | P1 |
| Coverage reporting | HIGH | LOW | P1 |
| CI integration | HIGH | LOW | P1 |
| Test discovery | HIGH | LOW | P1 |
| Parametrization | MEDIUM | LOW | P2 |
| Temporary resources | MEDIUM | LOW | P2 |
| pytest-mock | MEDIUM | LOW | P2 |
| Module-scoped fixtures | MEDIUM | MEDIUM | P2 |
| Coverage thresholds | MEDIUM | LOW | P2 |
| Multiple coverage reports | MEDIUM | LOW | P2 |
| Parametrized fixtures | MEDIUM | MEDIUM | P3 |
| Session-scoped fixtures | LOW | MEDIUM | P3 |
| Flaky test detection | LOW | MEDIUM | P3 |
| Parallel test execution | LOW | HIGH | P3 |
| Integration tests | MEDIUM | HIGH | P3 |

**Priority key:**
- P1: Must have for v1.3 milestone
- P2: Should have, add when possible in v1.3+
- P3: Nice to have, future consideration (v2+)

## Competitor Feature Analysis

| Feature | Typical Flask Test Suites | Our Approach |
|---------|---------------------------|--------------|
| Framework coupling | Many test Flask routes directly (flask.test_client) | Framework-agnostic: test db.py and jellyfin_library.py modules directly |
| Database handling | Often use in-memory SQLite or shared test DB | tmp_path fixture for isolated databases per test/module |
| Mocking strategy | Mix of unittest.mock and monkeypatch | Standardize on pytest monkeypatch + pytest-mock for consistency |
| Coverage enforcement | Often manual review or low thresholds | Automated coverage thresholds in CI (future P2) |
| Test organization | Sometimes flat structure with fixtures in test files | conftest.py hierarchy for shared fixtures, clear separation |
| External dependencies | Some use real services, some over-mock | Mock all external dependencies (Jellyfin API, TMDB) for reliable unit tests |

## Module-Specific Testing Requirements

### db.py Testing

**Complexity:** MEDIUM
**Dependencies:**
- Temporary SQLite database (tmp_path)
- Schema initialization fixture
- Test data setup/teardown

**Test scenarios:**
- Database connection management (get_db returns same connection within context)
- Schema initialization (tables created, migrations applied)
- Database cleanup (connections closed after context)
- CRUD operations (rooms, swipes, matches tables)
- Migration logic (ALTER TABLE for new columns)
- Orphaned data cleanup (DELETE FROM swipes WHERE room_code NOT IN rooms)

**Key fixtures needed:**
- `test_db_path`: tmp_path for isolated database
- `test_db_conn`: Database connection with initialized schema
- `test_data`: Sample rooms, swipes, matches for query testing

### jellyfin_library.py Testing

**Complexity:** HIGH
**Dependencies:**
- Mock HTTP requests (monkeypatch or pytest-mock)
- Mock environment variables (JELLYFIN_API_KEY, JELLYFIN_USERNAME, etc.)
- Test data for Jellyfin API responses
- Provider instance fixture

**Test scenarios:**
- Authentication (API key vs username/password)
- Token caching and reuse
- User ID resolution (from /Users/Me or /Users)
- Library ID discovery (find movies library)
- Genre listing (with caching)
- Deck fetching (with genre filtering, "Recently Added", shuffle)
- Item-to-card transformation (formatting runtime, ratings)
- TMDB item resolution (title/year extraction)
- Server info (fallback to public endpoint)
- Image fetching (path validation, auth retry on 401)
- User session authentication
- User ID resolution from token
- Add to user favorites

**Key fixtures needed:**
- `mock_jellyfin_api`: Mock requests.Session for API calls
- `mock_env_vars`: Set test environment variables
- `jellyfin_provider`: Fresh provider instance per test
- `sample_jellyfin_responses`: Realistic API response data

### Route Testing (Future Consideration)

**Complexity:** HIGH
**Dependencies:**
- Flask test client
- Database fixture
- Mock Jellyfin provider
- Session management

**Note:** Not in scope for v1.3 milestone (framework-agnostic approach). Consider for integration test suite in future.

## Sources

- **pytest documentation** (https://docs.pytest.org/en/stable/) — HIGH confidence (official docs)
- **Flask testing tutorial** (https://flask.palletsprojects.com/en/stable/tutorial/tests/) — HIGH confidence (official docs)
- **pytest-cov documentation** (https://pytest-cov.readthedocs.io/) — HIGH confidence (official docs)
- **pytest-mock documentation** (https://pytest-mock.readthedocs.io/) — HIGH confidence (official docs)
- **Python unittest.mock documentation** (https://docs.python.org/3/library/unittest.mock.html) — HIGH confidence (official docs)
- **Context7: pytest-dev/pytest** — HIGH confidence (verified library documentation)
- **Context7: pallets/flask** — HIGH confidence (verified library documentation)
- **Context7: pytest-dev/pytest-cov** — HIGH confidence (verified library documentation)
- **Context7: pytest-dev/pytest-mock** — HIGH confidence (verified library documentation)

---
*Feature research for: Unit Testing for Jelly Swipe (v1.3)*
*Researched: 2026-04-25*
