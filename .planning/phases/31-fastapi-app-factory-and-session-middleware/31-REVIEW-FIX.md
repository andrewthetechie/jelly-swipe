---
phase: 31-fastapi-app-factory-and-session-middleware
fixed_at: 2026-05-02T00:00:00Z
review_path: .planning/phases/31-fastapi-app-factory-and-session-middleware/31-REVIEW.md
iteration: 1
findings_in_scope: 11
fixed: 11
skipped: 0
status: all_fixed
---

# Phase 31: Code Review Fix Report

**Fixed at:** 2026-05-02
**Source review:** .planning/phases/31-fastapi-app-factory-and-session-middleware/31-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 11
- Fixed: 11
- Skipped: 0

## Fixed Issues

### CR-01: Database connection leak — `get_db()` used as context manager never closes the connection

**Files modified:** `jellyswipe/__init__.py`, `jellyswipe/auth.py`
**Commit:** 07b66e5
**Applied fix:** Replaced all 16 occurrences of `with get_db() as conn:` with `with get_db_closing() as conn:` across both files. Added import of `get_db_closing` to `auth.py`. This prevents database connection exhaustion under load.

### CR-02: Session vault expires tokens after 24 hours; cookie lives 14 days — silent auth failure

**Files modified:** `jellyswipe/db.py`
**Commit:** 36daeaa
**Applied fix:** Extended `cleanup_expired_tokens()` vault TTL from 24 hours to 14 days to match the `SessionMiddleware` cookie `max_age` configuration. Updated docstring to reflect the change.

### CR-03: `str(None)` stores the literal string `"None"` as `movie_id` when body omits the field

**Files modified:** `jellyswipe/__init__.py`
**Commit:** fa996d1
**Applied fix:** Added validation in three endpoints (`swipe`, `delete_match`, `undo_swipe`) to check that `movie_id` is present and non-None before converting to string. Returns 400 error if `movie_id` is missing.

### CR-04: Path traversal in static file route — arbitrary file read

**Files modified:** `jellyswipe/__init__.py`
**Commit:** 32ee473
**Applied fix:** Replaced the unsafe `serve_static_route()` function with Starlette's `StaticFiles` mount at `/static`. Added import of `StaticFiles` and removed the vulnerable `FileResponse` with user-supplied path. The mount provides built-in path sanitization.

### CR-05: Broken manual transaction nested inside `with get_db() as conn:` in swipe endpoint

**Files modified:** `jellyswipe/__init__.py`
**Commit:** 19785ab
**Applied fix:** Restructured the entire `swipe` handler to use a single `BEGIN IMMEDIATE` transaction block wrapped with `get_db_closing()`. Removed the early `conn.commit()` that was causing race conditions. All swipe, cursor update, and match detection operations now execute atomically with proper locking.

### WR-01: Direct `JSONResponse` in `make_error_response` and rate-limit returns bypasses XSS escaping

**Files modified:** `jellyswipe/__init__.py`
**Commit:** 01b2197
**Applied fix:** Replaced 10 instances of `JSONResponse` with `XSSSafeJSONResponse` across error handling and rate limiting code. This ensures consistent XSS protection for all API responses.

### WR-02: User-controlled `item.title` and `item.year` interpolated unencoded into TMDB URL

**Files modified:** `jellyswipe/__init__.py`
**Commit:** b7d8f74
**Applied fix:** Added `urlencode` import from `urllib.parse`. Modified `get_trailer` and `get_cast` endpoints to use `urlencode()` for query parameters when constructing TMDB URLs. This prevents malformed URLs from special characters in movie titles.

### WR-03: `page` query parameter parsed with `int()` — unhandled `ValueError` on non-numeric input

**Files modified:** `jellyswipe/__init__.py`
**Commit:** c21a3c4
**Applied fix:** Added try/except block in `get_deck` endpoint to handle `ValueError` and `TypeError` when parsing the `page` parameter. Returns 400 error with descriptive message on invalid input. Ensures page is at least 1.

### WR-04: `GET /room/{code}/status` and `GET /room/{code}/stream` have no authentication

**Files modified:** `jellyswipe/__init__.py`
**Commit:** 278d477
**Applied fix:** Added `_require_login(request)` call as the first statement in both `room_status` and `room_stream` endpoints. Prevents unauthorized access to room state and SSE streams.

### WR-05: Room pairing code uses `random.randint` with no uniqueness check — collision and predictability

**Files modified:** `jellyswipe/__init__.py`
**Commit:** 2480a6d
**Applied fix:** Replaced `random.randint(1000, 9999)` with `secrets.randbelow(9000) + 1000` for cryptographically secure random generation. Added collision detection loop (10 attempts) with database query before inserting. Returns 503 error if unable to generate unique code after 10 attempts. Applied to both `create_room` and `create_solo_room` endpoints.

### WR-06: `JELLYFIN_URL` re-read from env inside `create_app()` — SSRF validation bypass possible in tests

**Files modified:** `jellyswipe/__init__.py`
**Commit:** 18c4723
**Applied fix:** Captured validated JELLYFIN_URL at module level as `_JELLYFIN_URL` after `validate_jellyfin_url()` call at line 70. Modified `create_app()` to use the captured `_JELLYFIN_URL` instead of re-reading from environment. Prevents SSRF bypass in test scenarios that mutate `os.environ`.

## Skipped Issues

None — all findings in scope were successfully fixed.

---

_Fixed: 2026-05-02_
_Fixer: the agent (gsd-code-fixer)_
_Iteration: 1_
