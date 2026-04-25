# Project Research Summary

**Project:** Jelly Swipe (v1.3 — Unit Tests)
**Domain:** Python Flask Application Unit Testing
**Researched:** 2026-04-25
**Confidence:** HIGH

## Executive Summary

This is a unit testing initiative for a Flask web application (Jelly Swipe) that uses SQLite for data persistence and integrates with external APIs (Jellyfin, TMDB). The project requires implementing a framework-agnostic test suite for core business logic modules (`db.py`, `jellyfin_library.py`) without coupling to Flask's request/response cycle. Expert approach: Use pytest as the testing foundation with fixtures for database setup, pytest-mock for external API isolation, and in-memory SQLite databases for complete test isolation.

The recommended approach prioritizes test infrastructure first to establish proper isolation patterns, preventing common pitfalls like state leakage and flaky tests. Key risks include over-mocking external dependencies (which hides integration bugs) and coupling tests to implementation details (which causes test fragility during refactoring). Mitigation strategy: Use framework-agnostic tests for pure Python modules, mock only external HTTP calls (Jellyfin/TMDB APIs), test database operations with temporary isolated databases, and establish clear fixture patterns in conftest.py before writing extensive tests.

## Key Findings

### Recommended Stack

The stack research confirms pytest as the industry standard for Python testing, with excellent Python 3.13+ compatibility. The recommended core technologies are pytest (^9.0.0) as the framework, pytest-mock (^3.14.0) for cleaner mocking via the `mocker` fixture, and responses (^0.25.0) for mocking HTTP requests to external APIs. Coverage reporting via pytest-cov (^6.0.0) provides quality metrics with multiple output formats (terminal, HTML, XML). pytest-timeout prevents hanging tests in SSE scenarios, while pytest-xdist offers optional parallel execution as the test suite grows.

**Core technologies:**
- **pytest (^9.0.0)**: Testing framework with fixtures and parametrize — Python 3.13 compatible, de facto standard, supports modern pytest.mark.parametrize and fixture-based tests, auto-discovery, rich assertion introspection
- **pytest-mock (^3.14.0)**: Mocking utilities — Thin wrapper around unittest.mock with cleaner API via `mocker` fixture, automatic cleanup, type annotations support, spy/stub utilities
- **responses (^0.25.0)**: HTTP request mocking — Mocks requests library calls to external APIs (Jellyfin, TMDB), decorator/context manager patterns, call tracking, dynamic response generation
- **pytest-cov (^6.0.0)**: Coverage measurement — Integrates coverage.py with pytest, provides multiple report formats (term, HTML, XML for CI), append mode for combining unit/integration test coverage

### Expected Features

The feature research identifies table stakes expected in any professional Python test suite. Core requirements include the pytest framework, fixtures for reusable test setup, automatic test discovery, parametrization for data-driven testing, mocking/patching for external dependency isolation, temporary resources for test isolation, conftest.py for shared fixtures, coverage reporting, and CI integration. The key differentiator for this project is the framework-agnostic approach—testing modules directly without Flask integration—which matches the explicit TEST-01 requirement.

**Must have (table stakes):**
- **pytest framework** — Industry standard for Python testing; modern, powerful, widely adopted
- **Fixtures** — Reusable test setup/teardown logic prevents code duplication
- **Mocking/patching** — Isolating units from external dependencies is fundamental
- **Temporary resources** — Tests must not interfere with each other or system state
- **conftest.py** — Shared fixtures and configuration across test modules is expected
- **Coverage reporting** — Measuring test completeness is basic quality metric
- **CI integration** — Tests should run automatically in CI/CD pipelines

**Should have (competitive):**
- **Framework-agnostic testing** — Tests modules in isolation, not tied to Flask app lifecycle
- **pytest-mock integration** — Cleaner mock API than unittest.mock
- **Module-scoped fixtures** — Efficient resource sharing across tests in same module
- **Coverage thresholds** — Enforce minimum coverage in CI to prevent regression

**Defer (v2+):**
- **Parallel test execution** — pytest-xdist for faster test runs (requires test isolation verification)
- **Integration test suite** — End-to-end tests with real Jellyfin server (separate from unit tests)
- **Property-based testing** — Hypothesis for edge case discovery

### Architecture Approach

The architecture research establishes a clear separation between test suite, test dependencies, production code, and external dependencies. The recommended project structure uses `tests/conftest.py` for shared fixtures, `tests/unit/` for isolated business logic tests (test_db.py, test_jellyfin_library.py, test_base.py), and `tests/integration/` for optional Flask route tests. Key architectural patterns include: (1) In-memory SQLite with tmp_path for complete database isolation, (2) Mock external API calls with pytest-mock to prevent network dependencies, (3) Environment variable monkeypatching for test-specific configuration, and (4) Parametrized fixtures for comprehensive scenario coverage.

**Major components:**
1. **conftest.py** — Centralized shared fixtures (database initialization, provider mocks, environment setup) with appropriate scopes (function, module, session)
2. **test_db.py** — Tests database schema, migrations, and CRUD operations using in-memory SQLite with tmp_path fixture
3. **test_jellyfin_library.py** — Tests Jellyfin API client logic, error handling, and caching using mocked requests library
4. **pytest-mock & tmp_path** — Test dependencies providing mocker fixture for patching and isolated temporary directories for each test

### Critical Pitfalls

The pitfalls research identifies critical risks that must be addressed during test infrastructure setup. The most severe is over-mocking external dependencies, where excessive mocking of Jellyfin/TMDB APIs creates tests that pass even when actual integration fails. Another critical pitfall is test coupling to implementation details, where tests break when refactoring code that doesn't change behavior. Flaky tests from state leakage are also critical—tests pass individually but fail together due to shared database state, singleton providers, or Flask sessions. Testing libraries instead of application logic provides no value, and hard-to-maintain test setups with complex fixture hierarchies create technical debt.

1. **Over-mocking external dependencies** — Keep mocks minimal and realistic; use integration tests for API boundary layers; prefer test doubles over mocks where possible; use autospec to match real method signatures
2. **Test coupling to implementation details** — Test behavior, not implementation; verify outcomes rather than how they're achieved; for database code, test state changes; avoid mocking private methods
3. **Flaky tests from state leakage** — Use pytest fixtures with yield for setup/teardown; reset singletons in fixtures; use in-memory SQLite databases; clear Flask session state; use autouse fixtures to prevent state leakage
4. **Testing libraries instead of application logic** — Test your code, not libraries; verify the logic you wrote, not what Flask/SQLite/requests do; use framework-agnostic tests for pure Python modules
5. **Hard-to-maintain test setups** — Keep fixtures simple and focused; prefer function-scoped fixtures (default); use monkeypatch for env var injection; document fixture dependencies clearly

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Test Infrastructure Setup
**Rationale:** Foundational infrastructure must be established first to prevent technical debt. Research emphasizes that flaky tests and hard-to-maintain setups are critical pitfalls that originate from poor fixture design. Creating proper isolation patterns (in-memory DB, provider reset, env var handling) before writing tests prevents rework.
**Delivers:** Configured pytest environment, conftest.py with basic fixtures (db_path, db_connection, mock_env_vars, mock_jellyfin_api), CI workflow configuration
**Addresses:** pytest framework, fixtures, temporary resources, conftest.py, CI integration (FEATURES.md P1)
**Avoids:** Flaky tests from state leakage, hard-to-maintain test setups (PITFALLS.md critical pitfalls)
**Uses:** pytest, pytest-mock, pytest-cov, pytest-timeout (STACK.md core)

### Phase 2: Core Module Tests (Database)
**Rationale:** Database module (db.py) has the fewest dependencies and provides a foundation for testing patterns. Architecture research recommends this as the first test module because it tests pure SQLite functions without external API dependencies. Establishes test patterns for state-based testing and database isolation.
**Delivers:** tests/unit/test_db.py with coverage of schema initialization, CRUD operations, migrations, and orphaned data cleanup
**Uses:** In-memory SQLite with tmp_path fixture (ARCHITECTURE.md Pattern 1)
**Implements:** Database testing fixture patterns, state change assertions (not implementation details)
**Addresses:** Database fixtures (FEATURES.md P1)
**Avoids:** Testing implementation details, shared database state (PITFALLS.md)

### Phase 3: Core Module Tests (Base Abstraction)
**Rationale:** The abstract base class (base.py) defines the contract that JellyfinLibraryProvider implements. Testing this contract first establishes expectations for the concrete implementation. Architecture research lists this as Phase 3 in the build order.
**Delivers:** tests/unit/test_base.py testing the LibraryMediaProvider abstract contract
**Uses:** Mock subclasses or concrete test implementations
**Implements:** Contract-based testing patterns
**Addresses:** Test discovery, parametrization (FEATURES.md)
**Avoids:** Testing libraries instead of application logic (PITFALLS.md)

### Phase 4: Core Module Tests (Jellyfin Provider)
**Rationale:** The JellyfinLibraryProvider has high complexity (authentication, caching, genre filtering, deck fetching, TMDB integration) and requires comprehensive mocking. This is the most complex module to test. Architecture research recommends this as Phase 4 after patterns are established in earlier phases.
**Delivers:** tests/unit/test_jellyfin_library.py with coverage of authentication, token caching, user ID resolution, library discovery, genre listing, deck fetching, item-to-card transformation, TMDB resolution, image fetching
**Uses:** pytest-mock to mock requests.Session, responses library for HTTP mocking (STACK.md)
**Implements:** Mock external API calls pattern, parametrized fixtures for genre variants (ARCHITECTURE.md Patterns 2 & 4)
**Addresses:** HTTP mocking, framework-agnostic testing, parametrization (FEATURES.md P1)
**Avoids:** Over-mocking, testing implementation details (PITFALLS.md critical)

### Phase 5: Test Suite Optimization (Deferred to v1.3+)
**Rationale:** Once core coverage is achieved, optimize the test suite for performance and maintainability. Features research identifies this as P2/P3 priority. PITFALLS.md performance traps indicate optimization is needed at 50-100+ tests, which is premature during initial implementation.
**Delivers:** Coverage thresholds, multiple coverage reports (HTML, XML), module-scoped fixtures for efficiency, pytest-mock integration, flaky test detection
**Uses:** pytest-cov advanced features, pytest-mock, pytest-xdist (optional)
**Implements:** Performance optimization patterns, quality gates
**Addresses:** Coverage thresholds, pytest-mock integration, module-scoped fixtures (FEATURES.md P2)
**Avoids:** Performance traps as suite grows (PITFALLS.md)

### Phase Ordering Rationale

The order follows the dependency hierarchy and complexity gradient identified in ARCHITECTURE.md. Test infrastructure (Phase 1) must precede all testing to establish proper isolation patterns—this prevents the critical pitfalls of flaky tests and hard-to-maintain setups. Database tests (Phase 2) come first among modules because they have no external dependencies, allowing test patterns to be validated in isolation. Base abstraction tests (Phase 3) establish the contract before testing the concrete implementation. Jellyfin provider tests (Phase 4) are most complex and require all patterns to be in place. Optimization (Phase 5) is deferred until coverage is achieved, as recommended in FEATURES.md and PITFALLS.md.

This grouping avoids the critical pitfalls identified in research: early fixture setup prevents state leakage (Pitfall 3), testing behavior over implementation prevents coupling (Pitfall 2), and mocking only external dependencies prevents over-mocking (Pitfall 1). The framework-agnostic approach (testing db.py and jellyfin_library.py directly, not through Flask) matches the explicit TEST-01 requirement and differentiates this test suite from typical Flask test suites.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 4:** Jellyfin provider test scenarios require detailed knowledge of API response structures, error conditions, and authentication flows. May need to review Jellyfin API documentation or inspect existing code for realistic test data.
- **Phase 5:** Optimization thresholds (coverage targets, performance budgets) may need project-specific decisions based on team quality standards and CI infrastructure.

Phases with standard patterns (skip research-phase):
- **Phase 1:** pytest fixture patterns, conftest.py organization, and CI configuration are well-documented with established patterns from official docs.
- **Phase 2:** SQLite in-memory database testing is a standard pattern with clear guidance from ARCHITECTURE.md and PITFALLS.md.
- **Phase 3:** Abstract base class testing follows standard contract testing patterns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All recommendations based on official library documentation (pytest, pytest-mock, responses) with verified Python 3.13+ compatibility |
| Features | HIGH | Table stakes and differentiators derived from pytest best practices, official docs, and Flask testing patterns |
| Architecture | HIGH | Patterns based on official pytest documentation, Flask testing guide, and established testing pyramid principles |
| Pitfalls | HIGH | Identified from official docs, Google Testing Blog, and direct analysis of existing codebase challenges |

**Overall confidence:** HIGH

### Gaps to Address

No significant gaps identified in research. All core questions about stack, features, architecture, and pitfalls were answered with high-confidence sources.

- **Jellyfin API response structures:** Phase 4 will need realistic test data for API responses. This can be derived from existing code inspection or Jellyfin API documentation during implementation—no upfront research needed.
- **Coverage threshold targets:** Phase 5 optimization may require project-specific decisions. This is a team/quality standard decision, not a research gap.

## Sources

### Primary (HIGH confidence)
- **pytest-dev/pytest** — Test framework, fixtures, parametrization, Python 3.13 compatibility
- **pytest-dev/pytest-cov** — Coverage measurement and reporting formats
- **pytest-dev/pytest-mock** — Mocking API, mocker fixture, type annotations
- **getsentry/responses** — HTTP request mocking for requests library, decorator patterns
- **gevent/gevent** — Python 3.13 support confirmed in CHANGES.rst
- **Official pytest docs** (docs.pytest.org) — Fixture parametrization, pytest.mark.parametrize usage
- **Flask testing guide** (flask.palletsprojects.com) — Test client, fixture patterns
- **Python unittest.mock docs** (docs.python.org) — Mocking best practices, autospec, patching

### Secondary (MEDIUM confidence)
- **Google Testing Blog - "Just Say No to More End-to-End Tests"** — Testing pyramid and test strategy principles
- **Existing codebase analysis** — Reviewed `jellyswipe/__init__.py`, `jellyswipe/db.py`, and `jellyswipe/jellyfin_library.py` to identify specific testing challenges (singleton provider, global state, environment dependencies)

### Tertiary (LOW confidence)
None identified. All sources are either official documentation or direct code analysis.

---
*Research completed: 2026-04-25*
*Ready for roadmap: yes*
