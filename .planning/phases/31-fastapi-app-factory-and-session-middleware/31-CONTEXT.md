# Phase 31: FastAPI App Factory and Session Middleware - Context

**Gathered:** 2026-05-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the Flask factory header in `jellyswipe/__init__.py` with a FastAPI app factory while keeping all existing route handlers in place (as FastAPI routes). Wire `SessionMiddleware`, `ProxyHeadersMiddleware`, `XSSSafeJSONResponse`, CSP/request-ID middleware, and lifespan DB initialization. Phase 33 will extract routes into domain routers; Phase 31's job is to make a bootable, fully-wired FastAPI host.

**In scope:**
- Replace `Flask(__name__, ...)` with `FastAPI(lifespan=lifespan)` factory pattern
- Port all 839-line monolith route handlers to FastAPI route syntax (keeping them in `__init__.py`)
- Register `SessionMiddleware` using `FLASK_SECRET` env var
- Register `ProxyHeadersMiddleware` (uvicorn) as ProxyFix equivalent
- Implement `XSSSafeJSONResponse` (subclass `JSONResponse`, override `render()`) and set as `app.default_response_class`
- Implement `RequestIdMiddleware` as a `BaseHTTPMiddleware` subclass; store request ID in `request.state.request_id`
- Add CSP header (`Content-Security-Policy`) via `@app.middleware("http")` or combined into `RequestIdMiddleware`
- Lifespan: call `init_db()` on startup; log graceful shutdown and reset `_provider_singleton` on teardown
- Preserve `FLASK_SECRET` env var name; wire `https_only` to `SESSION_COOKIE_SECURE` env var
- Keep module-level env var validation at import time (unchanged from current pattern)
- Session cookie: 14-day max_age (Starlette default), `same_site="lax"`

**Out of scope:**
- Extracting routes into domain routers (Phase 33)
- Auth module rewrite / `dependencies.py` (Phase 32)
- SSE route async migration (Phase 34)
- Test suite migration to FastAPI TestClient (Phase 35)
- Pydantic request/response models (v2.1)

</domain>

<decisions>
## Implementation Decisions

### Route Handling

- **D-01:** In-place port — Phase 31 rewrites the `create_app()` / factory header to FastAPI but keeps all route handlers in `__init__.py`. Phase 33 extracts them into domain routers. The app must be fully functional (all routes callable) after Phase 31.

### XSS-Safe JSON

- **D-02:** Implement `XSSSafeJSONResponse` as a `JSONResponse` subclass that overrides `render()` to escape `<`, `>`, and `&` as `<`, `>`, `&`. Set globally via `app.default_response_class = XSSSafeJSONResponse`. No per-route annotation needed.

### Lifespan

- **D-03:** Use the `@asynccontextmanager` lifespan pattern (not deprecated `@app.on_event`). Startup: call `init_db()`. Teardown: log graceful shutdown message + reset `_provider_singleton = None` so the process starts clean on restart.

### ProxyFix

- **D-04:** Include `uvicorn.middleware.proxy_headers.ProxyHeadersMiddleware` in Phase 31. Equivalent to the existing `ProxyFix(x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)`.

### Session Cookies

- **D-05:** `SessionMiddleware` params: `secret_key=os.environ["FLASK_SECRET"]`, `max_age=14*24*60*60` (Starlette default, 14 days), `same_site="lax"`, `https_only=os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true'`.
- **D-06:** Behavior change vs. Flask: Flask sessions were browser-session cookies (no persistent expiry). The new 14-day max_age means sessions persist across browser restarts. This is intentional — acceptable for v2.0.

### Request ID Middleware

- **D-07:** Implement `RequestIdMiddleware` as a `BaseHTTPMiddleware` subclass. Generates `req_{unix_ts}_{4-byte hex}` ID, stores in `request.state.request_id`, and injects `X-Request-Id` response header. The existing `generate_request_id()` helper function is reused.
- **D-08:** CSP header can be added in the same `RequestIdMiddleware.dispatch()` call on the response, or as a separate `@app.middleware("http")` — planner's choice. What matters: both `X-Request-Id` and `Content-Security-Policy` must appear on all responses.
- **D-09:** Route handlers that previously read `request.environ['jellyswipe.request_id']` must be updated to `request.state.request_id`.

### Env Validation

- **D-10:** Module-level env var validation (`TMDB_ACCESS_TOKEN`, `FLASK_SECRET`, `JELLYFIN_URL`, Jellyfin auth) stays at import time, unchanged. SSRF check (`validate_jellyfin_url`) also stays at import time. No test changes needed.

### Flask Session API Migration

- **D-11:** Flask's `session` dict (imported from `flask`) must be replaced. In FastAPI, `request.session` (from `SessionMiddleware`) is the equivalent dict. Route handlers that use `session.get(...)`, `session['key'] = val`, `session.pop(...)` must be updated to receive `request: Request` as a parameter and access `request.session` instead.
- **D-12:** `flask.g` (request-scoped globals for `user_id`, `jf_token`) has no direct FastAPI equivalent. For Phase 31, these can be stored in `request.state` (e.g., `request.state.user_id`). Phase 32 will replace this with `Depends()` injection.

### Flask API Removal

- **D-13:** All `flask` imports are removed: `Flask`, `jsonify`, `request` (replaced by `fastapi.Request`), `session`, `Response`, `render_template`, `abort`, `g`. The `try/except ImportError` guard from Phase 30 is removed.
- **D-14:** `jsonify(...)` calls replaced with `XSSSafeJSONResponse(content={...})` or by returning dicts (FastAPI auto-serializes dicts using the default response class).
- **D-15:** `render_template("index.html")` replaced with `Jinja2Templates` + `TemplateResponse`.
- **D-16:** `abort(404)` / `abort(403)` replaced with `raise HTTPException(status_code=404)` / `HTTPException(status_code=403)`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and Roadmap
- `.planning/REQUIREMENTS.md` — FAPI-01, FAPI-04, ARCH-04 fully specify this phase; also check DEP-01 (already done in Phase 30)
- `.planning/ROADMAP.md` §Phase 31 — Success criteria (4 items): bootable app, SessionMiddleware on FLASK_SECRET, XSS escaping, X-Request-Id + CSP headers

### Current Application
- `jellyswipe/__init__.py` — 839-line Flask monolith; this file is fully rewritten by Phase 31
- `jellyswipe/auth.py` — `create_session()`, `login_required`, `destroy_session()`; Flask-coupled; Phase 31 keeps calling these (Phase 32 rewrites auth)
- `jellyswipe/db.py` — `init_db()`, `get_db()`, `get_db_closing()`; unchanged in Phase 31
- `jellyswipe/templates/index.html` — SPA shell; served by `Jinja2Templates.TemplateResponse`

### Prior Phase Context
- `.planning/phases/30-package-deployment-infrastructure/30-CONTEXT.md` — D-05 through D-12 cover Uvicorn process model and package versions already installed

### Research
- `.planning/research/PITFALLS.md` §SSE-2, SSE-3 — Keep route handlers as sync `def`; only SSE generator is `async def` (Phase 34)
- `.planning/research/PITFALLS.md` §SSE-1, SSE-4 — SSE-specific CancelledError handling (Phase 34, not this phase)
- `.planning/research/STACK.md` — Verified package versions; itsdangerous (SessionMiddleware), jinja2 (templates), python-multipart (forms) are already in pyproject.toml from Phase 30

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `generate_request_id()` — already defined in `__init__.py`; reuse directly in `RequestIdMiddleware`
- `_XSSSafeJSONProvider.dumps()` — the escaping logic (`.replace("<", "\\u003c")` etc.) is already implemented; copy into `XSSSafeJSONResponse.render()`
- `_check_rate_limit()` — already defined; keep in place for Phase 31 (rate limiter wiring migrates to `dependencies.py` in Phase 32)
- `_get_cursor()`, `_set_cursor()`, `_resolve_movie_meta()` — pure helpers; keep as-is
- CSP policy string — already defined in `add_csp_header()`; copy verbatim into the new middleware

### Established Patterns
- Module-level singletons (`_provider_singleton`, `_token_user_id_cache`) stay as module-level state in `__init__.py` for Phase 31
- `request.environ['jellyswipe.request_id']` → `request.state.request_id` (FastAPI idiom)
- `flask.session` → `request.session` (from `SessionMiddleware`)
- `flask.g.user_id`, `flask.g.jf_token` → `request.state.user_id`, `request.state.jf_token` (temporary; Phase 32 replaces with `Depends()`)
- `flask.abort(N)` → `raise HTTPException(status_code=N)`
- `jsonify(...)` → return dict (FastAPI auto-serializes via `default_response_class`) or `XSSSafeJSONResponse(content=...)`

### Integration Points
- `jellyswipe/auth.py` — `login_required` decorator is Flask-coupled (`@wraps(f)` with Flask `request`/`session`/`g`); Phase 31 must either temporarily keep the Flask-coupled version working or inline the auth check in routes (Phase 32 rewrites properly)
- `jellyswipe/db.py` — `get_db()` / `get_db_closing()` are framework-agnostic; use unchanged
- `jellyswipe/rate_limiter.py` — `rate_limiter.check(endpoint, ip, limit)` is framework-agnostic; pass `request.client.host` instead of Flask's `request.remote_addr`
- Middleware stack order (FastAPI/Starlette LIFO): `ProxyHeadersMiddleware` outermost → `SessionMiddleware` → `RequestIdMiddleware` innermost

</code_context>

<specifics>
## Specific Ideas

- `login_required` in `jellyswipe/auth.py` is Flask-specific (`flask.request`, `flask.session`, `flask.g`). Phase 31 will need to either: (a) temporarily inline the auth check in routes that use it, or (b) convert `@login_required` to accept a FastAPI `Request` parameter. Phase 32 supersedes this entirely with `Depends(require_auth)`, so the Phase 31 solution only needs to work; it does not need to be clean.
- The `XSSSafeJSONResponse` class name should exactly match the one referenced in STATE.md and ARCHITECTURE.md so it is easy to grep/trace across phases.
- Starlette's `SessionMiddleware` default `max_age` is `14 * 24 * 60 * 60` — use the explicit expression (not just the number) in code so the value is readable.

</specifics>

<deferred>
## Deferred Ideas

- **Pydantic request/response models** — v2.1 requirement (ARCH-02), explicitly out of scope for v2.0
- **`httpx.AsyncClient` migration** — Option B from PITFALLS.md SSE-3; deferred; sync `requests` stays for v2.0
- **Coverage threshold restoration** — `--cov-fail-under` removed in Phase 30, restored in Phase 35
- **Multi-worker Uvicorn** — Single-process decision from Phase 30 (D-05); workers can be added via deploy-time env override post-v2.0

</deferred>

---

*Phase: 31-FastAPI App Factory and Session Middleware*
*Context gathered: 2026-05-02*
