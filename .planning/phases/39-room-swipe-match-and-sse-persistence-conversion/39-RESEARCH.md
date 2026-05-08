# Phase 39: Room, Swipe, Match, and SSE Persistence Conversion - Research

**Researched:** 2026-05-06
**Domain:** Async SQLAlchemy conversion for room lifecycle, swipe/match mutation, and SSE polling on SQLite
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
## Implementation Decisions

### Room Identity and Lifecycle
- **D-01:** Persisted room, swipe, and match flows keep using the current browser/session identity as the participant key everywhere in this phase.
- **D-02:** If local session state points at a missing or stale room, the app should clear `active_room` and related local room state immediately.
- **D-03:** Solo rooms use the same persistence and service path as multiplayer rooms, controlled by `solo_mode` rather than a separate solo-only stack.
- **D-04:** Room teardown is immediate hard cleanup when a room is closed or emptied; no reconnect or recovery retention is required in Phase 39.

### Swipe and Match Transaction Semantics
- **D-05:** A swipe remains one atomic mutation covering swipe write, deck cursor advance, match detection, and `last_match` update.
- **D-06:** Room swipe mutations must preserve serialized race protection equivalent to the current SQLite `BEGIN IMMEDIATE` behavior.
- **D-07:** Undo and delete behavior must recompute visible match and history state immediately for the affected room or user view.
- **D-08:** Persisted match history plus the room-level `last_match` sentinel remains the source of truth for fast room-status and SSE parity.

### SSE Stream Behavior
- **D-09:** SSE connect should keep sending the latest room snapshot immediately when one is available.
- **D-10:** SSE fanout must only reflect committed room or swipe state; no pre-commit event emission.
- **D-11:** Disconnected or missed clients do not get a replay buffer in this phase; reconnects resubscribe and refresh from current room state.
- **D-12:** Phase 39 keeps the current app-local broadcaster and polling semantics rather than introducing a persistence-backed event bus or outbox.

### Service and Repository Slicing
- **D-13:** Repositories should be split by aggregate concern: rooms, swipes, and matches, with transaction coordination staying in the service layer.
- **D-14:** Service structure should use one room-lifecycle orchestration service plus a dedicated swipe/match mutation service.
- **D-15:** Router migration should happen in vertical slices while keeping endpoint shapes, response bodies, and visible semantics unchanged throughout the conversion.
- **D-16:** Parity coverage should keep the current route-level behavior tests and add focused service and repository tests underneath them.

### the agent's Discretion
None. The user locked the main persistence, transaction, stream, and slicing choices for this phase.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MVC-02 | Room creation, join, quit, deck cursor, genre, and status persistence live behind async room persistence functions. | Use a room repository plus room lifecycle service; keep route handlers as thin controllers only. [VERIFIED: repo grep] |
| MVC-03 | Swipe, match creation, history, undo, and delete persistence live behind async swipe/match persistence functions. | Use a dedicated swipe/match service coordinating room, swipe, and match repositories; keep swipe atomic. [VERIFIED: repo grep] |
| MVC-04 | Route handlers remain controller-level code that delegates database behavior to dependency-injected services or repositories. | Current auth phase already established `DBUoW` and service/repository seams. [VERIFIED: jellyswipe/dependencies.py, jellyswipe/auth.py, jellyswipe/routers/auth.py] |
| PAR-02 | Existing room lifecycle behavior remains compatible for multiplayer and solo rooms. | Preserve current session side effects, `solo_mode`, `ready`, deck cursor initialization, and hard cleanup semantics. [VERIFIED: jellyswipe/routers/rooms.py, tests/test_routes_room.py, tests/test_route_authorization.py] |
| PAR-03 | Existing swipe behavior remains compatible, including deck cursor advancement, undo, right-swipe match detection, and match metadata. | Keep swipe mutation atomic, preserve `last_match_data`, and keep current participant/session matching semantics. [VERIFIED: jellyswipe/routers/rooms.py, tests/test_routes_room.py, tests/test_route_authorization.py, tests/test_routes_xss.py] |
| PAR-04 | Swipe persistence preserves race protection equivalent to the current SQLite `BEGIN IMMEDIATE` behavior. | Keep the SQLite lock acquisition inside a narrow `run_sync()` bridge owned by the same request UoW transaction. [VERIFIED: jellyswipe/routers/rooms.py, jellyswipe/db_uow.py, tests/test_dependencies.py][CITED: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html][CITED: https://www.sqlite.org/lang_transaction.html] |
| PAR-05 | SSE room stream behavior remains async and non-blocking while using async database access for polling. | SSE should open short-lived async DB access inside the generator rather than reusing the request-scoped UoW across the stream lifetime. [VERIFIED: jellyswipe/dependencies.py, jellyswipe/routers/rooms.py, tests/test_routes_sse.py][CITED: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/][CITED: https://github.com/sysid/sse-starlette] |
</phase_requirements>

## Summary

Phase 39 is not a generic ORM conversion; it is a behavior-parity conversion around three already-proven invariants: request-scoped async unit-of-work ownership, SQLite write serialization via `BEGIN IMMEDIATE`, and SSE polling that never blocks the event loop or holds one request session open for an hour. The current code already exposes those seams: auth uses `DBUoW`, swipe already uses `uow.run_sync()`, and the remaining room endpoints still talk to `get_db_closing()` directly. [VERIFIED: jellyswipe/dependencies.py, jellyswipe/auth.py, jellyswipe/db_uow.py, jellyswipe/routers/rooms.py]

The safest plan is a hybrid conversion. Convert room lifecycle, match history, undo, delete, deck, genre, and status to normal async repositories and services using `AsyncSession.execute()` and ORM/Core statements. Keep the swipe mutation on a narrow synchronous bridge invoked by `AsyncSession.run_sync()` so the exact SQLite `BEGIN IMMEDIATE` locking behavior survives while the outer request dependency still owns commit/rollback. [VERIFIED: jellyswipe/routers/rooms.py, tests/test_dependencies.py][CITED: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html][CITED: https://www.sqlite.org/lang_transaction.html]

SSE is the other planning trap. FastAPI `yield` dependencies with default request scope clean up after the response is sent, and `scope="function"` cleans up before the response is sent; neither model makes a request-scoped DB session appropriate for a long-lived stream generator. The current repo already avoids that by opening a dedicated raw SQLite connection inside `generate()`. The async replacement should keep the same lifetime rule, but switch from one long-lived raw connection to short-lived async DB access inside the generator loop so the stream stays non-blocking and does not share a mutable `AsyncSession` across concurrent work. [VERIFIED: jellyswipe/dependencies.py, jellyswipe/routers/rooms.py, tests/test_routes_sse.py][CITED: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/][CITED: https://docs.sqlalchemy.org/en/20/orm/session_basics.html][CITED: https://github.com/sysid/sse-starlette][CITED: https://aiosqlite.omnilib.dev/en/stable/]

**Primary recommendation:** Use async room/match repositories plus two services, but keep swipe serialization on a small `run_sync()` transaction bridge and give SSE its own short-lived async DB access inside the stream generator. [VERIFIED: repo grep][CITED: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html][CITED: https://github.com/sysid/sse-starlette]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Room lifecycle persistence (`/room`, `/room/solo`, join, quit, genre, deck, status) | API / Backend | Database / Storage | FastAPI routes own controller semantics and session mutation; SQLite stores authoritative room state. [VERIFIED: jellyswipe/routers/rooms.py, jellyswipe/models/room.py] |
| Swipe transaction serialization and match creation | API / Backend | Database / Storage | The mutation spans validation, persistence, match detection, and cursor updates in one DB transaction. [VERIFIED: jellyswipe/routers/rooms.py][CITED: https://www.sqlite.org/lang_transaction.html] |
| Match history and room `last_match_data` projection | API / Backend | Database / Storage | Routes expose the projection, but persisted matches plus `rooms.last_match_data` are the state source of truth. [VERIFIED: jellyswipe/routers/rooms.py, jellyswipe/models/match.py, jellyswipe/models/room.py] |
| SSE polling and disconnect handling | API / Backend | Database / Storage | EventSourceResponse and poll loop live in the FastAPI route; room snapshot data comes from the DB. [VERIFIED: jellyswipe/routers/rooms.py, tests/test_routes_sse.py][CITED: https://github.com/sysid/sse-starlette] |
| Stale `active_room` cleanup in session state | API / Backend | — | Session cookie state is managed server-side in request handling, not in the browser or database schema. [VERIFIED: jellyswipe/auth.py, jellyswipe/dependencies.py] |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | 2.0.49 (PyPI upload 2026-04-03) [VERIFIED: PyPI JSON] | Async ORM/Core statements, `AsyncSession`, `run_sync()` bridge | The repo already uses `AsyncSession` UoW wiring, and official docs explicitly support `run_sync()` for sync work under asyncio. [VERIFIED: jellyswipe/db_uow.py][CITED: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html] |
| aiosqlite | 0.22.1 (PyPI upload 2025-12-23) [VERIFIED: PyPI JSON] | Async SQLite driver under SQLAlchemy | Official docs confirm it keeps SQLite work off the main event loop via one shared thread per connection. [CITED: https://aiosqlite.omnilib.dev/en/stable/] |
| FastAPI | 0.136.1 (PyPI upload 2026-04-23) [VERIFIED: PyPI JSON] | Route/dependency lifecycle and response handling | The current app already depends on FastAPI DI boundaries, especially `yield` cleanup scope. [VERIFIED: jellyswipe/dependencies.py][CITED: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sse-starlette | Repo floor `>=3.4.1`; latest PyPI is 3.4.2 (uploaded 2026-05-06) [VERIFIED: pyproject.toml, PyPI JSON] | SSE framing, disconnect handling, heartbeat support | Use for `/room/{code}/stream`; do not replace with a custom SSE encoder. [VERIFIED: jellyswipe/routers/rooms.py][CITED: https://github.com/sysid/sse-starlette] |
| Alembic | 1.18.4 (PyPI upload 2026-02-10) [VERIFIED: PyPI JSON] | Schema baseline already established for this phase | Use only for existing schema assumptions and test bootstrap; Phase 39 does not need a schema redesign. [VERIFIED: .planning/ROADMAP.md, tests/conftest.py] |
| pytest | 9.0.3 in the verified local run [VERIFIED: executed `uv run pytest ...`] | Behavior parity and lower-level regression coverage | Use for route contract tests plus new service/repository tests mandated by D-16. [VERIFIED: tests/, 39-CONTEXT.md] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| SQLAlchemy `run_sync()` bridge for swipe | Pure async ORM/Core rewrite with default transaction handling | Higher risk: SQLite default deferred transactions do not guarantee the same write lock timing as `BEGIN IMMEDIATE`. [CITED: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html][CITED: https://www.sqlite.org/lang_transaction.html] |
| Short-lived async DB access inside the SSE generator | Reuse one request-scoped `DBUoW` or one shared `AsyncSession` for the whole stream | Wrong lifetime model: FastAPI dependency cleanup is tied to request/response scope, and SQLAlchemy says one `AsyncSession` should not be shared across concurrent tasks. [CITED: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/][CITED: https://docs.sqlalchemy.org/en/20/orm/session_basics.html] |
| Repository/service delegation in rooms router | Keep SQL/ORM logic inside route handlers | Violates MVC-04 and conflicts with the auth-phase seam already established. [VERIFIED: jellyswipe/routers/auth.py, jellyswipe/auth.py, .planning/REQUIREMENTS.md] |

**Installation:**
```bash
uv sync
```

**Version verification:** [VERIFIED: PyPI JSON]
- `sqlalchemy` `2.0.49` uploaded `2026-04-03T16:38:11Z`
- `aiosqlite` `0.22.1` uploaded `2025-12-23T19:25:42Z`
- `fastapi` `0.136.1` uploaded `2026-04-23T16:49:42Z`
- `sse-starlette` latest `3.4.2` uploaded `2026-05-06T19:42:12Z`; repo floor is `>=3.4.1`
- `alembic` `1.18.4` uploaded `2026-02-10T16:00:47Z`

## Architecture Patterns

### System Architecture Diagram

The recommended shape below follows the existing route/API boundaries and the verified session-lifetime constraints. [VERIFIED: jellyswipe/routers/rooms.py, jellyswipe/dependencies.py][CITED: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/]

```text
HTTP request
  |
  v
FastAPI room route
  |
  +--> request.session side effects
  |
  +--> RoomLifecycleService ----------------------+
  |        |                                      |
  |        +--> RoomRepository ------------------> rooms table
  |        +--> MatchRepository -----------------> matches table
  |
  +--> SwipeMatchService -------------------------+
           |
           +--> uow.run_sync(serialized_swipe_fn)
                    |
                    +--> BEGIN IMMEDIATE
                    +--> write swipe
                    +--> advance deck cursor
                    +--> detect/create match rows
                    +--> update rooms.last_match_data

SSE request
  |
  v
EventSourceResponse(async generator)
  |
  +--> request.is_disconnected()
  +--> open short-lived async DB access
  +--> read room snapshot
  +--> emit payload/heartbeat only after committed state is visible
```

### Recommended Project Structure
```text
jellyswipe/
├── repositories/
│   ├── rooms.py          # Room reads/writes, deck cursor, status projection
│   ├── swipes.py         # Swipe inserts/deletes and serialized sync bridge helper
│   └── matches.py        # Match reads/writes, history/archive queries
├── services/
│   ├── room_lifecycle.py # create/join/quit/genre/deck/status orchestration
│   └── swipe_match.py    # swipe/undo/delete transaction coordination
└── routers/
    └── rooms.py          # controller-only route layer calling services
```

### Pattern 1: Request-Scoped UoW for Ordinary Room Mutations
**What:** Room lifecycle endpoints should accept `DBUoW` and delegate persistence to async services and repositories. [VERIFIED: jellyswipe/dependencies.py, jellyswipe/routers/auth.py]
**When to use:** Use for create, solo create, join, quit, genre, deck, status, history, undo, and delete whenever the work fits normal async statements. [VERIFIED: jellyswipe/routers/rooms.py]
**Example:**
```python
# Source: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/
# Source: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
@router.post("/room/{code}/join")
async def join_room(code: str, request: Request, uow: DBUoW, user: AuthUser = Depends(require_auth)):
    result = await room_lifecycle_service.join_room(
        code=code,
        user_id=user.user_id,
        session_dict=request.session,
        uow=uow,
    )
    return result
```

### Pattern 2: Narrow `run_sync()` Bridge for Serialized Swipe Mutation
**What:** Keep one sync function that receives SQLAlchemy's sync `Session`, explicitly starts `BEGIN IMMEDIATE`, performs all swipe/match/cursor work, and returns to the async caller without owning commit/rollback. [VERIFIED: jellyswipe/routers/rooms.py, jellyswipe/db_uow.py, tests/test_dependencies.py][CITED: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html][CITED: https://www.sqlite.org/lang_transaction.html]
**When to use:** Use only for the atomic swipe mutation path where SQLite lock timing matters. [VERIFIED: 39-CONTEXT.md]
**Example:**
```python
# Source: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
# Source: https://www.sqlite.org/lang_transaction.html
async def swipe(..., uow: DatabaseUnitOfWork) -> None:
    await uow.run_sync(
        run_serialized_swipe,
        code=code,
        user_id=user_id,
        session_id=session_id,
        movie_id=movie_id,
        direction=direction,
    )
```

### Pattern 3: Stream-Local Async DB Access for SSE
**What:** Create DB access inside the generator, not as a request dependency, and keep each DB interaction short-lived. [CITED: https://github.com/sysid/sse-starlette][CITED: https://docs.sqlalchemy.org/en/20/orm/session_basics.html]
**When to use:** Use for `/room/{code}/stream`, where the generator may outlive normal request dependency cleanup by minutes or hours. [VERIFIED: jellyswipe/routers/rooms.py, tests/test_routes_sse.py]
**Example:**
```python
# Source: https://github.com/sysid/sse-starlette
# Source: https://docs.sqlalchemy.org/en/20/orm/session_basics.html
async def generate():
    while True:
        if await request.is_disconnected():
            break
        async with sessionmaker() as session:
            snapshot = await room_repository.fetch_stream_snapshot(session, code)
        yield {"data": snapshot.to_json()}
        await asyncio.sleep(1.5)
```

### Anti-Patterns to Avoid
- **Shared `AsyncSession` across the entire SSE stream:** SQLAlchemy documents `AsyncSession` as mutable, stateful, and unsafe to share across concurrent tasks; it also mismatches FastAPI dependency cleanup timing. [CITED: https://docs.sqlalchemy.org/en/20/orm/session_basics.html][CITED: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/]
- **Replacing `BEGIN IMMEDIATE` with ordinary async writes “because tests still pass”:** SQLite deferred transactions can postpone write-lock acquisition and break race protection. [CITED: https://www.sqlite.org/lang_transaction.html]
- **Moving provider metadata calls inside the serialized DB lock window:** `get_provider().resolve_item_for_tmdb()` is external work and should stay outside the lock where possible, as it does today. [VERIFIED: jellyswipe/routers/rooms.py]
- **Preserving route-level SQL while introducing repositories elsewhere:** This would leave MVC-04 incomplete and make Phase 40 sync-path removal harder. [VERIFIED: .planning/REQUIREMENTS.md, .planning/ROADMAP.md]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE framing and heartbeat comments | Custom `text/event-stream` writer | `EventSourceResponse` | The library already handles framing, disconnects, pings, headers, and cancellation patterns. [CITED: https://github.com/sysid/sse-starlette] |
| Application-level Python locks for swipe races | `asyncio.Lock`, thread locks, or in-memory room mutexes | SQLite write serialization via `BEGIN IMMEDIATE` inside the DB transaction | App-local locks do not protect across processes; SQLite does. [CITED: https://www.sqlite.org/lang_transaction.html] |
| Shared “global async session” for streams | Cached singleton `AsyncSession` | `async_sessionmaker` plus short-lived sessions | SQLAlchemy explicitly recommends session-per-task/transaction, not shared mutable sessions. [CITED: https://docs.sqlalchemy.org/en/20/orm/session_basics.html] |
| JSON/event escaping by hand in new endpoints | Ad hoc string concatenation | Existing JSON responses plus current XSS regression tests | The repo already enforces XSS-safe behavior around swipe-derived fields. [VERIFIED: tests/test_routes_xss.py] |

**Key insight:** The hard part of this phase is lifetime and lock semantics, not CRUD syntax; hand-rolled concurrency or stream plumbing adds new failure modes without satisfying any requirement. [VERIFIED: 39-CONTEXT.md][CITED: https://www.sqlite.org/lang_transaction.html][CITED: https://github.com/sysid/sse-starlette]

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Existing SQLite tables `rooms`, `swipes`, `matches`, and `auth_sessions` already hold the state this phase will read/write. The SQLAlchemy models preserve the same columns used by current room/sse code. [VERIFIED: jellyswipe/models/room.py, jellyswipe/models/swipe.py, jellyswipe/models/match.py, jellyswipe/models/auth_session.py, jellyswipe/routers/rooms.py] | Code edit only. No schema or data migration is required by the planned approach as long as Phase 39 keeps the current fields and serialized JSON shapes. [VERIFIED: .planning/ROADMAP.md, 39-CONTEXT.md] |
| Live service config | None found. Phase 39 explicitly keeps the current app-local broadcaster/polling model and does not introduce an external event bus, queue, or dashboard-backed config. [VERIFIED: 39-CONTEXT.md, repo grep] | None. |
| OS-registered state | None found in repo or planning artifacts; no checked-in launchd/systemd/pm2 registration for room/swipe/SSE behavior was present. [VERIFIED: repo grep] | None for repo-managed artifacts. Host-level service registrations were not inspected directly. [ASSUMED] |
| Secrets/env vars | Existing runtime still depends on Jellyfin/TMDB env vars plus session secret config, but Phase 39 does not rename or add env keys. [VERIFIED: jellyswipe/dependencies.py, .planning/PROJECT.md] | None for key names; code must keep current auth/session semantics intact. [VERIFIED: 39-CONTEXT.md] |
| Build artifacts | No generated artifacts tied specifically to room/swipe/SSE persistence were found in the phase scope. The repo is clean and this phase writes only source/test changes. [VERIFIED: `git status --short`, repo grep] | None. |

## Common Pitfalls

### Pitfall 1: Losing SQLite Write Serialization
**What goes wrong:** Two users right-swipe the same title and match rows or `last_match_data` diverge from current behavior. [VERIFIED: tests/test_routes_room.py, tests/test_route_authorization.py]
**Why it happens:** A plain async statement sequence does not automatically reproduce `BEGIN IMMEDIATE` write-lock timing. [CITED: https://www.sqlite.org/lang_transaction.html]
**How to avoid:** Keep the swipe critical section inside one `run_sync()` function that explicitly starts `BEGIN IMMEDIATE`, while leaving final commit/rollback to the request dependency. [VERIFIED: jellyswipe/db_uow.py, jellyswipe/routers/rooms.py, tests/test_dependencies.py][CITED: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html]
**Warning signs:** Duplicate/missing match rows, flaky concurrent swipe tests, or a refactor that removes the explicit lock acquisition. [VERIFIED: tests/test_route_authorization.py]

### Pitfall 2: Reusing a Request Session in SSE
**What goes wrong:** Streams leak sessions, close too early, or reuse a mutable `AsyncSession` beyond the controller lifetime. [VERIFIED: jellyswipe/dependencies.py, jellyswipe/routers/rooms.py]
**Why it happens:** FastAPI dependency cleanup is request/response scoped, and SQLAlchemy does not want one `AsyncSession` shared across long-lived concurrent work. [CITED: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/][CITED: https://docs.sqlalchemy.org/en/20/orm/session_basics.html]
**How to avoid:** Open DB access inside the generator and keep each poll query short-lived. [CITED: https://github.com/sysid/sse-starlette]
**Warning signs:** Attempts to inject `DBUoW` directly into the stream generator or one session object surviving for the full stream timeout. [VERIFIED: repo grep]

### Pitfall 3: Breaking Immediate Session Cleanup for Stale Rooms
**What goes wrong:** `GET /me` or room routes leave stale `active_room` / `solo_mode` values in the session after the room has been deleted. [VERIFIED: jellyswipe/auth.py, tests/test_route_authorization.py]
**Why it happens:** The stale-room cleanup logic lives in `resolve_active_room()` and must stay aligned with room lifecycle deletes. [VERIFIED: jellyswipe/auth.py]
**How to avoid:** Make room services update persisted room state and preserve current session cleanup behavior on missing-room paths. [VERIFIED: 39-CONTEXT.md]
**Warning signs:** Tests that used to assert `activeRoom == code` after create/join/solo start failing or stale cookies remain after room deletion. [VERIFIED: tests/test_route_authorization.py]

### Pitfall 4: Regressing XSS/Error-Handling Behavior While Rewiring Persistence
**What goes wrong:** Moving DB code accidentally changes sanitized fields, error payload shape, or `request_id` propagation. [VERIFIED: tests/test_routes_xss.py, tests/test_error_handling.py]
**Why it happens:** Refactors often rework response and exception paths along with persistence code. [ASSUMED]
**How to avoid:** Keep route response shapes unchanged and preserve provider-derived title/thumb behavior and existing error helpers. [VERIFIED: jellyswipe/routers/rooms.py, tests/test_routes_xss.py, tests/test_error_handling.py]
**Warning signs:** New route-level helpers bypass `XSSSafeJSONResponse`, or match payloads start echoing client-supplied title/thumb. [VERIFIED: tests/test_routes_xss.py]

## Code Examples

Verified patterns from official sources:

### Request-Scoped Dependency Cleanup
```python
# Source: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/
async def get_db():
    db = Session()
    try:
        yield db
    finally:
        db.close()
```

### `Depends(scope="function")` for Early Cleanup
```python
# Source: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/
username: Annotated[str, Depends(get_username, scope="function")]
```

### Sync Work Under `AsyncSession`
```python
# Source: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
result = await async_session.run_sync(some_business_method, param="value")
```

### SSE Generator Pattern
```python
# Source: https://github.com/sysid/sse-starlette
async def stream(request):
    try:
        while True:
            if await request.is_disconnected():
                break
            yield {"data": "payload"}
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        raise
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Route handlers call raw `sqlite3` via `get_db_closing()` | Async `DBUoW` plus repository/service delegation | Established in Phases 37-38 on 2026-05-06, incomplete for rooms in Phase 39. [VERIFIED: .planning/ROADMAP.md, jellyswipe/routers/auth.py, jellyswipe/routers/rooms.py] | Phase 39 should finish the controller/persistence separation for the room domain. [VERIFIED: .planning/REQUIREMENTS.md] |
| Swipe uses route-embedded sync SQL | Swipe should move into a dedicated service, but keep the narrow `run_sync()` bridge for lock parity | Phase 39 scope. [VERIFIED: 39-CONTEXT.md] | Minimizes race-regression risk while still satisfying MVC-03/MVC-04. [VERIFIED: .planning/REQUIREMENTS.md] |
| SSE uses one long-lived raw SQLite connection | SSE should use async DB access with short-lived session/connection scope inside the generator | Phase 39 scope. [VERIFIED: .planning/ROADMAP.md, jellyswipe/routers/rooms.py] | Preserves non-blocking stream behavior without sharing a request-scoped session across the stream lifetime. [CITED: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/][CITED: https://docs.sqlalchemy.org/en/20/orm/session_basics.html] |

**Deprecated/outdated:**
- Direct application-layer `get_db_closing()` usage in `jellyswipe/routers/rooms.py` is the old persistence path this phase is meant to retire. [VERIFIED: jellyswipe/routers/rooms.py, .planning/ROADMAP.md]
- Treating SSE as safe to back with one request-bound dependency session is outdated for FastAPI streaming routes. [CITED: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | No host-level OS service registration needs adjustment for this persistence conversion. | Runtime State Inventory | Low; the plan might miss a deployment-specific service restart note. |
| A2 | Refactoring response/error paths is avoidable if router shapes stay unchanged. | Common Pitfalls | Low; implementation may still touch helpers if repository errors surface differently. |
| A3 | `python -m pytest` is a viable fallback if `uv` is unavailable but the virtualenv is already provisioned. | Environment Availability | Low; affects command choice, not implementation design. |
| A4 | The `sqlite3` CLI is optional because runtime behavior can still be validated through SQLAlchemy/aiosqlite and pytest. | Environment Availability | Low; affects debugging ergonomics only. |
| A5 | A dedicated `tests/test_sse_persistence.py` file is only needed if the planner extracts stream snapshot logic into a separate unit. | Validation Architecture | Low; exact test-file naming may change. |
| A6 | The team may or may not want to rewrite the swipe critical section into pure ORM/Core statements in this phase. | Open Questions | Medium; if they insist on a full rewrite, task scope and risk increase. |

## Open Questions

1. **Should Phase 39 fully eliminate raw SQL from the swipe critical section, or only move ownership into a service while retaining the sync bridge?**
   - What we know: The user locked race protection equivalence to the current `BEGIN IMMEDIATE` path, and current tests already verify `run_sync()` commit/rollback semantics. [VERIFIED: 39-CONTEXT.md, tests/test_dependencies.py]
   - What's unclear: Whether the team wants Phase 39 to also rewrite the critical section into pure ORM/Core statements despite the added locking risk. [ASSUMED]
   - Recommendation: Plan for a service-owned sync bridge first; leave “remove the bridge” to a later hardening/refactor only if new concurrency tests prove parity. [CITED: https://www.sqlite.org/lang_transaction.html]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | App runtime and tests | ✓ [VERIFIED: `python3 --version`] | 3.13.9 | — |
| `uv` | Dependency sync and pytest commands | ✓ [VERIFIED: `uv --version`] | 0.9.5 | `python -m pytest` if the virtualenv is already provisioned [ASSUMED] |
| `sqlite3` CLI | DB inspection/debugging during implementation | ✓ [VERIFIED: `sqlite3 --version`] | 3.51.0 | SQLAlchemy/aiosqlite runtime still works without the CLI. [ASSUMED] |
| Git | Optional commit flow | ✓ [VERIFIED: `git --version`] | 2.50.1 | — |

**Missing dependencies with no fallback:**
- None. [VERIFIED: environment probes]

**Missing dependencies with fallback:**
- None. [VERIFIED: environment probes]

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest 9.0.3` with `anyio 4.13.0` and `pytest-cov 7.1.0` in verified local runs. [VERIFIED: executed `uv run pytest ...`] |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]`. [VERIFIED: pyproject.toml] |
| Quick run command | `uv run pytest tests/test_dependencies.py::TestGetDbUow::test_yields_uow_and_commits_on_success -q` or `uv run pytest tests/test_routes_sse.py::test_stream_response_headers -q`. Both passed during research. [VERIFIED: executed commands] |
| Full suite command | `uv run pytest` [VERIFIED: pyproject.toml] |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MVC-02 | Room create/join/quit/genre/deck/status persistence still behaves the same | route + service | `uv run pytest tests/test_routes_room.py tests/test_route_authorization.py -x` | ✅ |
| MVC-03 | Swipe/history/undo/delete persistence delegates cleanly and preserves match outputs | route + service | `uv run pytest tests/test_routes_room.py tests/test_route_authorization.py tests/test_routes_xss.py -x` | ✅ |
| MVC-04 | Routes remain controller-only and DB work moves behind services/repositories | unit | `uv run pytest tests/test_room_services.py tests/test_room_repositories.py -x` | ❌ Wave 0 |
| PAR-02 | Multiplayer and solo room lifecycle parity | route | `uv run pytest tests/test_routes_room.py -x` | ✅ |
| PAR-03 | Swipe parity, deck cursor advancement, enriched match metadata, undo/delete parity | route + service | `uv run pytest tests/test_routes_room.py tests/test_route_authorization.py tests/test_routes_xss.py -x` | ✅ |
| PAR-04 | Serialized swipe transaction still commits/rolls back correctly and protects races | unit + focused integration | `uv run pytest tests/test_dependencies.py -x` | ✅ |
| PAR-05 | SSE stays async/non-blocking with correct headers, disconnect, cleanup, heartbeat, and closed-room behavior | route | `uv run pytest tests/test_routes_sse.py -x` | ✅ |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_dependencies.py -q` plus the touched route file (`tests/test_routes_room.py` or `tests/test_routes_sse.py`). [VERIFIED: tests/, executed commands]
- **Per wave merge:** `uv run pytest tests/test_routes_room.py tests/test_route_authorization.py tests/test_routes_sse.py tests/test_routes_xss.py tests/test_error_handling.py -x`. [VERIFIED: tests/]
- **Phase gate:** Full suite green before `$gsd-verify-work`. [VERIFIED: .planning/config.json]

### Wave 0 Gaps
- [ ] `tests/test_room_services.py` — direct room lifecycle service coverage for create/join/quit/genre/deck/status delegation. [VERIFIED: repo grep]
- [ ] `tests/test_room_repositories.py` — repository-level coverage for deck cursor and status/history queries. [VERIFIED: repo grep]
- [ ] `tests/test_swipe_service.py` — focused coverage for undo/delete recomputation and serialized mutation orchestration beyond route tests. [VERIFIED: repo grep]
- [ ] `tests/test_sse_persistence.py` or equivalent unit coverage — DB snapshot logic separated from the stream route, if the planner extracts it. [ASSUMED]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | `require_auth()` backed by persisted `auth_sessions` rows. [VERIFIED: jellyswipe/dependencies.py, jellyswipe/models/auth_session.py] |
| V3 Session Management | yes | Server-side session cookie state plus aggressive stale-session clearing. [VERIFIED: jellyswipe/dependencies.py, jellyswipe/auth.py] |
| V4 Access Control | yes | Room, match, and SSE routes require authenticated user context and use persisted identity rather than trusting spoofed headers. [VERIFIED: jellyswipe/routers/rooms.py, tests/test_route_authorization.py] |
| V5 Input Validation | yes | Current routes explicitly validate required JSON fields and regression tests protect XSS and error-shape behavior. [VERIFIED: jellyswipe/routers/rooms.py, tests/test_routes_xss.py, tests/test_error_handling.py] |
| V6 Cryptography | no | Phase 39 does not introduce cryptographic logic; session-cookie signing remains existing framework behavior outside this phase. [VERIFIED: .planning/PROJECT.md, repo grep] |

### Known Threat Patterns for FastAPI + SQLite + SSE

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Lost-update / duplicate-match race during concurrent swipes | Tampering | Keep serialized DB mutation with SQLite `BEGIN IMMEDIATE` semantics. [CITED: https://www.sqlite.org/lang_transaction.html] |
| Shared mutable session across concurrent async work | Tampering / DoS | Use one `AsyncSession` per transaction/task; do not share across stream lifetime. [CITED: https://docs.sqlalchemy.org/en/20/orm/session_basics.html] |
| SSE resource leak after disconnect or cancellation | DoS | Check `request.is_disconnected()`, re-raise `CancelledError`, and close per-stream/per-poll resources. [VERIFIED: jellyswipe/routers/rooms.py, tests/test_routes_sse.py][CITED: https://github.com/sysid/sse-starlette] |
| Stored XSS through match metadata | Elevation of Privilege | Keep provider-derived metadata flow and existing XSS regression coverage. [VERIFIED: tests/test_routes_xss.py, jellyswipe/routers/rooms.py] |
| Stale session state pointing at deleted rooms | Spoofing / Integrity | Preserve `resolve_active_room()` cleanup semantics and clear stale local room state immediately. [VERIFIED: jellyswipe/auth.py, 39-CONTEXT.md] |

## Sources

### Primary (HIGH confidence)
- Repo source and tests — `jellyswipe/routers/rooms.py`, `jellyswipe/dependencies.py`, `jellyswipe/db_uow.py`, `jellyswipe/auth.py`, `jellyswipe/models/*.py`, `tests/test_routes_room.py`, `tests/test_routes_sse.py`, `tests/test_route_authorization.py`, `tests/test_routes_xss.py`, `tests/test_error_handling.py`. [VERIFIED: repo reads/grep]
- Context7 `/websites/sqlalchemy_en_20` — `AsyncSession` concurrency model and `run_sync()` usage. [CITED: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html]
- SQLAlchemy session docs — session-per-task / concurrent-task guidance. [CITED: https://docs.sqlalchemy.org/en/20/orm/session_basics.html]
- FastAPI dependency docs — `yield` cleanup timing and `scope="function"`. [CITED: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/]
- SSE-Starlette README — `EventSourceResponse`, disconnect handling, cancellation, multi-loop support, and generator-local DB session guidance. [CITED: https://github.com/sysid/sse-starlette]
- SQLite transaction docs — `BEGIN IMMEDIATE`, write-transaction exclusivity, `SQLITE_BUSY`, and WAL-mode notes. [CITED: https://www.sqlite.org/lang_transaction.html]
- aiosqlite docs — one shared thread per connection and proxy connection model. [CITED: https://aiosqlite.omnilib.dev/en/stable/]
- Official PyPI JSON endpoints — current package versions and upload dates for `sqlalchemy`, `aiosqlite`, `fastapi`, `sse-starlette`, `alembic`, and `uvicorn`. [VERIFIED: PyPI JSON]

### Secondary (MEDIUM confidence)
- None.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - verified against official PyPI metadata and current official docs. [VERIFIED: PyPI JSON][CITED: official docs above]
- Architecture: HIGH - strongly constrained by current repo seams plus official SQLAlchemy/FastAPI/SSE lifetime guidance. [VERIFIED: repo reads][CITED: official docs above]
- Pitfalls: HIGH - backed by current parity tests and official concurrency/transaction/streaming documentation. [VERIFIED: tests/][CITED: official docs above]

**Research date:** 2026-05-06
**Valid until:** 2026-06-05
