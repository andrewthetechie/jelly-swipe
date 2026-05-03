---
phase: 31-fastapi-app-factory-and-session-middleware
plan: "01"
subsystem: app-factory
tags: [fastapi, middleware, sessions, xss-defense, lifespan]
dependency_graph:
  requires: []
  provides:
    - "FastAPI app factory with SessionMiddleware, ProxyHeadersMiddleware, RequestIdMiddleware"
    - "XSSSafeJSONResponse for XSS-safe JSON output"
    - "All 29 routes converted from Flask to FastAPI syntax"
    - "Phase 31 auth bridge (create_session/destroy_session accept session_dict)"
  affects:
    - "jellyswipe/__init__.py — complete rewrite"
    - "jellyswipe/auth.py — Flask imports removed, session_dict bridge added"
tech_stack:
  added:
    - "fastapi.FastAPI — app factory replacing Flask"
    - "starlette.middleware.sessions.SessionMiddleware — cookie session management"
    - "uvicorn.middleware.proxy_headers.ProxyHeadersMiddleware — ProxyFix equivalent"
    - "starlette.middleware.base.BaseHTTPMiddleware — base for RequestIdMiddleware"
    - "starlette.templating.Jinja2Templates — replaces flask.render_template"
    - "fastapi.responses.FileResponse — replaces flask.send_from_directory"
    - "fastapi.responses.StreamingResponse — replaces flask.Response for SSE"
  patterns:
    - "asynccontextmanager lifespan pattern for startup/teardown (replaces @app.on_event)"
    - "request.state for request-scoped values (replaces flask.g)"
    - "request.session for session access (from SessionMiddleware)"
    - "HTTPException for error responses (replaces flask.abort)"
    - "LIFO middleware order: RequestIdMiddleware -> SessionMiddleware -> ProxyHeadersMiddleware"
key_files:
  created: []
  modified:
    - "jellyswipe/__init__.py — complete Flask-to-FastAPI rewrite; 33 routes registered"
    - "jellyswipe/auth.py — removed Flask imports; session_dict bridge pattern"
decisions:
  - "D-01: All routes kept in __init__.py for Phase 31; Phase 33 extracts to domain routers"
  - "D-02: XSSSafeJSONResponse subclasses JSONResponse and overrides render() to escape < > &"
  - "D-03: asynccontextmanager lifespan calls init_db() on startup; resets _provider_singleton on teardown"
  - "D-04: ProxyHeadersMiddleware added as outermost middleware (LIFO order)"
  - "D-05: SessionMiddleware with FLASK_SECRET, max_age=14*24*60*60, same_site=lax, https_only from SESSION_COOKIE_SECURE env"
  - "D-07: RequestIdMiddleware generates req_{unix_ts}_{4-byte hex} and stores in request.state.request_id"
  - "D-08: CSP header added in RequestIdMiddleware.dispatch() alongside X-Request-Id"
  - "D-11: Flask session replaced with request.session throughout all routes"
  - "D-12: flask.g.user_id/jf_token replaced with request.state.user_id/jf_token"
  - "D-13: All Flask imports removed from both __init__.py and auth.py"
  - "POST routes with JSON body use async def + await request.json() for reliable body parsing"
metrics:
  duration: "4m"
  completed_date: "2026-05-03"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
---

# Phase 31 Plan 01: FastAPI App Factory and Session Middleware Summary

FastAPI app factory rewrite of 848-line Flask monolith with SessionMiddleware, ProxyHeadersMiddleware, XSSSafeJSONResponse, RequestIdMiddleware (CSP+request-ID), and lifespan DB init; all 29 Flask routes converted to FastAPI syntax with session/g migration.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Rewrite app factory, middleware, helpers, and bridge auth.py | dd10393 | jellyswipe/__init__.py, jellyswipe/auth.py |
| 2 | Verify app boots and middleware stack works | dd10393 | (verification only — no new commits needed) |

## Verification Results

All success criteria met:

1. `from jellyswipe import app` imports a `FastAPI` instance — CONFIRMED
2. App has 33 registered routes (>20 minimum) — CONFIRMED
3. Zero Flask imports in `jellyswipe/__init__.py` — CONFIRMED
4. Zero Flask imports in `jellyswipe/auth.py` — CONFIRMED
5. Zero gevent imports — CONFIRMED
6. `XSSSafeJSONResponse` class present and escapes `<`, `>`, `&` as `<`, `>`, `&` — CONFIRMED
7. `SessionMiddleware` registered with `FLASK_SECRET`, `max_age=14*24*60*60`, `same_site=lax` — CONFIRMED
8. `ProxyHeadersMiddleware` registered (outermost) — CONFIRMED
9. `RequestIdMiddleware` as `BaseHTTPMiddleware` subclass — CONFIRMED
10. `asynccontextmanager` lifespan registered — CONFIRMED
11. `HTTPException` used for error responses — CONFIRMED
12. `Jinja2Templates.TemplateResponse` for HTML rendering — CONFIRMED

## Deviations from Plan

### Auto-selected Implementation Details

**1. [Rule 2 - Enhancement] POST route body parsing uses async def + await request.json()**

- **Found during:** Task 1
- **Issue:** Plan Task 1 noted that sync FastAPI routes can't call `await request.json()`. The plan suggested using `body: dict = None` parameter annotation. However, FastAPI's auto-parsing of `body: dict` would require `Content-Type: application/json` header handling that's less flexible than direct body reading.
- **Fix:** Routes that need to read JSON POST bodies (`/auth/jellyfin-login`, `/room/{code}/swipe`, `/matches/delete`, `/room/{code}/undo`, `/room/{code}/genre`) were implemented as `async def` with `await request.json()`. This is cleaner than the `body: dict = None` annotation approach since routes already need `request: Request`.
- **Files modified:** `jellyswipe/__init__.py`
- **Commit:** dd10393

**2. [Rule 2 - Enhancement] `_require_login` used as inline function call, not decorator**

- **Found during:** Task 1
- **Issue:** The plan specified replacing `@login_required` with `_require_login(request)` inline — implemented exactly as specified. The auth check raises `HTTPException(status_code=401)` for unauthenticated requests.
- **Fix:** Implemented as specified in the plan.
- **Files modified:** `jellyswipe/__init__.py`
- **Commit:** dd10393

**3. [Rule 1 - Bug] `create_session`/`destroy_session` in auth.py accept `session_dict` parameter**

- **Found during:** Task 1
- **Issue:** The original `auth.py` used `flask.session` (global proxy) directly. After removing Flask, these functions needed a way to access the session.
- **Fix:** Updated function signatures to accept `session_dict: dict` parameter. Callers in `__init__.py` pass `request.session`. The `login_required` decorator (Flask-specific) was removed entirely since `__init__.py` uses `_require_login(request)` inline.
- **Files modified:** `jellyswipe/auth.py`
- **Commit:** dd10393

## Known Stubs

None — all routes are fully implemented with the FastAPI framework.

## Threat Flags

No new security surface beyond what was documented in the plan's threat model. All T-31-01 through T-31-07 mitigations are implemented:
- T-31-01 (Spoofing): SessionMiddleware with FLASK_SECRET, same_site=lax, https_only configurable
- T-31-02 (Tampering): XSSSafeJSONResponse escapes < > & in all JSON output
- T-31-03 (Tampering): ProxyHeadersMiddleware trusts X-Forwarded from reverse proxy
- T-31-04 (Info Disclosure): Request IDs use secrets.token_hex(4) — not predictable
- T-31-05 (Info Disclosure): 5xx errors return generic "Internal server error" via make_error_response
- T-31-06 (DoS): Rate limiter preserved using request.client.host
- T-31-07 (Elevation): _require_login bridge accepted as temporary — Phase 32 replaces

## Self-Check: PASSED

- [x] `jellyswipe/__init__.py` exists: FOUND
- [x] `jellyswipe/auth.py` exists: FOUND
- [x] Commit `dd10393` exists: FOUND
- [x] `from jellyswipe import app; type(app).__name__ == 'FastAPI'`: PASS
- [x] 33 routes registered (>= 20 required): PASS
- [x] Zero Flask imports in both files: PASS
