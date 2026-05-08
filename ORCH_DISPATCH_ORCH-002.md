## Ticket
- ID: ORCH-002
- Title: Merge POST /room and POST /room/solo into single setup-aware endpoint
- State: In Progress
- Risk Score: 3
- Rework Loop Count: 3
- Linked PR: https://github.com/andrewthetechie/jelly-swipe/pull/40

### Description
Merge the two room-creation endpoints into one. The new `POST /room` accepts setup choices (media types + solo toggle) as a JSON body and creates the room with those settings. The `DeckProvider.fetch_deck()` call gains awareness of media types.

**Files to modify:**
- `jellyswipe/routers/rooms.py` — merge `create_room` and `create_solo_room` handlers into one; parse request body for `movies`, `tv_shows`, `solo`
- `jellyswipe/services/room_lifecycle.py` — merge `create_room` and `create_solo_room` into one method that reads setup params; pass `include_movies`/`include_tv_shows` to repository; pass media types to `DeckProvider.fetch_deck()`
- `jellyswipe/room_types.py` — no changes needed (fields added in ORCH-001)

**Key decisions:**
- Solo toggle is part of the setup body, not a separate endpoint (grilling decision 5).
- Backward compat: if body is empty/missing, default to `{movies: true, tv_shows: false, solo: false}` so the old frontend still works until Ticket 6 lands.
- The `DeckProvider` protocol stays unchanged for now — the provider implementation (Ticket 4) handles media types internally via a new parameter on `fetch_deck`.


### Acceptance Criteria
- `POST /room` accepts JSON body `{"movies": true, "tv_shows": false, "solo": false}`.
- `POST /room/solo` returns 404 or is removed.
- At least one of `movies` or `tv_shows` must be `true`; otherwise returns 400 with error message.
- `create_room` service method reads `movies`/`tv_shows`/`solo` from request body and persists `include_movies`/`include_tv_shows`/`solo_mode` to the Room row.
- `ready` defaults to `true` when `solo=true`, `false` otherwise (existing behavior preserved).
- Frontend is NOT updated in this ticket — the old `POST /room` without a body should still work (treat missing body as `{movies: true, tv_shows: false, solo: false}` for backward compat during rollout).


### File Paths
jellyswipe/routers/rooms.py, jellyswipe/services/room_lifecycle.py, jellyswipe/room_types.py

### Test Expectations
- `POST /room` with body `{"movies": true, "tv_shows": false, "solo": false}` creates a hosted room with `include_movies=1, include_tv_shows=0, solo_mode=0, ready=0`.
- `POST /room` with body `{"movies": true, "tv_shows": false, "solo": true}` creates a solo room with `ready=1`.
- `POST /room` with body `{"movies": false, "tv_shows": false, "solo": false}` returns 400.
- `POST /room` with empty body defaults to movies-only hosted session.
- `POST /room/solo` returns 404 or redirects.
- Existing `test_create_and_solo_set_session_cursor_defaults` updated for new signature.

## Comments
- **router**: Agent exited with code -2 without completing. Moved to Needs Human Review.
- **Reviewer Agent**: ## Code Review: Rework Required

### Summary
Tests are failing (5/333 failed). The PR has 4 blocking issues that must be addressed before approval.

---

### Blocking Issue 1: Protocol Incompatibility - CRITICAL

**File:** jellyswipe/jellyfin_library.py:277

**Problem:** The DeckProvider protocol was updated with new include_movies and include_tv_shows parameters, but JellyfinLibrary.fetch_deck() does NOT implement them. It still hardcodes IncludeItemTypes: "Movie".

**Why it matters:** The protocol expects implementations to support media type filtering, but the production implementation ignores these parameters. Type checkers will fail.

**Remediation patch:**

```diff
--- a/jellyswipe/jellyfin_library.py
+++ b/jellyswipe/jellyfin_library.py
@@ -274,7 +274,9 @@ class JellyfinLibrary:
         }
 
-    def fetch_deck(self, genre_name: Optional[str] = None) -> List[dict]:
+    def fetch_deck(
+        self, genre_name: Optional[str] = None, 
+        include_movies: bool = True, include_tv_shows: bool = False
+    ) -> List[dict]:
         lib = self._movies_library_id()
         uid = self._user_id()
         params: Dict[str, Any] = {
             "ParentId": lib,
             "UserId": uid,
-            "IncludeItemTypes": "Movie",
+            "IncludeItemTypes": _get_include_item_types(include_movies, include_tv_shows),
             "Recursive": "true",
             "Fields": "Overview,RunTimeTicks,ProductionYear,CommunityRating,CriticRating",
         }
```

Add helper function before the class:

```python
def _get_include_item_types(include_movies: bool, include_tv_shows: bool) -> str:
    """Build IncludeItemTypes parameter from boolean flags."""
    types = []
    if include_movies:
        types.append("Movie")
    if include_tv_shows:
        types.append("Series")
    if not types:
        # Fallback to movies only if both false (validation should prevent this)
        return "Movie"
    return ",".join(types)
```

---

### Blocking Issue 2: Missing Test Updates for Baseline Migration

**File:** tests/test_db.py:46-55

**Problem:** The baseline test expects the rooms table to have a fixed set of columns, but the migration now adds include_movies and include_tv_shows.

**Why it matters:** The test fails because it validates the exact set of columns.

**Remediation patch:**

```diff
--- a/tests/test_db.py
+++ b/tests/test_db.py
@@ -44,7 +44,9 @@ class TestAlembicBaseline:
             assert set(columns) == {
                 "pairing_code",
                 "movie_data",
+                "include_movies",
+                "include_tv_shows",
                 "ready",
                 "current_genre",
                 "solo_mode",
@@ -56,6 +58,8 @@ class TestAlembicBaseline:
             assert columns["movie_data"]["dflt_value"] in ("'[]'", '"[]"', "[]")
             assert columns["ready"]["dflt_value"] in ("0", "'0'")
             assert columns["current_genre"]["dflt_value"] in ("'All'", '"All"')
             assert columns["solo_mode"]["dflt_value"] in ("0", "'0'")
+            assert columns["include_movies"]["dflt_value"] in ("1", "'1'")
+            assert columns["include_tv_shows"]["dflt_value"] in ("0", "'0'")
```

---

### Blocking Issue 3: Obsolete Test Cases for Deprecated Endpoint

**File:** tests/test_route_authorization.py:680-733, 940-951

**Problem:** Tests test_solo_room_creation, test_solo_room_deck_cursor_initialized, test_solo_room_sets_session, and test_solo_endpoint_not_go_solo expect /room/solo to return 200, but the implementation now returns 404.

**Why it matters:** These tests fail because they test deprecated behavior.

**Remediation:** Update or remove these tests. Since the acceptance criteria says "POST /room/solo returns 404 or is removed", these tests should be updated to expect 404:

```diff
--- a/tests/test_route_authorization.py
+++ b/tests/test_route_authorization.py
@@ -685,16 +685,14 @@ class TestSoloRoom:
         _setup_deck_session(client_real_auth, db_connection, os.environ["FLASK_SECRET"])
 
         resp = client_real_auth.post('/room/solo')
-        assert resp.status_code == 200
-        data = resp.json()
-        assert 'pairing_code' in data
-        code = data['pairing_code']
-        assert len(code) == 4
+        assert resp.status_code == 404
+        assert resp.json() == {'error': 'Endpoint removed. Use POST /room with {"solo": true}'}
```

Delete test_solo_room_deck_cursor_initialized and test_solo_room_sets_session entirely (they can't work with 404).

Update test_solo_endpoint_not_go_solo:

```diff
--- a/tests/test_route_authorization.py
+++ b/tests/test_route_authorization.py
@@ -940,10 +940,7 @@ class TestPhase27Compliance:
         """POST /room/solo creates solo room (200), POST /room/{code}/go-solo returns 404."""
         _setup_deck_session(client_real_auth, db_connection, os.environ["FLASK_SECRET"])
 
         # POST /room/solo now returns 404 (deprecated)
         resp = client_real_auth.post('/room/solo')
-        assert resp.status_code == 200
-        code = resp.json()['pairing_code']
-
-        # Old route returns 404
-        resp = client_real_auth.post(f'/room/{code}/go-solo')
-        assert resp.status_code == 404
+        assert resp.status_code == 404
```

---

### Blocking Issue 4: Weak Input Validation (Recommended)

**File:** jellyswipe/routers/rooms.py:76-83

**Problem:**
- Bare except Exception: catches all errors, including JSON parsing errors, and silently defaults to empty body
- No type validation - accepts integers, strings, or any truthy/falsy value for boolean flags

**Why it matters:** Malformed JSON could be a real error that should return 400, not silently ignored. Non-boolean values could cause unexpected behavior.

**Remediation patch:**

```diff
--- a/jellyswipe/routers/rooms.py
+++ b/jellyswipe/routers/rooms.py
@@ -73,8 +73,16 @@ async def create_room(request: Request, uow: DBUoW, user: AuthUser = Depends(re
     Backward compat: if body is empty/missing, defaults to movies-only hosted session.
     """
-    try:
+    try:
         body = await request.json()
-    except Exception:
+    except json.JSONDecodeError:
+        return XSSSafeJSONResponse(
+            content={"error": "Invalid JSON body"},
+            status_code=400,
+        )
+    body = body or {}
+    
+    # Validate and coerce input types
+    include_movies = bool(body.get("movies", True))
+    include_tv_shows = bool(body.get("tv_shows", False))
+    solo = bool(body.get("solo", False))
-        body = {}
-    
-    # Parse setup choices with backward-compatible defaults
-    include_movies = body.get("movies", True)
-    include_tv_shows = body.get("tv_shows", False)
-    solo = body.get("solo", False)
```

---

### Security Review (Risk Score 3 - Thorough)

**Authentication/Authorization:** No changes - endpoints still require require_auth.

**Input Validation:** 
- Medium priority: Request body parsing uses bare except Exception: which could mask JSON parsing errors. See issue #4 above.
- Medium priority: No type validation for boolean flags. See issue #4 above.

**Injection Risks:** No SQL queries constructed from user input. Repository uses parameterized queries.

**Data Exposure:** No secrets or PII in responses.

**Cryptography/Session Handling:** No changes.

**Access Control:** No changes.

**Rate Limiting:** No changes.

**Infrastructure/Configuration:** Migration adds columns with defaults, which is safe.

---

### Test Failures

1. tests/test_db.py::TestAlembicBaseline::test_rooms_table_has_phase36_columns_and_defaults - Missing columns in test expectation
2. tests/test_route_authorization.py::TestSoloRoom::test_solo_room_creation - Expects 200, gets 404
3. tests/test_route_authorization.py::TestSoloRoom::test_solo_room_deck_cursor_initialized - KeyError: 'pairing_code'
4. tests/test_route_authorization.py::TestSoloRoom::test_solo_room_sets_session - KeyError: 'pairing_code'
5. tests/test_route_authorization.py::TestPhase27Compliance::test_solo_endpoint_not_go_solo - Expects 200, gets 404

---

All issues include concrete remediation patches above that a junior engineer can apply mechanically.
- **router**: Agent exited with code -2 without completing. Moved to Needs Human Review.
- **router**: Agent exited with code 0 without completing. Moved to Needs Human Review.
- **router**: Reached 3 rework loops. Escalating to Needs Human Review.
- **router**: Reached 3 rework loops. Escalating to Needs Human Review.
- **router**: ## Needs Human Review — escalated by router

**Agent:** coder  |  **Exit code:** 0  |  **Rework loops:** 1

**Reason:** The agent exited without moving this ticket to the expected next state.

**Last agent comment** (from Reviewer Agent):

## Code Review: Rework Required

### Summary
Tests are failing (5/333 failed). The PR has 4 blocking issues that must be addressed before approval.

---

### Blocking Issue 1: Protocol Incompatibility - CRITICAL

**File:** jellyswipe/jellyfin_library.py:277

**Problem:** The DeckProvider protocol was updated with new include_movies and include_tv_shows parameters, but JellyfinLibrary.fetch_deck() does NOT implement them. It still hardcodes IncludeItemTypes: "Movie".

**Why it matters:** The protocol expects implementations to support media type filtering, but the production implementation igno
... *(truncated — see full comment above)*

**To resume:** move this ticket to `Rework` once the issues above are addressed.
- **coder**: ## Rework Complete

Applied all 4 blocking fixes from code review:

1. **Protocol compatibility** - Added `include_movies`/`include_tv_shows` params to `JellyfinLibrary.fetch_deck()` with helper `_get_include_item_types()`
2. **Test baseline** - Updated `test_db.py` to expect new columns with correct defaults
3. **Obsolete tests** - Updated `test_route_authorization.py` solo tests to expect 404
4. **Input validation** - Fixed `rooms.py` to handle JSON errors properly and coerce boolean types

**Validation:**
- `uv run pytest`: 331 passed
- `uv run ruff check src/`: ruff not installed (pre-existing)

PR updated: https://github.com/andrewthetechie/jelly-swipe/pull/40
- **coder**: ## Rework Complete

All 4 blocking fixes from code review have been applied and validated:

1. **Protocol compatibility** - Added `include_movies`/`include_tv_shows` params to `JellyfinLibrary.fetch_deck()` with helper `_get_include_item_types()`
2. **Test baseline** - Updated `test_db.py` to expect new columns with correct defaults
3. **Obsolete tests** - Updated `test_route_authorization.py` solo tests to expect 404
4. **Input validation** - Fixed `rooms.py` to handle JSON errors properly and coerce boolean types

**Validation:**
- `uv run pytest`: 331 passed ✓
- `uv run ruff check`: ruff not installed (pre-existing)

PR updated: https://github.com/andrewthetechie/jelly-swipe/pull/40

Ticket moved to Code Review.
- **reviewer**: ## Code Review: Rework Required

### Summary
I found 1 new blocking issue with type coercion that was not addressed in the previous rework. All 4 issues from the previous review have been properly fixed, tests pass (331/331), but this new issue must be addressed before approval.

---

### Blocking Issue 1: Incorrect Type Coercion

**File:** jellyswipe/routers/rooms.py:94-96

**Problem:** The code uses `bool()` for type coercion, which treats any non-empty string or non-empty collection as `True`. For example:
- `bool("false")` returns `True` (non-empty string is truthy)
- `bool("0")` returns `True`
- `bool([])` returns `False` (empty list is falsy)
- `bool([1])` returns `True` (non-empty list is truthy)

A user sending `{"movies": "false", "tv_shows": false}` would end up with `include_movies=True`.

**Why it matters:** The API contract expects boolean values, not strings or other types. Users sending string values will get unexpected behavior.

**Remediation patch:**

```diff
--- a/jellyswipe/routers/rooms.py
+++ b/jellyswipe/routers/rooms.py
@@ -91,9 +91,22 @@ async def create_room(request: Request, uow: DBUoW, user: AuthUser = Depends(re
     body = body or {}
     
     # Validate and coerce input types
-    include_movies = bool(body.get("movies", True))
-    include_tv_shows = bool(body.get("tv_shows", False))
-    solo = bool(body.get("solo", False))
+    
+    # Validate that boolean fields are actual booleans, not strings or other types
+    movies_val = body.get("movies", True)
+    tv_shows_val = body.get("tv_shows", False)
+    solo_val = body.get("solo", False)
+    
+    if not isinstance(movies_val, bool):
+        return XSSSafeJSONResponse(
+            content={"error": "movies must be a boolean value"},
+            status_code=400,
+        )
+    if not isinstance(tv_shows_val, bool):
+        return XSSSafeJSONResponse(
+            content={"error": "tv_shows must be a boolean value"},
+            status_code=400,
+        )
+    if not isinstance(solo_val, bool):
+        return XSSSafeJSONResponse(
+            content={"error": "solo must be a boolean value"},
+            status_code=400,
+        )
+    
+    include_movies = movies_val
+    include_tv_shows = tv_shows_val
+    solo = solo_val
     
     # Validate: at least one media type must be selected
     if not include_movies and not include_tv_shows:
```

---

### Previously Fixed Issues (All Correctly Resolved ✅)

1. **Protocol incompatibility** - ✅ `JellyfinLibrary.fetch_deck()` now accepts `include_movies`/`include_tv_shows` parameters
2. **Test baseline** - ✅ `test_db.py` expects new columns with correct defaults
3. **Obsolete tests** - ✅ Solo tests updated to expect 404
4. **Input validation (JSON parsing)** - ✅ Fixed bare `except Exception` to `except json.JSONDecodeError`

---

### Security Review (Risk Score 3 - Thorough)

**Authentication/Authorization:** ✅ No changes - endpoints still require `require_auth`

**Input Validation:** 
- ❌ **NEW:** Type coercion uses `bool()` which incorrectly treats strings as truthy/falsy (see blocking issue #1)
- ✅ JSON parsing errors now return 400 with specific error message

**Injection Risks:** ✅ No SQL queries constructed from user input. Repository uses parameterized queries.

**Data Exposure:** ✅ No secrets or PII in responses.

**Cryptography/Session Handling:** ✅ No changes.

**Access Control:** ✅ No changes.

**Rate Limiting:** ✅ No changes.

**Infrastructure/Configuration:** ✅ Migration adds columns with defaults, which is safe.
- **coder**: ## Rework Complete

Fixed the type coercion issue identified in code review:

**Blocking Issue 1: Incorrect Type Coercion** - ✅ Fixed
- Replaced `bool()` coercion with strict `isinstance()` validation for `movies`, `tv_shows`, and `solo` fields
- Returns 400 with specific error message if any field is not a boolean type
- Prevents unexpected behavior from string values like `"false"` being treated as truthy

**Validation:**
- `uv run pytest tests/`: 331 passed ✓

PR updated: https://github.com/andrewthetechie/jelly-swipe/pull/40

Ticket moved to Code Review.

## Pull Request
- URL: https://github.com/andrewthetechie/jelly-swipe/pull/40

## Workflow Instructions
- Agent Role: reviewer
- Current State: In Progress
- Target State: Ready to Merge
- Working Directory: /home/andrew/jelly-swipe/.orchestra/worktrees/ORCH-002
- **All commands must run from the working directory above.** Never `cd` outside it. All file paths are relative to this directory.