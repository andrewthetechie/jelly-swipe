---
phase: 34-sse-route-migration
reviewed: 2026-05-04T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - jellyswipe/routers/rooms.py
  - jellyswipe/__init__.py
  - pyproject.toml
findings:
  critical: 1
  warning: 3
  info: 3
  total: 7
status: issues_found
---

# Phase 34: Code Review Report

**Reviewed:** 2026-05-04T00:00:00Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Phase 34 migrated the SSE `/room/{code}/stream` route from an inline `StreamingResponse`-based sync generator in `__init__.py` to the `rooms_router` using `sse-starlette`'s `EventSourceResponse` with an async generator, `check_same_thread=False`, and `asyncio.sleep`. The `sse-starlette` dependency was added to `pyproject.toml`. Several prior review fixes (WR-01 through WR-05 from Phase 33) are also included in the diff.

Key concerns: (1) the multi-user match query has a logic bug that creates self-match records when `session_id` is NULL, (2) approximately 100 lines of dead helper functions remain in `__init__.py` after the SSE route removal, and (3) multiple unused imports exist in `rooms.py`.

## Critical Issues

### CR-01: Self-match when session_id is NULL in multi-user swipe handler

**File:** `jellyswipe/routers/rooms.py:254-264`
**Issue:** When `_session_id` is `None`, the SQL clause `(? IS NULL OR session_id != ?)` evaluates to `(TRUE OR ...)` which is unconditionally TRUE. This returns ALL right-swipes for the movie, including the swipe the current user just inserted at line 222. The `fetchone()` at line 258 can therefore return the current user's own swipe record. When that happens, line 260-264 unconditionally creates a match record for the current user -- a spurious self-match with no actual partner. The `user_id` guard at line 266 only prevents the second match insert and SSE broadcast, but the first match insert (line 261-264) has already executed.

This affects any session where `session_id` is not set (e.g., tests, edge-case sessions created without the login flow setting a session_id).
**Fix:** Add `AND user_id != ?` to the query to exclude the current user's own swipe, which is the actual semantic intent:
```python
_session_id = request.session.get('session_id')
other_swipe = conn.execute(
    'SELECT user_id, session_id FROM swipes WHERE room_code = ? AND movie_id = ? AND direction = "right" AND user_id != ? AND (? IS NULL OR session_id != ?)',
    (code, mid, user.user_id, _session_id, _session_id)
).fetchone()
```

## Warnings

### WR-01: Dead code -- ~100 lines of unused helper functions in __init__.py

**File:** `jellyswipe/__init__.py:111-208`
**Issue:** Seven functions (`_require_login`, `_jellyfin_user_token_from_request`, `_request_has_identity_alias_headers`, `_set_identity_rejection_reason`, `_identity_rejection_reason`, `_token_cache_key`, `_resolve_user_id_from_token_cached`, `_provider_user_id_from_request`) are defined but never called from anywhere in the codebase. They were SSE-route helpers that are now obsolete after the route was migrated to `rooms_router` with `Depends(require_auth)`. This dead code increases maintenance burden and makes the module harder to understand.
**Fix:** Delete lines 107-208 (the entire "SSE route helpers" section). Also remove the now-unused imports: `hashlib` (line 8), `random` (line 12), `sqlite3` (line 14).

### WR-02: Stale module docstring in __init__.py

**File:** `jellyswipe/__init__.py:4`
**Issue:** The docstring states "The SSE route (/room/{code}/stream) stays inline until Phase 34 migrates it." Phase 34 has completed this migration, so this comment is now misleading. It will confuse future developers into thinking the route is still inline.
**Fix:** Update the docstring to reflect the current state:
```python
"""Jelly Swipe app factory -- thin factory mounting all 5 domain routers.

Per D-15: __init__.py is a thin app factory. All domain routes live in routers/*.
SSE route migrated to rooms_router in Phase 34.
"""
```

### WR-03: Unused imports in rooms.py

**File:** `jellyswipe/routers/rooms.py:19-28`
**Issue:** Several imported names are never used in the file:
- `typing` (line 19) -- not referenced anywhere
- `HTTPException` (line 21) -- not used (errors return `XSSSafeJSONResponse` directly)
- `Response` (line 21) -- not used
- `check_rate_limit` (line 27) -- imported but no route applies it
- `get_db_dep` (line 27) -- the `DBConn` annotated type is used instead; `get_db_dep` itself is not called directly

Unused imports increase coupling and can mask actual dependency issues.
**Fix:** Clean up the import lines:
```python
import typing  # DELETE

from fastapi import APIRouter, Depends, Request  # remove HTTPException, Response
from jellyswipe.dependencies import AuthUser, DBConn, get_provider, require_auth  # remove check_rate_limit, get_db_dep
```

## Info

### IN-01: Unused imports in __init__.py after SSE removal

**File:** `jellyswipe/__init__.py:12,14`
**Issue:** `import random` and `import sqlite3` are no longer used in `__init__.py` after the SSE route was moved out. They were only used by the now-deleted inline SSE generator.
**Fix:** Remove `import random` (line 12) and `import sqlite3` (line 14).

### IN-02: f-string in logging call

**File:** `jellyswipe/routers/rooms.py:202`
**Issue:** `_logger.warning(f"Failed to resolve metadata for movie_id={mid}: {exc}")` uses an f-string instead of `%s`-style lazy formatting. The string is always interpolated even if warning-level logging is disabled.
**Fix:** Use lazy formatting:
```python
_logger.warning("Failed to resolve metadata for movie_id=%s: %s", mid, exc)
```

### IN-03: Duplicate dev dependency specifications in pyproject.toml

**File:** `pyproject.toml:24-32,39-44`
**Issue:** Dev dependencies are declared in both `[project.optional-dependencies] dev` (lines 24-32) and `[dependency-groups] dev` (lines 39-44) with different version pins. For example, `pytest>=9.0.0` vs `pytest>=9.0.3` and `pytest-cov>=6.0.0` vs `pytest-cov>=7.1.0`. The `[dependency-groups]` section is also missing several packages that appear in `[project.optional-dependencies]` (`pytest-mock`, `responses`, `pytest-timeout`). This creates confusion about which specification is authoritative.
**Fix:** Consolidate to a single dev dependency specification. If targeting PEP 735 (`[dependency-groups]`), remove `[project.optional-dependencies] dev` and ensure all packages are listed in `[dependency-groups]`, or vice versa.

---

_Reviewed: 2026-05-04T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
