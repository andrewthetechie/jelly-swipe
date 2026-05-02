# Stack Research: Flask → FastAPI Migration

**Project:** Jelly Swipe v2.0 — Flask → FastAPI + MVC Refactor
**Researched:** 2026-05-01
**Confidence:** HIGH (all versions verified against PyPI as of 2026-05-01)

---

## Current Stack (what is being replaced or kept)

| Package | Current Version Constraint | Role | Migration Fate |
|---------|---------------------------|------|----------------|
| `flask` | >=3.1.3 | Web framework | **REMOVE** |
| `gunicorn` | >=25.3.0 | WSGI server | **REMOVE** |
| `gevent` | >=24.10 | Async I/O / SSE concurrency | **REMOVE** |
| `werkzeug` | >=3.1.8 | WSGI utilities (ProxyFix, routing) | **REMOVE** (pulled in by Flask; no longer a direct dep) |
| `requests` | >=2.33.1 | HTTP client for Jellyfin/TMDB | **KEEP** — unchanged |
| `python-dotenv` | >=1.2.2 | .env loading | **KEEP** — unchanged |
| `pytest` | >=9.0.0 | Test runner | **KEEP** — update test patterns only |
| `pytest-cov` | >=6.0.0 | Coverage | **KEEP** |
| `pytest-mock` | >=3.14.0 | Mocking | **KEEP** |
| `responses` | >=0.25.0 | HTTP mock | **KEEP** |
| `pytest-timeout` | >=2.3.0 | Test timeout | **KEEP** |

---

## Required Changes

### Packages to ADD (runtime)

| Package | Latest Version | Purpose | Why this one |
|---------|---------------|---------|--------------|
| `fastapi` | **0.136.1** | Web framework | Replaces Flask. Python >=3.10 required — compatible with project's Python 3.13 constraint. Bundles Starlette 1.0.0 and Pydantic >=2.9.0 as hard deps. |
| `uvicorn[standard]` | **0.46.0** | ASGI server | Replaces Gunicorn+gevent. The `[standard]` extra adds `uvloop`, `httptools`, and `websockets` for production throughput. Python >=3.10. |
| `itsdangerous` | **2.2.0** | Cookie signing for SessionMiddleware | Required by Starlette's `SessionMiddleware` (replaces Flask's cookie sessions). Python >=3.8. |
| `jinja2` | **3.1.6** | HTML template rendering | Required by FastAPI's `Jinja2Templates` class to serve `index.html`. Was an indirect Flask dep; now must be explicit. Python >=3.7. |
| `python-multipart` | **>=0.0.18** | Form body parsing | Required when any route uses `Form(...)`. The existing routes use JSON bodies, not HTML forms — but the login route (`/auth/jellyfin-login`) receives JSON, so this may not be strictly needed. Add it as a guard against Starlette raising `RuntimeError` if form parsing is ever triggered. |

**Do NOT add `pydantic` explicitly.** FastAPI 0.136.1 already pins `pydantic>=2.9.0` as a hard dependency. It will be resolved transitively. Adding an explicit constraint risks creating a version conflict if the project's pin diverges from FastAPI's.

**Do NOT add `starlette` explicitly.** FastAPI 0.136.1 pins Starlette 1.0.0. Adding a separate explicit dep creates the same conflict risk.

### Packages to ADD (dev/test)

| Package | Latest Verified | Purpose | Why |
|---------|----------------|---------|-----|
| `httpx` | **>=0.28.1** | TestClient transport | FastAPI's `TestClient` is Starlette's `TestClient` re-exported. It is backed by `httpx`, which is NOT included in `fastapi` or `fastapi[standard]` — it must be installed explicitly. Without it, `from fastapi.testclient import TestClient` raises `RuntimeError: httpx is not installed`. |

**anyio** is not needed explicitly — it is a hard transitive dep of both `httpx` and `starlette`.

### Packages to REMOVE

| Package | Why |
|---------|-----|
| `flask` | Replaced by `fastapi` |
| `gunicorn` | Replaced by `uvicorn` |
| `gevent` | No longer needed — uvicorn handles async concurrency natively via asyncio |
| `werkzeug` | Was only a direct dep because Flask required it. No longer used. |

---

## Package Versions (verified 2026-05-01)

| Package | Pinned Constraint | Latest on PyPI | Python compat | Confidence |
|---------|------------------|----------------|---------------|------------|
| `fastapi` | `>=0.136.1` | 0.136.1 | >=3.10 | HIGH |
| `uvicorn[standard]` | `>=0.46.0` | 0.46.0 | >=3.10 | HIGH |
| `itsdangerous` | `>=2.2.0` | 2.2.0 | >=3.8 | HIGH |
| `jinja2` | `>=3.1.6` | 3.1.6 | >=3.7 | HIGH |
| `python-multipart` | `>=0.0.18` | (latest) | >=3.8 | HIGH |
| `httpx` (dev) | `>=0.28.1` | 0.28.1 | >=3.8 | HIGH |
| *(transitive) pydantic* | >=2.9.0 via fastapi | 2.13.3 | >=3.9 | HIGH |
| *(transitive) starlette* | 1.0.0 via fastapi 0.136.1 | 1.0.0 | >=3.10 | HIGH |

### pyproject.toml delta

```toml
# REMOVE these lines:
#   "flask>=3.1.3",
#   "gevent>=24.10",
#   "gunicorn>=25.3.0",
#   "werkzeug>=3.1.8",

# ADD these lines (runtime):
#   "fastapi>=0.136.1",
#   "uvicorn[standard]>=0.46.0",
#   "itsdangerous>=2.2.0",
#   "jinja2>=3.1.6",
#   "python-multipart>=0.0.18",

# ADD to [project.optional-dependencies] dev section:
#   "httpx>=0.28.1",
```

### Dockerfile CMD delta

```dockerfile
# REMOVE:
CMD ["/app/.venv/bin/gunicorn", "-b", "0.0.0.0:5005", "-k", "gevent", "--worker-connections", "1000", "jellyswipe:app"]

# REPLACE WITH:
CMD ["/app/.venv/bin/uvicorn", "jellyswipe:app", "--host", "0.0.0.0", "--port", "5005"]
```

The ASGI app entry point becomes `jellyswipe:app` where `app` is the `FastAPI()` instance returned by `create_app()`. The `jellyswipe/__init__.py` module-level `app = create_app()` pattern is preserved — same import path, different object type.

---

## Migration Mapping: Flask → FastAPI Equivalents

| Flask concept | FastAPI equivalent | Notes |
|---------------|--------------------|-------|
| `Flask(__name__)` | `FastAPI()` | Same factory pattern, same `create_app()` wrapper |
| `@app.route('/path', methods=['GET'])` | `@router.get('/path')` | Use `APIRouter` per domain; mount with `app.include_router()` |
| `flask.request` | `Request` parameter in route function | Pass `request: Request` explicitly |
| `flask.session` | `request.session` via `SessionMiddleware` | Starlette `SessionMiddleware` with `itsdangerous` signing |
| `flask.jsonify(data)` | `return data` (dict/Pydantic model) | FastAPI auto-serializes dicts and Pydantic models to JSON |
| `flask.g` | FastAPI `Depends()` | Move `g.user_id`, `g.jf_token` into a `get_current_user()` dependency |
| `@login_required` decorator | `current_user: User = Depends(get_current_user)` | Dependency injection replaces decorator pattern |
| `Response(generate(), mimetype='text/event-stream')` | `StreamingResponse(generate(), media_type='text/event-stream')` | The SSE generator can stay synchronous; FastAPI runs it in a thread pool via `anyio.to_thread.run_sync` |
| `render_template('index.html')` | `templates.TemplateResponse('index.html', {'request': request})` | Requires `Jinja2Templates` instance and `jinja2` installed |
| `send_from_directory('static', path)` | `app.mount('/static', StaticFiles(directory=...))` | Mount once at app init; removes need for explicit static routes |
| `app.wsgi_app = ProxyFix(...)` | `app.add_middleware(ProxyHeadersMiddleware, trusted_hosts='*')` | `uvicorn.middleware.proxy_headers.ProxyHeadersMiddleware` handles X-Forwarded-* |
| `@app.after_request` CSP header | `@app.middleware('http')` | Standard Starlette-style HTTP middleware |
| `flask.abort(403)` | `raise HTTPException(status_code=403)` | FastAPI's `HTTPException` |
| `app.config['KEY']` | Module-level variable or `lifespan` state | FastAPI has no `app.config`; use `app.state` or pass config through DI |

---

## SSE-Specific Notes

The existing SSE generator in `room_stream()` is a **synchronous** generator using `time.sleep()`. FastAPI/Uvicorn handle this correctly:

- `StreamingResponse` accepts both sync and async iterables.
- When given a sync generator, FastAPI runs it in a thread pool via `anyio`, so it does not block the event loop.
- `gevent_sleep` is used in the current code only as a fallback to `time.sleep` — both can be removed in favor of plain `time.sleep()`, since the thread pool isolation makes it safe.
- The `asyncio.sleep()` alternative is only necessary if the generator is converted to `async def` — not required for the initial migration.

**Do NOT add `sse-starlette`** (PyPI: `sse-starlette 3.4.1`). It is a third-party wrapper providing `EventSourceResponse`. FastAPI 0.136.x has native `EventSourceResponse` in `fastapi.sse`. The existing `StreamingResponse` with `media_type='text/event-stream'` is sufficient and already matches the behavior of the current Flask `Response(generate(), mimetype='text/event-stream')`.

---

## Test Suite Migration

The current test infrastructure patches `dotenv.load_dotenv` and `Flask` at the session level. After migration:

- The `app` fixture in `conftest.py` calls `create_app()` — this will return a `FastAPI()` instance instead of `Flask()`. The fixture shape is identical; only the import and object type change.
- `app.test_client()` (Flask) → `TestClient(app)` from `fastapi.testclient` — same synchronous HTTP interface, backed by `httpx`.
- `client.session_transaction()` context manager (Flask test client only) → does not exist in FastAPI's `TestClient`. Session manipulation in tests must use the `SessionMiddleware` cookie approach: set cookies directly on `TestClient` requests, or use an override dependency for `get_current_user()`.
- `monkeypatch.setattr(jellyswipe_module, '_provider_singleton', fake_provider)` — works unchanged; the singleton pattern is framework-agnostic.

**The biggest test migration effort** is replacing `with client.session_transaction() as sess: sess[...] = ...` (used in SSE and route tests) with FastAPI-compatible session seeding. The standard pattern is to override the `get_current_user` dependency in tests using `app.dependency_overrides[get_current_user] = lambda: fake_user`.

---

## What NOT to Add

| Package | Why to avoid |
|---------|-------------|
| `sse-starlette` | Redundant — FastAPI 0.136 has `fastapi.sse.EventSourceResponse` natively. The existing `StreamingResponse` approach also works fine. |
| `pydantic` (explicit) | FastAPI pins it. Explicit constraint risks divergence conflict. |
| `starlette` (explicit) | Same reason as pydantic — FastAPI pins Starlette 1.0.0 exactly. |
| `anyio` (explicit) | Transitive dep of starlette and httpx. Adding it explicitly is noise. |
| `flask` / `gunicorn` / `gevent` | Being removed; do not carry them forward as optional deps. |
| `aiohttp` | Not needed. `requests` continues to serve sync Jellyfin/TMDB API calls. No reason to introduce an async HTTP client. |
| `sqlalchemy` / `databases` | Project uses raw `sqlite3`. No ORM is needed or desired. |
| `fastapi-users` | Overkill. Auth is Jellyfin-delegated. No local user table. |
| `slowapi` | Rate limiting is already implemented in `jellyswipe/rate_limiter.py`. Do not replace it with a new library. |
| `uvloop` (explicit) | Included in `uvicorn[standard]` already. |
| `httptools` (explicit) | Same — included in `uvicorn[standard]`. |

---

## Sources

- FastAPI 0.136.1 on PyPI — version, Python requirements, Starlette 1.0.0 and python-multipart >=0.0.18 dependency (HIGH confidence, verified 2026-05-01)
- Uvicorn 0.46.0 on PyPI — version, Python requirements, `[standard]` extras (HIGH confidence, verified 2026-05-01)
- Starlette 1.0.0 on PyPI — `itsdangerous` required for `SessionMiddleware` (HIGH confidence, verified 2026-05-01)
- Pydantic 2.13.3 on PyPI — latest version, Python >=3.9 (HIGH confidence, verified 2026-05-01)
- Jinja2 3.1.6 on PyPI — latest version (HIGH confidence, verified 2026-05-01)
- itsdangerous 2.2.0 on PyPI — latest version (HIGH confidence, verified 2026-05-01)
- httpx 0.28.1 on PyPI — latest version, required for TestClient (HIGH confidence, verified 2026-05-01)
- FastAPI release notes (fastapi.tiangolo.com/release-notes) — 0.136.1 upgrades Starlette to 1.0.0; 0.135.2 bumps Pydantic lower bound to >=2.9.0 (HIGH confidence)
- FastAPI docs: TestClient (fastapi.tiangolo.com/tutorial/testing) — requires httpx, not bundled (HIGH confidence)
- FastAPI docs: SSE / StreamingResponse (fastapi.tiangolo.com/tutorial/server-sent-events, reference/responses) — native EventSourceResponse in fastapi.sse; StreamingResponse accepts sync generators (HIGH confidence)
- FastAPI docs: SessionMiddleware inherited from Starlette (fastapi.tiangolo.com/features) — HIGH confidence
- Context7 /fastapi/fastapi — TestClient, SessionMiddleware, StreamingResponse, Depends() patterns (HIGH confidence)
- Context7 /websites/uvicorn_dev — CLI options, --host/--port, proxy headers middleware (HIGH confidence)
- GitHub discussion fastapi/fastapi #11958 — httpx not bundled since FastAPI 0.112.0, must install separately (HIGH confidence)
