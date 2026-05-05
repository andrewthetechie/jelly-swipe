---
phase: 35-test-suite-migration-and-full-validation
reviewed: 2026-05-04T12:00:00Z
depth: deep
files_reviewed: 14
files_reviewed_list:
  - jellyswipe/__init__.py
  - jellyswipe/db.py
  - jellyswipe/routers/proxy.py
  - jellyswipe/routers/rooms.py
  - jellyswipe/routers/static.py
  - tests/conftest.py
  - tests/test_error_handling.py
  - tests/test_route_authorization.py
  - tests/test_routes_auth.py
  - tests/test_routes_proxy.py
  - tests/test_routes_room.py
  - tests/test_routes_sse.py
  - tests/test_routes_xss.py
  - tests/test_tmdb_auth.py
findings:
  critical: 3
  warning: 8
  info: 5
  total: 16
status: issues_found
---

# Phase 35: Code Review Report

**Reviewed:** 2026-05-04T12:00:00Z
**Depth:** deep
**Files Reviewed:** 14
**Status:** issues_found

## Summary

Deep review of the production source (5 files) and test suite (9 files) for the Phase 35 test migration. The production code has a connection leak in `cleanup_expired_tokens`, a module-level `create_app()` call that triggers side effects at import time, and an XSS escaping approach that corrupts binary response bodies. The test suite has several findings around weak assertions, duplicated provider stubs, and a skipped test that should be removed or fixed rather than left dormant.

## Critical Issues

### CR-01: Connection leak in `cleanup_expired_tokens` -- `get_db()` never closed

**File:** `jellyswipe/db.py:109`
**Issue:** `cleanup_expired_tokens()` uses `with get_db() as conn:` which enters SQLite's `__enter__` (transaction context manager) but does NOT close the connection when the `with` block exits. `sqlite3.Connection.__exit__` only commits/rollbacks -- it does not call `conn.close()`. Every call to `cleanup_expired_tokens()` (on startup and every `create_session`) leaks an open SQLite connection. Over time this exhausts file descriptors.
**Fix:**
```python
def cleanup_expired_tokens():
    cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    with get_db_closing() as conn:
        conn.execute(
            'DELETE FROM user_tokens WHERE created_at < ?',
            (cutoff,)
        )
```
Use `get_db_closing()` (which calls `conn.close()` in its `finally` block) instead of bare `get_db()`.

### CR-02: XSSSafeJSONResponse byte replacement corrupts binary-like JSON and double-escapes already-safe content

**File:** `jellyswipe/__init__.py:62-67`
**Issue:** The `render()` override applies naive `bytes.replace()` on the entire JSON body. This has two problems:
1. It replaces `&` with `\u0026` **after** `<` and `>` have already been replaced, so any pre-existing `\u003c` or `\u003e` in the original JSON content (e.g., a movie title containing a literal backslash-u sequence) is unaffected, but legitimate `&` characters in JSON string values (e.g., `"Tom & Jerry"`) become `\u0026` in the raw bytes. While JSON parsers decode Unicode escapes correctly, the replacement order is wrong: replacing `&` last means it does NOT double-encode the `\u003c` it just inserted (the `\u003c` contains no `&`), but it does encode `&amp;` patterns if the original JSON contained HTML entities, turning `&amp;` into `\u0026amp;`.
2. More critically, if `XSSSafeJSONResponse` is ever used as the base for non-JSON responses (or if the JSON contains base64-encoded binary data with `<`, `>`, or `&` bytes), the replacement corrupts the payload.

This is classified as BLOCKER because `XSSSafeJSONResponse` is the `default_response_class` for the entire FastAPI app (line 232), meaning every JSON response goes through this -- including responses that may contain user data with `&` characters (e.g., movie titles like "Dungeons & Dragons" returned from `/matches`). The client receives `Dungeons \u0026 Dragons` in the raw HTTP body. While JSON.parse handles this correctly, any client doing raw string matching on the response body will break.

**Fix:** This is an acceptable defense-in-depth measure if the team understands the tradeoff. Document explicitly that all `&` in JSON string values will be Unicode-escaped in the wire format. Alternatively, perform escaping only on HTML template responses and use standard JSONResponse for API endpoints.

### CR-03: Module-level `app = create_app()` triggers side effects on every import

**File:** `jellyswipe/__init__.py:288`
**Issue:** `app = create_app()` at module scope means importing `jellyswipe` for ANY reason (e.g., `from jellyswipe import XSSSafeJSONResponse` in `proxy.py`) creates a full FastAPI app instance, adds middleware, and reads `os.environ["FLASK_SECRET"]` (line 247). If `FLASK_SECRET` is not set at import time, this crashes with `KeyError`. The test suite works around this by setting env vars at conftest module level (line 13-17), but any tool importing jellyswipe in a non-test context without those env vars set will fail. The `config.py` module also runs `validate_jellyfin_url()` and raises `RuntimeError` for missing env vars at import time -- combined with the module-level `create_app()`, this makes the package impossible to import for documentation generation, linting, or IDE indexing without a fully configured environment.
**Fix:** Remove the module-level `create_app()` call or guard it:
```python
# Only create when running as ASGI server, not when imported as library
import os as _os
if _os.environ.get("JELLYSWIPE_CREATE_APP", "1") == "1":
    app = create_app()
```
Or use a lazy pattern. Uvicorn's `--factory` flag supports `jellyswipe:create_app` directly.

## Warnings

### WR-01: `get_db_closing()` yields inside a `with conn:` block but callers use `BEGIN IMMEDIATE` manually

**File:** `jellyswipe/db.py:19-30` / `jellyswipe/routers/rooms.py:205`
**Issue:** `get_db_closing()` wraps the yielded connection in `with conn:` (line 27-28), which enters SQLite's implicit transaction context manager. The swipe handler then calls `conn.execute('BEGIN IMMEDIATE')` on this same connection (rooms.py:205). SQLite does not support nested transactions via `BEGIN` -- if the connection is already in an implicit transaction from the `with conn:` context, the explicit `BEGIN IMMEDIATE` will raise `sqlite3.OperationalError: cannot start a transaction within a transaction`. This works today only because the `DBConn` dependency calls `get_db_dep()` which uses `get_db_closing()`, but the connection may or may not be in auto-commit mode depending on SQLite driver state. The interaction is fragile and undocumented.
**Fix:** Either (a) have `get_db_closing()` yield without the `with conn:` wrapper and let callers manage transactions, or (b) use `conn.isolation_level = None` (autocommit) for connections that need manual transaction control.

### WR-02: Bare `except Exception` swallows all errors in SSE generator loop

**File:** `jellyswipe/routers/rooms.py:447-453`
**Issue:** The inner `except Exception` in the SSE generator (line 447) catches everything except `CancelledError` and silently continues polling. Database corruption errors, `OperationalError` (disk full, locked), and programming errors are all swallowed. The only signal is a delayed retry sleep. This can mask serious issues in production.
**Fix:** Log the exception before continuing:
```python
except Exception as exc:
    if isinstance(exc, asyncio.CancelledError):
        raise
    _logger.warning("SSE poll error for room %s: %s", code, exc)
    delay = POLL + random.uniform(0, 0.5)
    await asyncio.sleep(delay)
```

### WR-03: `__import__('time').time()` inline import anti-pattern

**File:** `jellyswipe/routers/rooms.py:231,262`
**Issue:** `__import__('time').time()` is used twice inside the swipe handler's transaction block. The `time` module is already imported at the top of the file (line 18). This is likely a copy-paste artifact from an earlier version. It works but is confusing and non-idiomatic.
**Fix:** Replace with `time.time()` since `time` is already imported at line 18.

### WR-04: Duplicate `FakeProvider` class in test_route_authorization.py

**File:** `tests/test_route_authorization.py:16-62`
**Issue:** `test_route_authorization.py` defines its own `FakeProvider` class that is nearly identical to the one in `conftest.py` (lines 147-204) but missing `fetch_library_image()` and `list_genres()` methods, and `resolve_item_for_tmdb` returns a different shape (no `thumb` attribute). The conftest `FakeProvider` is used by the `app` fixture, while this local one is used by `app_real_auth` via `_provider_singleton` patching. Having two slightly different FakeProvider implementations risks test behavior diverging from production.
**Fix:** Remove the local `FakeProvider` from `test_route_authorization.py` and import/use the one from `conftest.py`, or refactor `conftest.py` to export it explicitly.

### WR-05: `test_watchlist_500_no_exception_details` has conditional assertion

**File:** `tests/test_error_handling.py:123-125`
**Issue:** The assertion `if resp.status_code == 500:` on line 123 means the test silently passes if the status code is NOT 500. This defeats the purpose of the test -- if the endpoint returns 200 or 401, the test passes without checking anything. The intent was to verify that 500 errors don't leak details, but the test doesn't even assert the expected status code.
**Fix:**
```python
assert resp.status_code == 500
assert 'SECRET_WATCHLIST_ERROR' not in str(data)
assert data.get('error') == 'Internal server error'
```

### WR-06: `test_routes_room.py` uses `jellyswipe.db.get_db()` directly without closing connections

**File:** `tests/test_routes_room.py:41-50,94-100,131-137` (and many more)
**Issue:** Multiple test helper functions and test bodies call `jellyswipe.db.get_db()` and manually manage `try/finally/conn.close()`. Some places use `with jellyswipe.db.get_db() as conn:` which (like CR-01) enters a transaction context but does NOT close the connection. For example `_seed_room()` at line 41 does `conn = jellyswipe.db.get_db()` then `try/finally/conn.close()` which is correct, but `test_routes_xss.py` at lines 49, 80, 95, 125, 166, 199, 213, 246, 254 uses `with jellyswipe.db.get_db() as conn:` which leaks connections in test. While test connection leaks are less severe than production leaks, they can cause `database is locked` flaky test failures.
**Fix:** Use `get_db_closing()` consistently, or at minimum close connections in finally blocks.

### WR-07: `app_real_auth` fixture re-imports `app_module` in teardown

**File:** `tests/conftest.py:306`
**Issue:** Line 306 does `import jellyswipe as app_module` which shadows the earlier import on line 287. While Python caches modules so this is functionally harmless, it is confusing and suggests the teardown was added later without noticing the existing import. More importantly, the `app_real_auth` fixture does not reset `_token_user_id_cache` or `rate_limiter`, while the `app` fixture does reset `rate_limiter`. This inconsistency could cause cross-test pollution in authorization tests.
**Fix:** Add `_rl.reset()` teardown and remove the duplicate import:
```python
yield fast_app
fast_app.dependency_overrides.clear()
app_module._provider_singleton = None
from jellyswipe.rate_limiter import rate_limiter as _rl
_rl.reset()
```

### WR-08: Skipped test left in test suite without issue tracking

**File:** `tests/test_routes_sse.py:181-195`
**Issue:** `test_stream_room_not_found` is marked `@pytest.mark.skip(reason="Flask test client does not properly consume SSE generator; verified manually")`. The skip reason references "Flask test client" but the codebase has migrated to FastAPI TestClient. This test should either be updated to work with the new client or removed entirely. Skipped tests that reference outdated infrastructure are misleading.
**Fix:** Either update the test to work with FastAPI TestClient (the other SSE tests demonstrate working patterns) or delete it entirely since `test_stream_no_active_room` (line 140) already covers the nonexistent-room case.

## Info

### IN-01: Duplicate `make_error_response` and `log_exception` across routers

**File:** `jellyswipe/routers/rooms.py:39-62`, `jellyswipe/routers/auth.py:23-49`, `jellyswipe/routers/media.py:23-49`
**Issue:** `make_error_response()` and `log_exception()` are copy-pasted across three router modules with identical implementations. This violates DRY and means a bug fix must be applied in three places.
**Fix:** Move to a shared module (e.g., `jellyswipe/errors.py`) and import from there.

### IN-02: Unused imports in `jellyswipe/__init__.py`

**File:** `jellyswipe/__init__.py:11-12,14`
**Issue:** `random` (line 12) and `json` (line 9) are imported but not used in `__init__.py`. They were likely used before the router extraction.
**Fix:** Remove unused imports: `import random`, `import json`.

### IN-03: Unused `db_path` parameter in `_seed_solo_room`

**File:** `tests/test_routes_xss.py:281`
**Issue:** `_seed_solo_room(db_path, room_code="ROOM1")` accepts a `db_path` parameter but never uses it (line 281). The caller passes `None` (line 298). The function uses `jellyswipe.db.get_db()` directly.
**Fix:** Remove the `db_path` parameter from the function signature and update callers.

### IN-04: `_set_session_room` in test_routes_sse.py sets `jf_delegate_server_identity` unnecessarily

**File:** `tests/test_routes_sse.py:37`
**Issue:** The session cookie includes `jf_delegate_server_identity: True` which is a legacy Flask session flag. With vault-based auth, this flag is not read by any route that uses `require_auth` dependency (which is overridden in tests). It is dead session data that adds confusion.
**Fix:** Remove `jf_delegate_server_identity` from the session cookie in `_set_session_room`.

### IN-05: `_PRE_GENERATOR_OVERHEAD` magic number fragility

**File:** `tests/test_routes_sse.py:71`
**Issue:** `_PRE_GENERATOR_OVERHEAD = 6` is a fragile magic number that depends on the internal implementation of httpx, starlette, and cookie handling calling `time.time()` exactly 6 times before the SSE generator starts. Any upgrade to these dependencies could change this count, causing all SSE tests to fail with confusing timeout behavior.
**Fix:** Consider using a more robust approach such as `unittest.mock.patch` on `time.time` that returns real time for all calls but triggers deadline expiry based on a flag or event, rather than counting exact call counts.

---

_Reviewed: 2026-05-04T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
