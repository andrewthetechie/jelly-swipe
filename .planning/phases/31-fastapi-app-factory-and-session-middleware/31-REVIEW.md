---
phase: 31-fastapi-app-factory-and-session-middleware
reviewed: 2026-05-02T00:00:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - jellyswipe/__init__.py
  - jellyswipe/auth.py
findings:
  critical: 5
  warning: 6
  info: 0
  total: 11
status: issues_found
---

# Phase 31: Code Review Report

**Reviewed:** 2026-05-02
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Reviewed the FastAPI app factory (`jellyswipe/__init__.py`) and the session/auth module (`jellyswipe/auth.py`). The middleware wiring, `XSSSafeJSONResponse` class, lifespan pattern, CSP/request-ID middleware, and proxy header ordering are structurally correct. Five blocker-level defects were found: a pervasive database connection leak caused by misusing `get_db()` as a context manager (every route leaks), a 14-day session cookie paired with a 24-hour vault TTL that silently logs users out every day, `str(None)` being stored as a literal movie ID when request bodies omit `movie_id`, a path traversal vulnerability on the static file route, and a broken manual transaction nested inside a context-managed connection in the swipe handler. Six warnings cover direct `JSONResponse` usage bypassing XSS escaping, unencoded user data in TMDB URLs, an unhandled `ValueError` on the `page` parameter, unauthenticated room status and SSE stream endpoints, a non-collision-checked guessable pairing code, and a re-read of `JELLYFIN_URL` inside `create_app()` that can bypass boot-time SSRF validation.

---

## Critical Issues

### CR-01: Database connection leak — `get_db()` used as context manager never closes the connection

**File:** `jellyswipe/__init__.py:282, 508, 536, 550, 566, 598, 665, 675, 691, 703, 721, 743` and `jellyswipe/auth.py:33, 59, 79`

**Issue:** `get_db()` (defined in `db.py:11-16`) returns a raw `sqlite3.Connection` object. SQLite's built-in context manager protocol (`__enter__`/`__exit__`) commits on success and rolls back on exception, but **does not close the connection**. Every `with get_db() as conn:` block throughout both files opens a new connection and leaks it — the connection is never closed. Over time, under any real load, this exhausts OS file descriptors. The correct helper that closes connections is `get_db_closing()`, which wraps `with conn:` inside a `finally: conn.close()`. This affects all 13 call sites in `__init__.py` and all 3 in `auth.py`.

**Fix:** Replace every `with get_db() as conn:` with `with get_db_closing() as conn:`. `get_db_closing()` is already imported at line 234 of `__init__.py`; `auth.py` must add it to its import.

```python
# auth.py — change import
from jellyswipe.db import get_db_closing, cleanup_expired_tokens

# auth.py and __init__.py — every with block
with get_db_closing() as conn:
    conn.execute(...)
```

---

### CR-02: Session vault expires tokens after 24 hours; cookie lives 14 days — silent auth failure

**File:** `jellyswipe/__init__.py:205` / `jellyswipe/db.py:101-113` / `jellyswipe/auth.py:30`

**Issue:** `SessionMiddleware` is configured with `max_age=14 * 24 * 60 * 60` (14 days, line 205). The browser retains the cookie for 14 days. However, `cleanup_expired_tokens()` in `db.py` deletes vault rows older than 24 hours, and `create_session()` in `auth.py` calls this cleanup on every new login. A user who logs in and returns on day 2 will have a valid session cookie but `_require_login` will find no matching vault row and return 401. The user is silently logged out every ~24 hours with no feedback.

**Fix:** Either extend the vault TTL to match the cookie `max_age`:

```python
# db.py: cleanup_expired_tokens
cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
```

Or reduce the cookie `max_age` to 24 hours (`max_age=24 * 60 * 60`). The two values must agree.

---

### CR-03: `str(None)` stores the literal string `"None"` as `movie_id` when body omits the field

**File:** `jellyswipe/__init__.py:587, 690, 702`

**Issue:** All three handlers (`swipe`, `delete_match`, `undo_swipe`) do:

```python
mid = str(data.get('movie_id'))
```

When `movie_id` is absent from the request body, `data.get('movie_id')` returns `None`, and `str(None)` returns the string `"None"`. This value is then inserted into the `swipes` table or used in `DELETE` statements as a valid-looking movie ID. A client that accidentally omits `movie_id` will corrupt the database with `"None"` rows, and a targeted `DELETE` with `movie_id = "None"` could destroy every such row across users.

**Fix:** Validate that `movie_id` is present and non-None before proceeding:

```python
mid = data.get('movie_id')
if not mid:
    return JSONResponse(content={'error': 'movie_id required'}, status_code=400)
mid = str(mid)
```

---

### CR-04: Path traversal in static file route — arbitrary file read

**File:** `jellyswipe/__init__.py:873-874`

**Issue:**

```python
@app.get('/static/{path:path}')
def serve_static_route(path: str, request: Request):
    return FileResponse(path=os.path.join(_APP_ROOT, 'static', path))
```

`os.path.join` does not sanitise `..` segments. A request to `/static/../../jellyswipe/auth.py` or `/static/../.env` resolves outside the `static/` directory and serves arbitrary files readable by the process. Starlette's `StaticFiles` mount handles this safely; bare `FileResponse` with a user-supplied path does not.

**Fix:** Use Starlette's `StaticFiles` mount, or add explicit path-containment validation:

```python
from starlette.staticfiles import StaticFiles
app.mount('/static', StaticFiles(directory=os.path.join(_APP_ROOT, 'static')), name='static')
```

If a manual route is required:

```python
import pathlib
_STATIC_ROOT = pathlib.Path(_APP_ROOT, 'static').resolve()

def serve_static_route(path: str, request: Request):
    target = (_STATIC_ROOT / path).resolve()
    if not str(target).startswith(str(_STATIC_ROOT) + os.sep):
        raise HTTPException(status_code=403)
    if not target.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(path=str(target))
```

---

### CR-05: Broken manual transaction nested inside `with get_db() as conn:` in swipe endpoint

**File:** `jellyswipe/__init__.py:625-655`

**Issue:** The multi-user match path calls `conn.commit()` at line 625 while inside the outer `with get_db() as conn:` block, then immediately issues `conn.execute('BEGIN IMMEDIATE')` at line 627. This is incorrect:

1. `conn.commit()` inside a `with conn:` block commits and closes the implicit transaction; `conn.__exit__` will then commit again on an already-committed transaction, whose behaviour is version-dependent.
2. More critically: there is an unprotected gap between `conn.commit()` (line 625) and `conn.execute('BEGIN IMMEDIATE')` (line 627) where no lock is held. A concurrent swipe from the second user can insert its `swipes` row in that gap, causing the `other_swipe` query at line 629 to miss it and silently skip match detection.

**Fix:** Remove the early `conn.commit()` and structure the entire handler as a single `BEGIN IMMEDIATE` block using `get_db_closing()`:

```python
with get_db_closing() as conn:
    conn.execute('BEGIN IMMEDIATE')
    try:
        conn.execute('INSERT INTO swipes ...')
        # cursor update, match detection — all here
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise
```

---

## Warnings

### WR-01: Direct `JSONResponse` in `make_error_response` and rate-limit returns bypasses XSS escaping

**File:** `jellyswipe/__init__.py:259, 373, 411, 455, 489, 529, 578, 741, 839, 855`

**Issue:** `make_error_response()` at line 259 constructs a plain `JSONResponse` instead of `XSSSafeJSONResponse`. Error messages can contain reflected data (the `message` parameter comes from call sites), so these responses bypass the XSS defence the class was designed to provide. Rate limit responses (lines 373, 411, 455, 839) and several inline responses have the same problem.

**Note:** Python's `json.dumps` with `ensure_ascii=True` (the default) already encodes `<`, `>`, `&` as Unicode escapes, which means `XSSSafeJSONResponse.render` as written is currently a no-op (the `bytes.replace` calls target literal `b"<"` which `json.dumps` never emits). However, correctness here means using the designated class consistently so the intent is enforced regardless of serializer behaviour.

**Fix:**

```python
# make_error_response (line 259)
return XSSSafeJSONResponse(content=body, status_code=status_code)

# Rate limit and inline responses
return XSSSafeJSONResponse(content=rl[0], status_code=rl[1])
```

---

### WR-02: User-controlled `item.title` and `item.year` interpolated unencoded into TMDB URL

**File:** `jellyswipe/__init__.py:376, 414`

**Issue:**

```python
search_url = f"https://api.themoviedb.org/3/search/movie?query={item.title}&year={item.year}"
```

`item.title` comes from Jellyfin library data and is not URL-encoded. A movie title containing `&`, `=`, `#`, or `?` (e.g., `"Q&A"`, `"Spider-Man: No Way Home"`) will produce a malformed URL, corrupting the query or truncating the year parameter, causing missed trailers and cast data.

**Fix:**

```python
from urllib.parse import urlencode
params = urlencode({'query': item.title, 'year': item.year})
search_url = f"https://api.themoviedb.org/3/search/movie?{params}"
```

---

### WR-03: `page` query parameter parsed with `int()` — unhandled `ValueError` on non-numeric input

**File:** `jellyswipe/__init__.py:719`

**Issue:**

```python
page = int(request.query_params.get('page', 1))
```

If a client sends `?page=abc` or `?page=`, `int()` raises `ValueError`, which propagates as an unhandled exception and produces a 500 Internal Server Error instead of a 400 Bad Request.

**Fix:**

```python
try:
    page = max(1, int(request.query_params.get('page', 1)))
except (ValueError, TypeError):
    return JSONResponse(content={'error': 'Invalid page parameter'}, status_code=400)
```

---

### WR-04: `GET /room/{code}/status` and `GET /room/{code}/stream` have no authentication

**File:** `jellyswipe/__init__.py:756-762, 765-833`

**Issue:** Both `room_status` and `room_stream` routes are missing `_require_login(request)`. Any unauthenticated client who can guess or brute-force a 4-digit pairing code (only 9,000 possibilities) can poll the SSE stream or status endpoint and receive match data, genre changes, and ready state without being a room participant. The SSE stream also exposes `last_match_data` including movie titles, thumbnails, and deep links.

**Fix:** Add `_require_login(request)` as the first statement of both handlers:

```python
def room_status(code: str, request: Request):
    _require_login(request)
    ...

def room_stream(code: str, request: Request):
    _require_login(request)
    ...
```

---

### WR-05: Room pairing code uses `random.randint` with no uniqueness check — collision and predictability

**File:** `jellyswipe/__init__.py:534, 548`

**Issue:** `pairing_code = str(random.randint(1000, 9999))` has two problems. First, `random.randint` is not cryptographically secure — an attacker can guess codes with high probability across the 9,000-value space. Second, there is no uniqueness check before `INSERT INTO rooms`. If a code collision occurs, the INSERT fails with a PRIMARY KEY constraint violation, producing an unhandled exception (500 response) and no room created.

**Fix:** Use `secrets` and check for collisions before inserting:

```python
for _ in range(10):
    pairing_code = str(secrets.randbelow(9000) + 1000)
    existing = conn.execute(
        'SELECT 1 FROM rooms WHERE pairing_code = ?', (pairing_code,)
    ).fetchone()
    if not existing:
        break
else:
    return JSONResponse(content={'error': 'Could not generate unique room code'}, status_code=503)
```

---

### WR-06: `JELLYFIN_URL` re-read from env inside `create_app()` — SSRF validation bypass possible in tests

**File:** `jellyswipe/__init__.py:68, 214`

**Issue:** At module load time, `validate_jellyfin_url(os.getenv("JELLYFIN_URL"))` (line 68) validates the URL against SSRF rules. Inside `create_app()`, the URL is independently re-read:

```python
JELLYFIN_URL = os.getenv("JELLYFIN_URL", "").rstrip("/")
```

If test code mutates `os.environ["JELLYFIN_URL"]` before calling `create_app()` (a standard test pattern), the new value is never validated. A test could inject a `JELLYFIN_URL` pointing to an internal network address and the SSRF guard would not fire.

**Fix:** Capture the validated value at module level and reuse it inside `create_app()`:

```python
# Module level (after validate_jellyfin_url call, line ~69)
_JELLYFIN_URL: str = os.getenv("JELLYFIN_URL", "").rstrip("/")

# Inside create_app()
JELLYFIN_URL = _JELLYFIN_URL
```

---

_Reviewed: 2026-05-02_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
