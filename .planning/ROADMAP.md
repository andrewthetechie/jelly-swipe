# Roadmap — Jelly Swipe

**Milestone:** v2.0 Flask → FastAPI + MVC Refactor
**Granularity:** Standard (5-8 phases)
**Current Phase:** 35 - Test Suite Migration and Full Validation (Planning)
**Last Updated:** 2026-05-03

---

## Overview

v2.0 replaces the 839-line Flask WSGI monolith in `jellyswipe/__init__.py` with a FastAPI ASGI application — domain routers, a dependency injection layer, and a thin app factory — while preserving 100% of existing endpoint behavior and keeping all 324 tests green. The migration runs in dependency order: infrastructure first, then the app factory skeleton, then auth (the highest-coupling file that every router depends on), then router extraction, then the highest-risk SSE async generator, and finally test suite migration as the validation gate.

**Phases:** 6
**Requirements:** 9 (FAPI-01, FAPI-02, FAPI-03, FAPI-04, ARCH-01, ARCH-03, ARCH-04, DEP-01, TST-01)
**Starting Phase:** 30 (continuing from v1.7 Phase 29)

---

## Milestones

- ✅ **v1.0–v1.7** — Phases 1–29 (all shipped)
- 🚧 **v2.0 Flask → FastAPI + MVC Refactor** — Phases 30–35 (in progress)

---

## Phases

<details>
<summary>✅ v1.0–v1.7 (Phases 1–29) — ALL SHIPPED</summary>

- [x] Phase 1–9: v1.0 Jellyfin support
- [x] Phase 10–13: v1.2 uv + package layout + Plex removal
- [x] Phase 14–17: v1.3 unit tests
- [x] Phase 18: v1.4 authorization hardening
- [x] Phase 19–22: v1.5 XSS security fix
- [x] Phase 23–26: v1.6 Plex reference cleanup
- [x] Phase 27–29: v1.7 SSE/SQLite architecture fix

</details>

### v2.0 Flask → FastAPI + MVC Refactor (Phases 30–35)

**Milestone Goal:** Replace Flask with FastAPI and Uvicorn, split the 839-line monolith into domain routers with dependency injection, and migrate all 324 tests to FastAPI's TestClient — with zero change to endpoint behavior.

- [x] **Phase 30: Package and Deployment Infrastructure** — Swap Flask/Gunicorn/gevent for FastAPI/Uvicorn in pyproject.toml; update Dockerfile CMD; zero logic changes (completed 2026-05-02)
- [x] **Phase 31: FastAPI App Factory and Session Middleware** — Create the FastAPI app factory with SessionMiddleware, security headers, XSS-safe JSON response class, and lifespan DB initialization (completed 2026-05-03)
- [x] **Phase 32: Auth Rewrite and Dependency Injection Layer** — De-Flaskify auth.py; create dependencies.py with require_auth(), get_db_dep(), get_provider() (completed 2026-05-03)
- [x] **Phase 33: Router Extraction and Endpoint Parity** — Split all 21 non-SSE routes from the monolith into five domain APIRouter modules; every original URL path works (completed 2026-05-03)
- [x] **Phase 34: SSE Route Migration** — Migrate the SSE stream endpoint to an async generator with await asyncio.sleep() and try/finally connection cleanup (completed 2026-05-03)
- [ ] **Phase 35: Test Suite Migration and Full Validation** — Replace Flask test client with FastAPI TestClient; all 324 tests pass; Docker build starts with Uvicorn

---

## Phase Details

### Phase 30: Package and Deployment Infrastructure

**Goal**: The dependency set reflects the FastAPI/Uvicorn stack so that all subsequent code changes have the correct packages available and the container starts correctly.

**Depends on**: Phase 29 (v1.7 complete)

**Requirements**: DEP-01

**Success Criteria** (what must be TRUE):
  1. `uv sync` completes cleanly with Flask, Gunicorn, gevent, and Werkzeug absent and fastapi, uvicorn[standard], itsdangerous, jinja2, python-multipart, and httpx present in the resolved environment
  2. `docker build` succeeds and the resulting container starts with the Uvicorn CMD without errors
  3. No application logic has changed — existing test files import cleanly (framework-agnostic tests still pass)

**Plans**: 1 plan

Plans:
- [x] 30-01-PLAN.md — Update pyproject.toml, regenerate uv.lock, update Dockerfile CMD, add Flask import guard

---

### Phase 31: FastAPI App Factory and Session Middleware

**Goal**: A bootable FastAPI application exists — with session handling, security headers, XSS-safe JSON serialization, and lifespan DB initialization — so that router and dependency work in later phases has a stable host application to mount onto.

**Depends on**: Phase 30

**Requirements**: FAPI-01, FAPI-04, ARCH-04

**Success Criteria** (what must be TRUE):
  1. `from jellyswipe import app` imports a FastAPI instance (not Flask); `uvicorn jellyswipe:app` starts without errors
  2. `SessionMiddleware` is registered on the app using the `FLASK_SECRET` environment variable so existing operator deployments need no env change
  3. JSON responses from the app escape `<`, `>`, and `&` — the XSS-safe serialization behavior from v1.5 is preserved
  4. The `X-Request-Id` and `Content-Security-Policy` headers are present on responses, matching the v1.7 behavior

**Plans**: 1 plan

Plans:
- [x] 31-01-PLAN.md — Rewrite Flask monolith to FastAPI app factory with middleware stack, XSS-safe JSON, and all 29 routes converted

---

### Phase 32: Auth Rewrite and Dependency Injection Layer

**Goal**: All Flask-specific imports are removed from `auth.py` and shared per-request logic (auth checking, DB connection, provider access, rate limiting) is available as FastAPI Depends() callables — unblocking every router that needs authenticated access.

**Depends on**: Phase 31

**Requirements**: ARCH-03

**Success Criteria** (what must be TRUE):
  1. `jellyswipe/auth.py` contains zero Flask imports; session access uses `request.session` (Starlette) instead of `flask.session`
  2. `require_auth()` is a FastAPI Depends() function that returns `(jf_token, user_id)` and raises HTTP 401 for unauthenticated requests — replacing the `@login_required` decorator
  3. `jellyswipe/dependencies.py` exists and exports `get_db_dep()`, `get_provider()`, `require_auth()`, and `check_rate_limit()` — each working as a standalone FastAPI dependency
  4. Unit tests for `auth.py` pass using a minimal FastAPI test app (no Flask app required)

**Plans**: 1 plan

Plans:
- [x] 32-01-PLAN.md — Create dependencies.py with all DI callables; rewrite test_auth.py with FastAPI TestClient

---

### Phase 33: Router Extraction and Endpoint Parity

**Goal**: All 21 non-SSE route handlers are extracted from the Flask monolith into five domain APIRouter modules and mounted on the FastAPI app — with every original URL path, HTTP method, status code, and response shape preserved.

**Depends on**: Phase 32

**Requirements**: ARCH-01, FAPI-02

**Success Criteria** (what must be TRUE):
  1. Five router files exist — `routers/auth.py`, `routers/rooms.py`, `routers/media.py`, `routers/proxy.py`, `routers/static.py` — each containing only routes for their domain
  2. Every original URL path responds with its original HTTP method and status code; no 404s or path-doubling regressions (router prefix set in exactly one location)
  3. All authenticated routes correctly reject unauthenticated requests with HTTP 401 using the `require_auth` dependency
  4. The swipe handler's `BEGIN IMMEDIATE` transaction logic is preserved and produces correct match detection behavior

**Plans**: 2 plans

Plans:
- [x] 33-01-PLAN.md — Create config.py foundation and extract 4 simpler routers (auth, static, media, proxy)
- [x] 33-02-PLAN.md — Extract rooms router (swipe transaction) and refactor __init__.py into thin app factory

---

### Phase 34: SSE Route Migration

**Goal**: The SSE stream endpoint works correctly under Uvicorn — using an async generator with `await asyncio.sleep()` so the event loop is never blocked — and SQLite connections are guaranteed to close on client disconnect.

**Depends on**: Phase 33

**Requirements**: FAPI-03

**Success Criteria** (what must be TRUE):
  1. `/room/{code}/stream` returns a `StreamingResponse` driven by an `async def generate()` using `await asyncio.sleep()` — `time.sleep()` does not appear anywhere in the SSE code path
  2. The `Cache-Control: no-cache` and `X-Accel-Buffering: no` headers are present on SSE responses (nginx proxy compatibility preserved)
  3. Closing a browser tab while an SSE stream is active causes the SQLite connection held by that generator to close — verified by `try/finally` connection cleanup in the async generator
  4. SSE events (match notifications, room-full signal, room-closed signal, heartbeat) arrive at the browser in the same format as before migration

**Plans**: 2 plans

Plans:
- [x] 34-01-PLAN.md — Add sse-starlette>=3.4.1 to pyproject.toml and regenerate uv.lock
- [x] 34-02-PLAN.md — Add async SSE route to rooms.py and remove inline SSE block from __init__.py

---

### Phase 35: Test Suite Migration and Full Validation

**Goal**: All 324 tests run against the FastAPI app using TestClient — the session_transaction() pattern is replaced throughout, and the full suite passes — confirming behavioral parity with the pre-migration Flask app.

**Depends on**: Phase 34

**Requirements**: TST-01, FAPI-01

**Success Criteria** (what must be TRUE):
  1. All 324 tests pass with `uv run pytest` — zero failures (max 4 pre-existing failures documented)
  2. No test file contains `session_transaction()`, `response.get_json()`, `response.data`, or `from flask` — all Flask test client patterns replaced with FastAPI equivalents
  3. `app.dependency_overrides` cleanup is managed through fixtures with teardown — no override state leaks between test functions
  4. `docker build` succeeds and `docker run` starts the container with Uvicorn serving on port 5005

**Plans**: 6 plans

Plans:
**Wave 1**
- [x] 35-01-PLAN.md — Rewrite conftest.py with FastAPI TestClient fixtures; wire SECRET_KEY in create_app()

**Wave 2** *(blocked on Wave 1 completion)*
- [ ] 35-02-PLAN.md — Migrate test_routes_room.py and test_routes_xss.py
- [ ] 35-03-PLAN.md — Migrate test_route_authorization.py and test_routes_auth.py (real-auth path)
- [ ] 35-04-PLAN.md — Migrate test_routes_sse.py

**Wave 3** *(blocked on Wave 2 completion)*
- [ ] 35-05-PLAN.md — Migrate test_routes_proxy.py and test_error_handling.py

**Wave 4** *(blocked on Wave 3 completion)*
- [ ] 35-06-PLAN.md — Full suite run, REQUIREMENTS.md update, Docker build verification

---

## Progress

**Execution Order:**
Phases execute in numeric order: 30 → 31 → 32 → 33 → 34 → 35

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 30. Package and Deployment Infrastructure | 1/1 | Complete    | 2026-05-02 |
| 31. FastAPI App Factory and Session Middleware | 0/1 | Not started | - |
| 32. Auth Rewrite and Dependency Injection Layer | 1/1 | Complete   | 2026-05-03 |
| 33. Router Extraction and Endpoint Parity | 2/2 | Complete    | 2026-05-03 |
| 34. SSE Route Migration | 2/2 | Complete   | 2026-05-03 |
| 35. Test Suite Migration and Full Validation | 1/6 | In Progress|  |

---

## Milestone Context

**Shipped Milestones:**
- v1.0 (Jellyfin support): Phases 1–9 ✅
- v1.1 (Rename): No numbered phases ✅
- v1.2 (uv + Package Layout + Plex Removal): Phases 10–13 ✅
- v1.3 (Unit Tests): Phases 14–17 ✅
- v1.4 (Authorization Hardening): Phase 18 ✅
- v1.5 (XSS Security Fix): Phases 19–22 ✅
- v1.6 (Plex Reference Cleanup): Phases 23–26 ✅
- v1.7 (SSE/SQLite Architecture Fix): Phases 27–29 ✅

**Current Milestone:** v2.0 Flask → FastAPI + MVC Refactor — Phases 30–35

---

*Roadmap created: 2026-05-01*
*Last updated: 2026-05-03 (Phase 35 planned — 6 plans)*
