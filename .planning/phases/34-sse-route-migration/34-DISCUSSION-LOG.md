# Phase 34: SSE Route Migration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-03
**Phase:** 34-sse-route-migration
**Areas discussed:** Route location, SSE response class, Disconnect detection, Auth wiring, Exception handling, SQLite connection, sse-starlette version

---

## Route Location

| Option | Description | Selected |
|--------|-------------|----------|
| (a) `routers/rooms.py` | Move alongside other room routes | ✓ |
| (b) Keep inline in `__init__.py` | Avoids circular import risk | |
| (c) New dedicated `routers/sse.py` | Isolated file for SSE | |

**User's choice:** 1a — `routers/rooms.py`
**Notes:** Consistent with Phase 33 router structure; outer handler stays `def` (sync), inner generator is `async def`.

---

## SSE Response Class

| Option | Description | Selected |
|--------|-------------|----------|
| (a) `sse-starlette` / `EventSourceResponse` | Adds dependency; handles retry/ID/shutdown | ✓ |
| (b) Keep manual `StreamingResponse` | Zero new deps; headers already correct | |

**User's choice:** 2a — `EventSourceResponse`
**Notes:** Addresses PITFALLS SSE-5; adds proper retry field support and disconnect hooks.

---

## Disconnect Detection

| Option | Description | Selected |
|--------|-------------|----------|
| (a) `request.is_disconnected()` at top of loop + narrow `except Exception` | Dead clients skip DB query; belt-and-suspenders | ✓ |
| (b) Only narrow exception handler | Simpler; relies on `CancelledError` propagation alone | |

**User's choice:** 3a — `is_disconnected()` guard + narrowed exceptions
**Notes:** Addresses PITFALLS SSE-4; check fires before SQLite query so dead clients cause zero DB overhead.

---

## Auth Wiring

| Option | Description | Selected |
|--------|-------------|----------|
| (a) `Depends(require_auth)` | Consistent with all Phase 33 routes | ✓ |
| (b) Keep `_require_login(request)` | Defers normalization to Phase 35 | |

**User's choice:** 4a — `Depends(require_auth)`
**Notes:** `AuthUser` dataclass already available from Phase 32 DI layer.

---

## sse-starlette Version

| Option | Description | Selected |
|--------|-------------|----------|
| (a) `>=1.8` | Older stable range | |
| (b) `>=2.0` | Newer major, cleaner async API | |
| (c) Claude decides | User confirmed 3.4.1 is current release | ✓ |

**User's choice:** 5c — `sse-starlette>=3.4.1` (user confirmed current release)
**Notes:** Use `>=3.4.1` constraint in `pyproject.toml`.

---

## Disconnect Guard Placement

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Top of each iteration — before SQLite query | Dead clients skip DB round-trip | ✓ |
| (b) After sleep — belt-and-suspenders only | Less DB savings | |

**User's choice:** 6a — top of loop, before SQLite query

---

## Async Scope

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Outer `def room_stream()` + inner `async def generate()` | Consistent with all other routes staying `def` | ✓ |
| (b) Full `async def room_stream()` | Technically cleaner with EventSourceResponse | |

**User's choice:** 7a — outer `def`, inner `async def` generator

---

## SQLite Connection in Generator

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Direct `sqlite3.connect()` — connection spans full stream | Correct lifetime for 3600s stream | |
| (b) `get_db_dep()` per iteration | Safe but per-1.5s-poll overhead | |
| (c) Direct `sqlite3.connect()` + `check_same_thread=False` | SQL-1 belt-and-suspenders | ✓ |

**User's choice:** 8c — direct connect + `check_same_thread=False`
**Notes:** `get_db_dep()` is request-scoped and can't span the stream lifetime. `check_same_thread=False` per SQL-1 pitfall.

---

## Claude's Discretion

- `sse-starlette` constraint syntax in `pyproject.toml` (user confirmed version, planner picks format)
- Closure pattern for passing `request` into async generator

## Deferred Ideas

None — discussion stayed within phase scope.
