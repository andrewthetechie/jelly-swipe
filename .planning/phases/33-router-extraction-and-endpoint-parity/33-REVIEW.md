---
phase: 33-router-extraction-and-endpoint-parity
reviewed: 2026-05-03T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - jellyswipe/config.py
  - jellyswipe/routers/__init__.py
  - jellyswipe/routers/auth.py
  - jellyswipe/routers/static.py
  - jellyswipe/routers/media.py
  - jellyswipe/routers/proxy.py
  - jellyswipe/routers/rooms.py
  - jellyswipe/__init__.py
  - tests/test_tmdb_auth.py
findings:
  critical: 2
  warning: 5
  info: 5
  total: 12
status: issues_found
---

# Phase 33: Code Review Report

**Reviewed:** 2026-05-03T00:00:00Z
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Phase 33 extracted five domain routers from the monolithic `__init__.py` into `jellyswipe/routers/`. The refactor is structurally sound — parameterized queries are used throughout, the `BEGIN IMMEDIATE` transaction is preserved verbatim, and `XSSSafeJSONResponse` is applied consistently. However, two critical defects were introduced that break existing tests outright: the conftest `client` fixture calls a Flask-only API on a FastAPI app, and the `TestBearerTokenHeaders` tests patch a symbol that no longer exists at the `jellyswipe` package level after routes moved to `jellyswipe.routers.media`. There are also five warnings around missing input validation, silent failure modes, a broken TYPE_CHECKING guard, and a deployment footgun with `ProxyHeadersMiddleware`.

---

## Critical Issues

### CR-01: `conftest.py` calls `app.test_client()` on a FastAPI app — all route tests fail

**File:** `tests/conftest.py:228`
**Issue:** The `client` fixture calls `app.test_client()`, which is a Flask API. `create_app()` now returns a `FastAPI` instance, which has no `test_client()` method. Any test that injects the `client` fixture (including `TestBearerTokenHeaders` in `test_tmdb_auth.py`) fails immediately with `AttributeError: 'FastAPI' object has no attribute 'test_client'` before the test body executes.
**Fix:**
```python
# tests/conftest.py
from fastapi.testclient import TestClient

@pytest.fixture
def client(app):
    """Provide a Starlette/FastAPI test client for HTTP requests."""
    return TestClient(app)
```

---

### CR-02: `TestBearerTokenHeaders` patches `jellyswipe.make_http_request` — a symbol that does not exist at the package level

**File:** `tests/test_tmdb_auth.py:74` and `tests/test_tmdb_auth.py:106`
**Issue:** After Phase 33, the trailer and cast routes live in `jellyswipe/routers/media.py`, which imports `make_http_request` as `from jellyswipe.http_client import make_http_request`. `make_http_request` is never imported into `jellyswipe/__init__.py`, so `jellyswipe.make_http_request` does not exist. `unittest.mock.patch('jellyswipe.make_http_request', ...)` raises `AttributeError` at test runtime, causing both `test_tmdb_bearer_token_in_trailer_headers` and `test_tmdb_bearer_token_in_cast_headers` to fail. The mocked function is never installed, so even if the error were swallowed, the real HTTP client would be called against a live TMDB API.
**Fix:**
```python
# Patch the symbol where it is actually looked up — in the media router module
with patch('jellyswipe.routers.media.make_http_request',
           side_effect=[mock_response, second_response]) as mock_http:
    ...
```

---

## Warnings

### WR-01: `add_to_watchlist` silently calls provider with `None` `movie_id` when body field is absent

**File:** `jellyswipe/routers/media.py:143-151`
**Issue:** The route declares `body: dict = None` (body is optional). If the request body is omitted or does not contain `movie_id`, `movie_id` is `None` and `get_provider().add_to_user_favorites(user.jf_token, None)` is called unconditionally. No 400 validation error is returned. Depending on the Jellyfin provider implementation this either silently no-ops or raises an exception that becomes a 500.
**Fix:**
```python
@media_router.post('/watchlist/add')
def add_to_watchlist(request: Request, user: AuthUser = Depends(require_auth),
                     _: None = Depends(check_rate_limit), body: dict = None):
    try:
        movie_id = (body or {}).get('movie_id')
        if not movie_id:
            return XSSSafeJSONResponse(
                content={'error': 'movie_id required'}, status_code=400
            )
        get_provider().add_to_user_favorites(user.jf_token, movie_id)
        return {'status': 'success'}
    ...
```

---

### WR-02: `_RATE_LIMITS` dict is duplicated in `config.py` and `dependencies.py` — they can silently diverge

**File:** `jellyswipe/config.py:76-81` and `jellyswipe/dependencies.py:52-57`
**Issue:** `_RATE_LIMITS` is defined identically in both files. `dependencies.py` uses its own copy for enforcement; `config.py`'s copy is never read by any router or dependency. If a limit is updated in one file but not the other, the wrong limit is silently enforced. This is the kind of divergence that causes production incidents.
**Fix:** Delete `_RATE_LIMITS` from `config.py` (it is unused there) or make `dependencies.py` import it from `config.py`:
```python
# dependencies.py
from jellyswipe.config import _RATE_LIMITS  # single source of truth
```

---

### WR-03: `ProxyHeadersMiddleware` uses default `trusted_hosts='127.0.0.1'` — IP-based rate limiting breaks behind a non-loopback reverse proxy

**File:** `jellyswipe/__init__.py:251`
**Issue:** `app.add_middleware(ProxyHeadersMiddleware)` uses the default `trusted_hosts='127.0.0.1'`. When deployed behind a reverse proxy whose IP is not `127.0.0.1` (e.g., a Docker network gateway, a cloud load balancer), `X-Forwarded-For` is not rewritten, so `request.client.host` in `check_rate_limit` always resolves to the proxy IP. This means all users share a single rate-limit bucket, and the first legitimate burst of traffic from `N` concurrent users exhausts everyone's quota.
**Fix:**
```python
# Allow configuration via env var
trusted = os.getenv('TRUSTED_PROXY_IPS', '127.0.0.1')
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=trusted)
```

---

### WR-04: Broken `TYPE_CHECKING` guard in `config.py` — the entire `if False:` block is dead code

**File:** `jellyswipe/config.py:85-91`
**Issue:** The guard is `if False:  # TYPE_CHECKING`. The `if False` block **never executes**. The `from typing import TYPE_CHECKING` and the inner `if TYPE_CHECKING:` import on lines 86–89 are permanently unreachable. The comment claims this prevents a circular import, but the mechanism is wrong. The `else:` branch (line 90–91) executes unconditionally and uses a string annotation `Optional['JellyfinLibraryProvider']`, which is the correct way to avoid a circular import at runtime — but the `if False:` wrapper around the dead branch is misleading and will confuse future maintainers.
**Fix:**
```python
# config.py — remove the if False block entirely; the else branch is already correct
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from jellyswipe.jellyfin_library import JellyfinLibraryProvider

_provider_singleton: Optional['JellyfinLibraryProvider'] = None
```

---

### WR-05: `swipe` handler inserts a swipe record for any room code without validating the room exists

**File:** `jellyswipe/routers/rooms.py:200-258`
**Issue:** The swipe handler performs `conn.execute('INSERT INTO swipes ...')` inside the `BEGIN IMMEDIATE` transaction without first verifying that a row exists in `rooms` for `code`. If the room has been deleted (e.g., by `quit_room`) between the client loading the deck and submitting a swipe, the swipe is inserted against a non-existent room, the cursor update is a silent no-op (UPDATE matches 0 rows), and `{'accepted': True}` is returned to the client. This is a pre-existing design choice (D-12 preserves the body verbatim), but it means orphaned swipe rows accumulate permanently — `init_db` only cleans up swipes for deleted rooms at startup. The match detection also queries `rooms` (line 212) and silently skips match processing when `room` is `None`, masking the error entirely.
**Fix:** Add an existence check at the start of the transaction body and return a 404 if the room is gone:
```python
conn.execute('BEGIN IMMEDIATE')
try:
    room_check = conn.execute(
        'SELECT 1 FROM rooms WHERE pairing_code = ?', (code,)
    ).fetchone()
    if not room_check:
        conn.execute('ROLLBACK')
        return XSSSafeJSONResponse(
            content={'error': 'Room not found'}, status_code=404
        )
    # ... rest of swipe logic
```

---

## Info

### IN-01: `HTTPException` imported but never raised in `rooms.py`, `auth.py`, and `media.py`

**File:** `jellyswipe/routers/rooms.py:17`, `jellyswipe/routers/auth.py:10`, `jellyswipe/routers/media.py:9`
**Issue:** All three routers import `HTTPException` from fastapi but return `XSSSafeJSONResponse` or `JSONResponse` objects for every error path. `HTTPException` is never instantiated or raised.
**Fix:** Remove `HTTPException` from the import in each file where it is unused.

---

### IN-02: `Response` and `get_db_dep` imported but never used in `rooms.py`; `check_rate_limit` and `TMDB_AUTH_HEADERS` imported but never used in `auth.py`

**File:** `jellyswipe/routers/rooms.py:17` (`Response`), `jellyswipe/routers/rooms.py:22` (`get_db_dep`, `check_rate_limit`), `jellyswipe/routers/auth.py:13` (`check_rate_limit`), `jellyswipe/routers/auth.py:15` (`TMDB_AUTH_HEADERS`)
**Issue:** Several symbols are imported and never referenced beyond the import line. `get_db_dep` in `rooms.py` is superseded by the `DBConn` type alias (which embeds the dependency). `check_rate_limit` is imported in `rooms.py` and `auth.py` but no route in either file applies it.
**Fix:** Remove the unused names from each import statement.

---

### IN-03: `typing` imported at module level in `rooms.py` but never used

**File:** `jellyswipe/routers/rooms.py:15`
**Issue:** `import typing` is present but `typing.` is not referenced anywhere in the file.
**Fix:** Remove `import typing`.

---

### IN-04: `make_error_response` and `log_exception` are copy-pasted identically across three router files

**File:** `jellyswipe/routers/auth.py:23-49`, `jellyswipe/routers/media.py:23-49`, `jellyswipe/routers/rooms.py:34-57`
**Issue:** Three identical definitions of `make_error_response` and `log_exception` exist. Any fix or enhancement to one must be replicated manually to the others.
**Fix:** Extract both helpers to a shared module (e.g., `jellyswipe/routers/_utils.py`) and import from there.

---

### IN-05: `__import__('time')` used inline in `rooms.py` swipe handler instead of the already-imported `time` module

**File:** `jellyswipe/routers/rooms.py:226` and `jellyswipe/routers/rooms.py:250`
**Issue:** `__import__('time').time()` is called twice inside the `BEGIN IMMEDIATE` transaction body. `time` is not imported at the top of `rooms.py`, so this workaround was used. `__import__` is a dynamic import mechanism that bypasses the normal import system conventions; it is harder to read and grep. The module-level `import time` is the correct fix.
**Fix:**
```python
# Add to top-level imports in rooms.py:
import time

# In swipe handler, replace:
__import__('time').time()
# with:
time.time()
```

---

_Reviewed: 2026-05-03T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
