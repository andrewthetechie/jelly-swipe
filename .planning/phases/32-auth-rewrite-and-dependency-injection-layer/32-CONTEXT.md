# Phase 32: Auth Rewrite and Dependency Injection Layer - Context

**Gathered:** 2026-05-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Create `jellyswipe/dependencies.py` as a standalone FastAPI DI module exporting `require_auth()`, `get_db_dep()`, `get_provider()`, and `check_rate_limit()`. Complete the auth rewrite by de-coupling `auth.py` from any remaining Flask surface (it is already de-Flaskified by the Phase 31 bridge). Phase 32 creates the module; Phase 33 wires it into extracted domain routers.

**In scope:**
- Create `jellyswipe/dependencies.py` exporting all four dependency callables
- `require_auth(request: Request)` — Depends()-compatible, returns `AuthUser` dataclass, raises HTTP 401
- `get_db_dep()` — yield dependency wrapping `get_db_closing()`; exposes `DBConn` type alias
- `get_provider()` — moved from `__init__.py` singleton factory; Depends()-compatible
- `check_rate_limit(request: Request)` — Depends()-compatible; uses request path for endpoint inference
- `destroy_session_dep(request: Request)` — Depends()-compatible wrapper around `auth.destroy_session()`
- Unit tests for `auth.py` using a minimal FastAPI test app (no Flask app required)

**Out of scope:**
- Updating routes in `__init__.py` to use `Depends(require_auth)` — Phase 33 wires this during router extraction
- Fixing CR-01 (connection leak in existing routes) and CR-02 (session/vault TTL mismatch) — deferred
- Pydantic request/response models (v2.1)
- SSE route migration (Phase 34)

</domain>

<decisions>
## Implementation Decisions

### `require_auth()` Design

- **D-01:** `require_auth(request: Request)` returns an `AuthUser` dataclass — not a plain tuple. Fields: `jf_token: str`, `user_id: str`. Routes declare: `auth: AuthUser = Depends(require_auth)` and access `auth.jf_token`, `auth.user_id`.
- **D-02:** Internally calls `auth.get_current_token(request.session)` (thin wrapper). If `None`, raises `HTTPException(status_code=401, detail="Authentication required")`.
- **D-03:** `destroy_session_dep(request: Request)` is also exported from `dependencies.py`. It is a Depends()-compatible thin wrapper around `auth.destroy_session(request.session)`.

### `get_db_dep()` Lifecycle

- **D-04:** `get_db_dep()` is a yield dependency — opens the connection, yields it, closes on exit:
  ```python
  def get_db_dep():
      with get_db_closing() as conn:
          yield conn
  ```
  Connection lifetime matches the request/response cycle.
- **D-05:** Expose `DBConn = Annotated[sqlite3.Connection, Depends(get_db_dep)]` as a type alias so routes declare `conn: DBConn` instead of spelling out `Depends(get_db_dep)` inline.

### `check_rate_limit()` Design

- **D-06:** `check_rate_limit(request: Request)` uses **request path inference** — reads `request.url.path` to look up the rate limit config from `_RATE_LIMITS`. No per-route factory argument needed; endpoint key maps from URL path. If the path is not in `_RATE_LIMITS`, the request passes through (no limit applied).
- **D-07:** `check_rate_limit()` is exported as a Depends()-compatible callable. Routes declare: `_: None = Depends(check_rate_limit)` (or it raises `HTTPException(status_code=429)` directly so the return value is unused).

### `get_provider()` Migration

- **D-08:** `get_provider()` moves from the closure inside `create_app()` in `__init__.py` to `dependencies.py` as a module-level function. It continues to use the `_provider_singleton` module-level global — the singleton stays in `__init__.py` until Phase 33 extracts routers and resolves the global reference.

### Phase 32 Scope

- **D-09:** Phase 32 creates `dependencies.py` only. Routes in `__init__.py` continue using `_require_login()` until Phase 33 extracts them into domain routers and wires `Depends(require_auth)` at that time.
- **D-10:** CR-01 (connection leak in existing routes) and CR-02 (session/vault TTL mismatch) are not addressed in Phase 32. The new `get_db_dep()` yield pattern fixes future routes; existing routes in `__init__.py` remain unchanged until Phase 33.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and Roadmap
- `.planning/REQUIREMENTS.md` — ARCH-03 fully specifies this phase (`dependencies.py` with `Depends()` pattern)
- `.planning/ROADMAP.md` §Phase 32 — Success criteria (4 items): zero Flask imports in auth.py, `require_auth()` Depends() returning `(jf_token, user_id)`, `dependencies.py` exports all 4 functions, unit tests pass

### Current Application
- `jellyswipe/auth.py` — Phase 31 bridge; already de-Flaskified. `get_current_token(session_dict)`, `create_session()`, `destroy_session()` are the three callable targets. Phase 32 wraps these.
- `jellyswipe/__init__.py` — `_require_login()` (line ~285) is the Phase 31 bridge being superseded. `get_provider()` (line ~235) and `_check_rate_limit()` (line ~244) move to `dependencies.py`.
- `jellyswipe/db.py` — `get_db_closing()` is the contextmanager that `get_db_dep()` wraps
- `jellyswipe/rate_limiter.py` — `rate_limiter.check(endpoint, ip, limit)` interface; `_RATE_LIMITS` dict maps endpoint keys to limits (must move or reference in `dependencies.py`)

### Prior Phase Context
- `.planning/phases/31-fastapi-app-factory-and-session-middleware/31-CONTEXT.md` — D-11, D-12: `request.session` and `request.state` bridge decisions Phase 32 supersedes

### Code Review
- `.planning/phases/31-fastapi-app-factory-and-session-middleware/31-REVIEW.md` — CR-01 (connection leak) and CR-02 (TTL mismatch) are logged; Phase 32 defers both but planner should note them for Phase 33/35

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `auth.get_current_token(session_dict)` — returns `(jf_token, jf_user_id)` or `None`; `require_auth()` is a thin wrapper raising 401 on `None`
- `auth.destroy_session(session_dict)` — deletes vault entry and clears session; `destroy_session_dep()` wraps this
- `get_db_closing()` in `db.py` — contextmanager that opens, wraps in `with conn:`, and closes; `get_db_dep()` is a one-liner yield around it
- `_provider_singleton` global in `__init__.py` — `get_provider()` reads/writes this; moves to `dependencies.py` but references the global until Phase 33

### Established Patterns
- `Depends()` injection: FastAPI resolves Depends() callables per request, injecting the return value as a route parameter
- `Annotated[T, Depends(fn)]` type alias pattern: declare once at module level, reuse everywhere as a bare type annotation
- yield dependencies: the body before `yield` runs before the response; the body after `yield` runs after (cleanup)

### Integration Points
- `require_auth()` feeds into all authenticated routes in Phase 33 (auth, rooms, media, watchlist)
- `get_db_dep()` + `DBConn` alias used by any route that needs a DB connection — replaces direct `get_db_closing()` calls in route bodies
- `check_rate_limit()` attaches to the routes that currently call `_check_rate_limit("endpoint", request)` — path inference eliminates the per-route string argument
- `get_provider()` used by media/proxy routes; singleton lifecycle unchanged

</code_context>

<specifics>
## Specific Ideas

- `AuthUser` dataclass should be defined in `dependencies.py` (not `auth.py`) since it is a FastAPI DI concept, not a pure auth concept
- Route declaration idiom for auth: `auth: AuthUser = Depends(require_auth)` — then `auth.jf_token`, `auth.user_id`
- Route declaration idiom for DB: `conn: DBConn` — no inline Depends needed
- `check_rate_limit()` path inference: `request.url.path` as the lookup key against `_RATE_LIMITS`. Paths not in the map pass through silently (no 429).

</specifics>

<deferred>
## Deferred Ideas

- **CR-01 fix (connection leak):** New routes in Phase 33 use `get_db_dep()` which fixes the leak; existing routes in `__init__.py` are untouched until extraction
- **CR-02 fix (TTL mismatch):** Session cookie max_age = 14 days vs vault TTL = 24 hours — deferred to Phase 35 or a standalone fix phase
- **`httpx.AsyncClient` migration** — deferred post-v2.0 (from Phase 31 deferred list)
- **Pydantic request/response models** — v2.1 (ARCH-02), out of scope for v2.0

</deferred>

---

*Phase: 32-Auth Rewrite and Dependency Injection Layer*
*Context gathered: 2026-05-02*
