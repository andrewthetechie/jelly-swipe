# Architecture Research: Flask → FastAPI MVC Migration (v2.0)

**Domain:** Flask monolith → FastAPI router/model/dependency split
**Researched:** 2026-05-01
**Overall confidence:** HIGH — based on direct codebase analysis + Context7-verified FastAPI docs

---

## Current Architecture

### Source Layout

```
jellyswipe/
  __init__.py         839-line Flask monolith — create_app() + all routes as closures
  auth.py             Session vault CRUD + @login_required (Flask-specific)
  db.py               SQLite layer — get_db(), init_db(), cleanup_expired_tokens()
  jellyfin_library.py JellyfinLibraryProvider (framework-agnostic, no Flask imports)
  base.py             LibraryMediaProvider ABC (framework-agnostic)
  http_client.py      Outbound HTTP helper (framework-agnostic)
  rate_limiter.py     In-memory token-bucket (framework-agnostic)
  ssrf_validator.py   Boot-time URL validator (framework-agnostic)
  templates/          index.html (SPA shell)
  static/             app.js, sw.js, styles.css

tests/
  conftest.py         app + client fixtures (Flask create_app + test_client)
  test_routes_*.py    Route tests via Flask test client
  test_db.py          DB tests (framework-agnostic)
  test_jellyfin_library.py  Provider tests (framework-agnostic)
  ...
```

### What Needs to Change vs What Doesn't

**Framework-agnostic already — keep as-is:**
- `jellyswipe/db.py` — pure Python, no Flask imports; `get_db()` returns a `sqlite3.Connection`
- `jellyswipe/jellyfin_library.py` — pure Python, uses `requests.Session`; no Flask context anywhere
- `jellyswipe/base.py` — ABC only
- `jellyswipe/http_client.py` — pure `requests` wrapper
- `jellyswipe/rate_limiter.py` — pure Python threading
- `jellyswipe/ssrf_validator.py` — pure Python

**Flask-coupled — must be rewritten:**
- `jellyswipe/__init__.py` — imports `flask`, `flask.g`, `flask.session`, `flask.request`, `flask.Response`, `flask.jsonify`, `werkzeug.middleware.proxy_fix.ProxyFix`
- `jellyswipe/auth.py` — imports `flask.session`, `flask.g`, `flask.jsonify`; `@login_required` uses Flask `g`
- `tests/conftest.py` — the `app` and `client` fixtures call `create_app()` and `app.test_client()`
- `tests/test_routes_*.py` — use Flask test client `.get()/.post()` with `session_transaction()`

### Route Inventory (all currently in `__init__.py`)

| Route | Method | Auth | Group |
|-------|--------|------|-------|
| `/` | GET | No | static |
| `/auth/provider` | GET | No | auth |
| `/auth/jellyfin-use-server-identity` | POST | No | auth |
| `/auth/jellyfin-login` | POST | No | auth |
| `/auth/logout` | POST | Yes | auth |
| `/me` | GET | Yes | auth |
| `/jellyfin/server-info` | GET | No | auth |
| `/plex/server-info` | GET | No | auth (legacy, exists in code) |
| `/room` | POST | Yes | rooms |
| `/room/solo` | POST | Yes | rooms |
| `/room/<code>/join` | POST | Yes | rooms |
| `/room/<code>/status` | GET | No | rooms |
| `/room/<code>/stream` | GET | No | rooms (SSE) |
| `/room/<code>/deck` | GET | Yes | rooms |
| `/room/<code>/genre` | POST | Yes | rooms |
| `/room/<code>/swipe` | POST | Yes | rooms |
| `/room/<code>/undo` | POST | Yes | rooms |
| `/room/<code>/quit` | POST | Yes | rooms |
| `/matches` | GET | Yes | rooms |
| `/matches/delete` | POST | Yes | rooms |
| `/get-trailer/<movie_id>` | GET | No | media |
| `/cast/<movie_id>` | GET | No | media |
| `/watchlist/add` | POST | Yes | media |
| `/genres` | GET | No | media |
| `/proxy` | GET | No | proxy |
| `/manifest.json` | GET | No | static |
| `/sw.js` | GET | No | static |
| `/static/<path>` | GET | No | static |
| `/favicon.ico` | GET | No | static |

### Key Closures Inside `create_app()`

The current monolith captures shared state as closure variables inside `create_app()`. Every route handler closes over:
- `get_provider()` — returns `_provider_singleton` (global)
- `TMDB_AUTH_HEADERS` — dict built from config
- `JELLYFIN_URL` — string from config
- `get_db` / `get_db_closing` — from `jellyswipe.db`
- `make_error_response()` — local helper
- `log_exception()` — local helper
- `get_request_id()` — local helper

In FastAPI, these become either `Depends()` dependencies or module-level constants.

---

## Target Architecture

### Directory Structure

```
jellyswipe/
  __init__.py             Thin app factory — create_app() only (~50 lines)
  app.py                  (optional) — module-level `app = create_app()` for Uvicorn entry
  dependencies.py         Shared FastAPI Depends() callables
  models/
    __init__.py
    auth.py               Pydantic models: LoginRequest, AuthResponse, etc.
    rooms.py              SwipeRequest, RoomResponse, MatchResponse, etc.
    media.py              GenreList, TrailerResponse, CastResponse, etc.
  routers/
    __init__.py
    auth.py               /auth/*, /me, /jellyfin/server-info
    rooms.py              /room/*, /matches
    media.py              /get-trailer/*, /cast/*, /watchlist/add, /genres
    proxy.py              /proxy
    static.py             /, /manifest.json, /sw.js, /static/*, /favicon.ico
  db.py                   UNCHANGED
  jellyfin_library.py     UNCHANGED
  base.py                 UNCHANGED
  http_client.py          UNCHANGED
  rate_limiter.py         UNCHANGED
  ssrf_validator.py       UNCHANGED
  auth.py                 REWRITTEN (remove Flask session/g, use Request.state and starlette session)
  templates/              UNCHANGED
  static/                 UNCHANGED
```

### App Factory (`jellyswipe/__init__.py` after migration)

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .routers import auth, rooms, media, proxy, static as static_router
from .db import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

def create_app(test_config: dict | None = None) -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    app.add_middleware(SessionMiddleware, secret_key=os.environ["SECRET_KEY"],
                       same_site="lax", https_only=False)
    # ProxyFix equivalent: use ProxyHeadersMiddleware from uvicorn or starlette
    app.include_router(auth.router)
    app.include_router(rooms.router)
    app.include_router(media.router)
    app.include_router(proxy.router)
    app.include_router(static_router.router)
    return app
```

---

## Integration Points

### 1. `jellyswipe/db.py` — Zero Changes Required

`db.py` has no Flask imports. All functions (`get_db`, `get_db_closing`, `init_db`, `cleanup_expired_tokens`) are pure Python context managers returning `sqlite3.Connection`.

**Integration in FastAPI:** Wrap `get_db()` as a FastAPI dependency in `dependencies.py`:

```python
# jellyswipe/dependencies.py
from contextlib import contextmanager
from jellyswipe.db import get_db as _get_db

def get_db_dep():
    """FastAPI dependency for a short-lived DB connection (route handlers)."""
    conn = _get_db()
    try:
        with conn:
            yield conn
    finally:
        conn.close()
```

The SSE stream (`/room/<code>/stream`) must NOT use `get_db_dep()` — it needs the same persistent-connection pattern as the current code (direct `sqlite3.connect()`). This is unchanged.

`init_db()` moves into the FastAPI `lifespan` async context manager (replaces Flask's inline `init_db()` call in `create_app()`).

### 2. `jellyswipe/jellyfin_library.py` — Zero Changes Required

`JellyfinLibraryProvider` is entirely framework-agnostic. It uses `requests.Session` internally.

**Integration in FastAPI:** The provider singleton pattern moves to `dependencies.py`:

```python
# jellyswipe/dependencies.py
from jellyswipe.jellyfin_library import JellyfinLibraryProvider

_provider_singleton: JellyfinLibraryProvider | None = None

def get_provider() -> JellyfinLibraryProvider:
    global _provider_singleton
    if _provider_singleton is None:
        _provider_singleton = JellyfinLibraryProvider(os.getenv("JELLYFIN_URL", ""))
    return _provider_singleton
```

**For testing:** Replace with `app.dependency_overrides[get_provider] = lambda: FakeProvider()`. This is cleaner than the current `monkeypatch.setattr(jellyswipe_module, "_provider_singleton", ...)`.

### 3. `jellyswipe/auth.py` — Rewrite Required

Current `auth.py` imports `flask.session`, `flask.g`, `flask.jsonify`. All three must go.

**Migration mapping:**

| Flask | FastAPI equivalent |
|-------|-------------------|
| `from flask import session` | `from starlette.requests import Request; request.session` |
| `from flask import g; g.user_id` | Inject via `Depends()` — dependency returns `(jf_token, user_id)` tuple |
| `from flask import jsonify` | Remove — routers return Pydantic models directly |
| `@login_required` decorator | Replace with `Depends(get_current_user)` dependency |

**New `auth.py` shape:**

```python
# jellyswipe/auth.py (FastAPI version)
from fastapi import Depends, HTTPException, Request
from jellyswipe.db import get_db, cleanup_expired_tokens
import secrets
from datetime import datetime, timezone

def create_session(request: Request, jf_token: str, jf_user_id: str) -> str:
    """Store token in vault, set session cookie."""
    session_id = secrets.token_hex(32)
    cleanup_expired_tokens()
    with get_db() as conn:
        conn.execute(
            'INSERT INTO user_tokens (session_id, jellyfin_token, jellyfin_user_id, created_at) '
            'VALUES (?, ?, ?, ?)',
            (session_id, jf_token, jf_user_id, datetime.now(timezone.utc).isoformat())
        )
    request.session['session_id'] = session_id
    return session_id

def get_current_token(request: Request) -> tuple[str, str] | None:
    """Return (jf_token, jf_user_id) for current session, or None."""
    sid = request.session.get('session_id')
    if not sid:
        return None
    with get_db() as conn:
        row = conn.execute(
            'SELECT jellyfin_token, jellyfin_user_id FROM user_tokens WHERE session_id = ?',
            (sid,)
        ).fetchone()
    if not row:
        return None
    return (row['jellyfin_token'], row['jellyfin_user_id'])

def destroy_session(request: Request) -> None:
    """Clear session cookie and delete vault entry."""
    sid = request.session.get('session_id')
    if sid:
        with get_db() as conn:
            conn.execute('DELETE FROM user_tokens WHERE session_id = ?', (sid,))
        request.session.pop('session_id', None)

# Dependency — replaces @login_required
def require_auth(request: Request) -> tuple[str, str]:
    """FastAPI dependency: requires authenticated session. Returns (jf_token, user_id)."""
    result = get_current_token(request)
    if not result:
        raise HTTPException(status_code=401, detail="Authentication required")
    return result
```

**In routers:** Route handlers declare `Depends(require_auth)` instead of `@login_required`:

```python
# jellyswipe/routers/rooms.py
from fastapi import APIRouter, Depends, Request
from jellyswipe.auth import require_auth

router = APIRouter()

@router.post("/room")
def create_room(
    request: Request,
    auth: tuple = Depends(require_auth),
):
    jf_token, user_id = auth
    ...
```

### 4. Rate Limiter — Adapt for FastAPI Request Object

`rate_limiter.py` is framework-agnostic. It needs `endpoint` name and `client_ip`.

**Current Flask usage:** `_rate_limiter.check(endpoint, request.remote_addr, limit)`

**FastAPI equivalent:** Create a rate-limit dependency in `dependencies.py`:

```python
from fastapi import Request, HTTPException
from jellyswipe.rate_limiter import rate_limiter as _rate_limiter

def check_rate_limit(endpoint: str, limit: int):
    def _check(request: Request):
        client_ip = request.client.host if request.client else "unknown"
        allowed, retry_after = _rate_limiter.check(endpoint, client_ip, limit)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(int(retry_after) + 1)}
            )
    return _check
```

Usage in routers:
```python
@router.get("/proxy", dependencies=[Depends(check_rate_limit("proxy", 200))])
def proxy(...):
    ...
```

### 5. SSE Stream — Async Generator with `StreamingResponse`

The SSE generator is the most complex migration. The current implementation:
- Uses `gevent.sleep` or `time.sleep` for cooperative yield
- Opens a persistent `sqlite3.connect()` directly (bypasses `get_db()`)
- Accesses `jellyswipe.db.DB_PATH` directly
- Returns Flask `Response(generate(), mimetype='text/event-stream')`

**FastAPI equivalent** uses `StreamingResponse` with an async generator. Under Uvicorn (asyncio), `asyncio.sleep` replaces `gevent.sleep`. The SQLite access pattern remains synchronous — `sqlite3` is a blocking C extension. Under asyncio, blocking DB calls should run in a threadpool via `run_in_executor`, but for Jelly Swipe's scale (10s of concurrent users) and the existing WAL mode, synchronous calls in an async route will work correctly — they block only one task for ~1ms per poll, not the entire event loop (asyncio handles this via threadpool offloading when using `loop.run_in_executor`).

**Recommended SSE approach:**

```python
# jellyswipe/routers/rooms.py
import asyncio
import json
import random
import sqlite3
import time
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import jellyswipe.db

router = APIRouter()

@router.get("/room/{code}/stream")
async def room_stream(code: str):
    async def generate():
        last_genre = None
        last_ready = None
        last_match_ts = None
        POLL = 1.5
        TIMEOUT = 3600
        last_event_time = time.time()

        conn = sqlite3.connect(jellyswipe.db.DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            deadline = time.time() + TIMEOUT
            while time.time() < deadline:
                row = conn.execute(
                    'SELECT ready, current_genre, solo_mode, last_match_data '
                    'FROM rooms WHERE pairing_code = ?', (code,)
                ).fetchone()

                if row is None:
                    yield f"data: {json.dumps({'closed': True})}\n\n"
                    return

                # ... same state-diff logic as current ...
                await asyncio.sleep(POLL + random.uniform(0, 0.5))
        finally:
            conn.close()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
```

Key difference: `await asyncio.sleep(...)` replaces `gevent.sleep() / time.sleep()`. No other logic changes.

### 6. Session Management — Starlette `SessionMiddleware`

**Flask:** `flask.session` is an implicit thread-local accessible anywhere.

**FastAPI/Starlette:** `request.session` is explicit — passed in as a `Request` parameter.

`SessionMiddleware` from Starlette provides the same signed cookie session semantics as Flask's default session. Configuration:

```python
from starlette.middleware.sessions import SessionMiddleware

app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ["SECRET_KEY"],
    same_site="lax",
    https_only=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
    max_age=None,  # session expires on browser close (matches current Flask behavior)
)
```

Env var rename: `FLASK_SECRET` → `SECRET_KEY` (or keep `FLASK_SECRET` and read it as `os.environ["FLASK_SECRET"]`). The existing env contract can be preserved by reading the same variable name.

### 7. CSP + Request ID Middleware

**Flask:** `@app.after_request` hooks add `Content-Security-Policy` and `X-Request-Id` headers.

**FastAPI:** Use `@app.middleware("http")` or Starlette `BaseHTTPMiddleware`:

```python
# jellyswipe/__init__.py
import secrets, time
from starlette.middleware.base import BaseHTTPMiddleware

CSP_POLICY = (
    "default-src 'self'; script-src 'self'; object-src 'none'; "
    "img-src 'self' https://image.tmdb.org; frame-src https://www.youtube.com"
)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        req_id = f"req_{int(time.time())}_{secrets.token_hex(4)}"
        request.state.request_id = req_id
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = CSP_POLICY
        response.headers["X-Request-Id"] = req_id
        return response
```

### 8. XSS-Safe JSON — FastAPI Equivalent

**Flask:** `_XSSSafeJSONProvider` overrides the JSON encoder to escape `<`, `>`, `&`.

**FastAPI:** FastAPI uses Pydantic for serialization. The cleanest equivalent is a custom `JSONResponse` subclass used as the default response class:

```python
# jellyswipe/__init__.py
import json
from fastapi.responses import JSONResponse

class XSSSafeJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return (
            json.dumps(content, ensure_ascii=False)
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("&", "\\u0026")
        ).encode("utf-8")

app = FastAPI(default_response_class=XSSSafeJSONResponse)
```

### 9. ProxyFix — Uvicorn/Starlette Equivalent

**Flask:** `ProxyFix(app.wsgi_app, x_for=1, x_proto=1, ...)` from werkzeug.

**FastAPI/Uvicorn:** Use Uvicorn's `--proxy-headers` flag (recommended) or Starlette's `ProxyHeadersMiddleware`:

```python
from starlette.middleware.trustedhost import TrustedHostMiddleware
# Or: pass --proxy-headers --forwarded-allow-ips='*' to Uvicorn CMD
```

For the Dockerfile, the simpler solution is adding `--proxy-headers` to the Uvicorn CMD. No code change needed.

### 10. SPA Template Serving

**Flask:** `render_template('index.html', media_provider="jellyfin")`

**FastAPI:** Uses `Jinja2Templates`:

```python
# jellyswipe/routers/static.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os

router = APIRouter()
_APP_ROOT = os.path.dirname(os.path.abspath(__file__ + "/.."))
templates = Jinja2Templates(directory=os.path.join(_APP_ROOT, "templates"))

@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"media_provider": "jellyfin"}
    )
```

---

## New vs Modified Files

### New Files

| File | What It Contains | Notes |
|------|-----------------|-------|
| `jellyswipe/dependencies.py` | `get_provider()`, `get_db_dep()`, `require_auth()`, `check_rate_limit()` | Central DI container |
| `jellyswipe/models/__init__.py` | Package marker | Empty |
| `jellyswipe/models/auth.py` | `LoginRequest`, `LoginResponse`, `ServerInfoResponse` | Pydantic v2 BaseModel |
| `jellyswipe/models/rooms.py` | `SwipeRequest`, `RoomStatusResponse`, `MatchResponse`, `DeckItem`, `GenreRequest` | Pydantic v2 BaseModel |
| `jellyswipe/models/media.py` | `TrailerResponse`, `CastResponse`, `WatchlistRequest` | Pydantic v2 BaseModel |
| `jellyswipe/routers/__init__.py` | Package marker | Empty |
| `jellyswipe/routers/auth.py` | All `/auth/*`, `/me`, `/jellyfin/server-info` routes | ~120 lines |
| `jellyswipe/routers/rooms.py` | All `/room/*`, `/matches` routes + SSE | ~300 lines |
| `jellyswipe/routers/media.py` | `/get-trailer/*`, `/cast/*`, `/watchlist/add`, `/genres` | ~120 lines |
| `jellyswipe/routers/proxy.py` | `/proxy` | ~50 lines |
| `jellyswipe/routers/static.py` | `/`, `/manifest.json`, `/sw.js`, `/static/*`, `/favicon.ico` | ~60 lines |

### Modified Files

| File | Change | Scope |
|------|--------|-------|
| `jellyswipe/__init__.py` | Full rewrite: Flask create_app → FastAPI create_app (~50 lines) | Replace 839 lines with ~50 |
| `jellyswipe/auth.py` | Rewrite: remove Flask imports, use `Request.session` instead of `flask.session`; replace `@login_required` decorator with `require_auth` Depends | ~40 lines |
| `jellyswipe/jellyfin_library.py` | Update device string: `Device="FlaskApp"` → `Device="FastAPI"` | 1 line |
| `tests/conftest.py` | Replace `create_app` + `test_client` with FastAPI `create_app` + `TestClient` | ~50 lines |
| `tests/test_routes_auth.py` | Swap `client.session_transaction()` → `httpx` cookies or session_state approach | Medium |
| `tests/test_routes_rooms.py` | Same session approach change | Medium |
| `tests/test_routes_sse.py` | Same + `TestClient` streaming | Medium |
| `tests/test_routes_proxy.py` | Minimal changes — request syntax same | Low |
| `Dockerfile` | Replace `gunicorn` CMD with `uvicorn` | 1 line |
| `pyproject.toml` | Replace `flask`, `gevent`, `gunicorn`, `werkzeug` with `fastapi`, `uvicorn[standard]`, `pydantic` | ~5 lines |

### Unchanged Files

| File | Reason |
|------|--------|
| `jellyswipe/db.py` | No Flask imports |
| `jellyswipe/jellyfin_library.py` | No Flask imports (except 1-line device string) |
| `jellyswipe/base.py` | No Flask imports |
| `jellyswipe/http_client.py` | No Flask imports |
| `jellyswipe/rate_limiter.py` | No Flask imports |
| `jellyswipe/ssrf_validator.py` | No Flask imports |
| `jellyswipe/templates/` | No framework dependency in HTML/JS |
| `jellyswipe/static/` | No framework dependency |
| `tests/test_db.py` | Already framework-agnostic |
| `tests/test_jellyfin_library.py` | Already framework-agnostic |
| `tests/test_auth.py` | Tests auth.py functions — needs minor update for `Request.session` mock |
| `tests/test_rate_limiter.py` | Framework-agnostic |
| `tests/test_ssrf_validator.py` | Framework-agnostic |
| `tests/test_http_client.py` | Framework-agnostic |

---

## Suggested Build Order

The migration has clear dependency layers. Each phase should leave the test suite green before proceeding.

### Phase 1: Dependency + Package Setup

**Goal:** Replace Flask/gevent/gunicorn with FastAPI/uvicorn/pydantic in pyproject.toml. Verify nothing imports yet.

**Files:**
- `pyproject.toml` — swap runtime deps
- `Dockerfile` — swap CMD
- `uv.lock` — regenerate

**Risk:** LOW. No logic changes. Tests won't run until Phase 3+ (they still import Flask routes).

**Validation:** `uv sync`, `docker build` succeeds.

### Phase 2: App Factory + Middleware Skeleton

**Goal:** Create the FastAPI `create_app()` in a new file (e.g., `jellyswipe/app.py`), leaving the old `__init__.py` intact temporarily. Wire up middleware, lifespan, and empty router includes. Move env var validation and SSRF check inside the factory.

**Files:**
- `jellyswipe/app.py` (new) — thin factory with middleware
- `jellyswipe/__init__.py` — add `from .app import create_app, app` shim (keep old code too, temporarily)

**Risk:** LOW. Factory exists but no routes yet. Old routes still importable for reference.

**Validation:** `from jellyswipe.app import create_app; create_app()` succeeds without error.

### Phase 3: `dependencies.py` + Auth Rewrite

**Goal:** Create `dependencies.py` with `get_provider()`, `get_db_dep()`, `require_auth()`, `check_rate_limit()`. Rewrite `auth.py` to remove Flask imports.

**Files:**
- `jellyswipe/dependencies.py` (new)
- `jellyswipe/auth.py` (rewrite)
- `tests/conftest.py` (update fixtures to use FastAPI TestClient)

**Why here:** `require_auth` is referenced by every authenticated router. It must exist before any router is written.

**Risk:** MEDIUM. The `auth.py` rewrite is the most Flask-coupled non-route file. Session access via `request.session` (Starlette) vs `flask.session` (thread-local) is the key conceptual shift.

**Key decision:** `create_session(request, ...)` now requires an explicit `request` parameter — this propagates into all auth route handlers. The DB-layer (`get_db`, `cleanup_expired_tokens`) is unchanged.

**Validation:** `tests/test_auth.py` and `tests/test_db.py` pass (minimal test suite at this point).

### Phase 4: Pydantic Models

**Goal:** Define all request/response Pydantic models in `jellyswipe/models/`. No route logic yet — just the data shapes.

**Files:**
- `jellyswipe/models/__init__.py`
- `jellyswipe/models/auth.py`
- `jellyswipe/models/rooms.py`
- `jellyswipe/models/media.py`

**Why here:** Models are needed by all routers. Defining them before routers avoids circular import issues.

**Risk:** LOW. No runtime impact — models are just class definitions. Can iterate.

**Validation:** `from jellyswipe.models.rooms import SwipeRequest; SwipeRequest(movie_id="abc", direction="right")` works.

### Phase 5: Non-SSE Routers (Auth, Media, Proxy, Static)

**Goal:** Migrate all non-SSE routes into domain routers. These are the straightforward routes with no streaming complexity.

**Files (in this order):**
1. `jellyswipe/routers/auth.py` — `/auth/*`, `/me`, `/jellyfin/server-info`
2. `jellyswipe/routers/media.py` — `/get-trailer/*`, `/cast/*`, `/watchlist/add`, `/genres`
3. `jellyswipe/routers/proxy.py` — `/proxy`
4. `jellyswipe/routers/static.py` — `/`, `/manifest.json`, `/sw.js`, `/static/*`, `/favicon.ico`
5. `jellyswipe/routers/__init__.py`

**Update app factory** to include these routers.

**Risk:** LOW-MEDIUM. Mostly mechanical translation from Flask route handlers to FastAPI path operations. The main friction points:
- `flask.jsonify(...)` → just return a dict or Pydantic model
- `flask.abort(403)` → `raise HTTPException(status_code=403)`
- `flask.request.json` → Pydantic model parameter
- `flask.request.args.get(...)` → `Query(...)` parameter
- `flask.g.user_id` → `Depends(require_auth)` return value

**Validation:** Route tests for auth, proxy, and media pass with FastAPI `TestClient`.

### Phase 6: Rooms Router (Non-SSE)

**Goal:** Migrate all room lifecycle routes EXCEPT `/room/<code>/stream`. This is the most logic-heavy router.

**Files:**
- `jellyswipe/routers/rooms.py` (partial — no SSE yet)

**Why separate from Phase 5:** Room routes contain the most complex business logic (swipe/match detection, deck cursors, transaction locking). Isolating them reduces blast radius.

**Risk:** MEDIUM-HIGH. The swipe handler uses a `BEGIN IMMEDIATE` transaction with manual `conn.execute('COMMIT')`. This pattern works fine with `sqlite3` — it doesn't change in FastAPI. But it's the most test-sensitive route.

**Special attention:**
- The `JELLYFIN_URL` closure variable becomes `os.getenv("JELLYFIN_URL", "")` or a config dependency
- `session.get('session_id')` in swipe → read from `request.session`
- `g.user_id` / `g.jf_token` → from `Depends(require_auth)` return tuple

**Validation:** All non-SSE room route tests pass.

### Phase 7: SSE Route Migration

**Goal:** Migrate `/room/<code>/stream` to an async FastAPI route using `StreamingResponse`.

**Files:**
- `jellyswipe/routers/rooms.py` (complete)

**Why last among routes:** SSE is the most complex route and requires async generator syntax, `asyncio.sleep`, and direct `sqlite3.connect()`. All other routes must be working before tackling this.

**Key changes from Flask:**
- `Response(generate(), mimetype='text/event-stream')` → `StreamingResponse(generate(), media_type="text/event-stream")`
- `def generate():` + `gevent.sleep()` → `async def generate():` + `await asyncio.sleep()`
- `import jellyswipe; jellyswipe._gevent_sleep` check removed — asyncio native
- Session reading: Flask SSE warning about "read session in view function not generator" applies here too — read `request.session.get('session_id')` in the route function, pass to generator if needed

**Validation:** `tests/test_routes_sse.py` passes. This requires the most test fixture adaptation because `session_transaction()` doesn't exist in FastAPI TestClient.

### Phase 8: Remove Old Flask Code + Cleanup

**Goal:** Delete the old `jellyswipe/__init__.py` Flask monolith. Finalize the thin app factory. Update `app.py` as Uvicorn entry point.

**Files:**
- `jellyswipe/__init__.py` — replace with thin `from .app import create_app, app`
- `jellyswipe/app.py` — finalize as canonical entry point
- Remove any remaining Flask/werkzeug/gevent imports project-wide

**Validation:** `uv run uvicorn jellyswipe.app:app` starts; `rg 'from flask' jellyswipe/` returns zero matches.

### Phase 9: Test Suite Migration + Coverage

**Goal:** Update all remaining test files and ensure the full 48-test suite passes on FastAPI.

**Key test migration patterns:**

| Flask TestClient | FastAPI TestClient |
|-----------------|-------------------|
| `app.test_client()` | `TestClient(app)` |
| `client.session_transaction() as sess: sess['x'] = y` | Use `dependency_overrides` to inject pre-seeded session state, or seed DB directly |
| `monkeypatch.setattr(jellyswipe_module, "_provider_singleton", fake)` | `app.dependency_overrides[get_provider] = lambda: FakeProvider()` |
| `flask_app.config["JELLYFIN_URL"] = ""` | `app.dependency_overrides[get_config] = lambda: TestConfig(...)` |
| `response.get_json()` | `response.json()` |

**Session test strategy:** The most painful migration point is tests that use `client.session_transaction()` to seed session state. FastAPI's `TestClient` (built on httpx) doesn't have this API. Two approaches:
1. **Direct vault seeding (recommended):** Tests that need an authenticated session insert a `user_tokens` row directly into the test DB and set the `session_id` cookie via `client.cookies`. This is what the current SSE and room tests already do (they call `jellyswipe.db.get_db()` directly in helpers like `_set_session()`).
2. **TestClient cookie injection:** `client = TestClient(app, cookies={"session": signed_session_value})` — requires signing the cookie with the test secret key. Complex.

**Recommendation:** Use approach 1. The existing `_set_session()` helper pattern in `test_routes_room.py` already seeds `user_tokens` directly — extend this pattern to all route tests.

**Validation:** `uv run pytest` — all 48 tests pass.

---

## Data Flow Changes

### Request ID (was Flask `request.environ`)

**Before:** `request.environ['jellyswipe.request_id'] = req_id`

**After:** `request.state.request_id = req_id` in `SecurityHeadersMiddleware`. Routers that need the request ID read `request.state.request_id`.

### User Identity (was Flask `flask.g`)

**Before:** `@login_required` sets `g.user_id` and `g.jf_token`; routes read `g.user_id`.

**After:** `Depends(require_auth)` returns `(jf_token, user_id)` tuple; routes destructure it:
```python
@router.post("/room")
def create_room(auth: Annotated[tuple, Depends(require_auth)]):
    jf_token, user_id = auth
```

### Provider Access (was module-level closure)

**Before:** `get_provider()` was a closure inside `create_app()`, closing over `app.config['JELLYFIN_URL']`.

**After:** `get_provider()` in `dependencies.py` reads directly from `os.getenv("JELLYFIN_URL")`. Env var is validated at factory startup (not module import time).

### Configuration (was `app.config` dict)

**Before:** Route handlers accessed `app.config['JELLYFIN_URL']`, `app.config['TMDB_ACCESS_TOKEN']` through closure.

**After:** These become module-level constants in `dependencies.py` or a `Config` class. TMDB auth headers built once:
```python
# jellyswipe/dependencies.py
_TMDB_AUTH_HEADERS = {"Authorization": f"Bearer {os.getenv('TMDB_ACCESS_TOKEN', '')}"}

def get_tmdb_headers() -> dict:
    return _TMDB_AUTH_HEADERS
```

---

## Architecture Diagram (Target)

```
Browser (SPA — app.js)
  │  HTTP + session cookie        │ EventSource SSE
  ▼                               ▼
┌──────────────────────────────────────────────────────────────┐
│  FastAPI Application  (jellyswipe/app.py — create_app())     │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Middleware Stack                                        │  │
│  │  SessionMiddleware (Starlette — signed cookie session) │  │
│  │  SecurityHeadersMiddleware (CSP, X-Request-Id)         │  │
│  │  ProxyHeadersMiddleware (Uvicorn --proxy-headers)      │  │
│  └────────────────────────────────────────────────────────┘  │
│  ┌────────────┐ ┌────────────┐ ┌──────────┐ ┌───────────┐   │
│  │routers/    │ │routers/    │ │routers/  │ │routers/   │   │
│  │auth.py     │ │rooms.py    │ │media.py  │ │proxy.py   │   │
│  └─────┬──────┘ └─────┬──────┘ └────┬─────┘ └─────┬─────┘   │
│        └──────────────┴─────────────┴──────────────┘         │
│                            │ Depends()                        │
│  ┌─────────────────────────▼──────────────────────────────┐  │
│  │  dependencies.py                                        │  │
│  │  get_provider() · get_db_dep() · require_auth()         │  │
│  │  check_rate_limit() · get_tmdb_headers()               │  │
│  └────────┬──────────────────────┬─────────────────────────┘  │
│           │                      │                            │
│  ┌────────▼────────┐  ┌──────────▼──────────────────────┐    │
│  │ db.py           │  │ jellyfin_library.py              │    │
│  │ (UNCHANGED)     │  │ (UNCHANGED)                      │    │
│  └─────────────────┘  └─────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
         │                                 │
┌────────▼─────────┐           ┌───────────▼──────────────┐
│ SQLite           │           │ Jellyfin Server           │
│ (UNCHANGED)      │           │ (UNCHANGED)               │
└──────────────────┘           └──────────────────────────┘
```

---

## Pitfalls Specific to This Migration

### P1: `session_transaction()` Has No FastAPI Equivalent

Flask TestClient's `session_transaction()` context manager doesn't exist in FastAPI's `TestClient` (httpx-based). All tests using this pattern must migrate to direct DB vault seeding + cookie injection. The current `_set_session()` helpers in `test_routes_room.py` and `test_routes_sse.py` already use the vault-seeding approach — extend this pattern universally.

### P2: Flask `g` Is Request-Scoped Thread-Local; FastAPI Has No Equivalent

`flask.g` is a request-local proxy. FastAPI uses `request.state` for the same purpose. Code that reads `g.user_id` or `g.jf_token` must be refactored to receive these as Depends() parameters, not thread-locals.

### P3: Env Var Validation At Module Import Time Must Move Inside Factory

Current `jellyswipe/__init__.py` validates env vars and calls `validate_jellyfin_url()` at module import time (before `create_app()` is called). This works in Flask because `app = create_app()` at module bottom triggers the validation on import. In FastAPI, if the new factory is in `jellyswipe/app.py`, the validation must explicitly run inside `create_app()` or the `lifespan` handler — not at the top of the module.

### P4: SSE Tests Are the Hardest to Migrate

The existing SSE tests use `monkeypatch.setattr(time, "sleep", ...)` and `monkeypatch.setattr(time, "time", ...)` to control the generator loop. With async generators, you must patch `asyncio.sleep` instead of `time.sleep`. The `_make_time_mock()` helper needs no change (it patches `time.time()` which is still used for deadline calculations). Add `monkeypatch.setattr(asyncio, "sleep", lambda _: asyncio.coroutine(lambda: None)())` or use `AsyncMock`.

### P5: `BEGIN IMMEDIATE` Transaction in Swipe Handler

The swipe handler in `rooms.py` uses a manual `conn.execute('BEGIN IMMEDIATE')` + `conn.execute('COMMIT/ROLLBACK')`. This pattern works correctly with `sqlite3` under asyncio (it's synchronous). Do not change it to async — `sqlite3` is not asyncio-native, and `aiosqlite` is not in scope for this milestone.

### P6: Provider Singleton Injection for Tests

**Before:** `monkeypatch.setattr(jellyswipe_module, "_provider_singleton", FakeProvider())`

**After:** `app.dependency_overrides[get_provider] = lambda: FakeProvider()`

The `app.dependency_overrides` approach is cleaner and is the FastAPI-idiomatic way. However, it requires the test fixture to hold a reference to the FastAPI `app` object (not just the `TestClient`). The `conftest.py` `app` fixture must yield the `FastAPI` instance, and the `client` fixture wraps it in `TestClient`.

---

## Sources

- FastAPI docs (Context7 `/fastapi/fastapi`): `APIRouter`, `Depends`, `StreamingResponse`, `TestClient`, `dependency_overrides`, `StaticFiles`, `Jinja2Templates`, `middleware` — HIGH confidence
- Starlette docs (FastAPI uses Starlette under the hood): `SessionMiddleware`, `Request.state`, `BaseHTTPMiddleware` — HIGH confidence
- Direct codebase analysis of `jellyswipe/__init__.py` (839 lines), `jellyswipe/auth.py`, `jellyswipe/db.py`, `jellyswipe/jellyfin_library.py`, all test files — HIGH confidence
- `.planning/codebase/ARCHITECTURE.md` (2026-05-01 refresh) — HIGH confidence
