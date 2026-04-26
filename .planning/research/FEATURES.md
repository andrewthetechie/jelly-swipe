# Feature Research: Flask Route Testing Patterns

**Domain:** Flask Application Route Testing
**Researched:** 2026-04-26
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features developers expect in Flask route test suites. Missing these = tests feel incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Test Client Usage** | Standard Flask testing approach using `app.test_client()` for making requests | LOW | Supports GET/POST/PUT/DELETE with JSON/form data |
| **Status Code Assertions** | Verifies routes return correct HTTP status (200, 400, 401, 403, 404, 500) | LOW | Use `assert response.status_code == expected` |
| **Response JSON Validation** | API routes return JSON; must verify structure and values | LOW | Use `response.json` for parsed JSON data |
| **Session Testing** | Flask apps use session for state; tests must verify session behavior | MEDIUM | Use `client.session_transaction()` context manager |
| **Database State Verification** | Routes modify SQLite; tests must verify DB changes | MEDIUM | Query DB before/after request to assert state |
| **Authentication Testing** | Protected routes require valid identity; tests verify auth enforcement | MEDIUM | Test both valid and invalid auth scenarios |
| **Input Validation Testing** | Routes validate request data; tests verify rejection of invalid input | LOW | Test missing required fields, wrong types, malformed JSON |
| **Parametrized Tests** | Multiple scenarios per route (different inputs, auth states) | LOW | Use `@pytest.mark.parametrize` for DRY tests |
| **Error Handling Testing** | Routes must handle errors gracefully; tests verify error responses | MEDIUM | Test exception paths and error JSON structure |
| **Header Validation** | Routes check headers (Authorization, Content-Type); tests verify enforcement | LOW | Test with/without required headers, invalid headers |

### Differentiators (Competitive Advantage)

Features that set a comprehensive test suite apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Security Regression Testing** | Prevents authorization bypass, XSS, injection attacks | HIGH | Tests for header spoofing, body injection, stored XSS |
| **SSE Streaming Testing** | Validates Server-Sent Events for real-time updates | HIGH | Requires testing generator functions, event format |
| **Proxy Route Allowlist Testing** | Prevents SSRF (Server-Side Request Forgery) via proxy | MEDIUM | Tests regex allowlist, rejects invalid paths |
| **Rate Limiting Testing** | Prevents abuse of rate-limited endpoints | MEDIUM | Tests rate limit enforcement, headers |
| **Concurrent Request Testing** | Validates SSE handles multiple clients, room operations | HIGH | Tests isolation between concurrent sessions |
| **Generator/Iterator Testing** | Validates streaming responses don't leak resources | MEDIUM | Tests GeneratorExit, cleanup, timeouts |
| **Token Cache Testing** | Validates identity resolution caching behavior | MEDIUM | Tests cache TTL, invalidation, stale data |
| **Session Isolation Testing** | Ensures sessions don't leak between test cases | LOW | Uses function-scoped fixtures for fresh sessions |
| **Mock Provider Testing** | Isolates route logic from Jellyfin API calls | MEDIUM | Uses FakeProvider stub for deterministic tests |
| **Coverage Threshold Enforcement** | CI enforces minimum coverage (70% for routes) | LOW | Uses `--cov-fail-under=70` in pytest |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems in route testing.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Real API Calls in Tests** | "Tests should be realistic" | Slow, flaky, requires real Jellyfin server | Mock all external calls with FakeProvider |
| **Shared Database State** | "Setup DB once, run all tests" | Tests interfere with each other, hard to debug | Use function-scoped `db_connection` fixture |
| **Sleep/Time-Based Assertions** | "Wait for SSE event" | Flaky, slow, brittle | Mock `time.time()` or use deterministic generators |
| **Hard-Coded URLs** | "Simple to write" | Breaks when routes change | Use `client.get(url_for('endpoint'))` |
| **Testing Implementation Details** | "Verify internal function calls" | Brittle to refactoring | Test observable behavior (inputs/outputs) |
| **Global Test State** | "Share fixtures across tests" | Leaks state, causes intermittent failures | Use function-scoped fixtures, explicit setup/teardown |
| **Testing Flask Internals** | "Verify g object, request context" | Brittle, tests framework not app | Test HTTP responses, not Flask internals |
| **Single Monolithic Test File** | "All tests in one place" | Hard to navigate, slow CI runs | Split by route category (auth, room, proxy, sse, xss) |
| **Assertion-less Tests** | "Just run route, check no error" | Doesn't verify correctness | Assert status, response body, DB state |
| **Testing Multiple Concerns** | "Test auth + business logic together" | Hard to diagnose failures | One concern per test, use fixtures for setup |

## Feature Dependencies

```
[Authentication Tests]
    └──requires──> [FakeProvider Fixture]
    └──requires──> [Client Fixture]
    └──requires──> [Session Management Helper]

[Room Operation Tests]
    └──requires──> [DB Connection Fixture]
    └──requires──> [Client Fixture]
    └──requires──> [Session Management Helper]
    └──requires──> [Room Seeding Helper]

[SSE Streaming Tests]
    └──requires──> [Client Fixture]
    └──requires──> [Session Management Helper]
    └──requires──> [Room Seeding Helper]
    └──requires──> [Streaming Response Parser]

[Proxy Route Tests]
    └──requires──> [FakeProvider Fixture]
    └──requires──> [Client Fixture]
    └──requires──> [Path Validation Helper]

[XSS Security Tests]
    └──requires──> [FakeProvider Fixture]
    └──requires──> [DB Connection Fixture]
    └──requires──> [Client Fixture]
    └──requires──> [XSS Payload Helper]
```

### Dependency Notes

- **[Authentication Tests] requires [FakeProvider Fixture]:** Auth routes depend on Jellyfin provider for token validation. FakeProvider stubs this to avoid real API calls.
- **[Room Operation Tests] requires [DB Connection Fixture]:** Room routes create/modify SQLite records. Tests need isolated DB to verify state changes.
- **[SSE Streaming Tests] requires [Streaming Response Parser]:** SSE returns generator with `text/event-stream` content-type. Tests must parse event data format.
- **[Proxy Route Tests] requires [Path Validation Helper]:** Proxy uses regex allowlist. Tests verify valid/invalid path patterns.
- **[XSS Security Tests] requires [XSS Payload Helper]:** Tests must inject malicious payloads to verify escaping/rejection.

## MVP Definition

### Launch With (v1.5 - Route Test Coverage)

Minimum viable route test suite — what's needed for 70% coverage of `jellyswipe/__init__.py`.

- [ ] **Auth Route Tests** (`tests/test_routes_auth.py`) — Verify authentication endpoints work correctly
  - Test `/auth/provider` returns provider config
  - Test `/auth/jellyfin-use-server-identity` with valid/invalid delegate
  - Test `/auth/jellyfin-login` with valid/invalid credentials
  - Test missing username/password returns 400
- [ ] **XSS Security Tests** (`tests/test_routes_xss.py`) — Prevent stored XSS attacks
  - Test movie titles with HTML tags are escaped
  - Test thumbnail URLs with `javascript:` are rejected
  - Test room pairing codes don't allow script injection
- [ ] **Room Operation Tests** (`tests/test_routes_room.py`) — Happy path for room lifecycle
  - Test `/room/create` generates valid pairing code, creates DB record
  - Test `/room/join` with valid/invalid code
  - Test `/room/swipe` records swipe, detects matches
  - Test `/room/quit` deletes room, archives matches
  - Test `/room/status` returns current state
  - Test `/room/go-solo` enables solo mode
- [ ] **Proxy Route Tests** (`tests/test_routes_proxy.py`) — SSRF prevention
  - Test `/proxy` with valid allowlisted path (UUID/MD5 pattern)
  - Test `/proxy` rejects invalid paths (403)
  - Test `/proxy` returns correct content-type
- [ ] **SSE Streaming Tests** (`tests/test_routes_sse.py`) — Real-time updates
  - Test `/room/stream` with valid room returns event stream
  - Test `/room/stream` with invalid room returns empty stream
  - Test `/room/stream` sends events when room state changes
  - Test `/room/stream` handles GeneratorExit gracefully

### Add After Validation (v1.6+)

Features to add once core route coverage is working.

- [ ] **Edge Case Tests** — Boundary conditions and error paths
  - Test concurrent room operations (race conditions)
  - Test database connection failures
  - Test provider authentication failures
  - Test malformed request bodies (invalid JSON)
- [ ] **Performance Tests** — Load testing for room operations
  - Test room creation under load
  - Test SSE with many concurrent clients
  - Test proxy response times
- [ ] **Integration Tests** — End-to-end workflows
  - Test full room lifecycle (create → join → swipe → match → quit)
  - Test authentication flow with real-ish provider
  - Test SSE updates trigger UI refreshes

### Future Consideration (v2+)

Features to defer until route testing is mature.

- [ ] **Property-Based Testing** — Hypothesis for generating test cases
  - Test pairing code generation never collides
  - Test swipe operations always consistent
  - Test match detection is transitive
- [ ] **Contract Testing** — Verify route contracts (Pact)
  - Document expected request/response schemas
  - Validate against frontend client expectations
- [ ] **Visual Regression Testing** — UI changes don't break routes
  - Test response JSON structure matches UI expectations
  - Test error messages are user-friendly

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Auth Route Tests | HIGH | MEDIUM | P1 |
| XSS Security Tests | HIGH | MEDIUM | P1 |
| Room Operation Tests | HIGH | HIGH | P1 |
| Proxy Route Tests | HIGH | MEDIUM | P1 |
| SSE Streaming Tests | HIGH | HIGH | P1 |
| Edge Case Tests | MEDIUM | HIGH | P2 |
| Performance Tests | MEDIUM | HIGH | P3 |
| Integration Tests | MEDIUM | HIGH | P2 |
| Property-Based Testing | LOW | HIGH | P3 |
| Contract Testing | LOW | MEDIUM | P3 |
| Visual Regression Tests | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for v1.5 (route test coverage milestone)
- P2: Should have, add when possible (v1.6+)
- P3: Nice to have, future consideration (v2+)

## Competitor Feature Analysis

| Feature | Flask Tutorial Tests | pytest-Flask Plugin | Our Approach |
|---------|---------------------|---------------------|--------------|
| **Test Client** | `app.test_client()` | `client` fixture | `client` fixture in conftest.py (already exists) |
| **Database Isolation** | Temporary file per test | Transaction rollback | Function-scoped `db_connection` fixture (already exists) |
| **Auth Testing** | `AuthActions` helper class | `login()` fixture | `_set_session()` helper in test_route_authorization.py (already exists) |
| **Session Testing** | `client.session_transaction()` | Built-in support | `client.session_transaction()` context manager |
| **Parametrization** | `@pytest.mark.parametrize` | Built-in support | `@pytest.mark.parametrize` for multiple scenarios |
| **Mocking** | `unittest.mock` | Built-in support | Custom `mocker` fixture in conftest.py (already exists) |
| **SSE Testing** | Not covered | Requires custom handling | Custom SSE event parsing for streaming responses |
| **Security Testing** | Basic auth only | Not covered | Dedicated security regression tests (test_route_authorization.py exists) |
| **Coverage Enforcement** | `pytest-cov` | Optional | `--cov-fail-under=70` for CI enforcement (v1.5 goal) |

**Key Differentiators:**
- We use framework-agnostic imports (conftest.py patches `load_dotenv` and `Flask`)
- We have dedicated security regression tests for authorization hardening
- We split route tests by category (auth, xss, room, proxy, sse) for maintainability
- We use FakeProvider stub to isolate route logic from Jellyfin API

## Implementation Patterns

### Standard Test Structure

```python
def test_route_name_happy_path(client, db_connection):
    """Test [route] with valid input returns 200 and expected data."""
    # Arrange: Setup DB state, session, auth
    _seed_room(db_connection, "ROOM1")
    _set_session(client, active_room="ROOM1")

    # Act: Make request
    response = client.post("/route", json={"key": "value"})

    # Assert: Verify response and DB state
    assert response.status_code == 200
    assert response.json == {"expected": "data"}
    rows = db_connection.execute("SELECT * FROM table").fetchall()
    assert len(rows) == 1
```

### Security Test Structure

```python
@pytest.mark.parametrize("header", SPOOF_HEADERS)
def test_spoof_header_rejected(client, header):
    """Test [route] rejects requests with [header] (security regression)."""
    _set_session(client, active_room="ROOM1")

    response = client.post("/route", json={"key": "value"}, headers={header: "attacker-id"})

    assert response.status_code == 401
    assert response.json == {"error": "Unauthorized"}
```

### SSE Test Structure

```python
def test_sse_streaming(client, db_connection):
    """Test [route] returns SSE event stream with room state changes."""
    _seed_room(db_connection, "ROOM1")
    _set_session(client, active_room="ROOM1")

    response = client.get("/room/stream")

    assert response.status_code == 200
    assert response.content_type == "text/event-stream"
    assert b"data: " in response.data
```

## Sources

- **Flask Official Documentation (HIGH confidence):** https://flask.palletsprojects.com/en/stable/testing/
  - Test client usage (`app.test_client()`)
  - Session testing (`client.session_transaction()`)
  - Pytest fixtures for Flask apps
- **Flask Tutorial Tests (HIGH confidence):** https://github.com/pallets/flask/blob/main/docs/tutorial/tests.md
  - AuthActions helper class for login/logout
  - Database fixture with temporary file
  - Parametrized tests for multiple scenarios
  - Authorization testing patterns
- **Flask Web Security Documentation (HIGH confidence):** https://flask.palletsprojects.com/en/stable/security/
  - XSS prevention with Markup/escape
  - Security considerations for input validation
- **Flask API Documentation (HIGH confidence):** https://flask.palletsprojects.com/en/stable/api/
  - Response.json property for JSON responses
  - stream_with_context for streaming responses
  - test_client() method and parameters
- **Existing Jelly Swipe Test Suite (HIGH confidence):** `tests/` directory
  - `conftest.py` - Framework-agnostic imports, mocker fixture, db_connection fixture
  - `test_route_authorization.py` - Security regression tests for EPIC-01
  - `test_db.py` - Database testing patterns
  - `test_jellyfin_library.py` - Provider mocking with FakeProvider
- **Jelly Swipe Project Context (HIGH confidence):** `.planning/PROJECT.md`
  - v1.5 milestone requirements (70% route coverage)
  - Factory pattern refactoring (FACTORY-01)
  - Route test files (TEST-ROUTE-01 through TEST-ROUTE-05)

---
*Feature research for: Flask Route Testing Patterns*
*Researched: 2026-04-26*
