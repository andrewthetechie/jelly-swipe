# Project Research Summary

**Project:** Jelly Swipe - v1.5 Route Test Coverage
**Domain:** Flask web application with route testing and app factory pattern
**Researched:** 2026-04-26
**Confidence:** HIGH

## Executive Summary

v1.5 is a focused testing milestone: refactor the Flask app to the standard app factory pattern and add comprehensive route tests to achieve 70% coverage of `jellyswipe/__init__.py`. Research confirms this is a well-established pattern in the Flask ecosystem with no new dependencies required. The existing stack (Flask 3.1.3+, pytest 9.0.0+, pytest-cov 7.1.0+) already provides all necessary components. Flask's built-in test client (`app.test_client()`) is sufficient—no need for pytest-flask plugin.

The recommended approach is straightforward: (1) refactor `jellyswipe/__init__.py` into a `create_app(test_config=None)` factory function with backwards-compatible global `app` instance, (2) add `app` and `client` fixtures to `conftest.py`, (3) create 5 route test files (auth, xss, room, proxy, sse) following existing patterns, and (4) add `--cov-fail-under=70` to pytest configuration for CI enforcement. Critical risks are test isolation (state leakage between tests) and testing implementation details rather than behavior—both addressed by following Flask's official testing documentation and the existing framework-agnostic test patterns in the codebase.

## Key Findings

### Recommended Stack

No new dependencies required for v1.5. The existing stack has all necessary components for Flask route testing with app factory pattern.

**Core technologies:**
- **Flask 3.1.3+** — Web framework with built-in test client and app factory pattern support. Standard Flask pattern, no additional plugins needed.
- **pytest 9.0.0+** — Test framework with excellent fixture support and parametrization. Already in use with 48 tests, well-understood in the codebase.
- **pytest-cov 7.1.0+** — Coverage measurement with `--cov-fail-under=70` threshold enforcement. Single configuration change to pyproject.toml.

**Supporting technologies:**
- **pytest-mock 3.14.0+** — Mocking utilities for external API calls. Already used in existing tests.
- **responses 0.25.0+** — HTTP request mocking for Jellyfin/TMDB APIs. Prevents real API calls during tests.

### Expected Features

**Must have (table stakes) for v1.5:**
- Test client usage with `app.test_client()` for making HTTP requests
- Status code assertions (200, 400, 401, 403, 404, 500) for all routes
- Response JSON validation for API routes
- Session testing via `client.session_transaction()` for stateful routes
- Database state verification for routes that modify SQLite
- Authentication testing for protected routes
- Input validation testing for malformed requests
- Header validation for Authorization and Content-Type headers
- Parametrized tests for multiple scenarios per route
- Error handling testing for exception paths

**Should have (differentiators) for v1.5:**
- Security regression testing (authorization bypass, XSS, injection attacks)
- SSE streaming testing for real-time updates
- Proxy route allowlist testing for SSRF prevention
- Coverage threshold enforcement (70%) in CI

**Defer (v2+):**
- Edge case tests (concurrent operations, connection failures, malformed JSON)
- Performance tests (load testing, SSE with many clients)
- Integration tests (end-to-end workflows)
- Property-based testing (Hypothesis)
- Contract testing (Pact)

### Architecture Approach

The test suite follows a layered architecture: Test Suite (pytest) → Test Dependencies (pytest-mock, tmp_path, monkeypatch) → Production Code (jellyswipe modules) → External Dependencies (SQLite, Jellyfin API, Flask). The app factory pattern allows creating isolated test instances with test configuration, enabling proper test isolation. Existing framework-agnostic tests (test_db.py, test_jellyfin_library.py) remain unchanged—route tests are additive.

**Major components:**
1. **conftest.py** — Shared fixtures (app, client, db_connection, mock_env_vars, mocker). Centralizes test setup/teardown.
2. **jellyswipe/__init__.py (refactored)** — `create_app(test_config=None)` factory function with backwards-compatible global `app` instance.
3. **Route test files** — 5 test files organized by route category (auth, xss, room, proxy, sse) for maintainability.
4. **pytest-cov** — Coverage measurement with 70% threshold enforcement in CI.

**Key patterns:**
- In-memory SQLite with tmp_path fixture for database isolation
- Mock external API calls with pytest-mock and responses
- Environment variable monkeypatching for test configuration
- Function-scoped fixtures for complete test isolation
- Framework-agnostic imports for existing module tests

### Critical Pitfalls

**Top 5 pitfalls to avoid:**

1. **Flaky tests from state leakage** — Tests pass individually but fail together. Use function-scoped fixtures with yield, in-memory databases, and explicit session clearing. All tests must be order-independent.

2. **Test coupling to implementation details** — Tests break when refactoring code without behavior change. Test behavior (given input X, expect output Y), not how it's achieved. Use black-box testing for routes.

3. **Over-mocking external dependencies** — Tests pass even when integration fails. Mock only what's necessary; use realistic mock data. Prefer test doubles over mocks where possible.

4. **Testing libraries instead of application logic** — Tests verify Flask/SQLite/requests work, not your code. Test your code, not well-tested libraries. Verify business logic and integration, not framework behavior.

5. **Hard-to-maintain test setups** — Complex fixture hierarchies become unmaintainable. Keep fixtures simple and focused (one responsibility per fixture). Prefer function-scoped fixtures. Use helper functions for complex setup.

## Implications for Roadmap

Based on research, suggested phase structure for v1.5:

### Phase 1: App Factory Refactor
**Rationale:** Must come first—route tests require app factory pattern for test isolation. This is a prerequisite for all subsequent phases.
**Delivers:** `jellyswipe/__init__.py` refactored into `create_app(test_config=None)` factory function with backwards-compatible global `app` instance.
**Addresses:** FACTORY-01 requirement
**Avoids:** "Testing libraries instead of application logic" pitfall by providing proper test infrastructure
**Features:** None (infrastructure phase)

### Phase 2: Test Infrastructure Setup
**Rationale:** Route tests need `app` and `client` fixtures before writing tests. This phase establishes the foundation for all route testing.
**Delivers:** Updated `conftest.py` with `app` and `client` fixtures that work with app factory pattern.
**Uses:** Flask's built-in test client, pytest fixtures
**Implements:** Architecture Pattern 3 (environment variable monkeypatching)
**Avoids:** "Flaky tests from state leakage" pitfall by establishing proper fixture patterns
**Features:** None (infrastructure phase)

### Phase 3: Auth Route Tests
**Rationale:** Authentication is a security-critical dependency for most other routes. Testing auth first validates the test infrastructure on a focused domain.
**Delivers:** `tests/test_routes_auth.py` with tests for `/auth/provider`, `/auth/jellyfin-use-server-identity`, `/auth/jellyfin-login`.
**Uses:** app fixture, client fixture, FakeProvider for mocking
**Implements:** Table stakes features (authentication testing, status code assertions, session testing)
**Avoids:** "Over-mocking external dependencies" by using realistic mock data for Jellyfin responses
**Features:** TEST-ROUTE-01 (auth route tests)

### Phase 4: XSS Security Tests
**Rationale:** Security testing is a competitive differentiator and should be done early to catch vulnerabilities. Independent of auth routes—can be tested in parallel.
**Delivers:** `tests/test_routes_xss.py` with tests for HTML tag escaping, `javascript:` URL rejection, script injection prevention.
**Uses:** app fixture, client fixture, db_connection fixture, XSS payload helpers
**Implements:** Differentiator features (security regression testing, input validation testing)
**Avoids:** "Testing implementation details" by focusing on observable behavior (escaped output, rejected input)
**Features:** TEST-ROUTE-02 (XSS security tests)

### Phase 5: Room Operation Tests
**Rationale:** Core business logic—rooms, swipes, matches are the primary value of the application. Depends on database state management, so comes after auth/xss tests validate test infrastructure.
**Delivers:** `tests/test_routes_room.py` with tests for `/room/create`, `/room/join`, `/room/swipe`, `/room/quit`, `/room/status`, `/room/go-solo`.
**Uses:** app fixture, client fixture, db_connection fixture, room seeding helpers
**Implements:** Table stakes features (database state verification, error handling testing)
**Avoids:** "Flaky tests from state leakage" by using function-scoped db_connection fixture
**Features:** TEST-ROUTE-03 (room operation tests)

### Phase 6: Proxy Route Tests
**Rationale:** SSRF prevention is a security requirement. Independent of room operations—tests proxy allowlist and rate limiting without room context.
**Delivers:** `tests/test_routes_proxy.py` with tests for `/proxy` with valid/invalid paths, allowlist regex validation, content-type verification.
**Uses:** app fixture, client fixture, FakeProvider for mocking
**Implements:** Differentiator features (proxy route allowlist testing, SSRF prevention)
**Avoids:** "Over-mocking external dependencies" by testing actual proxy behavior with mocked backends
**Features:** TEST-ROUTE-04 (proxy route tests)

### Phase 7: SSE Streaming Tests
**Rationale:** SSE is the most complex testing domain (generator functions, streaming responses). Comes last as it depends on room operations working correctly and requires special handling for streaming responses.
**Delivers:** `tests/test_routes_sse.py` with tests for `/room/stream` event streaming, invalid room handling, state change events, GeneratorExit handling.
**Uses:** app fixture, client fixture, db_connection fixture, room seeding helpers, SSE event parsing
**Implements:** Differentiator features (SSE streaming testing, generator/iterator testing)
**Avoids:** "Hard-to-maintain test setups" by keeping SSE test fixtures focused and simple
**Features:** TEST-ROUTE-05 (SSE streaming tests)

### Phase 8: Coverage Enforcement
**Rationale:** Final phase—add coverage threshold enforcement after all tests are written to avoid blocking development.
**Delivers:** Updated `pyproject.toml` with `--cov-fail-under=70` in pytest.ini_options.
**Uses:** pytest-cov 7.1.0+
**Implements:** Coverage threshold enforcement (70%)
**Avoids:** None—this is the validation phase
**Features:** TEST-COV-01 (coverage enforcement)

### Phase Ordering Rationale

- **Factory refactor first:** App factory pattern is a hard dependency for route tests. Cannot write route tests without it.
- **Test infrastructure second:** Fixtures must exist before tests can be written. Establishes patterns for all subsequent phases.
- **Auth and XSS early:** Security-critical domains tested early to catch vulnerabilities. Independent of each other—could be parallelized.
- **Room operations after auth:** Core business logic depends on database state management, validated by earlier phases.
- **Proxy after room:** Independent of room operations but validates SSRF prevention (security priority).
- **SSE last:** Most complex domain (streaming, generators), depends on room operations working correctly.
- **Coverage enforcement last:** Threshold added after all tests exist to avoid blocking development.

**How this avoids pitfalls:**
- Function-scoped fixtures in Phase 2 prevent state leakage (Pitfall 1)
- Behavior-focused tests in Phases 3-7 avoid testing implementation details (Pitfall 2)
- Realistic mock data in Phases 3, 4, 6 prevent over-mocking (Pitfall 3)
- Testing routes through HTTP contract in Phases 3-7 avoids testing libraries (Pitfall 4)
- Simple, focused fixtures in Phase 2 prevent hard-to-maintain setups (Pitfall 5)

### Research Flags

**Phases likely needing deeper research during planning:**
- **Phase 5 (Room Operation Tests):** Complex business logic with multiple database operations. May need to plan test scenarios carefully for edge cases (concurrent swipes, race conditions).
- **Phase 7 (SSE Streaming Tests):** Generator functions and streaming responses are niche. Flask documentation on SSE testing is sparse—may need to research generator testing patterns and SSE event format validation.

**Phases with standard patterns (skip research-phase):**
- **Phase 1 (App Factory Refactor):** Well-documented Flask pattern. Official Flask tutorial has examples.
- **Phase 2 (Test Infrastructure Setup):** Standard pytest fixture patterns. Already used in existing conftest.py.
- **Phase 3 (Auth Route Tests):** Standard Flask authentication testing. Existing test_route_authorization.py shows the pattern.
- **Phase 4 (XSS Security Tests):** Standard input validation and escaping tests. Well-understood security testing patterns.
- **Phase 6 (Proxy Route Tests):** Standard SSRF prevention testing. Regex allowlist testing is straightforward.
- **Phase 8 (Coverage Enforcement):** Single configuration change. Well-documented pytest-cov usage.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All technologies verified with official Flask and pytest documentation. No new dependencies required—existing stack is sufficient. |
| Features | HIGH | Flask testing patterns well-documented. Existing 48 tests demonstrate successful patterns. Feature dependencies clear from codebase. |
| Architecture | HIGH | App factory pattern is standard Flask. Layered test architecture verified with official docs. Anti-patterns identified from community best practices. |
| Pitfalls | HIGH | Pitfalls based on official pytest/Flask documentation and industry best practices. Anti-patterns map to well-known testing mistakes. |

**Overall confidence:** HIGH

All research sources are official documentation (Flask, pytest) or direct codebase analysis. No inference required. The recommended approach follows established patterns in the Flask ecosystem.

### Gaps to Address

No significant gaps. Research was comprehensive:

- **SSE testing patterns:** Flask documentation on SSE is sparse, but generator testing is standard Python. May need to research SSE event format validation during Phase 7 planning.
- **Coverage threshold target:** 70% is a milestone requirement, not derived from research. May need to validate this threshold is achievable after writing tests.
- **Room operation edge cases:** Complex business logic may have unanticipated edge cases. Tests should be written to surface these during implementation, not before.

These gaps are minor and don't block roadmap creation. They can be addressed during phase planning.

## Sources

### Primary (HIGH confidence)
- **Flask Official Documentation (Testing)** — https://flask.palletsprojects.com/en/stable/testing/ — Test client usage, app factory pattern, session management
- **Flask Official Documentation (Application Factory)** — https://flask.palletsprojects.com/en/stable/tutorial/factory/ — Factory pattern implementation
- **pytest Documentation** — https://docs.pytest.org/en/stable/ — Fixture system, parametrization, test discovery
- **pytest-mock Documentation** — https://pytest-mock.readthedocs.io/ — Mocking patterns, mocker fixture
- **pytest-cov Documentation** — `--cov-fail-under` threshold enforcement
- **Existing Jelly Swipe Test Suite** — `tests/conftest.py`, `tests/test_db.py`, `tests/test_jellyfin_library.py`, `tests/test_route_authorization.py` — Demonstrates successful patterns in the codebase

### Secondary (MEDIUM confidence)
- **Flask Tutorial Tests** — https://github.com/pallets/flask/blob/main/docs/tutorial/tests.md — AuthActions helper class, database fixtures, authorization testing
- **Flask Web Security Documentation** — https://flask.palletsprojects.com/en/stable/security/ — XSS prevention, input validation
- **Project pyproject.toml** — Confirms current versions: pytest >=9.0.0, pytest-cov >=6.0.0, pytest-mock >=3.14.0, responses >=0.25.0
- **uv.lock** — Confirms pytest-cov version 7.1.0 is locked

### Tertiary (LOW confidence)
- **Community blog posts on Flask testing** — Reinforced official documentation patterns, no new findings
- **pytest-xdist documentation** — Parallel execution patterns (deferred to v2+, not needed for v1.5)

---
*Research completed: 2026-04-26*
*Ready for roadmap: yes*
