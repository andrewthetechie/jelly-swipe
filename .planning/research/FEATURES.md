# Features Research: Flask → FastAPI + MVC Migration (v2.0)

**Domain:** Framework migration — Flask WSGI to FastAPI ASGI, with MVC split
**Researched:** 2026-05-01
**Confidence:** HIGH (all patterns verified against FastAPI 0.136.1 docs via Context7)

---

## Migration Scope

This is a **framework migration**, not a product feature release. "Features" are migration
capabilities — each one is a migration task that must be complete before v2.0 ships. The
end-user experience is identical; the internal structure and runtime change entirely.

The source is a 840-line `jellyswipe/__init__.py` Flask monolith with:
- 22 route handlers spanning auth, rooms, media, proxy, and static
- `auth.py` with hard Flask imports (`flask.session`, `flask.g`, `flask.jsonify`)
- A synchronous SSE generator using `time.sleep()` and `gevent` fallback
- 130+ test functions spread across 10 test files, ~40 usages of
  `client.session_transaction()`, 100 usages of `response.get_json()`, and 15 usages of
  `response.data`

---

## Table Stakes (Must Migrate — Blocking v2.0 Ship)

Every item here is required for behavior parity. Missing any = v2.0 is not shippable.

| # | Migration Task | Requirement ID | Complexity | Notes |
|---|---------------|----------------|------------|-------|
| 1 | **FastAPI app factory replaces Flask** | FAPI-01 | LOW | `create_app()` returns `FastAPI()` instead of `Flask()`. Module-level `app = create_app()` preserved for `uvicorn jellyswipe:app`. `ProxyFix` → `ProxyHeadersMiddleware`. `app.json = _XSSSafeJSONProvider` → `@app.middleware('http')` post-processing response bodies. |
| 2 | **Uvicorn replaces Gunicorn+gevent** | FAPI-01, DEP-01 | LOW | Dockerfile CMD changes from `gunicorn -k gevent` to `uvicorn`. `gevent` import in `__init__.py` removed. `_gevent_sleep` fallback removed. `time.sleep()` is safe in Uvicorn thread pool. |
| 3 | **All HTTP endpoints retain identical paths and behavior** | FAPI-02 | MEDIUM | 22 routes must produce identical URL paths, HTTP methods, status codes, JSON shapes, and headers. All existing route tests must pass without assertion changes. |
| 4 | **SSE endpoint migrated to StreamingResponse** | FAPI-03 | MEDIUM | `Response(generate(), mimetype='text/event-stream')` → `StreamingResponse(generate(), media_type='text/event-stream')`. Synchronous generator is preserved; Uvicorn runs it in anyio thread pool. `_gevent_sleep` removed. `Cache-Control` and `X-Accel-Buffering` headers preserved via `headers=` dict on `StreamingResponse`. |
| 5 | **Session management migrated to SessionMiddleware** | FAPI-04 | MEDIUM | `flask.session` → `request.session` via Starlette `SessionMiddleware`. Env var `FLASK_SECRET` renamed to `SECRET_KEY` (or kept as `FLASK_SECRET` but read for `SessionMiddleware`). `SESSION_COOKIE_SECURE` env var continues to control cookie security. `SESSION_COOKIE_SAMESITE` preserved. `app.secret_key` → `SessionMiddleware(app, secret_key=...)`. |
| 6 | **`auth.py` de-Flaskified** | ARCH-01, ARCH-03 | MEDIUM | `auth.py` imports `from flask import session, g, jsonify`. These must become: `session` → function parameter `request: Request` with `request.session`; `g` (for `g.user_id`, `g.jf_token`) → FastAPI `Depends()` returning a `CurrentUser` object; `jsonify` → removed (FastAPI auto-serializes dicts). The `@login_required` decorator pattern becomes a `Depends(get_current_user)` dependency. |
| 7 | **Domain routers extracted from `__init__.py`** | ARCH-01 | MEDIUM | 22 routes split into 5 `APIRouter` modules: `routers/auth.py` (auth/provider, login, logout, server-identity), `routers/rooms.py` (create, join, solo, swipe, deck, genre, status, quit, undo, matches), `routers/media.py` (trailer, cast, watchlist, genres, me, jellyfin-server-info), `routers/proxy.py` (image proxy), `routers/static.py` (index, manifest, sw.js, favicon, static files). `__init__.py` becomes the thin factory that imports and mounts routers. |
| 8 | **Pydantic models for all request bodies** | ARCH-02 | LOW | Every route that reads `request.json` or `request.form` gets a Pydantic `BaseModel`. Identified request body models: `JellyfinLoginRequest`, `SwipeRequest`, `GenreRequest`, `WatchlistRequest`, `DeleteMatchRequest`, `UndoSwipeRequest`. FastAPI validates and deserializes automatically; routes receive typed model instances. |
| 9 | **Pydantic models for significant response shapes** | ARCH-02 | LOW | Response models document the API contract. Candidates: `AuthResponse`, `RoomResponse`, `DeckItemResponse`, `MatchResponse`, `RoomStatusResponse`, `MeResponse`. Optional but strongly recommended for OpenAPI documentation and type safety. |
| 10 | **`dependencies.py` extracts shared logic** | ARCH-03 | MEDIUM | Shared per-request logic moved out of route handlers: `get_db()` connection as a dependency with `yield` (auto-close), `get_current_user()` replacing `@login_required`, `get_provider()` singleton accessor, `get_request_id()` from request state. `flask.g` is eliminated; values flow through dependency injection. |
| 11 | **`__init__.py` becomes thin app factory** | ARCH-04 | LOW | After router extraction, `__init__.py` contains only: imports, env validation, `create_app()` factory (creates `FastAPI()`, adds middleware, includes routers, calls `init_db()`), and `app = create_app()`. Target: under 60 lines. |
| 12 | **TestClient replaces Flask test client** | TST-01 | HIGH | `from fastapi.testclient import TestClient` replaces `app.test_client()`. `client.get_json()` → `response.json()`. `response.data` → `response.content` (bytes) or `response.text` (str). `response.content_type` → `response.headers['content-type']`. The 40 `client.session_transaction()` usages require a new pattern (see Key Dependencies). |
| 13 | **conftest.py updated for FastAPI** | TST-01 | MEDIUM | `FLASK_SECRET` env var keeps supporting test setup but `create_app()` returns `FastAPI()`. `app` fixture wraps `TestClient(create_app(...))`. `FakeProvider` mock pattern unchanged (monkeypatching the singleton). Rate limiter reset unchanged. Token cache clear unchanged. |
| 14 | **Dockerfile CMD uses Uvicorn** | DEP-01 | LOW | Single-line change: replace `gunicorn -b 0.0.0.0:5005 -k gevent --worker-connections 1000 jellyswipe:app` with `uvicorn jellyswipe:app --host 0.0.0.0 --port 5005`. |
| 15 | **All 48 unit tests pass** | TST-01 | — | The 48 pre-existing tests in `test_db.py` and `test_jellyfin_library.py` are framework-agnostic and require no changes. Route tests require the TestClient migration in item 12 above. |

---

## Optional Enhancements (Post-v2.0, Do Not Block Ship)

These improve the migration result but are not required for behavior parity.

| Enhancement | Value | Complexity | When |
|-------------|-------|------------|------|
| **`async def` route handlers** | Lower latency under load; full asyncio coroutine | HIGH | After v2.0 ships. Requires `aiosqlite` or `asyncpg` to avoid blocking the event loop on DB calls. Do not do half-async (sync DB + async routes). |
| **`EventSourceResponse` from `fastapi.sse`** | Cleaner SSE API; automatic keep-alive pings every 15s | LOW | Optional upgrade after SSE tests pass. Native `StreamingResponse` already works. `EventSourceResponse` adds automatic `Cache-Control: no-cache` and ping interval. |
| **OpenAPI docs at `/docs`** | FastAPI generates Swagger UI automatically from Pydantic models | NONE (free) | Ships with v2.0 at no extra cost. Consider whether to disable for production via `docs_url=None` in `FastAPI()`. |
| **`pytest-anyio` for async tests** | Enables testing `async def` route handlers directly | LOW | Only needed if routes are converted to `async def`. Not needed for sync handlers tested via `TestClient`. |
| **HTML/XML coverage reports** | `pytest-cov --cov-report=html` | LOW | Deferred from v1.3 (ADV-01). Trivial to add once migration is complete. |

---

## Migration Sequence

The tasks have hard dependencies. This is the only viable linear order:

### Phase A: Infrastructure (zero route changes)
1. **Update `pyproject.toml`** — Add `fastapi`, `uvicorn[standard]`, `itsdangerous`, `jinja2`, `python-multipart`; remove `flask`, `gunicorn`, `gevent`, `werkzeug`. Add `httpx` to dev deps.
2. **Update `Dockerfile` CMD** — Swap Gunicorn for Uvicorn.
3. **Verify `uv sync` resolves cleanly** — Confirm no dependency conflicts before touching application code.

### Phase B: App Factory (touches `__init__.py`, zero route logic changes)
4. **Replace `Flask()` with `FastAPI()` in `create_app()`** — Wire `SessionMiddleware`, `ProxyHeadersMiddleware`, CSP middleware, request-ID middleware. Verify the app boots with Uvicorn.
5. **Port all 22 routes directly into the new FastAPI app** — No structure change yet; just syntax conversion (decorators, `request.json` → body param, `jsonify()` → dict return, `abort()` → `HTTPException`). Smoke test with `TestClient`.

### Phase C: `auth.py` De-Flaskification
6. **Rewrite `auth.py`** — Remove `flask.session`, `flask.g`, `flask.jsonify`. Replace with `request: Request` parameter and `request.session`. Change `@login_required` decorator to a `get_current_user()` Depends function. This is the highest-risk single-file change.

### Phase D: Router Extraction (MVC split)
7. **Extract `routers/auth.py`** — Move 4 auth routes out of `__init__.py`.
8. **Extract `routers/rooms.py`** — Move 11 room-management routes.
9. **Extract `routers/media.py`** — Move 5 media/provider routes.
10. **Extract `routers/proxy.py`** — Move image proxy route.
11. **Extract `routers/static.py`** — Move 5 static-file routes or mount `StaticFiles`.
12. **Thin `__init__.py`** — Should be under 60 lines after all routers extracted.

### Phase E: Pydantic Models + Dependencies
13. **Add `routers/models.py`** (or `models.py`) — Define all request/response Pydantic models.
14. **Wire Pydantic models into routes** — Route functions receive typed model instances instead of parsing `request.json` manually.
15. **Create `dependencies.py`** — `get_db()`, `get_current_user()`, `get_provider()`, `get_request_id()`. Update all routes to use `Depends()`.

### Phase F: Test Migration
16. **Update `conftest.py`** — `create_app()` → `TestClient(create_app(...))`. Replace `app.test_client()` with `TestClient(app)`.
17. **Replace `session_transaction()` usages** — Implement `dependency_overrides[get_current_user]` pattern for auth seeding (see Key Dependencies).
18. **Fix response API differences** — `response.get_json()` → `response.json()`, `response.data` → `response.content`/`response.text`, `response.content_type` → `response.headers['content-type']`.
19. **Run full test suite** — All tests must pass.

### Phase G: Validation
20. **End-to-end smoke test** — Browser session, swipe, SSE stream, match, proxy all work.
21. **Docker build** — `docker build` succeeds; container starts with Uvicorn.

---

## Key Dependencies Between Tasks

```
[Phase A: pyproject.toml update]
    └──blocks──> [All subsequent phases] (nothing can run without deps installed)

[Phase B: FastAPI app factory]
    └──requires──> [Phase A complete]
    └──blocks──> [Phase C: auth.py] (auth.py uses request context from FastAPI app)
    └──blocks──> [Phase D: router extraction] (routers mount into the app)

[Phase C: auth.py de-Flaskification]
    └──requires──> [Phase B: FastAPI app factory]
    └──blocks──> [Phase D: routers/auth.py] (auth router uses get_current_user from auth.py)
    └──blocks──> [Phase E: dependencies.py] (dependencies.py wraps auth.py functions)

[Phase D: router extraction]
    └──requires──> [Phase B complete, Phase C complete]
    └──blocks──> [Phase E: Pydantic wiring] (models slot into extracted router signatures)

[Phase E: Pydantic models + dependencies.py]
    └──requires──> [Phase D complete]
    └──can proceed independently of Phase F]

[Phase F: test migration]
    └──requires──> [Phase B (TestClient needs FastAPI app)]
    └──can partially proceed in parallel with Phases D and E]
    └──session_transaction() replacement requires dependency_overrides]
         └──requires──> [get_current_user Depends defined in Phase C/E]

[Phase G: validation]
    └──requires──> [All phases complete and test suite passing]
```

### Critical Dependency: `session_transaction()` Replacement

The 40 usages of `client.session_transaction()` are the **single largest migration effort**
in the test suite. Flask's `session_transaction()` context manager does not exist in
Starlette's `TestClient`.

The replacement pattern uses `app.dependency_overrides`:

```python
# Flask pattern (REMOVE):
with client.session_transaction() as sess:
    sess["session_id"] = "test-session-123"
    sess["active_room"] = "TEST1"

# FastAPI pattern (REPLACE WITH):
def override_get_current_user():
    return CurrentUser(user_id="verified-user", jf_token="valid-token")

app.dependency_overrides[get_current_user] = override_get_current_user
# ... run test ...
app.dependency_overrides.clear()
```

For session state that is not authentication (e.g., `active_room`, `solo_mode`), routes
must either:
1. Accept these as route parameters or query params (preferred — cleaner API)
2. Accept them via a separate `get_session_state()` dependency that can also be overridden

This means some route signatures may need to change to accept `active_room` explicitly
rather than reading `session.get('active_room')` directly. **Audit each
`session_transaction()` call to determine whether it is seeding auth or non-auth state.**

### Critical Dependency: `response.get_json()` → `response.json()`

Flask `TestResponse.get_json()` → Starlette/httpx `Response.json()`. This affects ~100 test
assertions. The change is mechanical but must be done before the test suite passes.

### Critical Dependency: `response.data` → `response.content` or `response.text`

Flask `TestResponse.data` (bytes) → `response.content` (bytes) in httpx. For SSE tests that
call `response.data.decode()`, replace with `response.text`. Affects 15 test lines, mostly
in `test_routes_sse.py`.

### Critical Dependency: `response.content_type` → `response.headers['content-type']`

Affects only 2 test assertions (`test_routes_auth.py:33`, `test_routes_proxy.py:60`).
Note: FastAPI content-type headers include charset suffix (e.g.,
`application/json; charset=utf-8`), so assertions like `== "application/json"` become
`startswith("application/json")` or use `"application/json" in response.headers['content-type']`.

### SSE Test Complexity

The SSE tests (`test_routes_sse.py`) have the highest migration complexity:
- `TestClient` from Starlette buffers the entire streaming response before returning it,
  so `response.text` contains all SSE events concatenated — this matches how
  `response.data.decode()` works in Flask's sync test client. No structural change needed.
- `client.session_transaction()` usages in `_set_session_room()` and `_set_session_xss()`
  helper functions must be replaced with `dependency_overrides`.
- The `threading.Thread` test (`test_stream_generator_exit`) works identically with
  `TestClient` since both are synchronous.
- `monkeypatch.setattr(jellyswipe, "_gevent_sleep", None)` — this attribute disappears
  after migration. Remove the monkeypatch calls; `_gevent_sleep` no longer exists.

### `test_auth.py` Complete Rewrite

`test_auth.py` creates a bare `Flask(__name__)` app with test routes to exercise `auth.py`
in isolation. After `auth.py` is de-Flaskified, these tests must create a minimal FastAPI
app instead. This is a self-contained test file rewrite with no effect on other tests.

---

## Anti-Features (Do Not Build During This Migration)

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Async SQLite** | `aiosqlite` requires rewriting all db.py callers; out of scope for migration | Keep `sqlite3` synchronous. Uvicorn's thread pool handles it correctly. |
| **Redis/message broker** | Out of scope per PROJECT.md constraints | Keep SQLite SSE polling pattern unchanged |
| **`sse-starlette` library** | Redundant; FastAPI 0.136 has native `fastapi.sse.EventSourceResponse` | Use existing `StreamingResponse` or native `EventSourceResponse` |
| **`fastapi-users`** | Overkill; auth is Jellyfin-delegated | Keep existing vault-based auth pattern |
| **`slowapi` rate limiting** | `jellyswipe/rate_limiter.py` already exists | Keep existing rate limiter; wire into FastAPI via Depends |
| **`sqlalchemy`/`databases`** | Project uses raw `sqlite3` by design | No ORM |
| **Plex references restoration** | All Plex code removed in v1.2/v1.6 | Do not re-introduce |
| **Converting routes to `async def`** | Requires async DB layer to be safe; otherwise blocks event loop | Keep sync handlers; Uvicorn/anyio runs them in thread pool |

---

## Sources

- FastAPI 0.136.1 docs via Context7 (`/fastapi/fastapi`): `APIRouter`, `include_router`,
  `Depends`, `dependency_overrides`, `TestClient`, `StreamingResponse`, `SessionMiddleware`,
  Pydantic `BaseModel` request/response patterns (HIGH confidence, verified 2026-05-01)
- FastAPI docs: `fastapi.sse.EventSourceResponse` native in FastAPI 0.136 (HIGH confidence)
- FastAPI docs: TestClient backed by httpx; `response.json()` not `response.get_json()`
  (HIGH confidence)
- Starlette docs: `SessionMiddleware` requires `itsdangerous`; `request.session` dict
  interface (HIGH confidence)
- Direct code analysis: `jellyswipe/__init__.py` (840 lines, 22 routes), `jellyswipe/auth.py`
  (99 lines, Flask-coupled), `tests/conftest.py` (229 lines), all 10 test files (HIGH confidence)
- STACK.md research (this repo, 2026-05-01): package versions, SSE thread pool behavior,
  `gevent` removal rationale (HIGH confidence)

---

*Feature research for: Flask → FastAPI + MVC Migration (v2.0)*
*Researched: 2026-05-01*
