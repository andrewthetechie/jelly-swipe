---
phase: 34-sse-route-migration
plan: 02
subsystem: sse
tags: [sse, async, rooms-router, cleanup]
dependency_graph:
  requires: [34-01]
  provides: [sse-route-async]
  affects: [35-01]
tech_stack:
  added: ["asyncio", "sse-starlette.sse.EventSourceResponse"]
  patterns: ["async generator", "disconnect detection", "CancelledError propagation", "connection cleanup"]
key_files:
  created: []
  modified: [jellyswipe/routers/rooms.py, jellyswipe/__init__.py]
decisions: []
metrics:
  duration: "5 minutes"
  completed: "2026-05-03T16:13:00Z"
---

# Phase 34 Plan 02: Add async SSE route to rooms.py and remove inline SSE block from __init__.py Summary

Migrated the SSE route from its inline position in `jellyswipe/__init__.py` into `jellyswipe/routers/rooms.py`, converting the synchronous generator to an async generator with all safety patterns applied: non-blocking sleep, disconnect detection, CancelledError propagation, and guaranteed connection cleanup.

## What Was Done

### Task 1: Add async SSE route to jellyswipe/routers/rooms.py

1. **Extended imports:**
   - Added `asyncio`, `random`, `sqlite3`, `time` to existing imports
   - Added `from sse_starlette.sse import EventSourceResponse`
   - Preserved all existing imports (no duplicates)

2. **Implemented async SSE route:**
   - Added `room_stream()` route at the end of `rooms.py`
   - Outer handler is sync `def` per D-01 (FastAPI dependency injection requires sync)
   - Inner generator is `async def generate()` with async/await patterns
   - Applied all D-01–D-11 decisions from the threat model:
     - **D-01/D-02:** Separation of concerns — route in rooms.py, not inline
     - **D-03:** Uses `EventSourceResponse` from sse-starlette package
     - **D-04:** Sets Cache-Control: no-cache and X-Accel-Buffering: no headers
     - **D-05:** Applied `auth: AuthUser = Depends(require_auth)` for authentication
     - **D-06:** Checks `await request.is_disconnected()` before DB query
     - **D-07:** Closes over `request` from outer signature for disconnect detection
     - **D-08:** Removed `except GeneratorExit` (gevent pattern, not applicable under asyncio)
     - **D-09:** Re-raises `asyncio.CancelledError` so try/finally can clean up
     - **D-10:** Opens SQLite connection with `check_same_thread=False` (SQL-1 fix)
     - **D-11:** Guaranteed cleanup in `finally: conn.close()` block

3. **Applied SSE safety patterns (SSE-1, SSE-2, SSE-4, SSE-5):**
   - **SSE-1:** No `GeneratorExit` handler (gevent-specific, wrong for asyncio)
   - **SSE-2:** All `time.sleep()` replaced with `await asyncio.sleep()` (non-blocking)
   - **SSE-4:** `except Exception as exc: if isinstance(exc, asyncio.CancelledError): raise` ensures CancelledError propagates to finally block
   - **SSE-5:** SSE events as dicts `{"data": json.dumps(payload)}` not raw `f"data: ..."` strings

4. **Fixed SQLite thread-safety issue (SQL-1):**
   - Added `check_same_thread=False` to `sqlite3.connect()` call
   - Uvicorn may resume async generator on different thread
   - Connection scoped to stream lifetime with guaranteed cleanup

### Task 2: Remove inline SSE block from jellyswipe/__init__.py

1. **Removed inline SSE route:**
   - Deleted entire SSE route block (lines 275–346)
   - Removed `room_stream()` route definition
   - Removed inner `generate()` function with blocking `time.sleep()`
   - Removed `GeneratorExit` exception handler
   - Removed SQLite connection without `check_same_thread=False`

2. **Removed unused import:**
   - Changed `from fastapi.responses import JSONResponse, StreamingResponse` to `from fastapi.responses import JSONResponse`
   - StreamingResponse no longer used after SSE block removal

3. **Verified cleanup:**
   - App factory still works: `from jellyswipe import app` succeeds
   - SSE route now served by rooms_router: `/room/{code}/stream` in routes list
   - No dangling references to `generate`, `room_stream`, `StreamingResponse`, or `time.sleep`

## Verification

### Task 1 Verification
- ✅ `grep -n "async def generate" jellyswipe/routers/rooms.py` — found at line 381
- ✅ `grep -n "await asyncio.sleep" jellyswipe/routers/rooms.py` — found at lines 439, 446 (main path + error path)
- ✅ `grep -n "EventSourceResponse" jellyswipe/routers/rooms.py` — import + usage found
- ✅ `grep -n "is_disconnected" jellyswipe/routers/rooms.py` — found at line 400
- ✅ `grep -n "check_same_thread=False" jellyswipe/routers/rooms.py` — found at line 394
- ✅ `grep -n "finally:" jellyswipe/routers/rooms.py` — found at line 447
- ✅ `grep -n "GeneratorExit" jellyswipe/routers/rooms.py` — returns empty (good)
- ✅ `grep -n "time\.sleep" jellyswipe/routers/rooms.py` — returns empty (good)
- ✅ `grep -n 'yield f"data:' jellyswipe/routers/rooms.py` — returns empty (good)
- ✅ `python -c "from jellyswipe.routers.rooms import rooms_router"` — exits 0

### Task 2 Verification
- ✅ `grep "SSE route — stays inline" jellyswipe/__init__.py` — returns empty
- ✅ `grep "def room_stream" jellyswipe/__init__.py` — returns empty
- ✅ `grep "StreamingResponse" jellyswipe/__init__.py` — returns empty
- ✅ `python -c "from jellyswipe import app"` — exits 0
- ✅ `python -c "from jellyswipe.routers.rooms import rooms_router; routes = [r.path for r in rooms_router.routes]; assert '/room/{code}/stream' in routes"` — passes

## Deviations from Plan

None - plan executed exactly as written.

## Threat Flags

All threat mitigations from the plan were implemented:

| Threat ID | Category | Component | Mitigation |
|-----------|----------|-----------|------------|
| T-34-02-01 | Denial of Service | `/room/{code}/stream` — unbounded connections | TIMEOUT = 3600 caps connections; `await request.is_disconnected()` exits dead connections; `finally: conn.close()` guarantees cleanup |
| T-34-02-02 | Elevation of Privilege | Authentication bypass | `auth: AuthUser = Depends(require_auth)` applied; FastAPI evaluates dependency before handler runs |
| T-34-02-03 | Information Disclosure | Event injection | All payload values from DB rows; `json.dumps()` encodes special characters; no raw user input reflected |
| T-34-02-04 | Denial of Service | Connection leak | `try/finally: conn.close()` ensures closure on all exit paths; `asyncio.CancelledError` re-raised |
| T-34-02-05 | Tampering | Swallowing CancelledError | `except Exception as exc: if isinstance(exc, asyncio.CancelledError): raise` pattern applied |
| T-34-02-06 | Denial of Service | Blocking event loop | All `time.sleep()` replaced with `await asyncio.sleep()` |

## Self-Check: PASSED

**Files created:** None
**Files modified:** jellyswipe/routers/rooms.py, jellyswipe/__init__.py
**Commits verified:** 8a14b24, 158e572
