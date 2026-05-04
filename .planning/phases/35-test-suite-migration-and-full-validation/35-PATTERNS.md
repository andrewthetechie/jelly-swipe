# Phase 35: Test Suite Migration and Full Validation - Pattern Map

**Mapped:** 2026-05-03
**Files analyzed:** 10 files (2 modified source + 8 modified test files)
**Analogs found:** 10 / 10

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `tests/conftest.py` | test-infrastructure | request-response | `tests/test_auth.py` (auth_app + client fixtures) | exact |
| `jellyswipe/__init__.py` | config / app-factory | request-response | self (current `create_app()`) | self-modification |
| `tests/test_routes_room.py` | test | CRUD | `tests/test_auth.py` (TestClient + `resp.json()`) | role-match |
| `tests/test_routes_sse.py` | test | streaming | `tests/test_auth.py` (TestClient + `resp.text`) | role-match |
| `tests/test_routes_auth.py` | test | request-response | `tests/test_auth.py` (real-auth path, no override) | exact |
| `tests/test_route_authorization.py` | test | request-response | `tests/test_auth.py` (real-auth path, no override) | exact |
| `tests/test_routes_proxy.py` | test | request-response | `tests/test_dependencies.py` (inline TestClient) | role-match |
| `tests/test_routes_xss.py` | test | CRUD | `tests/test_auth.py` (TestClient + `resp.json()`) | role-match |
| `tests/test_error_handling.py` | test | request-response | `tests/test_dependencies.py` (TestClient inline) | role-match |
| `.planning/REQUIREMENTS.md` | docs | — | self (TST-01 update only) | self-modification |

---

## Pattern Assignments

### `tests/conftest.py` (test-infrastructure, full rewrite)

**Analog:** `tests/test_auth.py` (lines 32–78 — `auth_app` + `client` fixtures)

**Imports pattern** — copy from `tests/test_auth.py` lines 14–25:
```python
from fastapi import FastAPI, Depends, Request
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from jellyswipe.dependencies import (
    AuthUser,
    require_auth,
    get_db_dep,
    DBConn,
    check_rate_limit,
    destroy_session_dep,
    get_provider,
)
```

**`app` fixture with dependency overrides** — new pattern, per RESEARCH.md Pattern 1 (verified):
```python
@pytest.fixture
def app(tmp_path, monkeypatch):
    import jellyswipe as jellyswipe_module
    from jellyswipe import create_app

    db_file = str(tmp_path / "test_route.db")
    test_config = {
        "DB_PATH": db_file,
        "TESTING": True,
        "SECRET_KEY": os.environ["FLASK_SECRET"],   # matches set_session_cookie helper
    }
    fast_app = create_app(test_config=test_config)

    # Override auth — no DB vault needed (D-01)
    fast_app.dependency_overrides[require_auth] = lambda: AuthUser(
        jf_token="valid-token", user_id="verified-user"
    )
    # Override provider — replaces monkeypatch of _provider_singleton (D-05)
    fake_provider = FakeProvider()
    fast_app.dependency_overrides[get_provider] = lambda: fake_provider

    from jellyswipe.rate_limiter import rate_limiter as _rl
    _rl.reset()

    yield fast_app

    fast_app.dependency_overrides.clear()   # CRITICAL: prevents state leak (D-01)
```

**`client` fixture** — copy structure from `tests/test_auth.py` lines 75–78:
```python
@pytest.fixture
def client(app):
    return TestClient(app)
```

**`set_session_cookie` helper** — new, per RESEARCH.md Pattern 2 (verified against Starlette 1.0.0):
```python
import json
from base64 import b64encode
import itsdangerous

def set_session_cookie(client, data: dict, secret_key: str) -> None:
    """Inject session state into a FastAPI TestClient's cookie jar.

    Uses itsdangerous.TimestampSigner — Starlette 1.0.0 signing format.
    Format: base64(json_bytes).timestamp.signature
    """
    signer = itsdangerous.TimestampSigner(str(secret_key))
    payload = b64encode(json.dumps(data).encode("utf-8"))
    signed = signer.sign(payload)
    client.cookies.set("session", signed.decode("utf-8"))
```

**`app_real_auth` / `client_real_auth` fixture** — per RESEARCH.md Pattern 3 (D-02):
```python
@pytest.fixture
def app_real_auth(tmp_path, monkeypatch):
    """App fixture with real require_auth — for auth integration tests only."""
    import jellyswipe as jellyswipe_module
    from jellyswipe import create_app

    db_file = str(tmp_path / "test_route.db")
    test_config = {
        "DB_PATH": db_file,
        "TESTING": True,
        "SECRET_KEY": os.environ["FLASK_SECRET"],
    }
    fast_app = create_app(test_config=test_config)
    # NOTE: NO dependency_overrides[require_auth] set — real auth code path (D-02)
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

**`FakeProvider` class** — keep as-is from current `tests/conftest.py` lines 128–178.

**`db_connection`, `db_path`, `mock_env_vars`, `setup_test_environment`, `mocker` fixtures** — keep as-is from current `tests/conftest.py` (framework-agnostic, no changes needed).

---

### `jellyswipe/__init__.py` (app-factory, targeted edit)

**Analog:** self — current `create_app()` at lines 217–275

**`SECRET_KEY` wiring change** — replace lines 243–247 with conditional (D-07, D-08):
```python
# BEFORE (lines 243-247):
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ["FLASK_SECRET"],
    max_age=14 * 24 * 60 * 60,
    same_site="lax",
    https_only=os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true',
)

# AFTER:
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
```

**Nothing else changes** — `app = create_app()` at line 280 continues to use `os.environ["FLASK_SECRET"]` (D-08).

---

### `tests/test_routes_room.py` (test, mechanical migration)

**Analog:** `tests/test_auth.py` — `resp.json()` usage pattern (lines 116–117)

**`_set_session` helper rewrite** — replace the 20-line Flask helper with FastAPI pattern:
```python
# BEFORE (lines 22-44): vault seeding + session_transaction()
def _set_session(client, *, active_room=None, user_id="verified-user", authenticated=True, solo_mode=False):
    with client.session_transaction() as sess: ...
    # + INSERT INTO user_tokens + session_transaction() for session_id

# AFTER: auth via dependency_overrides (in fixture); only set app state
def _set_session(client, secret_key, *, active_room=None, solo_mode=False):
    data = {"solo_mode": solo_mode}
    if active_room is not None:
        data["active_room"] = active_room
    set_session_cookie(client, data, secret_key)
    # For tests that only need auth (no active_room): call with empty data or skip
```

**`secret_key` access** — tests that call `_set_session()` must receive it from the `app` fixture:
```python
def test_room_create_returns_pairing_code(client, app):
    _set_session(client, app.state_middleware_secret_key, ...)
    # OR: pass FLASK_SECRET env var directly — it matches since app fixture uses it
```

**Mechanical replacements** (6 `session_transaction`, 19 `get_json`):
- `response.get_json()` → `response.json()` (19 occurrences)
- Each `with client.session_transaction() as sess:` block → `set_session_cookie(client, {...}, secret_key)`

---

### `tests/test_routes_sse.py` (test, mechanical migration)

**Analog:** `tests/test_auth.py` — `resp.text` usage (line 208 area); response consumption pattern

**`_set_session_room` helper rewrite**:
```python
# BEFORE (lines 23-44): vault seeding + session_transaction()
def _set_session_room(client, room_code, user_id=None): ...

# AFTER: auth via dependency_overrides (fixture); session state via cookie
def _set_session_room(client, secret_key, room_code, user_id=None):
    if user_id is None:
        user_id = f"test-user-{secrets.token_hex(4)}"
    set_session_cookie(client, {
        "active_room": room_code,
        "my_user_id": user_id,
        "jf_delegate_server_identity": True,
        "solo_mode": False,
    }, secret_key)
    # DROP: vault INSERT + session_transaction() for session_id
```

**Mechanical replacements** (1 `session_transaction`, 10 `response.data`, 1 `get_data`):
- `response.data.decode()` → `response.text`
- `response.data` → `response.content`
- `_ = response.data` → `_ = response.content`
- `with client.session_transaction()` → `set_session_cookie(client, {...}, secret_key)`

**`_gevent_sleep` monkeypatch** — add `raising=False` to any `monkeypatch.setattr(jellyswipe, "_gevent_sleep", ...)` calls, or remove entirely (no effect on FastAPI route, per RESEARCH.md Pitfall 3).

---

### `tests/test_routes_auth.py` (test, real-auth variant)

**Analog:** `tests/test_auth.py` — real `require_auth` path without dependency_overrides

**Fixture swap** — tests use `client_real_auth` (from new conftest) instead of `client`:
```python
# Tests that currently use `client` fixture → use `client_real_auth`
# (D-02: these tests exercise the real auth code path)
def test_jellyfin_use_server_identity_sets_session_flag(client_real_auth):
    client_real_auth.post("/auth/jellyfin-use-server-identity")
    # Instead of session_transaction(), verify via follow-up API call:
    resp2 = client_real_auth.get("/auth/provider")
    assert resp2.status_code == 200   # session was set; auth works
```

**`session_transaction` → API follow-up** (3 occurrences):
```python
# BEFORE (test_routes_auth.py lines 51-53):
with client.session_transaction() as sess:
    assert "session_id" in sess

# AFTER: verify session is live by hitting an auth-protected or neutral endpoint
resp2 = client_real_auth.get("/auth/provider")
assert resp2.status_code == 200
```

**`response.content_type` → `response.headers["content-type"]`** (line 33):
```python
# BEFORE:
assert response.content_type == "application/json"

# AFTER:
assert "application/json" in response.headers["content-type"]
```

**Mechanical replacements** (3 `session_transaction`, 8 `get_json`):
- `response.get_json()` → `response.json()`

---

### `tests/test_route_authorization.py` (test, real-auth variant)

**Analog:** `tests/test_auth.py` — real-auth path + `tests/test_dependencies.py` — TestClient usage

**Current local fixtures at lines 61–72** — replace with `app_real_auth` / `client_real_auth` from conftest:
```python
# BEFORE (lines 61-72): local app_module + client fixtures using app.test_client()
@pytest.fixture
def app_module(db_connection, monkeypatch): ...
@pytest.fixture
def client(app_module):
    return app_module.app.test_client()

# AFTER: use shared conftest fixtures
# Remove local app_module and client fixtures.
# Tests receive `client_real_auth` from conftest instead.
# `db_connection` fixture passed to test directly for DB seeding.
```

**`_set_session` helper rewrite** (lines 75–90):
```python
# BEFORE: vault seeding + session_transaction() (2 modes: authenticated/unauthenticated)
def _set_session(client, db_connection, *, active_room, authenticated):
    if authenticated:
        # INSERT INTO user_tokens + session_transaction()

# AFTER: auth via real require_auth (vault still needed here — real auth tests);
# session state via set_session_cookie
def _set_session(client, db_connection, secret_key, *, active_room, authenticated):
    if authenticated:
        import jellyswipe.db
        session_id = "test-session-" + secrets.token_hex(8)
        db_connection.execute("INSERT INTO user_tokens ...", ...)
        db_connection.commit()
        # Use set_session_cookie to set session_id AND active_room
        set_session_cookie(client, {"session_id": session_id, "active_room": active_room}, secret_key)
    else:
        set_session_cookie(client, {"active_room": active_room}, secret_key)
```

**Note:** `test_route_authorization.py` IS a real-auth test (D-02), so vault seeding for auth is still required here. The key change is replacing `session_transaction()` with `set_session_cookie()`.

**Mechanical replacements** (16 `session_transaction`, 45 `get_json`, 1 `test_client`):
- `response.get_json()` → `response.json()`

---

### `tests/test_routes_proxy.py` (test, mechanical migration)

**Analog:** `tests/test_dependencies.py` lines 130–148 — `TestClient` pattern + `resp.json()`

**Three targeted fixes required** (per RESEARCH.md Pitfall 2 and Pitfall 4):

**Fix 1 — `response.data` → `response.content`** (line 47):
```python
# BEFORE:
assert response.data == b"\x89PNG\r\n"
# AFTER:
assert response.content == b"\x89PNG\r\n"
```

**Fix 2 — `response.content_type` → `response.headers["content-type"]`** (line 60):
```python
# BEFORE:
assert response.content_type == "image/webp"
# AFTER:
assert response.headers["content-type"] == "image/webp"
```

**Fix 3 — `client.application.config` → `monkeypatch.setattr`** (line 142):
```python
# BEFORE:
client.application.config["JELLYFIN_URL"] = ""
# AFTER:
import jellyswipe.config
monkeypatch.setattr(jellyswipe.config, "JELLYFIN_URL", "")
```

---

### `tests/test_routes_xss.py` (test, mechanical migration)

**Analog:** `tests/test_auth.py` lines 106–117 — `resp.json()` pattern

**`_setup_vault_session` helper rewrite** (lines 33–45):
```python
# BEFORE: vault seeding + session_transaction() for session_id and active_room
def _setup_vault_session(client, user_id="user_abc123", active_room="TEST123"):
    session_id = "xss-test-" + secrets.token_hex(8)
    conn = jellyswipe.db.get_db()
    conn.execute("INSERT INTO user_tokens ...", ...)
    ...
    with client.session_transaction() as sess:
        sess["session_id"] = session_id
        sess["active_room"] = active_room

# AFTER: auth via dependency_overrides (in fixture); only session state via cookie
def _setup_vault_session(client, secret_key, user_id="user_abc123", active_room="TEST123"):
    set_session_cookie(client, {"active_room": active_room}, secret_key)
    # DROP: vault INSERT; auth handled by dependency_overrides[require_auth]
```

**Additional `session_transaction` calls** (lines 60–61 in `TestLayer1ServerSideValidation`):
```python
# BEFORE:
with client.session_transaction() as sess:
    sess['solo_mode'] = True
# AFTER: merge into the set_session_cookie call above:
set_session_cookie(client, {"active_room": active_room, "solo_mode": True}, secret_key)
```

**Mechanical replacements** (7 `session_transaction`, 4 `get_json`, 4 `response.data`, 7 `get_data`):
- `response.get_json()` → `response.json()`
- `json.loads(response.data)` → `response.json()`
- `response.get_data(as_text=True)` → `response.text`
- `response.data` → `response.content`

---

### `tests/test_error_handling.py` (test, partial migration)

**Analog:** `tests/test_dependencies.py` lines 130–148 — `TestClient(app, raise_server_exceptions=False)` pattern

**The `client` fixture already uses the shared conftest `client` fixture** — most tests need no fixture changes.

**`raise_server_exceptions=False`** — apply to this file's test class or use a separate fixture (D-11):
```python
# Option A: override the client fixture for this file only
@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)

# Option B: per-test where 4xx/5xx assertions are made (more surgical)
```

**`session_transaction` (1 occurrence)** — in `test_error_handling.py`, used to set `session_id` only. Since the `app` fixture sets `dependency_overrides[require_auth]`, no session cookie is needed for auth. The call can be removed entirely.

**Mechanical replacements** (1 `session_transaction`, 13 `get_json`):
- `response.get_json()` → `response.json()`
- `with client.session_transaction() as sess: sess["session_id"] = ...` → remove (dependency_override handles auth)

---

## Shared Patterns

### Pattern A: TestClient Import and Construction
**Source:** `tests/test_auth.py` lines 15, 76–78
**Apply to:** `conftest.py` (app/client/app_real_auth/client_real_auth fixtures); remove from individual test files that currently create TestClient locally
```python
from fastapi.testclient import TestClient
# ...
return TestClient(app)                                    # standard
return TestClient(app, raise_server_exceptions=False)     # error-handling tests (D-11)
```

### Pattern B: `response.json()` (requests.Response API)
**Source:** `tests/test_auth.py` line 117; `tests/test_dependencies.py` line 149
**Apply to:** All 8 test files being migrated — 34 total occurrences
```python
data = resp.json()          # replaces resp.get_json()
```

### Pattern C: `response.content` / `response.text` (bytes/str body access)
**Source:** `tests/test_auth.py` — `requests.Response` API convention
**Apply to:** `test_routes_proxy.py`, `test_routes_sse.py`, `test_routes_xss.py` — 15 + 10 + 4 occurrences
```python
response.content            # bytes  — replaces response.data
response.text               # str    — replaces response.data.decode() / response.get_data(as_text=True)
```

### Pattern D: `dependency_overrides` teardown
**Source:** RESEARCH.md Pattern 1 (verified against FastAPI docs)
**Apply to:** `conftest.py` `app` and `app_real_auth` fixtures
```python
yield fast_app
fast_app.dependency_overrides.clear()   # must be AFTER yield
```

### Pattern E: `set_session_cookie` for app state injection
**Source:** RESEARCH.md Pattern 2 (verified against Starlette 1.0.0 source)
**Apply to:** Every location that currently calls `session_transaction()` to set `active_room`, `solo_mode`, `my_user_id`, or `jf_delegate_server_identity`
```python
set_session_cookie(client, {"active_room": code, "solo_mode": False}, secret_key)
```
**Key:** `secret_key` must be `os.environ["FLASK_SECRET"]` (the same value passed to `create_app(test_config={"SECRET_KEY": ...})`).

### Pattern F: `response.headers["content-type"]` (not `.content_type`)
**Source:** RESEARCH.md Pitfall 2; `requests.Response` API
**Apply to:** `test_routes_auth.py` (line 33), `test_routes_proxy.py` (line 60)
```python
assert "application/json" in response.headers["content-type"]
assert response.headers["content-type"] == "image/webp"
```

### Pattern G: `monkeypatch.setattr` for config mutation
**Source:** `tests/conftest.py` lines 113–115 — existing `monkeypatch.setattr(jellyswipe.db, 'DB_PATH', ...)` pattern
**Apply to:** `test_routes_proxy.py` line 142 to replace `client.application.config["JELLYFIN_URL"] = ""`
```python
import jellyswipe.config
monkeypatch.setattr(jellyswipe.config, "JELLYFIN_URL", "")
```

---

## No Analog Found

All files in scope have analogs. The `set_session_cookie` helper has no existing analog but is verified from RESEARCH.md (confirmed against Starlette 1.0.0 `inspect.getsource(starlette.middleware.sessions)`).

The following files are explicitly **not requiring migration** (framework-agnostic, confirmed by RESEARCH.md):

| File | Role | Reason |
|------|------|--------|
| `tests/test_auth.py` | test | Already uses FastAPI `TestClient`; no Flask patterns |
| `tests/test_db.py` | test | Pure SQLite; no HTTP client |
| `tests/test_dependencies.py` | test | Already uses FastAPI `TestClient` |
| `tests/test_http_client.py` | test | Tests HTTP client module directly |
| `tests/test_infrastructure.py` | test | Framework-agnostic infrastructure |
| `tests/test_jellyfin_library.py` | test | Unit tests; no HTTP client |
| `tests/test_migration_23.py` | test | DB migration; no HTTP client |
| `tests/test_rate_limiter.py` | test | Rate limiter unit tests |
| `tests/test_ssrf_validator.py` | test | Validator unit tests |
| `tests/test_tmdb_auth.py` | test | External auth; no Flask client |

---

## Pre-Existing Test Failures (Not Migration Regressions)

Per RESEARCH.md Pitfall 6, these failures exist before Phase 35 and must not block the phase:

| File | Test | Failure Cause |
|------|------|---------------|
| `tests/test_db.py` | `TestCleanupExpiredTokens` (3 tests) | `cleanup_expired_tokens()` uses 14-day threshold; tests expect 24h |
| `tests/test_dependencies.py` | `TestCheckRateLimit::test_raises_429_when_limit_exceeded` | Test-ordering sensitivity |

---

## Metadata

**Analog search scope:** `tests/`, `jellyswipe/`
**Files scanned:** 19 (18 test files + `jellyswipe/__init__.py`)
**Pattern extraction date:** 2026-05-03
