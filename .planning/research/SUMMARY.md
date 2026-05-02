# Project Research Summary

**Project:** Jelly Swipe v2.0 — Flask to FastAPI + MVC Refactor
**Domain:** Framework migration — WSGI monolith to ASGI router/dependency architecture
**Researched:** 2026-05-01
**Confidence:** HIGH (all research verified against PyPI, official docs, and direct codebase analysis)

---

## Executive Summary

Jelly Swipe v2.0 is a framework migration, not a product feature release. The goal is to replace the 839-line Flask WSGI monolith in `jellyswipe/__init__.py` with a FastAPI ASGI application structured as domain routers, Pydantic models, and a dependency injection layer — while preserving 100% of existing end-user behavior. The migration is well-understood: FastAPI 0.136.1 provides direct equivalents for every Flask primitive used in this codebase, the stack diff is minimal (five packages added, four removed), and six of the eight code modules require zero changes.

The recommended approach is a phased sequential migration starting with package infrastructure, then the app factory and auth layer (the highest-coupling points), then router extraction in order of increasing complexity, then Pydantic models and the dependency injection layer, and finally test suite migration. Each phase should leave the test suite green before proceeding. The one deviation from a purely mechanical port is the SSE generator: it must be converted to an `async def` generator using `await asyncio.sleep()` — keeping it synchronous with `time.sleep()` will block Uvicorn's event loop and degrade all concurrent requests. This is the single highest-risk change in the migration and must be treated with explicit test coverage for client disconnect and connection cleanup.

The key risks cluster around four areas: the SSE generator cancellation model (gevent vs asyncio have incompatible cancellation semantics that will cause connection leaks if not addressed), the ~40 `client.session_transaction()` usages in the test suite (Flask's API has no equivalent in Starlette's TestClient and requires a new approach using `dependency_overrides`), the XSS-safe JSON serialization behavior (silently lost if `jsonify()` is naively replaced with `return {}`), and the env var naming (`FLASK_SECRET` must either be preserved or explicitly migrated to avoid breaking existing operator deployments). None of these are blocking obstacles — all have clear, well-documented mitigations — but skipping any of them creates a silent regression.

---

## Key Findings

### Recommended Stack

The stack change is surgical. Four packages exit (`flask`, `gunicorn`, `gevent`, `werkzeug`) and five enter (`fastapi>=0.136.1`, `uvicorn[standard]>=0.46.0`, `itsdangerous>=2.2.0`, `jinja2>=3.1.6`, `python-multipart>=0.0.18`). One dev dependency is added (`httpx>=0.28.1` — required for FastAPI's TestClient, not bundled). All other runtime and dev dependencies are unchanged. All versions are verified against PyPI as of 2026-05-01.

**Critical "do not add" constraints:**
- Do NOT add `pydantic` or `starlette` explicitly — FastAPI 0.136.1 pins both as hard deps; explicit constraints risk version conflicts.
- Do NOT add `sse-starlette` — FastAPI 0.136 has native `EventSourceResponse` in `fastapi.sse`; the existing `StreamingResponse` approach also works.
- Do NOT add `aiohttp`, `aiosqlite`, `sqlalchemy`, `fastapi-users`, or `slowapi` — all are out of scope and/or already replaced by existing project code.
- Do NOT convert route handlers to `async def` broadly — only the SSE generator should be async; sync `def` handlers run safely in Uvicorn's threadpool.

**Core technology additions:**
- `fastapi>=0.136.1` — Web framework replacing Flask; bundles Starlette 1.0.0 and Pydantic >=2.9.0 transitively; Python >=3.10 compatible with project's Python 3.13 constraint.
- `uvicorn[standard]>=0.46.0` — ASGI server replacing Gunicorn+gevent; `[standard]` extra adds uvloop, httptools for production throughput.
- `itsdangerous>=2.2.0` — Required by Starlette's `SessionMiddleware` for cookie signing (replaces Flask's built-in session signing).
- `jinja2>=3.1.6` — Required by FastAPI's `Jinja2Templates`; was indirect Flask dep, must now be explicit.
- `httpx>=0.28.1` (dev) — Required for `from fastapi.testclient import TestClient`; not bundled with FastAPI since 0.112.0.

**Dockerfile CMD change (single line):**
- Remove: `gunicorn -b 0.0.0.0:5005 -k gevent --worker-connections 1000 jellyswipe:app`
- Replace with: `uvicorn jellyswipe:app --host 0.0.0.0 --port 5005`

### Migration Feature Scope

This milestone has no new user-facing features. Every item is a migration task required for behavioral parity. All 15 table-stakes tasks must be complete before v2.0 ships; none can be deferred.

**Must complete — the 15 table stakes:**
1. FastAPI app factory replaces Flask (FAPI-01) — LOW complexity
2. Uvicorn replaces Gunicorn+gevent (FAPI-01, DEP-01) — LOW complexity
3. All 22 HTTP endpoints retain identical paths and behavior (FAPI-02) — MEDIUM complexity
4. SSE endpoint migrated to StreamingResponse with `async def` generator (FAPI-03) — MEDIUM complexity
5. Session management migrated to `SessionMiddleware` (FAPI-04) — MEDIUM complexity
6. `auth.py` de-Flaskified: remove `flask.session`, `flask.g`, `flask.jsonify` (ARCH-01, ARCH-03) — MEDIUM complexity
7. Domain routers extracted into 5 `APIRouter` modules (ARCH-01) — MEDIUM complexity
8. Pydantic models for all request bodies (ARCH-02) — LOW complexity
9. Pydantic models for significant response shapes (ARCH-02) — LOW complexity
10. `dependencies.py` extracts shared logic — `get_db()`, `get_current_user()`, `get_provider()` (ARCH-03) — MEDIUM complexity
11. `__init__.py` becomes thin app factory, under 60 lines (ARCH-04) — LOW complexity
12. TestClient replaces Flask test client (TST-01) — HIGH complexity (40 `session_transaction()` usages)
13. `conftest.py` updated for FastAPI (TST-01) — MEDIUM complexity
14. Dockerfile CMD uses Uvicorn (DEP-01) — LOW complexity
15. All 48 unit tests pass (TST-01) — blocking gate

**Post-v2.0 optional enhancements (do not block ship):**
- `async def` route handlers broadly (requires async DB layer — out of scope for v2.0)
- `EventSourceResponse` from `fastapi.sse` (trivial upgrade after SSE tests pass)
- HTML/XML coverage reports (deferred from v1.3 ADV-01)

**Confirmed anti-features / out of scope:**
- Async SQLite (`aiosqlite`) — performance-neutral, adds dependency for no real gain
- Redis/message broker — PROJECT.md constraint
- Converting routes to `async def` broadly — only the SSE generator must be async

### Architecture Approach

The target architecture splits the 839-line Flask monolith into a thin factory (`jellyswipe/__init__.py`, ~50 lines), five domain routers, a dependency injection layer (`dependencies.py`), and a Pydantic models package. Six of the eight existing modules (`db.py`, `jellyfin_library.py`, `base.py`, `http_client.py`, `rate_limiter.py`, `ssrf_validator.py`) require zero changes — they have no Flask imports. Only `__init__.py` and `auth.py` need rewrites.

**Major components:**
1. `jellyswipe/__init__.py` (thin factory) — Creates `FastAPI()`, registers `SessionMiddleware`, `SecurityHeadersMiddleware` (CSP + X-Request-Id), `ProxyHeadersMiddleware`, mounts all routers, calls `init_db()` via lifespan context manager. Target: ~50 lines.
2. `jellyswipe/dependencies.py` (DI container) — `get_db_dep()` (yield-based connection per request), `get_provider()` (singleton accessor), `require_auth()` (replaces `@login_required`), `check_rate_limit()` (wraps existing `rate_limiter.py`), `get_tmdb_headers()`. This is where `flask.g` is eliminated.
3. `jellyswipe/routers/` (5 domain routers) — auth, rooms, media, proxy, static. Each uses `APIRouter`, declares `Depends(require_auth)` on protected routes. The rooms router contains the SSE generator as an `async def` with `await asyncio.sleep()`.
4. `jellyswipe/models/` (Pydantic v2 models) — Request models: `JellyfinLoginRequest`, `SwipeRequest`, `GenreRequest`, `WatchlistRequest`. Response models: `AuthResponse`, `RoomResponse`, `MatchResponse`, `MeResponse`. All nullable fields use `Optional[T] = None` explicitly.
5. `jellyswipe/auth.py` (rewritten, ~40 lines) — Removes all Flask imports. Functions operate on Starlette `Request` objects. `require_auth()` Depends function replaces `@login_required` decorator.

**Key data flow changes:**
- `flask.g.user_id / flask.g.jf_token` — injected via `Depends(require_auth)` returning `(jf_token, user_id)` tuple
- `flask.session` — `request.session` via Starlette `SessionMiddleware` (explicit `Request` parameter)
- `app.config['JELLYFIN_URL']` — `os.getenv("JELLYFIN_URL")` read in `dependencies.py`
- `request.environ['jellyswipe.request_id']` — `request.state.request_id` set in `SecurityHeadersMiddleware`
- `flask.jsonify({...})` — `return {...}` with custom `XSSSafeJSONResponse` as default response class (XSS escaping preserved)

**XSS-safe JSON must be preserved.** The current `_XSSSafeJSONProvider` escapes `<`, `>`, `&` in JSON (added as an explicit security fix in v1.5). Replacing `jsonify()` with bare `return {}` silently removes this. Use a custom `JSONResponse` subclass as `default_response_class` on the `FastAPI()` instance, implemented in Phase 2 before any route testing begins.

### Critical Pitfalls

**SSE migration pitfalls are the highest-risk cluster in this codebase:**

1. **`time.sleep()` blocks the Uvicorn event loop (SSE-2 — CRITICAL)** — With 5 concurrent SSE clients, all swipe/auth/match requests stall ~2 seconds per poll cycle. Convert the SSE generator to `async def` with `await asyncio.sleep()` on day one of SSE work. Non-negotiable.

2. **`GeneratorExit` vs `CancelledError` — SQLite connection leak on client disconnect (SSE-1 — HIGH)** — The existing `except Exception` block (lines 776-781 of `__init__.py`) will swallow `CancelledError` if ported as-is, leaking the persistent SQLite connection for up to 3600 seconds per disconnected client. Wrap generator body in `try/finally`; narrow `except Exception` to exclude `asyncio.CancelledError`; use `await request.is_disconnected()` as a guard.

3. **`@login_required` / `flask.g` have no direct FastAPI equivalent (FAPI-1 — CRITICAL)** — Porting the decorator as-is raises `RuntimeError: Working outside of application context`. Rewrite `auth.py` first — before any router is written — implementing `require_auth()` as a FastAPI `Depends()` function.

4. **`session_transaction()` has no FastAPI TestClient equivalent (TEST-2 — HIGH)** — Used in ~40 test locations. Use `app.dependency_overrides[require_auth] = lambda: ("mock_token", "mock_user")` for auth seeding. For non-auth session state, extend the vault-seeding + cookie injection pattern already used in `test_routes_room.py`.

5. **XSS-safe JSON silently removed when replacing `jsonify()` (FAPI-6 — HIGH)** — Implement `XSSSafeJSONResponse` as a `JSONResponse` subclass early (Phase 2) and set as `default_response_class` before any route testing.

6. **Router prefix doubling (FAPI-3 — MEDIUM)** — Setting prefix in both `APIRouter(prefix=...)` AND `app.include_router(..., prefix=...)` doubles the path. Set prefix in exactly one place; run URL smoke test after each router extraction step.

7. **`FLASK_SECRET` env var rename breaks existing deployments (DOCK-2 — HIGH)** — Preserve `FLASK_SECRET` as the env var name, or support both with `os.environ.get("SECRET_KEY", os.environ["FLASK_SECRET"])`. Decision must be made in Phase 2 and documented in v2.0 release notes.

8. **`app.dependency_overrides` not cleared between tests (TEST-4 — MEDIUM)** — Always manage overrides via fixtures with `yield` teardown; never set overrides directly in test function bodies.

---

## Implications for Roadmap

The research files agree on a single viable migration sequence with hard dependency ordering. Ten phases are suggested, each leaving the test suite green before proceeding.

### Phase 1: Package and Infrastructure Setup
**Rationale:** Nothing else can proceed until deps are installed and the server runtime is correct. Zero logic changes — pure config. Maximum reversibility.
**Delivers:** `pyproject.toml` updated (Flask/Gunicorn/gevent/werkzeug removed; FastAPI/Uvicorn/itsdangerous/jinja2/python-multipart added; httpx in dev deps); Dockerfile CMD updated to Uvicorn; `uv sync` and `docker build` pass.
**Addresses:** FAPI-01, DEP-01 (partially)
**Avoids:** DOCK-1 (Gunicorn WSGI vs ASGI mismatch)
**Research flag:** Standard patterns — skip phase research.

### Phase 2: FastAPI App Factory + Middleware Skeleton
**Rationale:** Middleware must exist before routers because `SessionMiddleware` must be registered before any route can read `request.session`. Preserve the old `__init__.py` alongside the new factory to avoid breaking anything during development.
**Delivers:** New app factory with `FastAPI()`, `SessionMiddleware`, `SecurityHeadersMiddleware`, `ProxyHeadersMiddleware`, lifespan-based `init_db()`, empty router stubs, and `XSSSafeJSONResponse` as default response class. App boots with Uvicorn.
**Addresses:** FAPI-01, FAPI-04, ARCH-04
**Avoids:** DOCK-2 (`FLASK_SECRET` env var compatibility — decided here), FAPI-4 (ProxyFix WSGI-to-ASGI), FAPI-6 (XSS-safe JSON — implement early not as afterthought), SQL-2 (WAL pragma outside transaction in lifespan)
**Research flag:** Standard patterns — skip phase research.

### Phase 3: `auth.py` Rewrite + `dependencies.py` Core
**Rationale:** `auth.py` is imported by every authenticated route and must be de-Flaskified before any router can be written. `dependencies.py` must exist before routes can declare `Depends()`. This is the highest-risk phase — the conceptual shift from `flask.g` thread-locals to explicit DI lives here.
**Delivers:** `jellyswipe/auth.py` with Flask imports removed; `require_auth()` Depends function replaces `@login_required`. `jellyswipe/dependencies.py` with `get_db_dep()`, `get_provider()`, `require_auth()`, `check_rate_limit()`, `get_tmdb_headers()`. `tests/conftest.py` updated to use `TestClient(create_app(...))`.
**Addresses:** ARCH-03, FAPI-04 (session access pattern)
**Avoids:** FAPI-1 (`flask.g` elimination), SSE-3 (decision to keep routes as `def` not `async def`)
**Research flag:** MEDIUM complexity — `require_auth()` must be unit-tested in isolation before router phases begin.

### Phase 4: Pydantic Models
**Rationale:** Models are needed by all routers. Defining them before routers avoids circular import issues and forces auditing actual request/response shapes upfront. Pydantic v2 `Optional[T]` semantics must be addressed here.
**Delivers:** `jellyswipe/models/` package with `auth.py`, `rooms.py`, `media.py`. All nullable fields use `Optional[T] = None` explicitly. Response models verified against actual DB columns returned to frontend.
**Addresses:** ARCH-02
**Avoids:** PYD-1 (`Optional` semantics), PYD-2 (`@validator` vs `@field_validator`), PYD-4 (`response_model` field stripping)
**Research flag:** Standard patterns — skip phase research.

### Phase 5: Non-SSE Routers (Auth, Media, Proxy, Static)
**Rationale:** These 4 router groups are the simplest — no streaming, no complex transaction management. Migrating them first validates the full routing pattern on low-risk targets. Router prefix decisions crystallize here.
**Delivers:** `routers/auth.py`, `routers/media.py`, `routers/proxy.py`, `routers/static.py` fully migrated and mounted. All route tests for these groups pass with `TestClient`.
**Addresses:** FAPI-02, ARCH-01 (partially)
**Avoids:** FAPI-3 (router prefix doubling — smoke test all URLs after each extraction), FAPI-5 (`abort()` to `HTTPException` — search and replace during mechanical port)
**Research flag:** Standard patterns — STACK.md migration mapping table is the reference.

### Phase 6: Rooms Router (Non-SSE Routes)
**Rationale:** Room routes contain the most complex business logic (swipe/match detection, deck cursors, BEGIN IMMEDIATE transactions). Isolating from SSE reduces blast radius. The swipe handler's manual transaction pattern works unchanged under FastAPI's sync threadpool.
**Delivers:** `routers/rooms.py` with all room lifecycle routes except `/room/{code}/stream` migrated and tested.
**Addresses:** FAPI-02, ARCH-01 (room routes)
**Avoids:** SQL-1 (`check_same_thread=False` in `get_db_dep()`), SQL-5 (BEGIN IMMEDIATE — keep synchronous, do not convert to async)
**Research flag:** MEDIUM complexity — swipe handler is the most test-sensitive route; integration smoke test before marking complete.

### Phase 7: SSE Route Migration
**Rationale:** SSE is last among routes because it requires async generator syntax, `asyncio.sleep`, and careful cancellation handling. All other routes must be working first.
**Delivers:** `/room/{code}/stream` as `async def` route with `StreamingResponse`, `async def generate()` using `await asyncio.sleep()`, `try/finally` connection cleanup, narrowed `except` excluding `CancelledError`, and preserved SSE headers.
**Addresses:** FAPI-03
**Avoids:** SSE-2 (event-loop blocking — CRITICAL; first change in this phase), SSE-1 (connection leak on disconnect), SSE-4 (client disconnect detection), SQL-4 (WAL checkpoint starvation)
**Research flag:** HIGH complexity — soak test (5 tabs, close rapidly, verify SQLite connection count drops to 0) required before phase is complete.

### Phase 8: Old Flask Code Removal + Thin Factory Finalization
**Rationale:** Once all routers are working, delete the Flask monolith and verify no Flask imports remain.
**Delivers:** `jellyswipe/__init__.py` reduced to ~50 lines. `rg 'from flask' jellyswipe/` returns zero matches.
**Addresses:** ARCH-04
**Research flag:** Standard patterns — skip phase research.

### Phase 9: Test Suite Migration + Full Suite Green
**Rationale:** Test migration depends on all application code being stable. The ~40 `session_transaction()` replacements require `require_auth` (Phase 3) and all routers (Phases 5-7) to exist first.
**Delivers:** All 10 test files migrated to `TestClient`; `session_transaction()` replaced with `dependency_overrides` pattern; `response.get_json()` to `response.json()` (~100 locations); `response.data` to `response.text`/`response.content` (~15 locations); `response.content_type` assertion updated to `startswith("application/json")` (2 locations); `test_auth.py` rewritten for minimal FastAPI app; `dependency_overrides` managed through fixtures with teardown; all 48 tests pass.
**Addresses:** TST-01
**Avoids:** TEST-1 (conftest over-patching), TEST-2 (session handling), TEST-3 (SSE streaming iterator patterns), TEST-4 (dependency_overrides state leakage)
**Research flag:** HIGH complexity — 40 `session_transaction()` replacements are the largest single test effort. Use vault-seeding + `dependency_overrides` pattern from FEATURES.md. Patch `asyncio.sleep` not `time.sleep` in SSE tests.

### Phase 10: Validation
**Rationale:** End-to-end confirmation that migrated app behaves identically to Flask version.
**Delivers:** Browser session validation (auth, create room, swipe, SSE updates, match); Docker build and Uvicorn startup; SSE soak test under concurrent load.
**Addresses:** FAPI-01 through FAPI-04 (final validation gate)
**Research flag:** Standard patterns — skip phase research.

### Phase Ordering Rationale

- Infrastructure first: Package resolution must succeed before any code changes.
- Factory before routers: `SessionMiddleware` must wrap all routes; cannot be added after.
- Auth before everything else: `require_auth()` is depended on by ~18 of 22 routes; must exist and be tested before any router is written.
- Models before routers: Defines data contracts routers consume; avoids circular imports; forces shape audit upfront.
- Simple routers before complex: Auth/media/proxy validate the routing pattern on low-risk code before room business logic.
- SSE last among routes: Async generator complexity compounds unresolved issues; isolate it.
- Test migration last: Requires stable app code and all `Depends()` functions to exist before `session_transaction()` replacements can be written.

### Conflict Resolution

One conflict exists between research files: STACK.md states the existing sync generator can be used with `StreamingResponse` (Uvicorn runs it in a thread pool via anyio), while ARCHITECTURE.md recommends converting to `async def generate()` with `await asyncio.sleep()`, and PITFALLS.md marks keeping `time.sleep()` as CRITICAL severity.

**Resolution: convert to `async def generate()` with `await asyncio.sleep()`.** PITFALLS.md is authoritative — `time.sleep()` in a sync SSE generator blocks the event loop under concurrent load. The anyio thread pool safety STACK.md references is not guaranteed for long-running persistent generators. The `async def` approach is explicit and unambiguous.

### Research Flags

Phases needing careful implementation attention (patterns documented; no external research needed):
- **Phase 3 (auth.py rewrite):** Highest-coupling file; `require_auth()` must be unit-tested before router work begins.
- **Phase 7 (SSE route):** Soak test for disconnect/connection leak before marking complete; patch `asyncio.sleep` not `time.sleep` in SSE tests.
- **Phase 9 (test migration):** 40 `session_transaction()` replacements; use vault-seeding + `dependency_overrides` pattern documented in FEATURES.md.

Phases with standard well-documented patterns (skip phase-specific research):
- Phase 1: Pure config change.
- Phase 2: FastAPI factory pattern is canonical in official docs.
- Phase 4: Pydantic v2 `BaseModel` is well-documented; pure data shapes.
- Phase 5: Mechanical route translation; STACK.md migration mapping table is the reference.
- Phase 8: Deletion phase.
- Phase 10: Browser + Docker smoke test.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All package versions verified against PyPI 2026-05-01. FastAPI 0.136.1, Uvicorn 0.46.0, Pydantic 2.13.3 confirmed. Transitive dep chain (FastAPI to Starlette 1.0.0, Pydantic >=2.9.0) verified. |
| Features | HIGH | Based on direct codebase analysis of `jellyswipe/__init__.py` (839 lines), all 10 test files, and official FastAPI 0.136.1 docs. Migration scope is concrete and countable (22 routes, 40 session_transaction usages, ~100 get_json usages). |
| Architecture | HIGH | Target structure derived from direct codebase analysis + FastAPI idiomatic patterns verified against Context7. All integration points have concrete code examples in ARCHITECTURE.md. |
| Pitfalls | HIGH | Critical pitfalls derived from official FastAPI concurrency docs and direct codebase analysis. SSE-4 (disconnect detection) and FAPI-2 (Starlette/Flask cookie incompatibility) are MEDIUM confidence based on community sources consistent with framework behavior. |

**Overall confidence: HIGH**

### Gaps to Address

- **SSE disconnect behavior under Uvicorn:** The exact `CancelledError` propagation path through `StreamingResponse` to the async generator should be verified with an integration test in Phase 7, not assumed from documentation alone.

- **`content-type` charset suffix in FastAPI responses:** FastAPI returns `application/json; charset=utf-8` where Flask returns `application/json`. The 2 test assertions using `== "application/json"` must become `startswith("application/json")`. Minor but will cause test failures if missed.

- **Session cookie forced logout on v2.0 deploy:** All existing users will be logged out (Starlette and Flask use incompatible cookie signing formats). Acceptable for a major version but must be documented in v2.0 release notes.

- **`test_auth.py` full rewrite required:** This file creates a bare `Flask(__name__)` app. After `auth.py` is de-Flaskified it needs a minimal FastAPI app instead. Self-contained rewrite with no effect on other test files.

- **OpenAPI docs exposure decision:** FastAPI auto-generates Swagger UI at `/docs`. Decide whether to expose in production or disable via `docs_url=None` in `FastAPI()`. No security risk either way; product choice only.

---

## Sources

### Primary (HIGH confidence)
- FastAPI 0.136.1 PyPI + docs (fastapi.tiangolo.com) — version, Starlette 1.0.0 pin, Pydantic >=2.9.0 dep, TestClient httpx requirement, native SSE EventSourceResponse, SessionMiddleware, Depends() patterns
- Uvicorn 0.46.0 PyPI + uvicorn.org/deployment — version, `[standard]` extras, `--proxy-headers` flag
- Starlette 1.0.0 PyPI — `itsdangerous` requirement for `SessionMiddleware`, `request.session` interface
- Pydantic v2 Migration Guide (docs.pydantic.dev) — `Optional[T]` semantics change, `@field_validator` vs deprecated `@validator`
- FastAPI Concurrency docs (fastapi.tiangolo.com/async/) — sync `def` routes in threadpool, `async def` routes on event loop
- Context7 `/fastapi/fastapi` — TestClient, dependency_overrides, StreamingResponse, APIRouter, include_router, StaticFiles, Jinja2Templates
- Direct codebase analysis — `jellyswipe/__init__.py` (839 lines), `jellyswipe/auth.py`, `jellyswipe/db.py`, `tests/conftest.py` (229 lines), all 10 test files

### Secondary (MEDIUM confidence)
- FastAPI GitHub Discussion #7572, Marcelo Tryle blog — `await request.is_disconnected()` canonical SSE disconnect pattern
- FastAPI GitHub Discussion #6395 — gevent incompatibility with asyncio
- starlette-flask GitHub — Flask/Starlette cookie format incompatibility documentation
- Forethought Engineering blog (2023) — practical Flask to FastAPI migration covering `flask.g` / `current_app`
- FastAPI GitHub Issue #510 — router prefix doubling documentation

### Tertiary (LOW confidence — verify during Phase 7)
- FastAPI GitHub Issue #1273 — sync TestClient limitations with async SSE streaming; behavior may have changed in Starlette 1.0.0

---
*Research completed: 2026-05-01*
*Ready for roadmap: yes*
