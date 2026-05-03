# Phase 34: SSE Route Migration - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Migrate the single SSE route from its inline position in `jellyswipe/__init__.py` into `jellyswipe/routers/rooms.py`, converting the synchronous generator to an `async def generate()` using `await asyncio.sleep()` so the Uvicorn event loop is never blocked — and guaranteeing SQLite connection cleanup on client disconnect via `try/finally`.

**In scope:**
- Move `room_stream()` and its inner `generate()` from `__init__.py` to `routers/rooms.py`
- Convert inner generator to `async def generate()` with `await asyncio.sleep(delay)`
- Add `sse-starlette>=3.4.1` to `pyproject.toml`; use `EventSourceResponse` as response class
- Switch auth from `_require_login(request)` to `auth: AuthUser = Depends(require_auth)`
- Add `await request.is_disconnected()` check at top of each poll iteration (before SQLite query)
- Narrow `except Exception` to exclude `asyncio.CancelledError` (catches both `CancelledError` and `GeneratorExit` patterns from PITFALLS SSE-1 and SSE-4)
- Keep `try/finally: conn.close()` for guaranteed connection cleanup
- Add `check_same_thread=False` to `sqlite3.connect()` call (SQL-1)
- Remove `except GeneratorExit: return` (gevent cancellation model — not applicable under asyncio)
- Remove SSE route stub from `__init__.py` once moved
- Regenerate `uv.lock` after adding `sse-starlette`

**Out of scope:**
- Test suite migration to FastAPI TestClient (Phase 35)
- Pydantic request/response models (v2.1)
- Any behavioral changes to SSE event format or payload shape
- Other route handlers (all already in domain routers from Phase 33)

</domain>

<decisions>
## Implementation Decisions

### Route Location

- **D-01:** SSE route moves to `jellyswipe/routers/rooms.py` alongside the other room routes. The outer handler `room_stream()` stays `def` (sync) — consistent with every other route in the codebase. The inner `async def generate()` is the only async surface.
- **D-02:** Remove the inline SSE route and its `# SSE route — stays inline per D-15` comment from `__init__.py` once moved.

### SSE Response Class

- **D-03:** Add `sse-starlette>=3.4.1` to `pyproject.toml` runtime dependencies. Use `EventSourceResponse` from `sse_starlette.sse` as the response class. This replaces the manual `StreamingResponse(generate(), media_type='text/event-stream', headers={...})` pattern.
- **D-04:** `EventSourceResponse` handles `Cache-Control: no-cache` and `X-Accel-Buffering: no` headers — verify these are still emitted (required by success criteria 2). If `EventSourceResponse` doesn't set them automatically, add them explicitly.

### Auth Wiring

- **D-05:** Switch `room_stream()` auth from `_require_login(request)` to `auth: AuthUser = Depends(require_auth)`. Import `AuthUser` and `require_auth` from `jellyswipe.dependencies`. This is consistent with all other Phase 33 routes.

### Disconnect Detection

- **D-06:** Add `if await request.is_disconnected(): break` at the **top** of each poll iteration — before the SQLite query — so dead clients skip the DB round-trip entirely. The `request` object must be passed into the generator (close over it from `room_stream`'s `request` parameter).
- **D-07:** The outer `room_stream(code: str, request: Request, auth: AuthUser = Depends(require_auth))` signature already receives `request` — pass it into the generator via closure.

### Exception Handling

- **D-08:** Replace `except GeneratorExit: return` with nothing — remove it entirely. Under asyncio, `CancelledError` is the cancellation signal, not `GeneratorExit`. The `try/finally` block guarantees cleanup regardless.
- **D-09:** Narrow the existing `except Exception` error-handling block to `except Exception as exc: if isinstance(exc, asyncio.CancelledError): raise`. This prevents `CancelledError` from being swallowed and re-raising it allows the `try/finally` to close the connection cleanly. Pattern:
  ```python
  except Exception as exc:
      if isinstance(exc, asyncio.CancelledError):
          raise
      delay = POLL + random.uniform(0, 0.5)
      await asyncio.sleep(delay)
  ```

### SQLite Connection

- **D-10:** Keep direct `sqlite3.connect(jellyswipe.db.DB_PATH, check_same_thread=False)` inside the generator. The connection lifetime must span the entire stream (up to 3600s) — `get_db_dep()` is request-scoped and cannot serve this purpose. `check_same_thread=False` added per SQL-1 pitfall.
- **D-11:** `try/finally: conn.close()` block is preserved. The `finally` fires regardless of how the generator exits: normal timeout, `CancelledError`, or any other exception.

### Claude's Discretion

- `sse-starlette` exact pin: use `sse-starlette>=3.4.1` (user confirmed 3.4.1 is current release); planner picks compatible constraint syntax for `pyproject.toml`.
- Generator pass pattern for `request`: closure over outer function's `request` parameter is the standard Python pattern here.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and Roadmap
- `.planning/REQUIREMENTS.md` — FAPI-03: SSE endpoint works via `StreamingResponse` with async generator using `await asyncio.sleep()`
- `.planning/ROADMAP.md` §Phase 34 — 4 success criteria: async generator, headers, try/finally cleanup, event format parity

### Current SSE Implementation (source to migrate)
- `jellyswipe/__init__.py` lines 275–348 — current inline SSE route and `generate()` generator; this is the exact code being migrated
- `jellyswipe/routers/rooms.py` — target file; SSE route moves here alongside the 10 existing room routes
- `jellyswipe/dependencies.py` — exports `AuthUser`, `require_auth()`, `DBConn` — import `require_auth` and `AuthUser` for auth wiring
- `jellyswipe/db.py` — `DB_PATH` constant used by direct `sqlite3.connect()`

### Pitfalls (MUST READ — all SSE pitfalls apply to this phase)
- `.planning/research/PITFALLS.md` §SSE-1 — `GeneratorExit` vs `CancelledError` cancellation incompatibility
- `.planning/research/PITFALLS.md` §SSE-2 — `time.sleep()` blocks event loop (the core fix)
- `.planning/research/PITFALLS.md` §SSE-4 — `except Exception` swallows `CancelledError`; disconnect not detected
- `.planning/research/PITFALLS.md` §SSE-5 — sse-starlette vs manual StreamingResponse; EventSourceResponse chosen
- `.planning/research/PITFALLS.md` §SQL-1 — `check_same_thread=False` for connections used across Uvicorn threads

### Prior Phase Context
- `.planning/phases/33-router-extraction-and-endpoint-parity/33-CONTEXT.md` — D-15 deferred SSE inline; D-06 router structure this route joins
- `.planning/phases/32-auth-rewrite-and-dependency-injection-layer/32-CONTEXT.md` — D-01 through D-05 define `AuthUser`, `require_auth()` this phase wires in

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `jellyswipe/routers/rooms.py` — `rooms_router` APIRouter; SSE route adds one more `@rooms_router.get('/room/{code}/stream')` entry
- `jellyswipe/dependencies.py` — `require_auth`, `AuthUser` already implemented and tested in Phase 32
- `jellyswipe/__init__.py` lines 279–340 — the full generator logic (poll loop, state tracking, payload building, heartbeat, timeout) moves verbatim except for the async conversion
- `EventSourceResponse` from `sse_starlette.sse` — replaces `StreamingResponse`

### Established Patterns
- Outer `def` + inner `async def`: every other route handler is `def`; only the SSE generator is async — match this pattern
- `Depends(require_auth)` in route signature: `auth: AuthUser = Depends(require_auth)` — exact pattern from Phase 33 routes
- Router-level import style: `from jellyswipe.dependencies import require_auth, AuthUser` at top of `rooms.py`
- `from jellyswipe import db as _db` lazy import already in generator — keep this

### Integration Points
- `__init__.py` app factory: remove the inline SSE route block after moving it to `rooms_router`; `rooms_router` is already `app.include_router(rooms_router)` so no factory change needed
- `pyproject.toml` dependencies: add `sse-starlette>=3.4.1` in `[project.dependencies]`; run `uv sync` to regenerate lockfile

</code_context>

<specifics>
## Specific Ideas

- `sse-starlette` version: 3.4.1 is the current release — use `>=3.4.1` constraint
- `check_same_thread=False` is a belt-and-suspenders guard per SQL-1, even though the generator runs on the event loop thread
- The `_last_event_time` heartbeat logic (15s ping) and the 3600s TIMEOUT remain unchanged — behavior parity

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 34-SSE Route Migration*
*Context gathered: 2026-05-03*
