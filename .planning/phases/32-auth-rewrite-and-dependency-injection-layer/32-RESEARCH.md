# Phase 32: Auth Rewrite and Dependency Injection Layer - Research

**Researched:** 2026-05-02
**Domain:** FastAPI dependency injection, session-based auth, SQLite yield dependency
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** `require_auth(request: Request)` returns an `AuthUser` dataclass. Fields: `jf_token: str`, `user_id: str`. Routes declare: `auth: AuthUser = Depends(require_auth)` and access `auth.jf_token`, `auth.user_id`.
- **D-02:** Internally calls `auth.get_current_token(request.session)` (thin wrapper). If `None`, raises `HTTPException(status_code=401, detail="Authentication required")`.
- **D-03:** `destroy_session_dep(request: Request)` is also exported from `dependencies.py`. It is a Depends()-compatible thin wrapper around `auth.destroy_session(request.session)`.
- **D-04:** `get_db_dep()` is a yield dependency — opens the connection, yields it, closes on exit via `get_db_closing()`. Connection lifetime matches the request/response cycle.
- **D-05:** Expose `DBConn = Annotated[sqlite3.Connection, Depends(get_db_dep)]` as a type alias so routes declare `conn: DBConn` instead of spelling out `Depends(get_db_dep)` inline.
- **D-06:** `check_rate_limit(request: Request)` uses request path inference — reads `request.url.path` to look up the rate limit config from `_RATE_LIMITS`. If the path is not in `_RATE_LIMITS`, the request passes through (no limit applied).
- **D-07:** `check_rate_limit()` is exported as a Depends()-compatible callable. Routes declare: `_: None = Depends(check_rate_limit)` (or it raises `HTTPException(status_code=429)` directly so the return value is unused).
- **D-08:** `get_provider()` moves from the closure inside `create_app()` in `__init__.py` to `dependencies.py` as a module-level function. It continues to use the `_provider_singleton` module-level global — the singleton stays in `__init__.py` until Phase 33 extracts routers and resolves the global reference.
- **D-09:** Phase 32 creates `dependencies.py` only. Routes in `__init__.py` continue using `_require_login()` until Phase 33 extracts them into domain routers and wires `Depends(require_auth)` at that time.
- **D-10:** CR-01 (connection leak in existing routes) and CR-02 (session/vault TTL mismatch) are not addressed in Phase 32.

### Claude's Discretion

None specified — all key design decisions are locked.

### Deferred Ideas (OUT OF SCOPE)

- CR-01 fix (connection leak): New routes in Phase 33 use `get_db_dep()` which fixes the leak; existing routes in `__init__.py` are untouched until extraction
- CR-02 fix (TTL mismatch): Session cookie max_age = 14 days vs vault TTL = 24 hours — deferred to Phase 35 or a standalone fix phase
- `httpx.AsyncClient` migration — deferred post-v2.0
- Pydantic request/response models — v2.1 (ARCH-02)
- Updating routes in `__init__.py` to use `Depends(require_auth)` — Phase 33
- SSE route migration — Phase 34
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ARCH-03 | Shared logic (auth checking, provider access, DB connection) extracted into `jellyswipe/dependencies.py` using FastAPI's `Depends()` pattern | FastAPI `Depends()` with `Annotated` type aliases is the verified standard pattern; yield dependency for DB lifetime management is documented in FastAPI official docs. `AuthUser` dataclass + `require_auth` replaces the Phase 31 bridge `_require_login()`. |
</phase_requirements>

---

## Summary

Phase 32 creates `jellyswipe/dependencies.py` — a self-contained FastAPI dependency injection module that bridges the existing `auth.py`, `db.py`, and `rate_limiter.py` modules into Depends()-compatible callables. The `auth.py` file is already free of Flask imports (Phase 31 completed this); Phase 32 builds on top of it by wrapping its three callables in FastAPI-native DI wrappers.

The new file exports five items: `AuthUser` dataclass, `require_auth()`, `get_db_dep()` + `DBConn` type alias, `get_provider()`, `check_rate_limit()`, and `destroy_session_dep()`. The `test_auth.py` file is the primary work surface for tests — its Flask-based fixtures must be replaced entirely with a minimal FastAPI test app using `TestClient`. The existing 10 tests in `test_auth.py` all fail with `ModuleNotFoundError: No module named 'flask'`, confirming the rewrite is needed.

**Primary recommendation:** Create `dependencies.py` with all five dependency callables, rewrite `test_auth.py` using a minimal FastAPI `TestClient` app with no Flask dependency. No changes to `__init__.py` routes in Phase 32.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Session token lookup | API / Backend | — | `request.session` is Starlette middleware state; the lookup against SQLite is a server-side operation |
| Auth dependency injection | API / Backend | — | FastAPI `Depends()` resolves per-request at the framework layer |
| DB connection lifecycle | API / Backend | — | yield dependency ensures connection opens before handler, closes after response |
| Rate limiting | API / Backend | — | `request.client.host` + path inference; pure server-side token bucket |
| Provider singleton access | API / Backend | — | `_provider_singleton` global in `__init__.py`; dependency provides access without leaking it into routes |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | 0.128.0 | `Depends()`, `HTTPException`, `Request` | Already installed; `Depends()` is the canonical DI pattern [VERIFIED: npm view equiv — `uv run python -c "import fastapi; print(fastapi.__version__)"` = 0.128.0] |
| starlette | (fastapi dep) | `Request.session`, `Request.client.host`, `Request.url.path` | FastAPI `Request` comes directly from Starlette [CITED: fastapi/fastapi docs/en/docs/advanced/using-request-directly.md] |
| dataclasses | stdlib | `AuthUser` dataclass definition | Stdlib; Pydantic models are deferred to v2.1 per ARCH-02 |
| sqlite3 | stdlib | `DBConn` type alias target | Already used throughout project |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| typing.Annotated | stdlib (3.9+) | `DBConn = Annotated[sqlite3.Connection, Depends(get_db_dep)]` | Type alias pattern for reusable dependencies |
| httpx | 0.28.1 | FastAPI `TestClient` transport layer | Required for `TestClient`; already in dev dependencies |
| pytest | 9.0.3 | Test runner | Already configured in pyproject.toml |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `dataclass` for `AuthUser` | `pydantic.BaseModel` | Pydantic adds validation; deferred to v2.1 per ARCH-02 |
| path inference for rate limit | Per-route factory `check_rate_limit("endpoint")` | Factory requires argument at Depends() call site, which requires lambda or partial; path inference avoids this cleanly |
| yield dependency for DB | contextmanager-in-route | yield dependency ensures cleanup even on exception; per-route contextmanager is more error-prone (CR-01 origin) |

**Installation:** No new dependencies needed. All required libraries are already installed.

---

## Architecture Patterns

### System Architecture Diagram

```
HTTP Request
    │
    ▼
[ProxyHeadersMiddleware]  ← resolves X-Forwarded-For → request.client.host
    │
    ▼
[SessionMiddleware]       ← decodes session cookie → request.session dict
    │
    ▼
[RequestIdMiddleware]     ← generates request_id → request.state.request_id
    │
    ▼
[Route Handler]
    │
    ├── Depends(require_auth) ─────────► auth.get_current_token(request.session)
    │       │                                    │
    │       │                            vault lookup (SQLite)
    │       │                                    │
    │       ▼                                    ▼
    │   AuthUser(jf_token, user_id)         None → HTTPException 401
    │
    ├── conn: DBConn ──────────────────► get_db_dep() [yield]
    │       │                            get_db_closing() wraps open/close
    │       ▼
    │   sqlite3.Connection (auto-closed on response exit)
    │
    ├── Depends(check_rate_limit) ─────► _RATE_LIMITS[request.url.path]
    │       │                            rate_limiter.check(endpoint, ip, limit)
    │       ▼                                    │
    │   None (pass-through)              False → HTTPException 429
    │
    └── Depends(get_provider) ─────────► _provider_singleton (in __init__.py)
            │                            JellyfinLibraryProvider singleton
            ▼
        JellyfinLibraryProvider instance
```

### Recommended Project Structure

```
jellyswipe/
├── auth.py              # unchanged — get_current_token(), create_session(), destroy_session()
├── dependencies.py      # NEW — all Depends()-compatible callables + AuthUser dataclass
├── db.py                # unchanged — get_db_closing(), get_db()
├── rate_limiter.py      # unchanged — rate_limiter singleton, RateLimiter.check()
└── __init__.py          # unchanged in Phase 32 — _provider_singleton stays here
```

### Pattern 1: Depends() with Annotated Type Alias

**What:** Define dependency once as a type alias using `Annotated`; routes use the bare type annotation.

**When to use:** For any dependency used in 3+ routes. Avoids repeating `Annotated[T, Depends(fn)]` everywhere.

**Example:**
```python
# Source: https://github.com/fastapi/fastapi/blob/master/docs/en/docs/tutorial/dependencies/index.md
from typing import Annotated
from fastapi import Depends
import sqlite3

DBConn = Annotated[sqlite3.Connection, Depends(get_db_dep)]

# Route usage:
def my_route(conn: DBConn):  # no Depends() needed inline
    ...
```

### Pattern 2: Yield Dependency for Resource Cleanup

**What:** Use `yield` in a dependency to perform cleanup after the response is sent.

**When to use:** Any dependency that opens a resource (DB connection, file handle, etc.)

**Example:**
```python
# Source: https://github.com/fastapi/fastapi/blob/master/docs/en/docs/tutorial/dependencies/dependencies-with-yield.md
from jellyswipe.db import get_db_closing

def get_db_dep():
    with get_db_closing() as conn:
        yield conn
    # conn.close() happens in get_db_closing()'s finally block
```

### Pattern 3: Dependency That Raises HTTPException

**What:** A dependency can raise `HTTPException` to short-circuit the route before the handler runs.

**When to use:** Auth checks, rate limit checks — any guard that should block the request.

**Example:**
```python
# Source: https://github.com/fastapi/fastapi/blob/master/docs/en/docs/tutorial/dependencies/index.md
from fastapi import Depends, HTTPException, Request
from dataclasses import dataclass

@dataclass
class AuthUser:
    jf_token: str
    user_id: str

def require_auth(request: Request) -> AuthUser:
    result = auth.get_current_token(request.session)
    if result is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    jf_token, user_id = result
    return AuthUser(jf_token=jf_token, user_id=user_id)
```

### Pattern 4: Cross-Module Dependency (global reference)

**What:** `get_provider()` in `dependencies.py` references `_provider_singleton` in `__init__.py`. This is an import-from-package pattern (not a closure), which means `dependencies.py` imports from `jellyswipe` (the package).

**When to use:** When the singleton lifecycle lives in a different module until Phase 33 extracts routers.

**Key detail:** `dependencies.py` must `import jellyswipe` (or `from jellyswipe import _provider_singleton`) to access the global. Since `jellyswipe/__init__.py` is the package init, importing from it inside the same package requires care to avoid circular imports. The safe pattern is a late/lazy import inside `get_provider()` body, or using `import jellyswipe as _app_module` at module level.

```python
# Safe pattern to avoid circular import
def get_provider():
    import jellyswipe as _mod  # lazy import; avoids circular at module load
    global _mod
    if _mod._provider_singleton is None:
        from jellyswipe.jellyfin_library import JellyfinLibraryProvider
        from jellyswipe import _JELLYFIN_URL
        _mod._provider_singleton = JellyfinLibraryProvider(_JELLYFIN_URL)
    return _mod._provider_singleton
```

### Pattern 5: Testing Dependencies with app.dependency_overrides

**What:** Override any Depends()-callable during tests so the real implementation is never called.

**When to use:** For auth dependencies in route tests — inject a fake `AuthUser` without a real DB vault lookup.

**Example:**
```python
# Source: https://github.com/fastapi/fastapi/blob/master/docs/en/docs/advanced/testing-dependencies.md
from fastapi.testclient import TestClient
from jellyswipe.dependencies import require_auth, AuthUser

def override_require_auth(request: Request) -> AuthUser:
    return AuthUser(jf_token="test-token", user_id="test-user")

app.dependency_overrides[require_auth] = override_require_auth
client = TestClient(app)
# After test: app.dependency_overrides = {}
```

### Anti-Patterns to Avoid

- **Importing Flask in test fixtures for auth.py:** `test_auth.py` currently uses `Flask()` as the test app. Phase 32 replaces this with `FastAPI()` + `TestClient`. Never re-introduce Flask imports. [VERIFIED: `flask` is not in pyproject.toml dependencies]
- **Using `get_db()` as a context manager:** `get_db()` is NOT a contextmanager — it returns a raw connection. The `with get_db() as conn:` pattern uses SQLite's native transaction protocol but never closes the connection (CR-01). Always use `get_db_closing()` in new code.
- **Defining `AuthUser` in `auth.py`:** `AuthUser` is a FastAPI DI concept (it wraps the return of `get_current_token()`). It belongs in `dependencies.py`, not `auth.py`, per the CONTEXT.md Specific Ideas section.
- **Closure-captured globals in `get_provider()`:** The current `get_provider()` is a nested function inside `create_app()` that captures `JELLYFIN_URL` via closure. The new version in `dependencies.py` must access `_JELLYFIN_URL` from the module level of `__init__.py` — not re-read from `os.getenv()` (which would bypass SSRF validation per WR-06).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Auth guard | Custom decorator/middleware | `Depends(require_auth)` | FastAPI resolves Depends before the handler runs; clean 401 path without decorator boilerplate |
| DB connection cleanup | Manual try/finally in route | `yield` dependency wrapping `get_db_closing()` | yield deps cleanup even on exception; consistent with FastAPI lifecycle |
| Dependency sharing across routes | Repeated inline Depends | `Annotated[T, Depends(fn)]` type alias | DRY; type checkers understand the alias |
| Test auth injection | Patching internals | `app.dependency_overrides[require_auth]` | Official FastAPI override mechanism; cleaner and faster than mock patching |

**Key insight:** The entire point of FastAPI's DI system is that guards, resources, and services compose cleanly without decorators, thread-locals (`flask.g`), or per-handler boilerplate.

---

## Common Pitfalls

### Pitfall 1: Circular Import Between `dependencies.py` and `__init__.py`

**What goes wrong:** `dependencies.py` is inside the `jellyswipe` package. If it does `from jellyswipe import _provider_singleton` at module load time, Python may try to re-execute `jellyswipe/__init__.py` while it is still being initialized, causing an `ImportError` or `AttributeError`.

**Why it happens:** The `jellyswipe` package init (`__init__.py`) imports `from jellyswipe.auth import ...` at the top, and if `dependencies.py` is imported during `__init__.py` execution, you get a circular import cycle.

**How to avoid:** Use a lazy import inside the `get_provider()` function body:
```python
def get_provider():
    import jellyswipe as _app
    # now _app._provider_singleton is safely accessible
    ...
```
Or access `_provider_singleton` through the module object rather than a direct name import.

**Warning signs:** `ImportError: cannot import name '_provider_singleton' from partially initialized module 'jellyswipe'`

### Pitfall 2: `_RATE_LIMITS` Keys Are URL Path Fragments, Not Route Names

**What goes wrong:** The existing `_RATE_LIMITS` dict in `__init__.py` uses keys like `'get-trailer'`, `'cast'`, `'watchlist/add'`, `'proxy'`. These are NOT full URL paths (`/get-trailer/123`). When `check_rate_limit()` does `request.url.path`, it gets `/get-trailer/abc123` — not `get-trailer`.

**Why it happens:** The current `_check_rate_limit(endpoint, req)` is called with an explicit string argument (e.g., `_check_rate_limit('get-trailer', request)`). The path inference approach needs to map from the full path to the key.

**How to avoid:** Use a prefix-match or contains-check, not an exact match:
```python
def _infer_rate_limit_key(path: str) -> Optional[str]:
    for key in _RATE_LIMITS:
        if key in path:
            return key
    return None
```
Or restructure `_RATE_LIMITS` to use path prefixes as keys. Confirm the exact mapping against the route paths in `__init__.py` before implementing.

**Warning signs:** All requests pass through without rate limiting even for known endpoints.

### Pitfall 3: `test_auth.py` Uses Flask App Fixtures — All 10 Tests Currently Error

**What goes wrong:** `test_auth.py` constructs a `Flask()` test app with routes like `/test-create-session`, `/test-get-current-token`, `/test-protected`, and uses `client.session_transaction()`. Flask is not installed in the uv venv, so all 10 tests fail with `ModuleNotFoundError: no module named 'flask'`.

**Why it happens:** `test_auth.py` was written before Phase 31 de-Flaskified `auth.py`. The tests predate the migration.

**How to avoid:** Rewrite the `auth_app` fixture in `test_auth.py` to use `FastAPI()` + `TestClient`. For session manipulation (the `session_transaction()` equivalent), use `TestClient(app, cookies={"session": <encoded_value>})` or set up vault entries directly via DB then rely on the session cookie. Key: FastAPI's `TestClient` uses `httpx` internally and does NOT have a `session_transaction()` method.

**Warning signs:** Any import of `flask` in `test_auth.py` will fail immediately in the current venv.

### Pitfall 4: `session_transaction()` Pattern Does Not Exist in FastAPI's TestClient

**What goes wrong:** The existing tests call `client.session_transaction() as sess: sess['session_id'] = sid` to set session state. FastAPI's `TestClient` (based on `httpx`) has no such method.

**Why it happens:** Flask's `FlaskClient` provides `session_transaction()` as a special context manager. `httpx`/`TestClient` doesn't.

**How to avoid:** For auth tests that need a session, there are two viable approaches:
1. **Direct vault seeding + signed cookie:** Insert a vault row directly via `db.get_db_closing()`, then construct a signed session cookie using `itsdangerous` (the same library `SessionMiddleware` uses) and pass it in `TestClient(app, cookies={"session": encoded})`.
2. **`app.dependency_overrides[require_auth]`:** For route-level tests, override the dependency entirely. For unit tests of `auth.py` functions, call them directly with a dict argument (since `auth.get_current_token(session_dict)` now accepts a plain dict, not `flask.session`).

The second approach (dependency_overrides) is simpler for any test that needs to test a route with auth. Direct `auth.py` function tests (create_session, get_current_token, destroy_session) should call the functions directly with a `{}` dict and a patched DB.

**Warning signs:** `AttributeError: 'TestClient' object has no attribute 'session_transaction'`

### Pitfall 5: `get_db_dep()` Is a Generator Function — Must NOT Call `next()` Manually

**What goes wrong:** Attempting to call `conn = get_db_dep()` directly (instead of via `Depends()`) returns a generator object, not a connection. Test code that tries to use `get_db_dep()` directly will get a generator, not a `sqlite3.Connection`.

**How to avoid:** In tests, mock `get_db_dep` via `app.dependency_overrides` or use the underlying `get_db_closing()` contextmanager directly. Never call a yield dependency outside FastAPI's DI system.

---

## Code Examples

Verified patterns from official sources:

### `AuthUser` Dataclass and `require_auth`

```python
# Source: FastAPI official docs — dependencies/index.md, using-request-directly.md
from dataclasses import dataclass
from fastapi import Depends, HTTPException, Request
import jellyswipe.auth as auth

@dataclass
class AuthUser:
    jf_token: str
    user_id: str

def require_auth(request: Request) -> AuthUser:
    result = auth.get_current_token(request.session)
    if result is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    jf_token, user_id = result
    return AuthUser(jf_token=jf_token, user_id=user_id)
```

### `get_db_dep()` Yield Dependency + `DBConn` Type Alias

```python
# Source: FastAPI official docs — dependencies-with-yield.md, dependencies/index.md
import sqlite3
from typing import Annotated
from fastapi import Depends
from jellyswipe.db import get_db_closing

def get_db_dep():
    with get_db_closing() as conn:
        yield conn

DBConn = Annotated[sqlite3.Connection, Depends(get_db_dep)]

# Route usage:
def some_route(conn: DBConn):
    row = conn.execute("SELECT 1").fetchone()
```

### `check_rate_limit()` Path Inference

```python
# Source: pattern synthesized from __init__.py _check_rate_limit() and CONTEXT.md D-06/D-07
from typing import Optional
from fastapi import Depends, HTTPException, Request
from jellyswipe.rate_limiter import rate_limiter as _rate_limiter

_RATE_LIMITS = {
    'get-trailer': 200,
    'cast': 200,
    'watchlist/add': 300,
    'proxy': 200,
}

def _infer_endpoint_key(path: str) -> Optional[str]:
    for key in _RATE_LIMITS:
        if key in path:
            return key
    return None

def check_rate_limit(request: Request) -> None:
    key = _infer_endpoint_key(request.url.path)
    if key is None:
        return  # no limit for this path
    ip = request.client.host if request.client else "unknown"
    allowed, retry_after = _rate_limiter.check(key, ip, _RATE_LIMITS[key])
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
```

### `destroy_session_dep()`

```python
# Source: CONTEXT.md D-03; wraps auth.destroy_session()
from fastapi import Request
import jellyswipe.auth as auth

def destroy_session_dep(request: Request) -> None:
    auth.destroy_session(request.session)
```

### Minimal FastAPI Test App for `test_auth.py`

```python
# Source: FastAPI official docs — testing.md; TestClient with SessionMiddleware
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

def make_test_app():
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret-key")

    @app.post("/test-create-session")
    def create_session_route(request: Request):
        import json
        body = ...  # parse request body
        sid = jellyswipe.auth.create_session(body["jf_token"], body["jf_user_id"], request.session)
        return {"session_id": sid}

    return app

# Session reading in tests — use TestClient cookies, not session_transaction()
# To seed a session: construct a signed cookie using itsdangerous (same as SessionMiddleware)
# Or: seed the vault directly via DB, set cookie via client.cookies
```

### `app.dependency_overrides` Pattern for Route Tests

```python
# Source: FastAPI official docs — testing-dependencies.md
from fastapi.testclient import TestClient
from jellyswipe.dependencies import require_auth, AuthUser
from jellyswipe import create_app

def test_authenticated_route(monkeypatch, tmp_path):
    app = create_app(test_config={"DB_PATH": str(tmp_path / "test.db")})

    def fake_require_auth(request: Request) -> AuthUser:
        return AuthUser(jf_token="test-token", user_id="test-user")

    app.dependency_overrides[require_auth] = fake_require_auth
    client = TestClient(app)
    response = client.get("/some-auth-required-route")
    # assert...
    app.dependency_overrides = {}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@login_required` Flask decorator | `Depends(require_auth)` FastAPI callable | Phase 31→32 | Routes declare auth via type annotation; no decorator stack |
| `flask.session` (thread-local proxy) | `request.session` (Starlette dict per request) | Phase 31 | No global session proxy; must pass `request.session` explicitly |
| `flask.g.jf_token` (thread-local) | `auth: AuthUser = Depends(require_auth)` | Phase 32 | Values injected as parameters; no thread-local state |
| `with get_db() as conn:` (leaks connection) | `conn: DBConn` via yield dependency | Phase 32 (new routes) | Connection guaranteed closed on response exit |
| `_check_rate_limit("endpoint", request)` inline | `Depends(check_rate_limit)` with path inference | Phase 32 | Rate limit applied declaratively; endpoint string not repeated |

**Deprecated/outdated:**
- `_require_login()` (Phase 31 bridge in `__init__.py` line ~285): Replaced by `require_auth` in `dependencies.py`; `_require_login()` stays in `__init__.py` until Phase 33 extraction
- `flask.session`, `flask.g`: Removed in Phase 31; zero Flask imports should remain in all new code

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `_RATE_LIMITS` dict will be copied or referenced in `dependencies.py` rather than importing from `__init__.py` — which could create a circular import | Code Examples (check_rate_limit) | `_RATE_LIMITS` is defined at module level in `__init__.py`; importing it from `dependencies.py` may trigger a circular import. Planner should verify: either duplicate the dict in `dependencies.py`, or extract it to a separate `config.py` module. | [ASSUMED]
| A2 | The `itsdangerous` `URLSafeTimedSerializer` is the correct approach for constructing session cookies in tests that need to verify session state | Test patterns | If the SessionMiddleware uses a different cookie format, hand-constructed cookies won't be accepted. Alternative: use `app.dependency_overrides` for all auth tests instead of cookie manipulation. | [ASSUMED]

---

## Open Questions

1. **`_RATE_LIMITS` placement — `dependencies.py` vs `__init__.py`**
   - What we know: `_RATE_LIMITS` is currently defined in `__init__.py` module scope. `dependencies.py` needs it to implement `check_rate_limit()`.
   - What's unclear: Does `dependencies.py` import from `__init__.py` (circular risk) or duplicate the dict?
   - Recommendation: Duplicate the dict into `dependencies.py` in Phase 32. Phase 33 router extraction can move it to a `config.py` or constants module.

2. **`_JELLYFIN_URL` access in `get_provider()`**
   - What we know: `get_provider()` must construct a `JellyfinLibraryProvider(_JELLYFIN_URL)` when the singleton is None. `_JELLYFIN_URL` is set at module level in `__init__.py` after SSRF validation.
   - What's unclear: How to access `_JELLYFIN_URL` from `dependencies.py` without a circular import.
   - Recommendation: Use a lazy import inside `get_provider()` body (`import jellyswipe as _mod; url = _mod._JELLYFIN_URL`). This reads the already-validated URL without triggering module re-init.

---

## Environment Availability

Step 2.6: Environment availability for this phase is code/config-only. No new external tools, services, or runtimes are required. All dependencies (FastAPI, httpx, pytest, starlette) are verified installed in the uv venv.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| fastapi | `dependencies.py`, test app | ✓ | 0.128.0 | — |
| httpx | `TestClient` | ✓ | 0.28.1 (dev dep) | — |
| pytest | Test runner | ✓ | 9.0.3 | — |
| starlette | `SessionMiddleware` in test app | ✓ | (fastapi dep) | — |
| flask | (legacy test fixtures) | ✗ | — | Replace with FastAPI TestClient — this is the work of Phase 32 |

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `uv run python -m pytest tests/test_auth.py -x -q` |
| Full suite command | `uv run python -m pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ARCH-03 | `require_auth()` raises 401 when no session | unit | `uv run python -m pytest tests/test_auth.py::TestRequireAuth -x` | ❌ Wave 0 (existing tests are Flask-based, must be rewritten) |
| ARCH-03 | `require_auth()` returns `AuthUser` with correct fields when session is valid | unit | `uv run python -m pytest tests/test_auth.py::TestRequireAuth -x` | ❌ Wave 0 |
| ARCH-03 | `get_db_dep()` yields a `sqlite3.Connection` and closes on exit | unit | `uv run python -m pytest tests/test_auth.py::TestGetDbDep -x` | ❌ Wave 0 |
| ARCH-03 | `check_rate_limit()` raises 429 when limit exceeded | unit | `uv run python -m pytest tests/test_auth.py::TestCheckRateLimit -x` | ❌ Wave 0 |
| ARCH-03 | `check_rate_limit()` passes through paths not in `_RATE_LIMITS` | unit | `uv run python -m pytest tests/test_auth.py::TestCheckRateLimit -x` | ❌ Wave 0 |
| ARCH-03 | `destroy_session_dep()` calls `auth.destroy_session(request.session)` | unit | `uv run python -m pytest tests/test_auth.py::TestDestroySessionDep -x` | ❌ Wave 0 |
| ARCH-03 | `create_session()` / `get_current_token()` / `destroy_session()` tests pass without Flask | unit | `uv run python -m pytest tests/test_auth.py -x` | ❌ Wave 0 (rewrite needed) |

### Sampling Rate

- **Per task commit:** `uv run python -m pytest tests/test_auth.py -x -q`
- **Per wave merge:** `uv run python -m pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_auth.py` — entire file must be rewritten; remove Flask fixtures, replace with FastAPI `TestClient` app; cover `TestCreateSession`, `TestGetCurrentToken`, `TestRequireAuth`, `TestGetDbDep`, `TestCheckRateLimit`, `TestDestroySessionDep`
- [ ] `tests/conftest.py` — `client` fixture returns `app.test_client()` (Flask); Phase 32 should update the shared `client` fixture to use `TestClient(app)` from FastAPI (or create a `dependencies_client` fixture in `test_auth.py` that is local to that file)

Note: The conftest `app` fixture already calls `create_app()` which returns a FastAPI instance. The `client` fixture calls `app.test_client()` which does NOT exist on FastAPI (confirmed: `AttributeError: 'FastAPI' object has no attribute 'test_client'`). All route tests that use the shared `client` fixture are currently failing. Phase 32 scope is `test_auth.py` specifically; the conftest `client` fixture is a blocker that likely also needs fixing in this phase or was meant for Phase 35 (TST-01). The safe approach: add a FastAPI `TestClient` fixture to `test_auth.py` locally without touching conftest (Phase 35 handles the full conftest migration).

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | `require_auth()` Depends() — raises 401 on missing/invalid session |
| V3 Session Management | yes | Starlette `SessionMiddleware` (already wired in Phase 31); `destroy_session_dep()` clears vault + session cookie |
| V4 Access Control | yes | `require_auth()` must be declared on every protected route; Phase 33 applies it |
| V5 Input Validation | partial | `request.url.path` used as rate limit key — no user-controlled injection risk since paths are matched against a fixed dict |
| V6 Cryptography | no | Session signing handled by `itsdangerous` via `SessionMiddleware` — not hand-rolled |

### Known Threat Patterns for FastAPI DI Auth

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Unauthenticated access to protected route | Elevation of Privilege | `Depends(require_auth)` on every route that requires auth |
| Session fixation | Spoofing | `create_session()` generates fresh `secrets.token_hex(32)` session_id on every login |
| Token exfiltration via response leakage | Information Disclosure | `AuthUser.jf_token` must not appear in response bodies — routes read it for upstream calls, not for returning to client |
| Rate limit bypass via path manipulation | Denial of Service | `_infer_endpoint_key()` uses substring match; verify all known rate-limited paths are correctly matched |

---

## Sources

### Primary (HIGH confidence)
- `/fastapi/fastapi` (Context7) — `Depends()`, `Annotated` type alias, yield dependencies, `TestClient`, `app.dependency_overrides`, `Request.session`, `HTTPException`
- `jellyswipe/auth.py` [VERIFIED: read in session] — confirms no Flask imports remain; `get_current_token(session_dict)` accepts plain dict
- `jellyswipe/db.py` [VERIFIED: read in session] — confirms `get_db_closing()` is a `@contextmanager` that closes the connection
- `jellyswipe/rate_limiter.py` [VERIFIED: read in session] — confirms `rate_limiter.check(endpoint, ip, limit)` interface
- `jellyswipe/__init__.py` lines 28-33, 235-258, 285-297 [VERIFIED: read in session] — confirms `_RATE_LIMITS` dict, `get_provider()` closure, `_require_login()` bridge
- `tests/test_auth.py` [VERIFIED: read in session] — confirms all 10 tests use Flask fixtures and fail with `ModuleNotFoundError: no module named 'flask'`
- `tests/conftest.py` [VERIFIED: read in session] — confirms `client` fixture uses `app.test_client()` (Flask API; broken for FastAPI)

### Secondary (MEDIUM confidence)
- `uv run python -m pytest tests/test_auth.py -v` output [VERIFIED: run in session] — confirms all 10 auth tests error on `ModuleNotFoundError: no module named 'flask'`
- `uv run python -m pytest tests/ -q --ignore=tests/test_auth.py` [VERIFIED: run in session] — 117 passing, 3 failing (pre-existing), 178 errors (all from `app.test_client()` not existing on FastAPI)

### Tertiary (LOW confidence)
- None — all key claims verified directly from codebase or official docs.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified from running uv venv and Context7 FastAPI docs
- Architecture: HIGH — read all source files directly; patterns confirmed against official docs
- Pitfalls: HIGH — verified by running tests and observing actual errors
- Test rewrite approach: MEDIUM — `session_transaction()` replacement strategy relies on [ASSUMED] itsdangerous cookie format detail (A2 above)

**Research date:** 2026-05-02
**Valid until:** 2026-06-01 (FastAPI 0.128.0 is stable; no fast-moving API changes expected in this area)
