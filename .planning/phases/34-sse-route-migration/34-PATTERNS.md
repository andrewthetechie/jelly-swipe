# Phase 34: SSE Route Migration - Pattern Map

**Mapped:** 2026-05-03
**Files analyzed:** 3 (new/modified files: rooms.py, __init__.py, pyproject.toml)
**Analogs found:** 3 / 3

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `jellyswipe/routers/rooms.py` | router | streaming (SSE) | `jellyswipe/__init__.py` lines 275–348 | exact (source code) |
| `jellyswipe/__init__.py` | app factory | request-response | itself — remove SSE block | self-modification |
| `pyproject.toml` | config | n/a | itself — add dependency entry | self-modification |

## Pattern Assignments

### `jellyswipe/routers/rooms.py` — add `room_stream()` SSE route

**Analog (source):** `jellyswipe/__init__.py` lines 275–348 (the SSE route being migrated)
**Secondary analog (structure):** `jellyswipe/routers/rooms.py` lines 101–366 (existing routes in the target file)

---

#### Imports pattern

Copy from `jellyswipe/routers/rooms.py` lines 11–27 (existing imports — extend, do not replace):

```python
import asyncio
import json
import random
import sqlite3
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sse_starlette.sse import EventSourceResponse   # NEW — add this line

from jellyswipe import XSSSafeJSONResponse
from jellyswipe.config import JELLYFIN_URL
from jellyswipe.dependencies import AuthUser, DBConn, check_rate_limit, get_db_dep, get_provider, require_auth
from jellyswipe.db import get_db_closing
```

New additions required:
- `import asyncio` — for `asyncio.CancelledError` and `await asyncio.sleep()`
- `import random` — already used in the generator; confirm it's present
- `import sqlite3` — for the long-lived connection inside `generate()`
- `import time` — for `time.time()` in the poll loop
- `from sse_starlette.sse import EventSourceResponse` — replaces `StreamingResponse`

---

#### Auth pattern

Copy from `jellyswipe/routers/rooms.py` line 102 (exact pattern used by all room routes):

```python
@rooms_router.get('/room/{code}/stream')
def room_stream(code: str, request: Request, auth: AuthUser = Depends(require_auth)):
```

- Outer handler is `def` (sync), consistent with all room routes (lines 102, 150, 277, 321, 358).
- `auth: AuthUser = Depends(require_auth)` replaces the old `_require_login(request)` call (source line 278).
- `request: Request` is kept — required for `await request.is_disconnected()` inside the generator (D-06/D-07).

---

#### Core SSE pattern — async generator

Source: `jellyswipe/__init__.py` lines 279–346, converted to async.

The `generate()` inner function changes from sync to async. Key conversion points:

```python
def room_stream(code: str, request: Request, auth: AuthUser = Depends(require_auth)):
    async def generate():
        last_genre = None
        last_ready = None
        last_match_ts = None
        POLL = 1.5
        TIMEOUT = 3600
        _last_event_time = time.time()

        import jellyswipe.db
        conn = sqlite3.connect(jellyswipe.db.DB_PATH, check_same_thread=False)  # SQL-1: check_same_thread=False added
        conn.row_factory = sqlite3.Row
        try:
            deadline = time.time() + TIMEOUT
            while time.time() < deadline:
                if await request.is_disconnected():   # D-06: disconnect check BEFORE DB query
                    break
                try:
                    row = conn.execute(
                        'SELECT ready, current_genre, solo_mode, last_match_data FROM rooms WHERE pairing_code = ?',
                        (code,)
                    ).fetchone()

                    if row is None:
                        yield {"data": json.dumps({'closed': True})}
                        return

                    ready = bool(row['ready'])
                    genre = row['current_genre']
                    solo = bool(row['solo_mode'])
                    last_match = json.loads(row['last_match_data']) if row['last_match_data'] else None
                    match_ts = last_match['ts'] if last_match else None

                    payload = {}
                    if ready != last_ready:
                        payload['ready'] = ready
                        payload['solo'] = solo
                        last_ready = ready
                    if genre != last_genre:
                        payload['genre'] = genre
                        last_genre = genre
                    if match_ts and match_ts != last_match_ts:
                        payload['last_match'] = last_match
                        last_match_ts = match_ts

                    if payload:
                        yield {"data": json.dumps(payload)}
                        _last_event_time = time.time()
                    elif time.time() - _last_event_time >= 15:
                        yield {"comment": "ping"}    # EventSourceResponse comment syntax for heartbeat
                        _last_event_time = time.time()

                    delay = POLL + random.uniform(0, 0.5)
                    await asyncio.sleep(delay)        # SSE-2: non-blocking sleep
                except Exception as exc:
                    if isinstance(exc, asyncio.CancelledError):   # SSE-4: do not swallow CancelledError
                        raise
                    delay = POLL + random.uniform(0, 0.5)
                    await asyncio.sleep(delay)
        finally:
            conn.close()                              # D-11: guaranteed cleanup

    return EventSourceResponse(generate())           # D-03: replaces StreamingResponse
```

**Specific change notes (point-by-point from CONTEXT.md decisions):**

| Source line | Change | Decision |
|-------------|--------|----------|
| `def generate():` | → `async def generate():` | D-01 |
| `sqlite3.connect(jellyswipe.db.DB_PATH)` | → `sqlite3.connect(jellyswipe.db.DB_PATH, check_same_thread=False)` | D-10, SQL-1 |
| *(missing)* | Add `if await request.is_disconnected(): break` at top of while-loop body | D-06 |
| `time.sleep(delay)` (×2) | → `await asyncio.sleep(delay)` | SSE-2 |
| `yield f"data: ...\n\n"` | → `yield {"data": ...}` (dict — EventSourceResponse serializes) | D-03 |
| `yield ": ping\n\n"` | → `yield {"comment": "ping"}` | D-03 |
| `except GeneratorExit: return` | Remove entirely | D-08, SSE-1 |
| `except Exception:` | → `except Exception as exc: if isinstance(exc, asyncio.CancelledError): raise` | D-09, SSE-4 |
| `StreamingResponse(generate(), media_type='text/event-stream', headers={...})` | → `EventSourceResponse(generate())` | D-03 |

---

#### SSE response class pattern

Source: `jellyswipe/__init__.py` lines 342–346 (old pattern — replaced):

```python
# OLD — remove this
return StreamingResponse(
    generate(),
    media_type='text/event-stream',
    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
)

# NEW — use this (D-03)
return EventSourceResponse(generate())
```

Per D-04: verify that `EventSourceResponse` emits `Cache-Control: no-cache` and `X-Accel-Buffering: no`. If it does not, pass them explicitly:

```python
return EventSourceResponse(generate(), headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
```

---

#### Router registration pattern

Copy from `jellyswipe/routers/rooms.py` line 101 (existing decorator pattern):

```python
@rooms_router.get('/room/{code}/stream')
```

The new route appends to the existing `rooms_router` APIRouter (line 25). No change to `jellyswipe/__init__.py` app factory is needed — `rooms_router` is already registered via `app.include_router(rooms_router)` (line 270).

---

### `jellyswipe/__init__.py` — remove inline SSE block

**Analog:** itself (self-modification — delete lines 275–347)

Lines to remove (source: `jellyswipe/__init__.py` lines 275–347):

```python
# SSE route — stays inline per D-15; Phase 34 migrates it
@app.get('/room/{code}/stream')
def room_stream(code: str, request: Request):
    _require_login(request)
    def generate():
        ...
    return StreamingResponse(
        generate(),
        media_type='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )
```

After deletion, `return app` (line 348) becomes the immediate close of `create_app()`. Also remove `StreamingResponse` from the imports at line 21 if it is no longer used elsewhere in `__init__.py` after this deletion.

---

### `pyproject.toml` — add `sse-starlette` dependency

**Analog:** `pyproject.toml` lines 9–17 (existing `[project.dependencies]` block)

Existing pattern:

```toml
[project]
dependencies = [
    "fastapi>=0.136.1",
    "itsdangerous>=2.2.0",
    "jinja2>=3.1.6",
    "python-dotenv>=1.2.2",
    "python-multipart>=0.0.18",
    "requests>=2.33.1",
    "uvicorn[standard]>=0.46.0",
]
```

New entry (add in alphabetical order, after `requests`):

```toml
[project]
dependencies = [
    "fastapi>=0.136.1",
    "itsdangerous>=2.2.0",
    "jinja2>=3.1.6",
    "python-dotenv>=1.2.2",
    "python-multipart>=0.0.18",
    "requests>=2.33.1",
    "sse-starlette>=3.4.1",
    "uvicorn[standard]>=0.46.0",
]
```

After editing, run `uv sync` to regenerate `uv.lock`.

---

## Shared Patterns

### Authentication
**Source:** `jellyswipe/routers/rooms.py` lines 102, 124, 150, 277, 321, 341, 358
**Apply to:** `room_stream()` in rooms.py

```python
user: AuthUser = Depends(require_auth)
```

The new route uses this exact pattern. Import already present in rooms.py line 22:
`from jellyswipe.dependencies import AuthUser, DBConn, check_rate_limit, get_db_dep, get_provider, require_auth`

### SQLite connection for long-lived streams
**Source:** `jellyswipe/__init__.py` lines 292–340
**Apply to:** `generate()` inner function only

```python
import jellyswipe.db
conn = sqlite3.connect(jellyswipe.db.DB_PATH, check_same_thread=False)
conn.row_factory = sqlite3.Row
try:
    ...  # poll loop
finally:
    conn.close()
```

Note: `get_db_dep()` / `DBConn` are request-scoped and cannot serve a streaming lifetime. Direct `sqlite3.connect()` with manual `try/finally` is the correct pattern here (D-10).

### CancelledError-safe exception handling
**Source:** CONTEXT.md D-09 (no existing analog — this is a new pattern)
**Apply to:** `except` clause inside `generate()` poll loop

```python
except Exception as exc:
    if isinstance(exc, asyncio.CancelledError):
        raise
    delay = POLL + random.uniform(0, 0.5)
    await asyncio.sleep(delay)
```

### Disconnect detection
**Source:** CONTEXT.md D-06 (no existing analog in codebase)
**Apply to:** Top of each poll iteration in `generate()`, before the SQLite query

```python
if await request.is_disconnected():
    break
```

`request` is closed over from `room_stream()`'s parameter — no additional passing needed.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| *(none)* | — | — | All patterns are covered by direct source migration or existing room route conventions |

The CancelledError-safe exception pattern and `request.is_disconnected()` check have no codebase analog (new patterns per D-06, D-09), but both are fully specified in CONTEXT.md with exact code.

---

## Metadata

**Analog search scope:** `jellyswipe/__init__.py`, `jellyswipe/routers/rooms.py`, `jellyswipe/dependencies.py`, `jellyswipe/db.py`, `pyproject.toml`
**Files scanned:** 5
**Pattern extraction date:** 2026-05-03
