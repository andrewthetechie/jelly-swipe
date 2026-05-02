# Pitfalls Research — v2.0 Flask→FastAPI Migration

**Domain:** Flask + SQLite + SSE monolith migrating to FastAPI + MVC split
**Researched:** 2026-05-01
**Codebase analyzed:** `jellyswipe/__init__.py` (839 lines), `jellyswipe/auth.py`, `jellyswipe/db.py`, `jellyswipe/templates/index.html`
**Overall confidence:** HIGH — all critical pitfalls derived from direct codebase analysis cross-referenced with official FastAPI, SQLite, and Pydantic documentation.

> **Note:** This file supersedes and extends the 2026-04-26 PITFALLS.md (architecture tier fix). That file's pitfalls remain valid; this file adds the migration-specific failure modes introduced by the Flask→FastAPI swap.

---

## SSE Migration Pitfalls

### SSE-1: `GeneratorExit` Swallowed — Gevent vs. AsyncIO Cancellation Model Are Incompatible

**What goes wrong:** The current SSE generator catches `GeneratorExit` explicitly (`except GeneratorExit: return`) and calls `gevent.sleep()` for the poll delay. Under FastAPI/Uvicorn, the cancellation model is `asyncio.CancelledError`, not `GeneratorExit`. If the generator is ported as-is to an `async def generate()` with `await asyncio.sleep()`, a client disconnect raises `CancelledError` which propagates up through the `while` loop and is NOT caught by `except GeneratorExit`. This means the generator never reaches the `finally: conn.close()` block.

**Why it happens:** `GeneratorExit` is the synchronous generator protocol. Async generators use `CancelledError` for disconnect. FastAPI's `StreamingResponse` does attempt to propagate disconnect, but the exact behavior depends on whether the generator is sync or async and how Starlette/Uvicorn deliver the cancel signal.

**Consequences:** SQLite connection leak — every client disconnect leaks the persistent `sqlite3.Connection` opened at the top of `room_stream`. Under load (10+ concurrent SSE clients) this exhausts SQLite's connection ceiling and causes `SQLITE_BUSY` on all new connections.

**Prevention:**
- Always wrap the `async` generator body in `try/finally` to close the connection regardless of how the coroutine is cancelled.
- Use `try: ... except (asyncio.CancelledError, GeneratorExit): break` in the poll loop to catch both cancellation patterns.
- Test by closing the browser tab while the SSE stream is active — verify the connection count drops.

**Phase:** SSE router phase. Must be addressed before any load testing.

---

### SSE-2: `time.sleep()` Blocks the Uvicorn Event Loop

**What goes wrong:** The current generator uses `_gevent_sleep(delay)` (falling back to `time.sleep(delay)`) for the 1.5s poll interval. In FastAPI, if this generator runs as a synchronous callable, `time.sleep()` blocks the entire Uvicorn worker's event loop, preventing all other concurrent requests from being served during the sleep. This is the single largest regression risk: under 5 concurrent SSE clients, Uvicorn effectively becomes single-threaded.

**Why it happens:** FastAPI runs `async def` endpoints on the asyncio event loop. A `time.sleep()` inside a coroutine (or inside a sync generator used by a streaming response) hands blocking time to the OS, not to asyncio. The event loop cannot process other coroutines while sleeping.

**Consequences:** All non-SSE requests (swipes, matches, auth) stall for up to `POLL + jitter` (≈2 seconds) behind every SSE poll cycle. With N concurrent SSE clients the cumulative stall is N×2s.

**Prevention:**
- Replace `time.sleep(delay)` with `await asyncio.sleep(delay)` inside an `async def generate()`.
- Remove the `_gevent_sleep` import and the try/except that conditionally selects it.
- Never call `time.sleep`, `requests.get` (sync), or any other blocking I/O inside an `async def` generator without `await`.

**Phase:** Core framework swap — must be fixed in the very first SSE conversion before any testing.

---

### SSE-3: `requests.get()` Inside the Async Scope (Proxy and Jellyfin Calls)

**What goes wrong:** `jellyswipe/http_client.py` and `jellyfin_library.py` use the synchronous `requests` library. Several routes that will be converted to `async def` call `get_provider().fetch_library_image()`, `get_provider().resolve_item_for_tmdb()`, etc. Calling synchronous `requests` inside `async def` handlers blocks the event loop just like `time.sleep()`.

**Why it happens:** Natural port — the route body is copy-pasted from Flask to FastAPI and made `async def`, but the underlying library calls are still synchronous.

**Consequences:** Under SSE-heavy load, all provider/proxy calls stall the event loop. Poster load times degrade proportionally to concurrent SSE client count.

**Prevention:**
- Option A (Recommended for v2.0): Keep route handlers as `def` (synchronous), not `async def`, except for the SSE route. FastAPI runs sync `def` routes in a threadpool, so they don't block the event loop.
- Option B: Migrate `http_client.py` to `httpx.AsyncClient` and make routes `async def`. More thorough but adds scope.
- Do not mix `async def` routes with synchronous blocking I/O calls.

**Detection:** Response times for `/proxy` and `/genres` spike under concurrent SSE load when routes are `async def` + sync `requests`.

**Phase:** Framework swap. Decision between Option A and B must be made before router extraction begins.

---

### SSE-4: Client Disconnect Not Detected — Goroutine Leak Equivalent

**What goes wrong:** FastAPI's `StreamingResponse` will auto-cancel the generator when a client disconnects, but only if the generator `await`s something that gives the event loop a chance to notice the disconnect. If the generator is a tight sync loop without any `await`, or if the `await asyncio.sleep()` catches `CancelledError` incorrectly, the generator keeps running for up to 3600 seconds (the `TIMEOUT` constant) after the client is gone.

**Why it happens:** Unlike gevent where the greenlet is forcibly killed when the socket closes, asyncio cancellation requires the coroutine to cooperate — it must hit an `await` point. A generator that calls only synchronous SQLite and then `await asyncio.sleep()` will be cancelled at the sleep, but if the sleep's `CancelledError` is caught and suppressed, the loop resumes.

**Consequences:** SQLite connections accumulate. CPU usage rises as dead generators continue polling. Memory grows with each "ghost" connection.

**Prevention:**
- Use `await request.is_disconnected()` as a guard at the top of each poll iteration.
- Do NOT suppress `CancelledError` with a bare `except Exception` — this is the exact failure mode of the current code's `except Exception: delay = POLL...`.
- The current codebase has `except Exception: delay = POLL + random.uniform(0, 0.5)` which will swallow `CancelledError` if the generator is ported as-is.

**Critical code reference:** `__init__.py` lines 776-781 — the `except Exception` block must be narrowed to exclude `asyncio.CancelledError` during migration.

**Phase:** SSE router phase.

---

### SSE-5: `sse-starlette` vs. Manual `StreamingResponse` — Protocol Compliance Risk

**What goes wrong:** A manual `StreamingResponse` with `mimetype='text/event-stream'` and hand-formatted `data: ...\n\n` strings is technically valid SSE, but misses several production concerns that `sse-starlette` (`EventSourceResponse`) handles automatically: retry field support, event ID tracking, proper shutdown grace period, and per-client context isolation.

**Why it happens:** The current Flask generator hand-formats SSE strings (`f"data: {json.dumps(payload)}\n\n"`). Porting this 1:1 to `StreamingResponse` works for the happy path but misses edge cases.

**Consequences:**
- Missing `retry:` field means browser default reconnect delay (3s), which may be too aggressive.
- No event ID means the browser cannot send `Last-Event-ID` header on reconnect — server cannot resume from last state.
- Manual implementation is more fragile if the SSE protocol evolves.

**Prevention:**
- Use `sse-starlette`'s `EventSourceResponse` as the response class. It wraps the async generator, handles proper headers, and provides disconnect detection hooks.
- If staying with manual `StreamingResponse`, ensure headers include `Cache-Control: no-cache`, `X-Accel-Buffering: no`, and `Connection: keep-alive`.
- The existing headers in the Flask response (lines 785-786) are correct and must be preserved.

**Phase:** SSE router phase.

---

## SQLite/Async Pitfalls

### SQL-1: `check_same_thread` Error Under Uvicorn's Threadpool

**What goes wrong:** SQLite connections created in one thread cannot be used in another by default. Under Uvicorn with a threadpool (used for sync `def` routes), a connection created in threadpool thread A may be passed to thread B if a dependency or context manager is used incorrectly across a thread boundary.

The current `get_db()` opens a new connection per call, which avoids this. But if a FastAPI dependency is written to open a connection once and yield it, and that dependency is cached (FastAPI's default), the cached connection could be returned to a different thread on a subsequent request.

**Why it happens:** FastAPI's dependency injection caches results per-request by default, which is safe for single-threaded async. But if the dependency is used in `def` (sync) routes, the request may run in the threadpool, and two requests can share the same thread — but FastAPI's request-scoped cache prevents the same connection being shared across requests. The real trap is using an application-scoped (not request-scoped) database connection.

**Prevention:**
- Always open SQLite connections inside `Depends()` functions that use `yield` — this ensures one connection per request.
- Set `check_same_thread=False` when creating the connection as a belt-and-suspenders guard: `sqlite3.connect(DB_PATH, check_same_thread=False)`.
- Never store a `sqlite3.Connection` in a module-level global without a locking wrapper.
- The current `get_db()` pattern (new connection per call) is safe — preserve it.

**Phase:** Dependency injection setup phase.

---

### SQL-2: WAL Pragma Must Run Outside a Transaction

**What goes wrong:** `PRAGMA journal_mode=WAL` must be executed outside any transaction. The current `init_db()` already handles this correctly by using `with sqlite3.connect(DB_PATH) as conn:` (which opens a transaction) but running WAL pragma first. If the migration wraps `init_db()` in a startup lifespan handler that itself is inside a transaction, the WAL pragma silently fails and the database runs in DELETE mode.

**Why it happens:** SQLAlchemy's `async with engine.begin()` and similar patterns open a transaction before any user code runs. Placing `EXECUTE 'PRAGMA journal_mode=WAL'` inside that block has no effect.

**Consequences:** Database runs without WAL mode. Under concurrent SSE clients (multiple readers + one writer), read operations block on write locks, causing the SSE polling loop to stall.

**Prevention:**
- Call `init_db()` via a FastAPI `lifespan` context manager (not inside a transaction).
- Verify WAL mode persisted after startup: `PRAGMA journal_mode` should return `wal`.
- Keep the existing `init_db()` logic that runs WAL pragma on a bare `sqlite3.connect()`, not wrapped in `with conn:`.

**Phase:** App factory (lifespan) phase.

---

### SQL-3: aiosqlite Is a Thread-Per-Connection Wrapper, Not True Async I/O

**What goes wrong:** If the migration decides to use `aiosqlite` for "async SQLite," teams expect non-blocking I/O. In reality, `aiosqlite` spawns a background thread per connection and uses `asyncio.Queue` to send queries to that thread. It is not non-blocking at the OS level because SQLite operates on files, not sockets.

**Why it happens:** The library name and its `async with` / `await conn.execute()` API implies it's fully async. The underlying model is a thread bridge.

**Consequences:**
- Adding `aiosqlite` buys cleaner async-compatible syntax but no performance gain over sync SQLite in a threadpool.
- Adds a dependency and changes the entire DB access layer for cosmetic async-ness.
- The existing sync `sqlite3` + sync `def` routes in FastAPI's threadpool achieves the same concurrency without extra overhead.

**Recommendation:** Keep sync `sqlite3` with sync `def` route handlers for database access. Reserve `async def` for the SSE generator only, where `await asyncio.sleep()` is the blocking point, not SQLite.

**Phase:** This is a decision that must be made before the DB dependency is wired — do not start with `aiosqlite` and switch back mid-milestone.

---

### SQL-4: Persistent SSE Connection + WAL Checkpoint Starvation

**What goes wrong:** The SSE generator holds a persistent `sqlite3.Connection` open for the room's lifetime (up to 3600s). In WAL mode, the database cannot checkpoint (compact the WAL file back into the main DB) while there are active readers. A long-lived SSE reader blocks WAL growth.

**Why it happens:** WAL checkpointing is blocked by any active read transaction. The SSE generator runs `conn.execute('SELECT ...')` in a loop, which implicitly holds a read snapshot. If many SSE clients are connected to the same room, the WAL file grows without bound until all readers disconnect.

**Consequences:** With 10 concurrent users in one room, WAL file can grow to hundreds of MB over a 1-hour session. `PRAGMA wal_checkpoint(PASSIVE)` calls (if any) silently fail.

**Prevention:**
- After each poll cycle read, explicitly release the read snapshot by calling `conn.commit()` or using `conn.execute("BEGIN DEFERRED")` only when reading (not holding a transaction open between polls).
- Or: open and close a fresh connection per poll cycle instead of a persistent one. The WAL mode prevents the write-lock contention that originally motivated the persistent connection.
- Alternatively, switch to short-lived connections per poll cycle now that WAL mode is set — the original reason for the persistent connection was lock contention, which WAL eliminates.

**Phase:** SSE router phase — checkpoint behavior should be verified under soak test.

---

## Pydantic/FastAPI Gotchas

### PYD-1: `Optional[T]` Semantics Changed in Pydantic v2

**What goes wrong:** In Pydantic v1 (used with Flask/Marshmallow patterns), `Optional[str]` implied `default=None`. In Pydantic v2, `Optional[str]` means "can be `None` but is still required." A model field `movie_id: Optional[str]` will raise a `ValidationError` if the request body omits `movie_id` entirely.

**Why it happens:** Pydantic v2 deliberately separated "nullable" from "optional" to align with type-theoretic correctness. This is a silent breakage if Pydantic v1 mental models are applied.

**Concrete example for this codebase:** The swipe endpoint reads `data.get('movie_id')` from raw JSON. If this is ported to a Pydantic model `class SwipeRequest(BaseModel): movie_id: Optional[str]`, requests without `movie_id` will fail validation even though the existing code handles `None` gracefully.

**Fix:** Use `movie_id: Optional[str] = None` (explicit default) for nullable fields that may be absent.

**Phase:** Pydantic model introduction phase.

---

### PYD-2: `@validator` Silently Ignored After Pydantic v2 Import

**What goes wrong:** If any existing validation logic is ported using Pydantic v1's `@validator` decorator, it will not raise an `ImportError` — `@validator` still exists in Pydantic v2 as a deprecated shim. However, the behavior is different: `@validator` in v2 does not automatically convert types, and `pre=True` validators have different semantics. Bugs here manifest as validation that appears to pass but does not enforce constraints.

**Prevention:**
- Use `@field_validator` (Pydantic v2 API) from the start.
- Run `bump-pydantic` on any code that uses v1 patterns.
- After writing models, verify with an explicit test that invalid payloads are rejected.

**Phase:** Pydantic model introduction phase.

---

### PYD-3: FastAPI's `ValidationError` Response Shape Differs from Flask's Error Pattern

**What goes wrong:** The existing codebase returns `{'error': '<message>', 'request_id': '<id>'}` for all errors (see `make_error_response` in `__init__.py`). FastAPI's automatic Pydantic validation errors return a different shape: `{'detail': [{'loc': [...], 'msg': '...', 'type': '...'}]}`.

**Why it happens:** FastAPI uses Pydantic's `ValidationError` format directly for request validation failures (422 status). There is no automatic integration with a custom error shape.

**Consequences:** The frontend JavaScript currently handles `response.error` to show error messages. If 422 responses use `response.detail`, existing error display logic silently swallows validation failures.

**Prevention:**
- Add a custom exception handler for `RequestValidationError` that reformats to the `{'error': ..., 'request_id': ...}` shape.
- Or update the frontend to handle both shapes during the migration period.
- Test by submitting malformed JSON to each migrated endpoint and checking the frontend error display.

**Phase:** Pydantic model introduction phase — must be addressed before any frontend testing.

---

### PYD-4: `response_model` Strips Fields Not in the Model

**What goes wrong:** FastAPI's `response_model` parameter automatically filters the response through the Pydantic model, removing any keys not declared in the model. If a route returns `conn.execute().fetchall()` converted to dicts (which include database columns not yet modeled), those fields are silently dropped from the response.

**Why it happens:** This is `response_model` working as designed, but it's a silent data loss during migration if models are incomplete.

**Concrete example:** The matches endpoint returns `deep_link`, `rating`, `duration`, `year` from the database. If a `MatchResponse` model is written without those fields initially, they disappear from the API response and the frontend match cards stop showing ratings/duration.

**Prevention:**
- Write response models to match the actual database columns being returned before enabling `response_model`.
- Or use `response_model=None` initially and add models incrementally, validating frontend behavior after each model addition.
- Use `model_config = ConfigDict(extra='ignore')` on response models to make filtering explicit rather than accidental.

**Phase:** Pydantic model introduction phase.

---

## FastAPI-Specific Gotchas

### FAPI-1: Flask `g` and `current_app` Have No Direct Equivalent

**What goes wrong:** `auth.py` uses `g.jf_token` and `g.user_id` (set by the `@login_required` decorator). `__init__.py` uses `g.user_id` in route bodies. FastAPI has no `g` object. Porting the `@login_required` decorator as-is will raise `RuntimeError: Working outside of application context`.

**Why it happens:** Flask's `g` is a request-scoped namespace on the application context stack. FastAPI uses dependency injection to pass per-request state.

**Correct FastAPI pattern:**
```python
async def get_current_user(
    request: Request,
    session: dict = Depends(get_session),
    db: sqlite3.Connection = Depends(get_db_dep),
) -> tuple[str, str]:
    # returns (jf_token, user_id)
    ...

@router.post("/room/{code}/swipe")
async def swipe(code: str, current_user: tuple = Depends(get_current_user)):
    jf_token, user_id = current_user
    ...
```

**Prevention:**
- Do not port `@login_required` as a decorator to FastAPI. Replace it with a `Depends(get_current_user)` dependency.
- `auth.py` must be refactored: `create_session`, `get_current_token`, `destroy_session` need to operate on a Starlette `Request` object, not Flask `session`.

**Phase:** Auth migration phase (earliest phase — all route handlers depend on this).

---

### FAPI-2: Starlette `SessionMiddleware` Uses a Different Cookie Format Than Flask

**What goes wrong:** Existing deployed users have Flask session cookies (signed with `itsdangerous`, base64-encoded JSON with timestamp). Starlette's `SessionMiddleware` uses a different signing format (also HMAC but different structure). After the migration, every existing user's session cookie is invalid — they are silently logged out.

**Why it happens:** The two frameworks sign session cookies differently. There is no automatic compatibility bridge.

**Consequences:**
- All users are logged out when the new Docker image deploys.
- Jellyfin auth must be re-established by every user.
- This is acceptable for a major version migration but must be communicated and tested.

**Prevention:**
- Accept the forced logout as a migration artifact for v2.0. Document in release notes.
- Set the same `SECRET_KEY` environment variable (from `FLASK_SECRET`) in the Starlette `SessionMiddleware` config to reuse the existing operator secret.
- Do NOT attempt to decode Flask session cookies in FastAPI — the signing format is incompatible and the `starlette-flask` bridge library adds maintenance burden for a one-time migration.

**Phase:** App factory phase — acknowledge and test the forced logout behavior explicitly.

---

### FAPI-3: Router Prefix Doubles When `include_router` Prefix + Route Decorator Path Both Specify the Prefix

**What goes wrong:** If the rooms router is created as `router = APIRouter(prefix="/room")` and then routes are decorated with `@router.get("/{code}/stream")`, the path is `/room/{code}/stream`. But if the router is also included as `app.include_router(router, prefix="/room")`, the prefix is applied twice: resulting path is `/room/room/{code}/stream` — a 404 for every room endpoint.

**Why it happens:** Both `APIRouter(prefix=...)` and `app.include_router(..., prefix=...)` add the prefix. Using both is a common mistake when splitting routers.

**Prevention:**
- Set the prefix in exactly one place: either in `APIRouter(prefix=...)` OR in `app.include_router(..., prefix=...)`, not both.
- Write a smoke test after router extraction that hits every original URL path and verifies 200/expected status.

**Phase:** Router extraction phase — this is a mechanical refactoring risk, not a design decision.

---

### FAPI-4: ProxyFix Middleware Must Become Starlette Middleware

**What goes wrong:** The current `app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)` is a WSGI middleware. It cannot be applied to a Starlette/FastAPI application in the same way.

**Why it happens:** FastAPI is ASGI, not WSGI. `werkzeug.middleware.proxy_fix.ProxyFix` wraps a WSGI callable and parses `X-Forwarded-*` headers. It is not ASGI-compatible.

**Consequences:** Without proper proxy header handling, `request.client.host` returns the load balancer IP instead of the real client IP, breaking IP-based rate limiting (`_check_rate_limit` uses `request.remote_addr`). Session cookies with `Secure=True` may not be sent if the app doesn't recognize HTTPS from `X-Forwarded-Proto`.

**Prevention:**
- Replace with `uvicorn.middleware.proxy_headers.ProxyHeadersMiddleware` or use Starlette's built-in trusted hosts middleware.
- Or set `--proxy-headers` flag in the Uvicorn CMD to handle `X-Forwarded-For` automatically.
- Verify `request.client.host` returns the real IP in a Docker deployment with a reverse proxy.

**Phase:** App factory phase — blocking for rate limiting correctness.

---

### FAPI-5: `abort(403)` / `abort(404)` Must Become `HTTPException`

**What goes wrong:** The current codebase uses Werkzeug's `abort(403)` and `abort(404)` in several routes (`proxy` endpoint, lines 793-799). These are not available in FastAPI.

**Why it happens:** `abort()` is a Flask/Werkzeug function that raises an `HTTPException`. FastAPI uses `raise HTTPException(status_code=403)`.

**Consequences:** An `abort()` call in a migrated route handler will raise a Werkzeug `HTTPException` which FastAPI does not catch as an HTTP response — it becomes a 500 Internal Server Error.

**Prevention:**
- Replace every `abort(N)` with `raise HTTPException(status_code=N)`.
- Search the entire codebase: `grep -n "abort(" jellyswipe/__init__.py` — at least 4 locations in the proxy route.
- Add Werkzeug to blocked imports after migration to catch any missed `abort()` calls at startup.

**Phase:** Router extraction phase — catch during mechanical porting.

---

### FAPI-6: `jsonify()` Must Become `return {...}` or `JSONResponse`

**What goes wrong:** The entire codebase returns `jsonify({...})` for JSON responses. FastAPI supports returning plain dicts directly (auto-serialized via Pydantic), but `jsonify()` will fail with `NameError` if Flask is not imported.

**Why it happens:** `jsonify` is Flask-specific. In FastAPI, route handlers return dicts or Pydantic models directly, or explicitly return `JSONResponse`.

**Additional complexity:** The current code has `_XSSSafeJSONProvider` that escapes `<`, `>`, `&` in JSON output (XSS defense). FastAPI's default JSON serializer does NOT do this. Simply replacing `jsonify({})` with `return {}` silently removes the XSS escaping.

**Prevention:**
- Either install a custom JSON serializer on the FastAPI app that performs the same HTML escaping.
- Or use `JSONResponse(content=..., media_type='application/json')` with a custom `json.dumps` call that escapes HTML entities.
- Do NOT forget to preserve the XSS-safe serialization behavior — it was added as an explicit security fix.

**Phase:** Framework swap phase — the XSS requirement is a security constraint, not optional.

---

## Test Migration Pitfalls

### TEST-1: `conftest.py` Monkeypatches Flask Imports — Must Be Rewritten

**What goes wrong:** The existing `tests/conftest.py` sets environment variables and patches `dotenv.load_dotenv` to prevent Flask side effects at import time. After migration, the import side effects change (no Flask startup, different env var requirements, FastAPI app factory). The existing conftest will either over-patch (mocking things FastAPI doesn't need) or under-patch (missing new startup side effects).

**Why it happens:** The test isolation strategy was designed around Flask's module-load-time side effects. FastAPI's app factory is cleaner but has its own startup requirements (lifespan events, middleware registration).

**Prevention:**
- Rewrite `conftest.py` from scratch after the FastAPI app factory is stable.
- Use FastAPI's `TestClient(app)` which handles app startup/shutdown correctly via ASGI lifespan.
- Use `app.dependency_overrides` instead of `patch()` to override database connections and Jellyfin provider in tests.

**Phase:** Test migration phase — cannot be done incrementally, requires the new app to be stable first.

---

### TEST-2: Flask `test_client()` vs FastAPI `TestClient` — Session Handling Differs

**What goes wrong:** Flask's `test_client()` has a `with app.test_client() as c: c.post('/login')` pattern where the session persists across requests within the `with` block. FastAPI's `TestClient` (from Starlette, based on `httpx`) requires explicit cookie passing or uses an internal cookie jar that works differently.

**Why it happens:** Flask's test client directly manipulates the session dict via `with client.session_transaction() as sess:`. FastAPI/Starlette's `TestClient` does not expose this — session state must be established via actual HTTP calls to the session-setting endpoint.

**Consequences:** Tests that directly set session variables will break. Tests must call the login endpoint to establish a session, or must use `dependency_overrides` to bypass auth.

**Prevention:**
- Replace session-manipulation patterns in tests with `app.dependency_overrides[get_current_user] = lambda: ("mock_token", "mock_user_id")`.
- Write a `authenticated_client` fixture that calls the auth endpoint in setup.
- Do not attempt to port `with client.session_transaction()` — this pattern does not exist in Starlette's TestClient.

**Phase:** Test migration phase.

---

### TEST-3: `TestClient` and SSE Streaming Tests — Sync Client Cannot Consume Async Generators

**What goes wrong:** SSE routes return a streaming response. FastAPI's `TestClient` is synchronous and based on HTTPX's sync client. Testing an SSE stream with `TestClient` requires consuming the response as an iterator, which works but requires specific patterns. Async test clients (`httpx.AsyncClient`) cannot be used inside synchronous `def test_*` functions.

**Why it happens:** `TestClient` runs the ASGI app synchronously using `anyio.from_thread.run_sync`. When a streaming response yields data asynchronously, the sync client wraps this correctly for simple cases, but SSE tests require using `response.iter_lines()` or similar iteration patterns.

**Prevention:**
- For SSE tests, use `with client.stream("GET", "/room/{code}/stream") as response: for line in response.iter_lines():` pattern.
- Use `pytest-anyio` or `pytest-asyncio` if async test functions are needed.
- Keep SSE tests as a separate test file that explicitly documents the iterator-based consumption pattern.

**Phase:** Test migration phase.

---

### TEST-4: `app.dependency_overrides` Not Reset Between Tests Causes State Leakage

**What goes wrong:** FastAPI's `app.dependency_overrides` is a dict on the app instance. If a test sets `app.dependency_overrides[get_db] = mock_db` and does not clean up, subsequent tests in the same session receive the mock, even if they don't intend to. This is the FastAPI equivalent of forgetting to `stopall()` patches.

**Why it happens:** `app.dependency_overrides` is mutable app state. Tests that add overrides must remove them.

**Prevention:**
- Use a fixture that sets overrides and tears them down:
  ```python
  @pytest.fixture
  def override_db(app, mock_db):
      app.dependency_overrides[get_db] = lambda: mock_db
      yield
      app.dependency_overrides.clear()
  ```
- Or use `autouse=True` fixture at the function scope that always clears overrides after each test.
- Never call `app.dependency_overrides[X] = Y` in test code directly — always go through a fixture.

**Phase:** Test migration phase.

---

## Docker/Deployment Pitfalls

### DOCK-1: `gunicorn jellyswipe:app` CMD Breaks — WSGI vs ASGI

**What goes wrong:** The current Dockerfile CMD is `gunicorn jellyswipe:app` (or similar). `gunicorn` is a WSGI server. FastAPI apps are ASGI. Running FastAPI under plain Gunicorn without a Uvicorn worker class will either fail at startup or silently serve only the first byte of responses.

**Why it happens:** `gunicorn` loads the `app` object and calls it using the WSGI protocol (synchronous callable). FastAPI's `app` is an ASGI callable (asynchronous, different interface). The mismatch causes `gunicorn` to call the app incorrectly.

**Prevention:**
- Replace with `uvicorn jellyswipe:app --host 0.0.0.0 --port 5000 --workers 1` for single-worker deployments.
- Or use `gunicorn jellyswipe:app -k uvicorn.workers.UvicornWorker` to run Uvicorn inside Gunicorn's process manager (adds Gunicorn's restart/health check benefits).
- For Docker single-container deployments, plain `uvicorn` with `--workers 1` is simpler and sufficient.

**Phase:** Dockerfile update phase — failing to update CMD means the migrated app never starts.

---

### DOCK-2: `FLASK_SECRET` Env Var Must Become `SECRET_KEY` (or Starlette Equivalent)

**What goes wrong:** Starlette's `SessionMiddleware` requires a `secret_key` parameter at instantiation: `SessionMiddleware(app, secret_key=os.environ["SECRET_KEY"])`. The current environment contract uses `FLASK_SECRET`. If the new app reads `FLASK_SECRET` for the session middleware, all existing deployments work. If the new app reads a different variable (e.g., `SECRET_KEY`), all existing Docker operator deployments break silently — sessions fail with a decoding error.

**Prevention:**
- Preserve the `FLASK_SECRET` environment variable name in the FastAPI app for backward compatibility with existing operator deployments.
- Or: support both `SECRET_KEY` and `FLASK_SECRET` with a fallback: `os.environ.get("SECRET_KEY", os.environ["FLASK_SECRET"])`.
- Update `README.md` and `.env.example` to clarify the variable name change if renaming.

**Phase:** App factory phase — operator-facing breaking change.

---

## Prevention Strategies

### Strategy 1: Migrate as `def` First, Then Selectively Convert to `async def`

Keep all route handlers as synchronous `def` initially. FastAPI runs sync handlers in a threadpool — this is safe and prevents event-loop blocking during the migration. Only convert to `async def` after verifying there are no blocking calls in the handler body. The SSE endpoint is the only handler that should be `async def` from day one (it needs `await asyncio.sleep()`).

### Strategy 2: Use a URL Smoke Test After Every Router Extraction Step

After extracting each router (auth, rooms, media, proxy), run a smoke test that hits every original URL path. A simple script:
```bash
for path in "/" "/manifest.json" "/sw.js" "/genres" "/room/XXXX/status"; do
  curl -s -o /dev/null -w "%{http_code} $path\n" http://localhost:5000$path
done
```
This catches router prefix bugs (FAPI-3) and missing routes immediately.

### Strategy 3: Preserve `_XSSSafeJSONProvider` Behavior Explicitly

The HTML-entity escaping in JSON responses is a security requirement (addresses XSS). Create a `custom_json_response.py` module early in the migration that implements the equivalent behavior for FastAPI, and use it as the default response class for all routers. Do not discover this is missing after frontend security testing.

### Strategy 4: Test SSE Disconnect Under Load Before Declaring Migration Complete

The most operationally risky migration item is the SSE generator disconnect handling (SSE-1, SSE-4). After migration, run a soak test:
1. Open 5 browser tabs, all in the same room.
2. Close all tabs rapidly.
3. Watch `SELECT count(*) FROM sqlite_master` or a connection counter — connections should drop to 0.
4. If connections accumulate, the `CancelledError` is being swallowed.

### Strategy 5: Keep the Old Flask App Running Alongside During Dev

Keep `jellyswipe/__init__.py` intact (the Flask app) while building the FastAPI app in parallel. Use separate entry points. This avoids breaking the running application and allows regression comparison. Only delete the Flask code when all tests pass on the FastAPI app.

### Strategy 6: Address `auth.py` First

`auth.py` is imported by every route that uses `@login_required`. It uses `flask.session`, `flask.g`, and `flask.jsonify` directly. It is the highest-leverage file to migrate: once it is converted to work with FastAPI's `Request` and dependency injection, all route migrations follow the same pattern.

---

## Phase-Specific Warnings

| Phase Topic | Pitfall | Severity | Mitigation |
|-------------|---------|----------|------------|
| App factory creation | `FLASK_SECRET` → Starlette `SessionMiddleware` | HIGH | Preserve env var name; test session persistence |
| App factory creation | ProxyFix → ASGI middleware | HIGH | Use uvicorn `--proxy-headers` or Starlette equivalent |
| App factory creation | WAL pragma in lifespan | MEDIUM | Keep `init_db()` outside transaction context |
| Auth router | `@login_required` / `flask.g` removal | CRITICAL | Rewrite as `Depends(get_current_user)` before any other router |
| Auth router | Flask/Starlette cookie incompatibility | MEDIUM | Accept forced logout; test explicitly |
| Rooms/SSE router | `time.sleep()` blocks event loop | CRITICAL | `await asyncio.sleep()` in `async def generate()` |
| Rooms/SSE router | `GeneratorExit` vs `CancelledError` | HIGH | `try/finally` + narrow `except Exception` |
| Rooms/SSE router | `requests` library inside async generator | HIGH | Keep SSE route as `async def`; don't call sync HTTP in the generator |
| Rooms/SSE router | WAL checkpoint starvation | MEDIUM | Release read snapshot between poll cycles |
| Pydantic models | `Optional[T]` breaking change | HIGH | Always add `= None` default for nullable fields |
| Pydantic models | XSS-safe JSON provider lost | HIGH | Custom `JSONResponse` class with HTML escaping |
| Pydantic models | `response_model` silently strips fields | MEDIUM | Verify response shape against frontend expectations |
| Dependency injection | `app.dependency_overrides` not cleared | MEDIUM | Fixture-enforced cleanup |
| Test migration | Flask session manipulation patterns | HIGH | Use `dependency_overrides` for auth bypass |
| Docker update | WSGI CMD breaks on ASGI app | CRITICAL | Replace `gunicorn jellyswipe:app` with `uvicorn` CMD |
| Docker update | Proxy headers not propagated | HIGH | `--proxy-headers` or Starlette middleware |

---

## Sources

- FastAPI gevent incompatibility: [FastAPI GitHub Discussion #6395](https://github.com/fastapi/fastapi/discussions/6395) — "Gevent does a lot of weird things that won't interact well with async code." MEDIUM confidence (community report, consistent with framework docs).
- FastAPI sync route threadpool: [FastAPI Concurrency docs](https://fastapi.tiangolo.com/async/) — sync `def` routes run in threadpool, `async def` routes run on event loop. HIGH confidence (official docs).
- SSE client disconnect detection: [FastAPI Discussion #7572](https://github.com/fastapi/fastapi/discussions/7572) and [Marcelo Tryle's blog](https://marcelotryle.com/blog/2024/06/06/understanding-client-disconnection-in-fastapi/) — `await request.is_disconnected()` is the canonical pattern. MEDIUM confidence.
- sse-starlette: [PyPI sse-starlette](https://pypi.org/project/sse-starlette/) and [GitHub sysid/sse-starlette](https://github.com/sysid/sse-starlette) — provides `EventSourceResponse` with disconnect handling. HIGH confidence.
- Pydantic v2 Optional change: [Pydantic v2 Migration Guide](https://docs.pydantic.dev/latest/migration/) — "Optional[T] does not imply default=None in v2." HIGH confidence (official docs).
- FastAPI Pydantic v2 migration: [FastAPI official guide](https://fastapi.tiangolo.com/how-to/migrate-from-pydantic-v1-to-pydantic-v2/) — HIGH confidence.
- SQLite `check_same_thread`: [FastAPI Discussion #5199](https://github.com/fastapi/fastapi/discussions/5199) — `check_same_thread=False` required under FastAPI threadpool. HIGH confidence.
- aiosqlite threading model: [aiosqlite GitHub](https://github.com/omnilib/aiosqlite) — thread-per-connection wrapper, not true async I/O. HIGH confidence (source code analysis).
- Starlette/Flask cookie incompatibility: [starlette-flask GitHub](https://github.com/hasansezertasan/starlette-flask) — documents incompatible signing methods. MEDIUM confidence.
- Starlette TestClient SSE: [FastAPI GitHub Issue #1273](https://github.com/fastapi/fastapi/issues/1273) — sync TestClient limitations with async streaming. MEDIUM confidence.
- FastAPI router prefix duplication: [FastAPI GitHub Issue #510](https://github.com/fastapi/fastapi/issues/510) — documented prefix-doubling bug with nested routers. HIGH confidence.
- Uvicorn Docker deployment: [FastAPI deployment docs](https://fastapi.tiangolo.com/deployment/server-workers/) and [uvicorn.org/deployment](https://www.uvicorn.org/deployment/) — Gunicorn+UvicornWorker vs plain Uvicorn. HIGH confidence (official docs).
- Flask `g` / `current_app` migration: [Forethought Engineering blog](https://engineering.forethought.ai/blog/2023/02/28/migrating-from-flask-to-fastapi-part-3/) — practical migration account. MEDIUM confidence.
- Codebase analysis: `jellyswipe/__init__.py`, `jellyswipe/auth.py`, `jellyswipe/db.py` — direct analysis. HIGH confidence.
