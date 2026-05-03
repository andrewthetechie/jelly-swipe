---
phase: 31-fastapi-app-factory-and-session-middleware
reviewed: 2026-05-02T00:00:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - jellyswipe/__init__.py
  - jellyswipe/auth.py
findings:
  critical: 3
  warning: 4
  info: 2
  total: 9
status: issues_found
---

# Phase 31: Code Review Report

**Reviewed:** 2026-05-02
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Reviewed the FastAPI app factory (`jellyswipe/__init__.py`) and the session/auth module (`jellyswipe/auth.py`). The overall structure is sound and the security-oriented design choices (XSS-safe JSON, CSP header, SSRF validation, request IDs) are correct. However, three critical defects were found: a path traversal vulnerability on the static file route, a pervasive database connection leak caused by using `get_db()` where `get_db_closing()` is required, and a broken transaction sequence in the multi-user swipe handler that creates a window for a phantom match. Four warnings cover a missing input validation gap on the watchlist endpoint, an insecure pairing-code space, a silent exception swallow in `_jellyfin_user_token_from_request`, and a `conn.commit()` call issued against a connection managed by `get_db()`'s context protocol.

---

## Critical Issues

### CR-01: Path Traversal on Static File Route

**File:** `jellyswipe/__init__.py:874`
**Issue:** The `path` parameter from the URL is joined directly onto `_APP_ROOT/static/` with no sanitization. A request like `GET /static/../../auth.py` resolves outside the static directory and returns arbitrary application source files, including `auth.py`, `db.py`, or any file readable by the process. `os.path.join` does not strip `..` segments.

```python
# VULNERABLE — current code
def serve_static_route(path: str, request: Request):
    return FileResponse(path=os.path.join(_APP_ROOT, 'static', path))
```

**Fix:** Resolve and assert the target stays inside the static root before serving.

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

### CR-02: Database Connection Leak — `get_db()` Does Not Close Connections

**File:** `jellyswipe/__init__.py:282, 508, 536, 550, 566, 598, 665, 675, 691, 703, 721, 743` and `jellyswipe/auth.py:33, 59, 79`
**Issue:** `get_db()` (defined in `db.py` lines 11-17) returns a bare `sqlite3.Connection`. Using it as `with get_db() as conn:` invokes `sqlite3.Connection.__enter__`/`__exit__`, which manages the transaction (commit/rollback) but **never closes the connection**. Every one of the ~15 call sites leaks an open file descriptor and SQLite connection for the lifetime of the process. Under load this will exhaust OS file descriptor limits and corrupt WAL state. `get_db_closing()` (also in `db.py`) is the correct context manager that calls `conn.close()` in its `finally` block.

**Fix:** Replace every `with get_db() as conn:` with `with get_db_closing() as conn:`. Both `__init__.py` and `auth.py` are affected. `get_db_closing()` is already imported in `__init__.py` at line 234; `auth.py` needs to add it to its import.

```python
# auth.py — change import
from jellyswipe.db import get_db_closing, cleanup_expired_tokens

# auth.py — change every with block
with get_db_closing() as conn:
    conn.execute(...)
```

```python
# __init__.py — every route handler
with get_db_closing() as conn:
    ...
```

---

### CR-03: Broken Transaction in Multi-User Swipe — `conn.commit()` Releases Implicit Transaction Before `BEGIN IMMEDIATE`

**File:** `jellyswipe/__init__.py:625-655`
**Issue:** The multi-user swipe path explicitly calls `conn.commit()` (line 625) while the connection is managed by `with get_db() as conn:` (which drives the transaction via the context manager). After that commit the code immediately issues `conn.execute('BEGIN IMMEDIATE')` (line 627). This sequence is wrong in two ways:

1. `conn.commit()` inside a `with conn:` block commits the outer implicit transaction early; `conn.__exit__` will then attempt a second commit on an already-committed (or now-empty) transaction — behaviour that varies by SQLite version.
2. More critically: between `conn.commit()` (line 625) and `conn.execute('BEGIN IMMEDIATE')` (line 627) there is a gap with no lock held. A concurrent swipe from the other user can insert its row in that gap, causing the `other_swipe` query to miss it. This is the exact race condition `BEGIN IMMEDIATE` was supposed to prevent.

**Fix:** Remove the early `conn.commit()`. Structure the entire swipe operation as a single `BEGIN IMMEDIATE` block from the start of the handler, or use `get_db_closing()` and manage the transaction explicitly without relying on the context manager's auto-commit.

```python
# Correct pattern — one atomic block
with get_db_closing() as conn:
    conn.execute('BEGIN IMMEDIATE')
    try:
        # Insert swipe, update cursor, check for match — all here
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise
```

---

## Warnings

### WR-01: `add_to_watchlist` Accepts Unauthenticated Body — No `movie_id` Validation

**File:** `jellyswipe/__init__.py:451-462`
**Issue:** The endpoint signature is `def add_to_watchlist(request: Request, body: dict = None)`. FastAPI does not parse a plain `dict` body automatically for a synchronous route — the `body` parameter will always be `None` in practice, so `movie_id` is always `None`. Even if it were populated, there is no validation that `movie_id` is a non-empty string before it is passed to `add_to_user_favorites`. Passing `None` to the provider likely causes an unhandled exception that leaks a 500.

**Fix:** Use `async def`, read the body explicitly (as done in other endpoints), and validate `movie_id` before use.

```python
@app.post('/watchlist/add')
async def add_to_watchlist(request: Request):
    _require_login(request)
    rl = _check_rate_limit('watchlist/add', request)
    if rl:
        return JSONResponse(content=rl[0], status_code=rl[1])
    try:
        data = await request.json()
    except Exception:
        data = {}
    movie_id = str(data.get('movie_id') or '').strip()
    if not movie_id:
        return make_error_response('movie_id required', 400, request)
    try:
        get_provider().add_to_user_favorites(request.state.jf_token, movie_id)
        return {'status': 'success'}
    except Exception as e:
        log_exception(e, request)
        return make_error_response('Internal server error', 500, request)
```

---

### WR-02: Pairing Code Is a 4-Digit Number — Trivially Guessable

**File:** `jellyswipe/__init__.py:534, 548`
**Issue:** Room pairing codes are generated with `random.randint(1000, 9999)`, producing only 9000 possible values. An attacker with a valid session can enumerate all codes in a trivial loop and join another user's active room, accessing their movie deck and swiping on their behalf. `random` is not cryptographically secure.

**Fix:** Use `secrets` to generate a longer, unguessable code.

```python
import secrets
pairing_code = secrets.token_hex(4)  # 8 hex chars, 2^32 space
```

Alternatively, use a 6-digit numeric code (`secrets.randbelow(900000) + 100000`) if a numeric UI is required.

---

### WR-03: Silent Exception Swallow in `_jellyfin_user_token_from_request`

**File:** `jellyswipe/__init__.py:292-306`
**Issue:** The `except Exception: token = None` block (lines 304-305) silently discards all errors from `extract_media_browser_token`, including programming errors, import failures, and unexpected exceptions from the provider. This makes authentication failures completely invisible in logs and is a maintenance hazard.

**Fix:** Log the exception at debug or warning level before suppressing it.

```python
except Exception as exc:
    _logger.debug("extract_media_browser_token failed: %s", exc)
    token = None
```

---

### WR-04: `XSSSafeJSONResponse.render` Double-Encodes Already-Escaped Content

**File:** `jellyswipe/__init__.py:93-98`
**Issue:** `super().render(content)` calls the standard `JSONResponse.render`, which uses `json.dumps` with `ensure_ascii=True` (the default). Python's `json.dumps` already encodes `<`, `>`, and `&` as `<`, `>`, `&` by default when `ensure_ascii=True`. The subsequent `bytes.replace` calls in `render` then attempt to replace the literal byte sequences `b"<"`, `b">"`, `b"&"` — which will never appear in the output of `json.dumps` with `ensure_ascii=True`. The XSS defence is a no-op for strings passed as Python objects. However, if any pre-serialized raw bytes containing `<` or `>` are ever passed, or if `ensure_ascii` changes in a future Python version, the encoding would double-encode already-escaped sequences.

**Fix:** Either rely on `json.dumps`'s built-in escaping (Python does this by default and it is sufficient for JSON-in-HTML contexts) and remove the custom class, or explicitly pass `ensure_ascii=False` to expose the raw characters so the `replace` calls actually do work:

```python
import json as _json

class XSSSafeJSONResponse(JSONResponse):
    def render(self, content: typing.Any) -> bytes:
        # Explicit escape of HTML-sensitive chars — works with ensure_ascii=False
        text = _json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
        )
        text = text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
        return text.encode("utf-8")
```

---

## Info

### IN-01: Module-Level Environment Variable Validation Runs at Import Time

**File:** `jellyswipe/__init__.py:48-65`
**Issue:** The `missing` variable check and the `raise RuntimeError` execute when the module is first imported, not inside `create_app()`. This makes it impossible to import the module in test environments without setting all required environment variables, even for unit tests that mock the provider. It also runs before `load_dotenv` has had a chance to be validated by any test harness.

**Fix:** Move the environment validation block inside `create_app()`, where it runs only when an actual application instance is being created.

---

### IN-02: `cleanup_expired_tokens` Uses ISO 8601 String Comparison for Expiry

**File:** `jellyswipe/auth.py:30` (calls `db.cleanup_expired_tokens`)
**Issue:** The expiry logic in `db.py:108` compares `created_at < cutoff` as ISO 8601 strings. This works correctly only if all `created_at` values use the same timezone representation. `datetime.now(timezone.utc).isoformat()` produces `+00:00`-suffixed strings (e.g. `2026-05-02T10:00:00+00:00`). SQLite lexicographic string comparison on these values is correct only because `+00:00` sorts consistently. If any legacy row was inserted with a `Z`-suffix or a naive datetime, it would compare incorrectly and never expire. This is fragile; a note or assertion would prevent future breakage.

**Fix:** Store `created_at` as a Unix timestamp (integer) or ensure the insert always uses the same `isoformat()` format with an explicit `timezone.utc` argument (already done in `auth.py:27`). Add a comment in `cleanup_expired_tokens` documenting the format invariant.

---

_Reviewed: 2026-05-02_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
