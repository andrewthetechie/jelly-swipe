# Phase 23: Auth Route Tests - Context

**Gathered:** 2026-04-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Add comprehensive test coverage for the 3 authentication route endpoints in `tests/test_routes_auth.py`. Tests verify correct responses for valid/invalid inputs, session state changes, error handling, and EPIC-01 header-spoof protection on auth routes. Uses shared `app`/`client` fixtures from Phase 22 conftest.py.

Routes in scope:
- `GET /auth/provider` — Returns provider info (static JSON)
- `POST /auth/jellyfin-use-server-identity` — Delegate identity via server credentials
- `POST /auth/jellyfin-login` — Username/password authentication

</domain>

<decisions>
## Implementation Decisions

### Test Structure
- **D-01:** Create `tests/test_routes_auth.py` — single file for all auth route tests
- **D-02:** Use shared `client` fixture from conftest.py (Phase 22) — no local fixture overrides
- **D-03:** Group tests by endpoint using pytest classes or descriptive function names (e.g., `test_auth_provider_returns_jellyfin`, `test_jellyfin_login_missing_credentials_returns_400`)

### `/auth/provider` Tests
- **D-04:** Test returns 200 with `{"provider": "jellyfin", "jellyfin_browser_auth": "delegate"}`
- **D-05:** Test response content-type is `application/json`

### `/auth/jellyfin-use-server-identity` Tests
- **D-06:** Test success case — returns 200 with `{"userId": "verified-user"}` and sets `session["jf_delegate_server_identity"] = True`
- **D-07:** Test failure case — provider raises RuntimeError, returns 401 with error JSON
- **D-08:** Verify session flag is NOT set on failure

### `/auth/jellyfin-login` Tests
- **D-09:** Test success case — returns 200 with `{"authToken": ..., "userId": ...}`
- **D-10:** Test missing username — returns 400 with error
- **D-11:** Test missing password — returns 400 with error
- **D-12:** Test empty body — returns 400 (both fields missing)
- **D-13:** Test auth failure — provider raises exception, returns 401

### EPIC-01 Header-Spoof Tests
- **D-14:** Test that identity alias headers (`X-Provider-User-Id`, `X-Jellyfin-User-Id`, `X-Emby-UserId`) are rejected on auth endpoints per ROADMAP success criterion 4
- **D-15:** Existing `test_route_authorization.py` covers header-spoof on protected routes — Phase 23 covers auth routes specifically

### Mock Strategy
- **D-16:** Default FakeProvider from conftest.py handles success cases — `authenticate_user_session` returns valid token/userId
- **D-17:** Failure tests override specific FakeProvider methods via monkeypatch (e.g., `fake_provider.authenticate_user_session = MagicMock(side_effect=Exception("auth failed"))`)
- **D-18:** For delegate RuntimeError, monkeypatch `server_access_token_for_delegate` to raise

### the agent's Discretion
- Whether to use pytest classes or flat function naming
- Exact number of parametrized vs individual tests
- Whether to add helper functions for common assertions

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Test Infrastructure (Phase 22)
- `tests/conftest.py` — Shared fixtures: `app`, `client`, `FakeProvider` (with `authenticate_user_session`, `server_access_token_for_delegate`, etc.)
- `.planning/phases/22-test-infrastructure-setup/22-CONTEXT.md` — Fixture design decisions (D-01 through D-11)

### Auth Route Implementation
- `jellyswipe/__init__.py:253-280` — Route handlers for `/auth/provider`, `/auth/jellyfin-use-server-identity`, `/auth/jellyfin-login`

### Existing Auth Test Patterns
- `tests/test_route_authorization.py` — FakeProvider usage, session helpers, header-spoof parametrize pattern

### Research
- `.planning/research/SUMMARY.md` — Testing pitfalls: avoid over-mocking, test behavior not implementation

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tests/conftest.py:FakeProvider` — Already has `authenticate_user_session`, `server_access_token_for_delegate`, `server_primary_user_id_for_delegate` methods
- `tests/conftest.py:client` fixture — Function-scoped Flask test client ready to use
- `tests/test_route_authorization.py:_set_session()` — Session manipulation helper pattern (set active_room, user_id, delegate flag)
- `tests/test_route_authorization.py:SPOOF_HEADERS` — Parametrized header-spoof tuple

### Established Patterns
- **Parametrized spoof headers**: `@pytest.mark.parametrize("spoof_header", SPOOF_HEADERS)` for EPIC-01 tests
- **Session verification**: `client.session_transaction()` to check session state after requests
- **JSON response assertion**: `response.get_json()` + dict comparison
- **Status code assertion**: `response.status_code` checks

### Integration Points
- `jellyswipe/__init__.py:create_app()` — Factory creates app with routes registered
- `jellyswipe/__init__.py:get_provider()` — Returns `_provider_singleton`, patched by conftest.py
- Flask `session` — Modified by `/auth/jellyfin-use-server-identity` (sets delegate flag)

</code_context>

<specifics>
## Specific Ideas

No specific requirements — standard Flask route testing following existing patterns.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---
*Phase: 23-auth-route-tests*
*Context gathered: 2026-04-26*
