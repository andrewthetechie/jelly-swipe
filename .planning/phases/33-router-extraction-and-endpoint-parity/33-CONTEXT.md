# Phase 33: Router Extraction and Endpoint Parity - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Extract all 21 non-SSE route handlers from the 924-line `jellyswipe/__init__.py` monolith into five domain `APIRouter` modules (`routers/auth.py`, `routers/rooms.py`, `routers/media.py`, `routers/proxy.py`, `routers/static.py`), create a `jellyswipe/config.py` for shared state, and mount all routers on the FastAPI app — with every original URL path, HTTP method, status code, and response shape preserved. Delete dead `/plex/server-info` route.

**In scope:**
- Create `jellyswipe/config.py` with all module-level globals (TMDB_AUTH_HEADERS, JELLYFIN_URL, _token_user_id_cache, env var constants, SSRF validation)
- Create `jellyswipe/routers/` directory with five APIRouter modules
- Extract 21 non-SSE routes into domain routers, wiring `Depends(require_auth)`, `DBConn`, `Depends(check_rate_limit)`, `get_provider()`
- Mount all routers in `__init__.py` app factory
- Switch swipe handler to `DBConn` dependency (fixes CR-01 connection leak)
- Delete dead `/plex/server-info` route (returns 410 Gone)
- SSE route (`/room/{code}/stream`) stays in `__init__.py` — Phase 34 migrates it
- `_get_cursor()`, `_set_cursor()`, `_resolve_movie_meta()` move inline to `routers/rooms.py`

**Out of scope:**
- SSE route async migration (Phase 34)
- Test suite migration to FastAPI TestClient (Phase 35)
- Pydantic request/response models (v2.1)
- Any behavioral changes to route handlers

</domain>

<decisions>
## Implementation Decisions

### Shared State Migration

- **D-01:** Create `jellyswipe/config.py` to hold all module-level globals currently in `__init__.py`: `TMDB_AUTH_HEADERS`, `JELLYFIN_URL`, `_token_user_id_cache`, `TMDB_ACCESS_TOKEN`, `FLASK_SECRET`, SSRF validation, and related env var reads. This is the single source of truth for shared runtime constants.
- **D-02:** `_token_user_id_cache` moves to `config.py` (not `dependencies.py`). All shared mutable state lives in one place.
- **D-03:** Config globals are initialized at import time in `config.py` — same pattern as today. Zero behavioral change from current `__init__.py` initialization.
- **D-04:** SSRF validation (`validate_jellyfin_url`) and `JELLYFIN_URL` both move to `config.py`. Import-time validation fires when `config.py` is first imported.
- **D-05:** Extracted routers import from `jellyswipe.config` (not `jellyswipe`). Example: `from jellyswipe.config import TMDB_AUTH_HEADERS, JELLYFIN_URL`.

### Router-to-Route Mapping

- **D-06:** Route assignments across five routers:

  **routers/auth.py** (6 routes):
  - `GET /auth/provider`
  - `POST /auth/jellyfin-use-server-identity`
  - `POST /auth/jellyfin-login`
  - `POST /auth/logout`
  - `GET /me`
  - `GET /jellyfin/server-info`

  **routers/rooms.py** (10 routes):
  - `POST /room`
  - `POST /room/solo`
  - `POST /room/{code}/join`
  - `POST /room/{code}/swipe`
  - `GET /matches`
  - `POST /room/{code}/quit`
  - `POST /matches/delete`
  - `POST /room/{code}/undo`
  - `GET /room/{code}/deck`
  - `POST /room/{code}/genre`
  - `GET /room/{code}/status`

  **routers/media.py** (3 routes):
  - `GET /get-trailer/{movie_id}`
  - `GET /cast/{movie_id}`
  - `GET /genres`

  **routers/proxy.py** (1 route):
  - `GET /proxy`

  **routers/static.py** (4 routes):
  - `GET /`
  - `GET /manifest.json`
  - `GET /sw.js`
  - `GET /favicon.ico`

- **D-07:** `/genres` goes in `routers/media.py` — it's a Jellyfin provider query (`list_genres`), not a room operation.
- **D-08:** `/matches` and `/matches/delete` go in `routers/rooms.py` — matches are room-scoped data (detected during swipes, stored in `last_match_data` column).
- **D-09:** `/me` goes in `routers/auth.py` — it's a session identity endpoint (returns user_id from auth state).
- **D-10:** `/jellyfin/server-info` goes in `routers/auth.py`. Dead `/plex/server-info` route is **deleted** (not moved to any router).

### Helper Function Placement

- **D-11:** `_get_cursor()`, `_set_cursor()`, and `_resolve_movie_meta()` move inline to `routers/rooms.py` as private module-level functions. They are room-domain helpers only used by room routes.

### Swipe Transaction Integrity

- **D-12:** Swipe handler body is a **verbatim copy** into `routers/rooms.py`. Add a comment marking the `BEGIN IMMEDIATE` block as critical transaction logic. No logic refactoring during extraction.
- **D-13:** Swipe handler switches from direct `get_db_closing()` to `DBConn` dependency (`conn: DBConn`). This fixes CR-01 (connection leak from Phase 31 review) — the yield dependency ensures cleanup even on exceptions. The `BEGIN IMMEDIATE` transaction still works on the same connection.

### Router Mounting

- **D-14:** Each router uses `APIRouter()` with no prefix — routes define their full paths (matching current `@app.get(...)` paths). The prefix is set in exactly one location: the `app.include_router()` call in `__init__.py`. This prevents path-doubling regressions (success criterion #2).
- **D-15:** `__init__.py` becomes the thin app factory: imports routers, calls `app.include_router(auth_router)`, `app.include_router(rooms_router)`, etc. SSE route stays inline.

### Agent's Discretion

- Exact router file organization (imports ordering, docstring style) — follow existing patterns in `dependencies.py` and `auth.py`
- Whether `_APP_ROOT` stays in `__init__.py` or moves to `config.py` — planner decides based on usage
- Rate limit wiring: whether routes use `_: None = Depends(check_rate_limit)` inline or router-level dependency — planner decides
- Error logging pattern in extracted routes (`_logger` setup per router vs shared)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and Roadmap
- `.planning/REQUIREMENTS.md` — ARCH-01 (router extraction into 5 domain routers), FAPI-02 (endpoint parity — identical URL paths, methods, status codes)
- `.planning/ROADMAP.md` §Phase 33 — Success criteria (4 items): 5 router files, URL parity, auth rejection with 401, swipe transaction integrity

### Current Application (source files to extract from)
- `jellyswipe/__init__.py` — 924-line monolith containing all 29 route handlers (21 non-SSE + SSE + static); the extraction source
- `jellyswipe/dependencies.py` — Phase 32 output; exports `AuthUser`, `require_auth()`, `DBConn`, `check_rate_limit()`, `get_provider()`, `destroy_session_dep()`
- `jellyswipe/auth.py` — `get_current_token(session_dict)`, `create_session()`, `destroy_session()` — called by auth router
- `jellyswipe/db.py` — `get_db_closing()`, `init_db()` — DB layer (unchanged this phase)
- `jellyswipe/rate_limiter.py` — `rate_limiter.check(endpoint, ip, limit)` — used by `check_rate_limit()` dependency
- `jellyswipe/ssrf_validator.py` — `validate_jellyfin_url()` — moves to `config.py`

### Prior Phase Context
- `.planning/phases/32-auth-rewrite-and-dependency-injection-layer/32-CONTEXT.md` — D-01 through D-10 define the dependency injection layer this phase wires into routers
- `.planning/phases/31-fastapi-app-factory-and-session-middleware/31-CONTEXT.md` — D-01 through D-16 define the FastAPI app factory, middleware stack, and Flask→FastAPI migration patterns
- `.planning/phases/31-fastapi-app-factory-and-session-middleware/31-REVIEW.md` — CR-01 (connection leak) and CR-02 (TTL mismatch) — CR-01 is fixed in this phase by switching swipe handler to DBConn

### Research
- `.planning/research/PITFALLS.md` — SSE-specific pitfalls (Phase 34, not this phase)
- `.planning/research/STACK.md` — Package versions already installed

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `dependencies.py` — All DI callables ready: `require_auth()`, `DBConn`, `check_rate_limit()`, `get_provider()`, `destroy_session_dep()`. Each router imports what it needs.
- `_RATE_LIMITS` dict — Already in `dependencies.py` with path-based inference. No per-route string argument needed.
- `_infer_endpoint_key()` — Handles path-to-rate-limit-key mapping. Routes just add `_: None = Depends(check_rate_limit)`.
- `XSSSafeJSONResponse` — Set as `app.default_response_class` in Phase 31. Router routes that return dicts automatically use it.
- `generate_request_id()` — Already in `__init__.py`; used by `RequestIdMiddleware`. Not needed in routers.

### Established Patterns
- `Depends()` injection: FastAPI resolves Depends() callables per request, injecting the return value as a route parameter
- `Annotated[T, Depends(fn)]` type alias: `DBConn = Annotated[sqlite3.Connection, Depends(get_db_dep)]` — declare once in `dependencies.py`, use as bare type annotation in routes
- `APIRouter()` with no prefix: Routes define full paths; `app.include_router()` mounts at root (`prefix=""` or no prefix)
- Sync `def` handlers: All route handlers stay as `def` (not `async def`) — only SSE generator is async (Phase 34)
- `get_provider()` lazy import: Uses `import jellyswipe as _app` to avoid circular dependency — same pattern works for routers accessing `config.py`

### Integration Points
- `__init__.py` app factory: Imports all five routers, calls `app.include_router()` for each, keeps SSE route inline
- `jellyswipe/config.py`: New file; imported by routers for constants, imported by `__init__.py` for app factory setup
- `dependencies.py`: Imported by routers for DI callables — no changes needed to this file
- `auth.py`: Imported by `routers/auth.py` for `create_session()`, `get_current_token()`, `destroy_session()`

</code_context>

<specifics>
## Specific Ideas

- Router directory structure: `jellyswipe/routers/__init__.py` (empty or re-exporting all routers) + individual router files
- Swipe handler comment: `# CRITICAL: BEGIN IMMEDIATE transaction — verbatim from Phase 31 __init__.py. Do not refactor.`
- `/plex/server-info` deletion is a one-line removal — the route returns 410 Gone and is dead code from v1.6 cleanup
- `_logger` setup: each router creates its own `logging.getLogger(__name__)` — standard Python pattern
- `watchlist/add` route (POST /watchlist/add) goes in `routers/media.py` — it's a TMDB/Jellyfin media operation

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 33-Router Extraction and Endpoint Parity*
*Context gathered: 2026-05-03*
