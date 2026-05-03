# Phase 35: Test Suite Migration and Full Validation - Research

**Researched:** 2026-05-03
**Domain:** FastAPI TestClient, Starlette SessionMiddleware cookie crafting, pytest fixture patterns
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01:** Most tests use `app.dependency_overrides[require_auth]` to bypass auth entirely. The `app` fixture adds this override by default; `client` fixture builds a `TestClient` from it. Teardown clears `app.dependency_overrides` after each test (no override state leaks — success criterion 3).

**D-02:** `test_routes_auth.py` and `test_route_authorization.py` explicitly opt OUT of the `require_auth` override by using a separate `app_real_auth` / `client_real_auth` fixture variant that does NOT set `dependency_overrides[require_auth]`. These tests exercise the real auth code path.

**D-03:** The default `AuthUser` injected by the override is `AuthUser(jf_token="valid-token", user_id="verified-user")` — matching the `FakeProvider` user identity used throughout existing tests.

**D-04:** Application session state (`active_room`, `solo_mode`, `my_user_id`, `jf_delegate_server_identity`, etc.) is injected via a `set_session_cookie(client, data, secret_key)` helper in `conftest.py`. The helper uses `itsdangerous.TimestampSigner` (Starlette's `SessionMiddleware` uses this under the hood with the `FLASK_SECRET` key) to produce a valid signed session cookie and sets it on the `TestClient`'s `cookies` dict.

**D-05:** The `_set_session` / `_set_session_room` local helpers in individual test files are replaced with calls to `set_session_cookie()`. Auth setup (seeding `user_tokens`, setting `session_id`) is dropped — auth is handled by the `dependency_overrides` from D-01 instead.

**D-06:** For tests that currently set ONLY auth-related session keys (just `session_id`), the override from D-01 is sufficient — no cookie crafting needed. Only tests that also need `active_room`, `solo_mode`, or similar app state call `set_session_cookie()`.

**D-07:** Update `create_app()` to read `SECRET_KEY` from `test_config` and pass it to `SessionMiddleware` instead of always reading `os.environ["FLASK_SECRET"]`. The `app` fixture passes `SECRET_KEY` matching the `FLASK_SECRET` env var already set in conftest — so the signing key used by `set_session_cookie()` and the key used by the live app are guaranteed to match.

**D-08:** The `global app` at module level (`app = create_app()`) continues to use `os.environ["FLASK_SECRET"]`. Only the test-created instances get `SECRET_KEY` from test_config.

**D-09:** `response.get_json()` → `response.json()` across all 34 occurrences. FastAPI's `TestClient` wraps `requests.Response`, which uses `.json()`.

**D-10:** `response.data` → `response.content` (bytes) across all 15 occurrences. If any test decodes to string, use `response.text` instead.

**D-11:** `app.test_client()` → `TestClient(app, raise_server_exceptions=False)` for error-handling tests that expect 4xx/5xx without exceptions being raised; `TestClient(app)` for the rest.

**D-12:** Update `REQUIREMENTS.md` TST-01 to reflect the actual test count (324 tests, not 48). The "no modifications to test logic" constraint still applies — only API surface changes are allowed.

### Claude's Discretion

- Exact Starlette session cookie format: planner should verify the `itsdangerous` signer variant Starlette 0.46+ uses (likely `URLSafeTimedSerializer` with a `cookiesession` salt) before writing the helper — the signing format must match exactly or cookies will be rejected.
- `raise_server_exceptions` flag: planner decides per-test-file whether it's needed; apply it surgically to error-handling test files only.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TST-01 | All 324 existing tests updated to use FastAPI's TestClient; full test suite passes with no modifications to test logic (only API surface changes) | Confirmed 324 tests collected by uv run pytest; all Flask patterns inventoried and replacements verified |
| FAPI-01 | FastAPI replaces Flask as the web framework; Uvicorn replaces Gunicorn+gevent as the ASGI server | Dockerfile CMD already uses uvicorn; create_app() is FastAPI; Docker build verification is success criterion 4 |

</phase_requirements>

---

## Summary

Phase 35 is a mechanical migration of 18 test files from Flask's test client API to FastAPI's `TestClient`. The app code (Phases 30–34) is already fully FastAPI — the only work is updating the test infrastructure to match. The root cause of all 178 test errors is a single line in `conftest.py`: `return app.test_client()`, which does not exist on a `FastAPI` instance.

The migration has two distinct parts: (1) updating `conftest.py` to build a `TestClient` with `dependency_overrides` and a `set_session_cookie()` helper, and (2) mechanically updating all 18 test files to use `requests.Response` API (`response.json()`, `response.content`, `response.text`) and `set_session_cookie()` instead of `session_transaction()`.

The critical research finding is the exact session cookie format used by Starlette 1.0.0: it uses `itsdangerous.TimestampSigner` (NOT `URLSafeTimedSerializer`) with the format `base64(json_payload).timestamp.signature`. The helper implementation is verified and works correctly — this removes the "Claude's Discretion" uncertainty from the CONTEXT.md.

**Primary recommendation:** Implement in two waves: Wave 1 rewrites `conftest.py` and `jellyswipe/__init__.py` (the plumbing that makes all other tests possible), Wave 2 applies the mechanical find-replace across all 18 test files.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Test client creation | Test infrastructure (conftest.py) | — | TestClient wraps the ASGI app directly |
| Auth bypass in tests | Test infrastructure (dependency_overrides) | App factory (create_app) | FastAPI DI system enables test-only auth bypass |
| Session state injection | Test infrastructure (set_session_cookie helper) | App factory (SessionMiddleware config) | Secret key must match between helper and app instance |
| DB isolation per test | Test infrastructure (db_path/db_connection fixtures) | App factory (test_config DB_PATH) | Already framework-agnostic, no change needed |
| Mechanical API replacements | Test files (18 files) | — | Pure string substitution, no logic changes |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | 0.136.1 | App framework + TestClient | Already installed; TestClient ships with it [VERIFIED: npm registry equivalent — `uv pip show fastapi`] |
| httpx | 0.28.1 | TestClient transport layer | Required by TestClient; already in pyproject.toml dev deps [VERIFIED: codebase] |
| starlette | 1.0.0 | SessionMiddleware + ASGI | Ships with FastAPI; provides the session cookie mechanism [VERIFIED: `python3 -c "import starlette; print(starlette.__version__)"` returned 1.0.0] |
| itsdangerous | 2.2.0 | Session cookie signing | Used by Starlette's SessionMiddleware internally; already in pyproject.toml [VERIFIED: `importlib.metadata.version("itsdangerous")` returned 2.2.0] |
| pytest | 9.0.3 | Test runner | Already installed [VERIFIED: codebase] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sse-starlette | 3.4.1 | SSE route (rooms.py) | Needed for test collection to succeed — already in pyproject.toml but was missing from venv [VERIFIED: installed] |

---

## Architecture Patterns

### System Architecture Diagram

```
conftest.py app fixture
    |-- create_app(test_config={SECRET_KEY, DB_PATH, TESTING})
    |-- app.dependency_overrides[require_auth] = lambda: AuthUser(...)
    |-- app.dependency_overrides[get_provider] = lambda: FakeProvider()
    |-- rate_limiter.reset()
    |-- yield app
    |-- app.dependency_overrides.clear()  [teardown]

conftest.py client fixture
    |-- TestClient(app)        [standard tests]
    |-- TestClient(app, raise_server_exceptions=False)  [error tests]

conftest.py set_session_cookie(client, data, secret_key)
    |-- itsdangerous.TimestampSigner(secret_key)
    |-- base64(json(data)) -> signer.sign() -> client.cookies.set("session", value)

Per-test session injection
    |-- Tests needing app state: call set_session_cookie(client, {"active_room": ..., "solo_mode": ...}, secret_key)
    |-- Tests needing only auth: dependency_override handles it; no cookie crafting needed

test_routes_auth.py + test_route_authorization.py
    |-- Use separate app_real_auth / client_real_auth fixture
    |-- No dependency_overrides[require_auth] set
    |-- Auth goes through real require_auth -> auth.get_current_token() -> DB lookup
```

### Recommended Project Structure

No structural changes. All files stay in `tests/`. The fixture changes are confined to `conftest.py`. The `create_app()` change is confined to `jellyswipe/__init__.py`.

### Pattern 1: FastAPI TestClient with Dependency Overrides

**What:** Replace `app.test_client()` with `TestClient(app)` after setting `dependency_overrides` on the app instance.

**When to use:** All tests that test route behavior, not authentication behavior.

**Example:**
```python
# Source: FastAPI docs / verified in this codebase
from fastapi.testclient import TestClient
from jellyswipe import create_app
from jellyswipe.dependencies import require_auth, get_provider, AuthUser

@pytest.fixture
def app(tmp_path, monkeypatch):
    import jellyswipe as jellyswipe_module
    db_file = str(tmp_path / "test_route.db")
    test_config = {
        "DB_PATH": db_file,
        "TESTING": True,
        "SECRET_KEY": "test-secret-key",   # matches FLASK_SECRET env var
    }
    fast_app = create_app(test_config=test_config)

    # Override auth — no DB vault needed
    fast_app.dependency_overrides[require_auth] = lambda: AuthUser(
        jf_token="valid-token", user_id="verified-user"
    )
    # Override provider
    fake_provider = FakeProvider()
    fast_app.dependency_overrides[get_provider] = lambda: fake_provider

    from jellyswipe.rate_limiter import rate_limiter as _rl
    _rl.reset()

    yield fast_app

    fast_app.dependency_overrides.clear()   # CRITICAL: prevents state leak

@pytest.fixture
def client(app):
    return TestClient(app)
```

### Pattern 2: Starlette Session Cookie Crafting

**What:** Produce a valid signed session cookie to inject app state (active_room, solo_mode) without going through a real HTTP flow.

**Verified signing format (Starlette 1.0.0, itsdangerous 2.2.0):**
```
base64url(json_payload) + "." + timestamp + "." + hmac_signature
```

This uses `itsdangerous.TimestampSigner` — NOT `URLSafeTimedSerializer`. The CONTEXT.md note about `URLSafeTimedSerializer` was incorrect; the verified source code shows `TimestampSigner`. [VERIFIED: `inspect.getsource(starlette.middleware.sessions)`]

**Example:**
```python
# Source: VERIFIED against Starlette 1.0.0 source code (starlette.middleware.sessions)
import json
from base64 import b64encode
import itsdangerous

def set_session_cookie(client, data: dict, secret_key: str) -> None:
    """Inject session state into a FastAPI TestClient's cookie jar.

    Replicates Starlette's SessionMiddleware signing format exactly:
      - Serialize data to JSON
      - Base64-encode the JSON bytes
      - Sign the base64 bytes with itsdangerous.TimestampSigner
      - Set the result as the 'session' cookie on the client
    """
    signer = itsdangerous.TimestampSigner(str(secret_key))
    payload = b64encode(json.dumps(data).encode("utf-8"))
    signed = signer.sign(payload)
    client.cookies.set("session", signed.decode("utf-8"))
```

### Pattern 3: Real-Auth Fixture Variant

**What:** A separate app/client fixture that does NOT set `dependency_overrides[require_auth]`, so auth tests exercise the real code path.

**When to use:** `test_routes_auth.py` and `test_route_authorization.py` only (D-02).

**Example:**
```python
@pytest.fixture
def app_real_auth(tmp_path, monkeypatch):
    """App fixture with real require_auth — for auth integration tests."""
    import jellyswipe as jellyswipe_module
    db_file = str(tmp_path / "test_route.db")
    test_config = {
        "DB_PATH": db_file,
        "TESTING": True,
        "SECRET_KEY": "test-secret-key",
    }
    fast_app = create_app(test_config=test_config)
    # NOTE: NO dependency_overrides[require_auth] set — real auth path
    fake_provider = FakeProvider()
    fast_app.dependency_overrides[get_provider] = lambda: fake_provider

    from jellyswipe.rate_limiter import rate_limiter as _rl
    _rl.reset()

    yield fast_app
    fast_app.dependency_overrides.clear()

@pytest.fixture
def client_real_auth(app_real_auth):
    return TestClient(app_real_auth)
```

### Pattern 4: Mechanical Response API Replacements

| Flask | FastAPI/requests | Notes |
|-------|-----------------|-------|
| `response.get_json()` | `response.json()` | Direct drop-in; returns dict |
| `response.data` | `response.content` | Returns bytes |
| `response.data.decode()` | `response.text` | Returns str |
| `json.loads(response.data)` | `response.json()` | Simplification |
| `response.get_data(as_text=True)` | `response.text` | Direct drop-in |
| `response.content_type` | `response.headers["content-type"]` | Note: lowercase key in requests |

**Exception:** `response.content_type` in test_routes_proxy.py — `requests.Response` uses `response.headers["content-type"]`, not a direct attribute. [VERIFIED: requests library behavior]

### Pattern 5: SSE Test Migration (test_routes_sse.py)

**What:** The SSE tests monkeypatch `jellyswipe._gevent_sleep` and `time.sleep` to control loop timing. The Phase 34 route uses `asyncio.sleep` — NOT gevent. The monkeypatch of `jellyswipe._gevent_sleep` sets a non-existent attribute (`raising=False` per conftest pattern), which is harmless. The real control is via `monkeypatch.setattr(time, "sleep", ...)` and `monkeypatch.setattr(time, "time", ...)`.

**Migration needed:**
- `_set_session_room()` helper → `set_session_cookie(client, {...}, secret_key)` + auth via dependency_override
- `session_transaction()` (1 occurrence) → `set_session_cookie()`
- `response.data` (10 occurrences) → `response.content` or `response.text`
- `response.data.decode()` → `response.text`
- `_ = response.data` → `_ = response.content`
- `client.session_transaction()` in `test_stream_room_not_found` is already skipped — no change needed

**Key SSE insight:** `TestClient` from `starlette.testclient` (bundled with FastAPI) buffers the entire SSE stream body when the response is fully consumed. The existing test pattern of `response.data` (consuming the full stream) maps directly to `response.content` (bytes). This approach works because the SSE generator is bounded by a 3600s timeout that tests mock to expire quickly.

### Anti-Patterns to Avoid

- **Setting `session_id` in session cookie:** The whole point of D-01 is that auth bypass via `dependency_overrides` replaces the vault-based session check. Do NOT seed `user_tokens` or set `session_id` in the session for tests that use the override fixture.
- **Forgetting `dependency_overrides.clear()`:** Without teardown, override state bleeds between tests. The `yield` fixture pattern handles this automatically if clearance is placed after the yield.
- **Using `TestClient(app)` at module level:** Module-level clients share state. Always create the `TestClient` inside a function-scoped fixture.
- **`raise_server_exceptions=True` for error tests:** Tests that assert on 4xx/5xx responses need `raise_server_exceptions=False`; otherwise TestClient raises the exception before the test can check the status code.
- **Confusing `response.headers["content-type"]` vs `response.content_type`:** The `requests.Response` object (used by httpx/TestClient) does NOT have a `.content_type` attribute. Use `response.headers["content-type"]` or check for substrings via `"image" in response.headers.get("content-type", "")`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Session cookie signing | Custom HMAC implementation | `itsdangerous.TimestampSigner` (same as Starlette) | Must match Starlette's exact format or cookies fail signature verification |
| Auth bypass | Per-test monkeypatching of auth internals | `app.dependency_overrides[require_auth]` | FastAPI DI system provides clean, isolated, automatically-reversible overrides |
| Response body access | Streaming consumption logic | `response.content` (bytes) or `response.text` (str) | httpx buffers the body; direct access is safe |
| Test isolation | Manual DB cleanup between tests | `tmp_path` fixture + fresh `create_app()` per test | Already established pattern, zero leakage |

---

## Common Pitfalls

### Pitfall 1: Starlette Uses `TimestampSigner`, NOT `URLSafeTimedSerializer`

**What goes wrong:** If the helper uses `URLSafeTimedSerializer` (as the CONTEXT.md noted as a possibility), the cookie will be rejected by Starlette with `BadSignature` and the session will be empty.

**Why it happens:** Confusion with Flask's `itsdangerous` usage, which does use `URLSafeTimedSerializer`. Starlette uses the simpler `TimestampSigner` that operates on base64-encoded JSON.

**How to avoid:** Use the exact pattern verified in this research session. The cookie format is: `base64(json_bytes)` passed to `TimestampSigner(secret_key).sign()`. [VERIFIED: `inspect.getsource(starlette.middleware.sessions)` — Starlette 1.0.0]

**Warning signs:** Session data empty inside route handlers after injecting cookie; HTTP 401 from routes that read `request.session["active_room"]`.

### Pitfall 2: `response.content_type` Does Not Exist on `requests.Response`

**What goes wrong:** `test_routes_proxy.py` line 60 uses `assert response.content_type == "image/webp"`. This will raise `AttributeError`.

**Why it happens:** Flask's response object has a `.content_type` property. `requests.Response` does not.

**How to avoid:** Replace with `response.headers["content-type"]` or `response.headers.get("content-type", "")`. Note: `requests` normalizes header names to lowercase.

**Warning signs:** `AttributeError: 'Response' object has no attribute 'content_type'`.

### Pitfall 3: `_gevent_sleep` Monkeypatch in SSE Tests Is No-Op But Harmless

**What goes wrong:** Tests monkeypatch `jellyswipe._gevent_sleep = None` but `_gevent_sleep` does not exist in the FastAPI app. Without `raising=False`, this raises `AttributeError`.

**Why it happens:** Phase 34 replaced the gevent-based sleep path with `asyncio.sleep`.

**How to avoid:** Keep `monkeypatch.setattr(jellyswipe, "_gevent_sleep", None, raising=False)` OR remove these lines (they have no effect on the FastAPI route). The actual sleep control comes from `monkeypatch.setattr(time, "time", ...)` mocking the deadline check.

**Warning signs:** `AttributeError: module 'jellyswipe' has no attribute '_gevent_sleep'` if `raising=False` is not specified.

### Pitfall 4: `client.application.config` Does Not Exist on `TestClient`

**What goes wrong:** `test_routes_proxy.py` line 142 uses `client.application.config["JELLYFIN_URL"] = ""`. `TestClient` has no `.application.config` — it's an ASGI wrapper.

**Why it happens:** Flask clients expose the Flask app object via `.application`; FastAPI `TestClient` does not.

**How to avoid:** The test must be restructured. Since the proxy route reads `JELLYFIN_URL` from the module-level config singleton, use `monkeypatch.setattr` on the config value, or pass an empty `JELLYFIN_URL` via `test_config` in a separate app fixture. The simpler approach: monkeypatch `jellyswipe.config._JELLYFIN_URL` to `""` for the duration of this test.

**Warning signs:** `AttributeError: 'TestClient' object has no attribute 'application'`.

### Pitfall 5: Auth Tests Use Both `session_transaction()` and Real Vault Lookups

**What goes wrong:** `test_routes_auth.py` and `test_route_authorization.py` use `session_transaction()` to read back session state after login/delegate operations (e.g., checking `session_id` was set). After migration, these tests use the real auth path — the session state is set by the route handler itself, not by test setup.

**Why it happens:** These tests verify that login sets session state, so they need to READ the session after the HTTP request. `TestClient` persists cookies; session data is accessible via the signed cookie in subsequent requests, but not via `session_transaction()`.

**How to avoid:** To verify session state was set, make a follow-up request to a route that reads session state (e.g., GET /me) rather than inspecting the cookie directly. Alternatively, parse and verify the `Set-Cookie` response header.

**Warning signs:** Test assertions checking `sess["session_id"]` will fail with `AttributeError: 'TestClient' object has no attribute 'session_transaction'`.

### Pitfall 6: Pre-Existing Test Failures Are Not Migration Regressions

**What goes wrong:** 3 tests in `test_db.py` (TestCleanupExpiredTokens) and 1 in `test_dependencies.py` fail in the current codebase on `uv run pytest` for reasons unrelated to the Flask→FastAPI migration:
- `test_db.py::TestCleanupExpiredTokens` — tests expect 24-hour token expiry but `db.py::cleanup_expired_tokens()` deletes after 14 days
- `test_dependencies.py::TestCheckRateLimit::test_raises_429_when_limit_exceeded` — passes when run in isolation but sometimes fails due to test ordering

**Why it happens:** These failures pre-date Phase 35. They are not caused by any Flask pattern.

**How to avoid:** Confirm these tests were failing before this phase's changes. Do not mark Phase 35 as blocked by them unless they count against the "324 tests pass" success criterion. Document them as pre-existing.

---

## Code Examples

Verified patterns from this codebase + official sources:

### Verified `set_session_cookie` Helper (Starlette 1.0.0)
```python
# Source: VERIFIED against Starlette 1.0.0 source (starlette.middleware.sessions)
import json
from base64 import b64encode
import itsdangerous

def set_session_cookie(client, data: dict, secret_key: str) -> None:
    signer = itsdangerous.TimestampSigner(str(secret_key))
    payload = b64encode(json.dumps(data).encode("utf-8"))
    signed = signer.sign(payload)
    client.cookies.set("session", signed.decode("utf-8"))
```
This was verified end-to-end: cookies set this way are correctly decoded by Starlette and appear in `request.session` inside route handlers.

### Replacing `_set_session()` (test_routes_room.py pattern)
```python
# BEFORE (Flask)
def _set_session(client, *, active_room=None, user_id="verified-user", authenticated=True, solo_mode=False):
    with client.session_transaction() as sess:
        if active_room is not None:
            sess["active_room"] = active_room
        sess["solo_mode"] = solo_mode
    if authenticated:
        session_id = "test-session-" + secrets.token_hex(8)
        conn = jellyswipe.db.get_db()
        conn.execute("INSERT INTO user_tokens ...", ...)
        conn.commit()
        conn.close()
        with client.session_transaction() as sess:
            sess["session_id"] = session_id

# AFTER (FastAPI)
# Auth is handled by app.dependency_overrides[require_auth] in the app fixture.
# Only need to set app state in the session cookie.
def _set_session(client, secret_key, *, active_room=None, solo_mode=False):
    data = {"solo_mode": solo_mode}
    if active_room is not None:
        data["active_room"] = active_room
    set_session_cookie(client, data, secret_key)
# OR for tests that only need auth (no active_room): do nothing — the override handles it
```

### Replacing `response.data` in SSE Tests
```python
# BEFORE
assert '"closed": true' in response.data.decode()
data = response.data.decode()

# AFTER
assert '"closed": true' in response.text
data = response.text
```

### Replacing `session_transaction()` for READ (auth tests)
```python
# BEFORE: verify session was set after login
client.post("/auth/jellyfin-login", json={...})
with client.session_transaction() as sess:
    assert "session_id" in sess

# AFTER: verify via a subsequent API call that requires the session
resp2 = client.get("/me")
assert resp2.status_code == 200   # 200 means session_id was set and auth worked
```

### `create_app()` SECRET_KEY Wiring (D-07)
```python
# In jellyswipe/__init__.py
def create_app(test_config=None):
    app = FastAPI(...)

    # Determine the session secret key
    if test_config and "SECRET_KEY" in test_config:
        session_secret = test_config["SECRET_KEY"]
    else:
        session_secret = os.environ["FLASK_SECRET"]

    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret,
        max_age=14 * 24 * 60 * 60,
        same_site="lax",
        https_only=os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true',
    )
    ...
```

---

## File-by-File Migration Map

| File | session_transaction | get_json | response.data | test_client | get_data | Notes |
|------|--------------------|---------|--------------:|------------|---------|-------|
| conftest.py | 0 | 0 | 0 | 1 | 0 | Full rewrite of app/client fixtures; add set_session_cookie, app_real_auth, client_real_auth |
| test_error_handling.py | 1 | 13 | 0 | 0 | 0 | 1 session_transaction for session_id injection — replace with real auth test approach |
| test_route_authorization.py | 16 | 45 | 0 | 1 | 0 | Uses real auth (D-02); test_client → TestClient; session_transaction → real-auth + set_session_cookie |
| test_routes_auth.py | 3 | 8 | 0 | 0 | 0 | Uses real auth (D-02); session_transaction → read-back via API call |
| test_routes_proxy.py | 0 | 0 | 1 | 0 | 0 | response.data → response.content; response.content_type fix; client.application.config fix |
| test_routes_room.py | 6 | 19 | 0 | 0 | 0 | _set_session helper rewrite; session_transaction → set_session_cookie |
| test_routes_sse.py | 1 | 0 | 10 | 0 | 1 | _set_session_room → set_session_cookie; response.data → response.content/response.text |
| test_routes_xss.py | 7 | 4 | 4 | 0 | 7 | Two helper functions rewrite; get_data → response.text; response.data → response.content |

**Not requiring migration (framework-agnostic):**
- test_auth.py, test_db.py, test_dependencies.py, test_http_client.py, test_infrastructure.py, test_jellyfin_library.py, test_migration_23.py, test_rate_limiter.py, test_ssrf_validator.py, test_tmdb_auth.py

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `app.test_client()` (Flask) | `TestClient(app)` (FastAPI/httpx) | Phase 30+ | Client is now a `requests`-compatible object |
| `session_transaction()` context manager | `set_session_cookie()` helper + `dependency_overrides` | Phase 35 | Clean separation of auth bypass and session state |
| `response.get_json()` | `response.json()` | Phase 35 | Standard `requests.Response` API |
| `response.data` | `response.content` (bytes) or `response.text` (str) | Phase 35 | Standard `requests.Response` API |
| Vault seeding for auth in tests | `dependency_overrides[require_auth]` | Phase 35 | No DB side effects for auth in most tests |
| `gevent.sleep` / `time.sleep` control in SSE tests | `asyncio.sleep` + `time.time` mocking | Phase 34 | `_gevent_sleep` references are no-ops |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Pre-existing `test_db.py::TestCleanupExpiredTokens` failures (3 tests) are not caused by Phase 35 migration and should not count against the 324-pass success criterion | Common Pitfalls #6 | If planner decides these must be fixed in Phase 35, requires investigating `db.py::cleanup_expired_tokens()` 14-day vs 24-hour discrepancy |
| A2 | The `_gevent_sleep` monkeypatches in test_routes_sse.py can be removed entirely (they have no effect) | Anti-Patterns | If the SSE route still somehow uses gevent in a code path not seen in this research, removing would break SSE test timing control |

---

## Open Questions (RESOLVED)

1. **Pre-existing test failures in scope?**
   - What we know: 3 test_db.py tests and potentially 1 test_dependencies.py test fail before Phase 35 changes begin, for reasons unrelated to Flask→FastAPI migration
   - What's unclear: Does the success criterion "all 324 tests pass" require fixing these pre-existing failures, or only the migration-caused failures?
   - Recommendation: Planner should treat these as pre-existing and note them in the plan. If the user's success criterion is literally 324/324, the db.py cleanup threshold mismatch (24h vs 14d) will need a separate fix.
   - **RESOLVED:** Pre-existing failures documented in Plan 06 Task 1; do not count against Phase 35 success criterion. The success criterion is "all migration-caused failures fixed"; pre-existing failures are noted and excluded.

2. **`test_routes_proxy.py`: `client.application.config["JELLYFIN_URL"] = ""`**
   - What we know: This test mutates the Flask app config to simulate a missing JELLYFIN_URL. There is no equivalent on `TestClient`.
   - What's unclear: The JELLYFIN_URL config value is read from `jellyswipe.config._JELLYFIN_URL` by the proxy router. Monkeypatching it in the test would work.
   - Recommendation: Replace `client.application.config["JELLYFIN_URL"] = ""` with `monkeypatch.setattr(jellyswipe.config, "_JELLYFIN_URL", "")` — this is a one-line change and does not modify test logic.
   - **RESOLVED:** Plan 05 Task 1 Fix 3 implements `monkeypatch.setattr(jellyswipe.config, "_JELLYFIN_URL", "")` as the replacement.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| fastapi | TestClient | Yes | 0.136.1 | — |
| httpx | TestClient transport | Yes | 0.28.1 | — |
| starlette | SessionMiddleware | Yes | 1.0.0 | — |
| itsdangerous | set_session_cookie helper | Yes | 2.2.0 | — |
| sse-starlette | rooms.py import (test collection) | Yes | 3.4.1 | — |
| pytest | Test runner | Yes | 9.0.3 | — |
| uv | Project runner (`uv run pytest`) | Yes | — | `python3 -m pytest` |
| docker | Success criterion 4 | Not checked | — | Skip Docker verification until environment confirmed |

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `uv run pytest tests/test_routes_room.py -x --no-cov` |
| Full suite command | `uv run pytest tests/` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TST-01 | All 324 tests pass with FastAPI TestClient | integration | `uv run pytest tests/` | Yes (all 18 test files exist) |
| TST-01 | No `session_transaction()` in any test file | structural | `grep -rn "session_transaction" tests/` — expect 0 results | Yes |
| TST-01 | No `response.get_json()` in any test file | structural | `grep -rn "get_json()" tests/` — expect 0 results | Yes |
| TST-01 | No `response.data` in any test file | structural | `grep -rn "response\.data" tests/` — expect 0 results | Yes |
| TST-01 | No override state leaks (success criterion 3) | integration | Test isolation verified by running tests in random order: `uv run pytest tests/ -p randomly` | Yes |
| FAPI-01 | Docker build succeeds | smoke | `docker build -t jelly-swipe-test .` | Dockerfile exists |
| FAPI-01 | Container starts with Uvicorn on port 5005 | smoke | `docker run --rm -e FLASK_SECRET=test -p 5005:5005 jelly-swipe-test` (manual verify) | Dockerfile exists |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x --no-cov -q` (stop at first failure)
- **Per wave merge:** `uv run pytest tests/ --no-cov -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

None — all test files and framework infrastructure already exist. The only "gap" is that the current conftest.py's `client` fixture is broken (`app.test_client()` fails) — but this is the primary work of Wave 1, not a Wave 0 gap.

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Yes | Tested via `require_auth` override + real auth fixtures |
| V3 Session Management | Yes | `itsdangerous.TimestampSigner` — max_age=14 days enforced by Starlette |
| V4 Access Control | Yes | Authorization tests preserved via `client_real_auth` fixture |
| V5 Input Validation | Yes | XSS tests (test_routes_xss.py) preserved, only API surface changes |
| V6 Cryptography | No | No cryptography changes in this phase |

### Known Threat Patterns for Test Migration

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Session cookie forgery in tests | Spoofing | `itsdangerous.TimestampSigner` with matching secret_key ensures signed cookies are accepted |
| Auth state leakage between tests | Elevation of Privilege | `app.dependency_overrides.clear()` in fixture teardown — enforced by yield fixture pattern |

---

## Sources

### Primary (HIGH confidence)
- Starlette 1.0.0 source code — `inspect.getsource(starlette.middleware.sessions)` — verified `TimestampSigner` usage and exact cookie format
- FastAPI TestClient — `inspect.getsource(TestClient.__init__)` — confirmed `raise_server_exceptions` parameter
- Codebase scan — grep counts of all Flask patterns; fixture code; `create_app()` implementation

### Secondary (MEDIUM confidence)
- FastAPI official docs on dependency overrides (verified against working codebase pattern)
- itsdangerous 2.2.0 — `TimestampSigner.sign()` behavior verified with live Python session

### Tertiary (LOW confidence)
- None — all claims verified against installed versions in this codebase

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified via `importlib.metadata.version()`
- Session cookie format: HIGH — verified via `inspect.getsource()` and live test
- Architecture: HIGH — all fixture patterns verified against working FastAPI test patterns
- Pitfalls: HIGH — derived from direct analysis of current test file errors

**Research date:** 2026-05-03
**Valid until:** 2026-06-03 (stable Starlette/FastAPI versions)
