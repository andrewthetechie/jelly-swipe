# Phase 31: FastAPI App Factory and Session Middleware - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-02
**Phase:** 31-fastapi-app-factory-and-session-middleware
**Areas discussed:** Route handling, XSSSafeJSONResponse scope, Lifespan teardown, ProxyFix, Session max_age, SESSION_COOKIE_SECURE wiring, Module-level env validation, Request ID middleware

---

## Route Handling in Phase 31

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Clean slate | Phase 31 creates minimal factory with zero routes; 404s everywhere; Phase 33 adds routes | |
| (b) In-place port | Phase 31 rewrites factory header to FastAPI, keeps all route handlers in `__init__.py` as FastAPI routes; Phase 33 extracts them | ✓ |

**User's choice:** 1b — In-place port
**Notes:** App must remain fully functional after Phase 31. Routes stay in `__init__.py` until Phase 33 extracts them.

---

## XSSSafeJSONResponse Scope

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Global default | Set `app.default_response_class = XSSSafeJSONResponse`; all routes auto-safe | ✓ |
| (b) Explicit per-route | Routes manually specify `response_class=XSSSafeJSONResponse` | |

**User's choice:** 2a — Global default
**Notes:** Mirrors the Flask `app.json = _XSSSafeJSONProvider(app)` behavior. No per-route annotation needed.

---

## Lifespan Teardown

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Startup only | `init_db()` in startup; nothing in teardown | |
| (b) Startup + shutdown | `init_db()` on startup; graceful shutdown log + provider reset on teardown | ✓ |

**User's choice:** 3b — Startup + shutdown
**Notes:** Provider singleton reset on shutdown for clean restarts.

---

## ProxyFix Inclusion

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Include in Phase 31 | Add `ProxyHeadersMiddleware` as part of app factory wiring | ✓ |
| (b) Defer | Skip for Phase 31; add in later hardening phase | |

**User's choice:** 4a — Include in Phase 31
**Notes:** Maintains parity with existing `ProxyFix(x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)`.

---

## Session max_age

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Preserve Flask default | `max_age=None`; browser-session cookies | |
| (b) Use Starlette default | 14-day persistent cookies | ✓ |
| (c) Configurable | `SESSION_MAX_AGE` env var, defaulting to 14 days | |

**User's choice:** 1b — 14-day persistent cookies
**Notes:** Behavioral change from Flask (browser-session) to Starlette default (14-day). Intentional and acceptable for v2.0.

---

## SESSION_COOKIE_SECURE Wiring

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Wire to env var | `https_only=os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true'` | ✓ |
| (b) Hard-code False | Drop the env var concern | |

**User's choice:** 2a — Wire to existing env var
**Notes:** Operator config unchanged; HTTP deployments (Docker, local dev) continue to work without setting this env var.

---

## Module-Level Env Validation

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Keep at import time | No change; tests keep existing conftest.py `os.environ.setdefault` pattern | ✓ |
| (b) Move into lifespan | Raise at app startup; cleaner factory; needs test adjustment in Phase 35 | |

**User's choice:** 3a — Keep at import time
**Notes:** Zero test changes required. Env validation at import is a known anti-pattern but acceptable for the duration of v2.0.

---

## Request ID Middleware

| Option | Description | Selected |
|--------|-------------|----------|
| (a) `@app.middleware("http")` decorator | Simple function-based; less boilerplate | |
| (b) `BaseHTTPMiddleware` class | Named class; easier to unit-test; matches ProxyHeadersMiddleware style | ✓ |

**User's choice:** 4b — `BaseHTTPMiddleware` class
**Notes:** `RequestIdMiddleware` as a named class; consistent with other middleware in the stack.

---

## Claude's Discretion

- Whether CSP header is combined into `RequestIdMiddleware.dispatch()` or as a separate `@app.middleware("http")` — either works as long as both headers appear on all responses
- Exact middleware stack registration order (LIFO: ProxyHeaders → Session → RequestId)
- How to temporarily handle `login_required` Flask coupling until Phase 32 rewrites auth

## Deferred Ideas

- Pydantic request/response models → v2.1 (ARCH-02)
- `httpx.AsyncClient` migration → deferred; sync `requests` stays for v2.0
- Coverage threshold restoration → Phase 35
- Multi-worker Uvicorn → post-v2.0 deploy-time config
