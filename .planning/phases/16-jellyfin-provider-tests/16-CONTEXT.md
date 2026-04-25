# Phase 16: Jellyfin Provider Tests - Context

**Gathered:** 2026-04-25
**Status:** Ready for planning

## Phase Boundary

Test Jellyfin library provider with mocked external API calls. This phase tests the `jellyswipe/jellyfin_library.py` module directly using framework-agnostic imports established in Phase 14, covering authentication, token caching, user/library resolution, genre listing, deck fetching, item-to-card transformation, and TMDB resolution.

## Implementation Decisions

### HTTP Mocking Strategy
- **D-01:** Use `mocker.patch('jellyswipe.jellyfin_library.requests.Session')` to mock the Session class
- **Rationale:** Matches ARCHITECTURE.md Pattern 2 from Phase 14 research; single mock intercepts all HTTP calls (GET/POST) via `Session.request()`; consistent with pytest-mock patterns already established
- **Implementation details:**
  - Mock `requests.Session` to intercept all HTTP calls
  - Configure mock response with `.ok`, `.status_code`, and `.json()` return value
  - Verify API calls using `.assert_called_once()` and check call args
  - Allows simulating both success and error states by changing mock response properties

### Mock Response Organization
- **D-02:** Use inline mock responses for unique scenarios, shared fixtures for common patterns
- **Rationale:** Balances readability (unique responses visible in test) with reuse (common patterns avoid duplication); pragmatic approach for initial test suite
- **Specific implementation:**
  - **Inline in tests:** Unique scenarios like specific error responses, edge cases, test-specific data
  - **Shared fixtures (in conftest.py):** Common patterns like auth success response, successful deck response, genre list response
  - Start with inline responses for early tests, extract to fixtures if duplication grows
  - Fixtures should return mock objects (e.g., `mock_jellyfin_auth_response()`) configured with `.ok = True`, `.json.return_value = {...}`

### Authentication Test Scope
- **D-03:** Test all three authentication paths: API key, username/password, and 401 retry logic
- **Rationale:** Comprehensive coverage of API-02 requirement (authentication, token caching, user ID resolution); validates resilience (401 retry) in addition to primary auth paths
- **Specific coverage:**
  - **API key path (line 82):** Test `ensure_authenticated()` sets `_access_token` from `JELLYFIN_API_KEY` env var
  - **Username/password path (line 84-110):** Test `_login_from_env()` makes auth request, extracts `AccessToken`, handles network errors and invalid credentials
  - **401 retry logic (line 152-155):** Test `_api()` resets and re-authenticates on 401, retries without `retry=True` flag to prevent infinite loop
  - **Token caching:** Verify `_access_token`, `_cached_user_id`, and `_cached_library_id` are cached after first call
  - **User ID resolution:** Test `_user_id()` fallback from `/Users/Me` to `/Users` with username matching

### Error & Edge Case Testing
- **D-04:** Test representative error cases: network failure, 401 retry, empty Items array, missing required fields
- **Rationale:** Covers major failure modes per API-01 without exhaustive testing; balances coverage with test maintainability
- **Specific error tests:**
  - **Network failure:** Test `requests.RequestException` in `_login_from_env()` (line 97) and `_user_id()` (line 181)
  - **401 retry:** Test `_api()` receives 401, calls `reset()`, re-authenticates, retries once
  - **Empty Items array:** Test `fetch_deck()` with `{"Items": []}` returns empty list
  - **Missing required fields:** Test missing `AccessToken` (line 109), missing `Id` in user list (line 191), missing `token`/`user_id` in `authenticate_user_session()` (line 432)
  - **Invalid JSON:** Test `ValueError` handling in `_login_from_env()` (line 105) and `_api()` (line 162)
  - **HTTP errors:** Test 403 (forbidden) in `fetch_library_image()` (line 384), 404 (not found) in `fetch_library_image()` (line 386)

### Test Organization
- **D-05:** Create `tests/test_jellyfin_library.py` for all Jellyfin provider tests
- **Rationale:** Single file for module under test (follows Phase 14's flat `tests/` structure); easy to find all Jellyfin tests; can split into multiple files if test count grows
- **Agent discretion:** Group related tests with docstrings (e.g., "Authentication tests", "Library discovery tests") using `# ----` comment separators for readability

### the agent's Discretion
- **Fixture creation:** Create shared fixtures for common mock responses in `conftest.py` as duplication emerges (start with inline responses in tests)
- **Test count balance:** Target ~15-20 tests covering all success criteria (API-01 through API-04); can expand to ~30 if more edge cases identified during planning
- **Mock verification granularity:** Verify key call parameters (method, path, critical query params) in assertions; don't assert on every parameter unless it's critical to the test
- **Cache invalidation:** Decide whether to test cache invalidation (`reset()` method clears all caches) — likely needed for completeness
- **Genre mapping edge case:** Test "Science Fiction" → "Sci-Fi" mapping (line 251) as it's a special case in `list_genres()`
- **Runtime formatting:** Test `_format_runtime()` edge cases (zero/negative seconds, minutes-only, hours+minutes) if not covered elsewhere

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Research Outputs (from Phase 14)
- `.planning/research/ARCHITECTURE.md` — Pattern 2: Mock External API Calls with pytest-mock (complete example of requests.Session mocking)
- `.planning/research/STACK.md` — Testing stack (pytest, pytest-mock, responses, pytest-cov, pytest-timeout)
- `.planning/research/FEATURES.md` — Feature landscape for unit testing (table stakes, differentiators)
- `.planning/research/PITFALLS.md` — Anti-patterns (over-mocking, test coupling to implementation details)
- `.planning/research/SUMMARY.md` — Executive synthesis with phase implications

### Project Documents
- `.planning/PROJECT.md` — v1.3 milestone goals (unit tests, framework-agnostic approach)
- `.planning/REQUIREMENTS.md` — API-01 (mock HTTP requests), API-02 (auth/token/user ID), API-03 (library/genres/deck), API-04 (item-to-card/TMDB resolution)
- `.planning/ROADMAP.md` — Phase 16 success criteria and dependencies

### Codebase Maps
- `.planning/codebase/TESTING.md` — Test framework patterns (mocking recommendations, what to mock vs not mock)
- `.planning/codebase/ARCHITECTURE.md` — Database schema, integration points (jellyfin_library.py HTTP endpoints)
- `.planning/codebase/STRUCTURE.md` — Package structure (jellyswipe/ layout from v1.2)

### Prior Phase Context
- `.planning/phases/14-test-infrastructure-setup/14-CONTEXT.md` — D-01 through D-04: test directory structure, fixture organization, pytest configuration, framework-agnostic import strategy
- `.planning/phases/15-database-module-tests/15-CONTEXT.md` — D-01 through D-06: tmp_path usage, function-scoped fixtures, monkeypatch patterns

### Code to Test
- `jellyswipe/jellyfin_library.py` — JellyfinLibraryProvider under test (482 lines)
  - **Authentication:** `_login_from_env()` (line 77-112), `_verify_items()` (line 114-128), `_api()` with 401 retry (line 133-163), `authenticate_user_session()` (line 408-434)
  - **User/Library resolution:** `_user_id()` (line 165-194), `_movies_library_id()` (line 196-210)
  - **Library operations:** `list_genres()` (line 212-253), `fetch_deck()` (line 272-327)
  - **Data transformation:** `_item_to_card()` (line 255-270), `_format_runtime()` (line 29-36)
  - **TMDB integration:** `resolve_item_for_tmdb()` (line 329-344)
  - **Image handling:** `fetch_library_image()` (line 362-391)
  - **Server info:** `server_info()` (line 346-360)
  - **Session management:** `ensure_authenticated()` (line 59-62), `reset()` (line 51-57)

## Existing Code Insights

### Reusable Assets
- `tests/conftest.py` — Already created in Phase 14 with `setup_test_environment` fixture (patches load_dotenv and Flask), `mock_env_vars` fixture
- `pytest` and `pytest-mock` — Already installed via Phase 14 (commit 895b1f9)
- `mocker` fixture — Built-in pytest-mock fixture for mocking, available in all tests
- `mock_env_vars` fixture — Sets test environment variables (JELLYFIN_URL, JELLYFIN_API_KEY, TMDB_API_KEY, FLASK_SECRET)

### Established Patterns
- **Mocking pattern from ARCHITECTURE.md:** Use `mocker.patch('module.requests.Session')` to intercept HTTP calls; configure mock response with `.ok`, `.status_code`, `.json()`
- **Monkeypatch pattern from Phase 14:** Use `monkeypatch.setenv()` or `monkeypatch.setattr()` for temporary modifications; automatically restored after test
- **Flat tests/ directory:** All test files in one place (test_infrastructure.py, test_db.py exist; will add test_jellyfin_library.py)
- **Fixture scope pattern:** Session-scoped for global setup, function-scoped for test-specific resources (from Phase 14/15 decisions)

### Integration Points
- **jellyswipe/jellyfin_library.py:** Module under test; uses `requests.Session` for HTTP calls (to be mocked); has caching attributes (`_access_token`, `_cached_user_id`, `_cached_library_id`)
- **jellyswipe/__init__.py:** Sets env vars on import (already patched in Phase 14's conftest.py)
- **Environment variables:** JELLYFIN_URL, JELLYFIN_API_KEY, JELLYFIN_USERNAME, JELLYFIN_PASSWORD, JELLYFIN_DEVICE_ID (already set in mock_env_vars fixture)
- **Jellyfin API endpoints:** /Users/AuthenticateByName, /Users/Me, /Users, /Users/{uid}/Views, /Items, /Items/Filters, /Genres, /Items/{item_id}, /System/Info, /System/Info/Public, /Users/{uid}/FavoriteItems/{item_id}, /Items/{iid}/Images/Primary

### Mocking Strategy Details
From `jellyfin_library.py` analysis:
- **HTTP client:** `self._session = requests.Session()` (line 44), all calls go through `self._session.request()` (line 144)
- **Authentication header:** `Authorization: MediaBrowser Client="JellySwipe", Device="FlaskApp", DeviceId="...", Version="1.0.0", Token="..."` (line 23-26)
- **Request timeout:** 30s for auth (line 95), 90s for API calls (line 150), 60s for images (line 373)
- **Retry logic:** 401 triggers `reset()` + `ensure_authenticated()` + retry once (line 152-155)
- **Error handling:** Network exceptions → RuntimeError with descriptive message; HTTP errors → RuntimeError with status code; JSON errors → RuntimeError

## Specific Ideas

No specific requirements — open to standard pytest patterns for HTTP mocking as outlined in ARCHITECTURE.md Pattern 2.

## Deferred Ideas

None — discussion stayed within phase scope.

---

*Phase: 16-jellyfin-provider-tests*
*Context gathered: 2026-04-25*
