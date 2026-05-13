# PRD: Shallow Module Cleanup — auth.py Deletion, HTTP Path Consolidation, Regex Deduplication

## Problem Statement

Three modules in the codebase fail the depth test — their interfaces are as complex as (or more complex than) the logic behind them, adding indirection without adding value.

1. **`auth.py` is a pass-through layer.** Four free functions each take `(session_dict: dict, uow: DatabaseUnitOfWork)`, extract `session_dict["session_id"]`, and forward to `uow.auth_sessions.*`. No invariants are enforced, no domain logic is applied, no error recovery is added beyond what the repository already provides. `clear_session_state` is literally `session_dict.clear()`. `resolve_active_room` contains a raw SQL query that duplicates `RoomRepository.pairing_code_exists`. A separate `destroy_session_dep` dependency in the dependencies module exists only to forward to `auth.destroy_session`. If `auth.py` were deleted, the one-liner forwards would reappear inline in the dependencies and route handlers, and nothing of value would be lost.

2. **`http_client.py` protects the wrong surface.** `make_http_request` was extracted to centralize HTTP concerns (User-Agent, logging, timeouts). But `JellyfinLibraryProvider` — the heaviest HTTP caller in the codebase — uses its own `requests.Session` directly for every API call. The only usage of `make_http_request` in the Jellyfin client is a single fallback call in `server_info()`. The module extracted "for correctness" is bypassed by the module that most needs HTTP discipline. The real risks (missing timeouts, inconsistent error handling) live in `_api()` and `fetch_library_image()`, untouched by the centralized helper.

3. **Duplicated image-path validation regex across a seam.** The proxy router and the Jellyfin library provider both validate Jellyfin image paths with nearly identical regexes (differing only in capture vs. non-capture group). The router validates before calling the provider, and the provider validates again internally. If one regex is updated and the other isn't, either security or functionality breaks silently.

## Solution

Eliminate the three shallow modules / duplications by inlining logic where it's consumed and consolidating ownership where it's split.

1. Delete `auth.py` entirely. Inline session lookup into `require_auth`, inline session lifecycle into the route handlers that use it, replace `resolve_active_room` with a direct call to the existing `RoomRepository.pairing_code_exists`.

2. Remove the Jellyfin adapter's single dependency on `http_client.py`. The adapter uses `self._session` consistently for all Jellyfin calls. `http_client.py` stays scoped to stateless external services (TMDB today).

3. Delete the router's duplicate regex. The provider's private regex is the single validation point; the router relies on the `PermissionError` it already catches.

## User Stories

1. As a developer reading `require_auth`, I want to see the full auth-resolution logic inline, so that I don't have to cross-reference a separate `auth.py` module to understand what happens when a session cookie arrives.
2. As a developer modifying session creation logic, I want it in the route handler that calls it, so that I can see the full request→create→respond flow in one place.
3. As a developer modifying session destruction logic, I want it in the logout route handler, so that I can see the full request→destroy→clear-cookie flow in one place.
4. As a developer reading the `/me` endpoint, I want the "does this room still exist?" check to use the existing repository method, so that I don't encounter a raw SQL query duplicating logic that lives elsewhere.
5. As a developer debugging a Jellyfin HTTP failure, I want every Jellyfin call to go through the same `self._session` path, so that I'm not confused by a single call using a different HTTP function with different timeout and error semantics.
6. As a developer reading `http_client.py`, I want its actual scope to match its callers, so that I know it's the TMDB HTTP helper — not a "centralized" module that the main HTTP consumer bypasses.
7. As a developer updating the Jellyfin image path format, I want one regex to update, so that the router and provider can't silently diverge.
8. As a developer reading the proxy route, I want to see that it trusts the provider's interface rather than duplicating the provider's internal validation.
9. As a developer adding a new proxy consumer, I want `fetch_library_image` to be self-contained — I call it, it validates internally, it raises `PermissionError` on bad input — so that I don't need to know about a regex I'm supposed to check first.
10. As a developer onboarding to the codebase, I want fewer modules with clearer ownership boundaries, so that my mental model of the system matches its actual structure.

## Implementation Decisions

### 1. Delete `auth.py`

**Inline `get_current_token` and `clear_session_state` into `require_auth`:**
The `require_auth` dependency currently calls `auth.get_current_token(request.session, uow)` which extracts the session_id from the dict and calls `uow.auth_sessions.get_by_session_id`. This becomes a direct call to `uow.auth_sessions.get_by_session_id(request.session.get("session_id"))` inside `require_auth`. `clear_session_state` (`session_dict.clear()`) inlines as `request.session.clear()`.

**Inline `create_session` into the `jellyfin_use_server_identity` route handler:**
Session ID generation, expired session cleanup, and auth session insertion happen directly in the handler. The handler already has access to `uow` and `request.session`.

**Inline `destroy_session` into the `logout` route handler:**
Session ID extraction, session dict clearing, and auth session deletion happen directly in the handler. The `destroy_session_dep` dependency in the dependencies module is also deleted — it was a forwarding-only dependency used by one route.

**Replace `resolve_active_room` with inline code in the `/me` handler:**
Four lines using the existing `uow.rooms.pairing_code_exists`:

- Get `active_room` from session
- If present, check existence via `uow.rooms.pairing_code_exists`
- If room is gone, pop `active_room` and `solo_mode` from session, set `active_room = None`

This eliminates the raw SQL query in `auth.py` that duplicated `RoomRepository.pairing_code_exists` and the `uow.run_sync` call that bridged sync/async for it.

**`AuthUser` is unchanged.** It stays as a dataclass with `jf_token` and `user_id`. No new fields. The "typed object instead of a raw dict" benefit comes from `require_auth` owning the full lookup — callers already receive `AuthUser`, they just no longer thread `session_dict: dict` through separate auth functions.

### 2. Decouple `http_client.py` from the Jellyfin adapter

Remove the `from .http_client import make_http_request` import from the Jellyfin library module. Replace the single `make_http_request` call in the `server_info()` fallback with `self._session.get()`, consistent with every other HTTP call in the class.

`http_client.py` remains in the codebase, scoped to stateless external services. Its current primary consumer is the TMDB module (4 call sites). No changes to `http_client.py` itself.

The deeper cleanup — making the Jellyfin adapter's `_api()` and `fetch_library_image()` handle timeouts and errors consistently — is out of scope. That belongs to the Architecture Deepening PRD's provider split.

### 3. Deduplicate image-path regex

Delete the regex check from the proxy route (the `re.match(...)` guard). The provider's private `_JF_IMAGE_PATH` regex inside `fetch_library_image` is the single validation point. It stays private — callers don't pre-validate, they call `fetch_library_image` and handle the `PermissionError` on invalid paths.

The proxy route already catches `PermissionError` and returns 403 (existing code), so the external behavior is identical. The `if not path` presence check in the proxy route stays — that's input presence validation, not format validation.

## Testing Decisions

### What makes a good test

Tests should exercise external behavior through the module's public interface, not implementation details. A test that breaks because an internal helper was renamed is a bad test. For this PRD specifically: tests should verify that auth routes still create/destroy sessions correctly and that the proxy still rejects bad image paths — they should not care whether validation happens in the route or the provider.

### Test changes

**Delete `tests/test_auth.py`.** Its test targets (`auth.create_session`, `auth.get_current_token`, `auth.destroy_session`) no longer exist as standalone functions. The behavior they tested — session lookup returns a record, expired sessions are cleaned up, destroy clears state — is covered by existing route-level tests in `test_routes_auth.py` (which hits `/auth/jellyfin-use-server-identity`, `/auth/logout`, `/me`) and `test_route_authorization.py`.

If any edge case from `test_auth.py` isn't covered by existing route tests (e.g., the expired-session cleanup during creation), add a targeted test to `test_dependencies.py` for `require_auth` or to `test_routes_auth.py` for the handlers.

**Update `test_dependencies.py`.** Tests that mock `auth.destroy_session` or `auth.get_current_token` need to be updated to mock the underlying `uow.auth_sessions.*` methods instead, since the auth module indirection is gone.

**Update `test_route_authorization.py`.** The `fake_resolve_active_room` mock target changes from `auth_routes.resolve_active_room` to directly mocking `uow.rooms.pairing_code_exists`.

**No new test files are created.** The proxy regex removal requires no test changes — the route's behavior (403 on bad paths) is unchanged and already tested.

### Prior art

- `test_routes_auth.py` for route-level auth testing patterns
- `test_dependencies.py` for dependency injection testing patterns
- `test_route_authorization.py` for authorization guard testing patterns

## Out of Scope

- **Auth model redesign.** The delegate identity flow is unchanged. `AuthUser` keeps its current shape. The vault concept persists — only its implementation location moves.
- **`http_client.py` changes.** The module itself is untouched. Only the Jellyfin adapter's single import is removed.
- **Jellyfin adapter HTTP hardening.** Making `_api()` and `fetch_library_image()` use consistent timeouts and error handling is the Architecture Deepening PRD's responsibility.
- **New features.** No user-facing behavior changes. These are structural cleanups only.
- **Frontend changes.** The HTML/JS client is untouched.
- **Route path renames.** All API routes keep their current paths and response shapes.

## Further Notes

- **These three changes are independent.** They touch different files with minimal overlap: (1) auth deletion touches `auth.py`, `dependencies.py`, `routers/auth.py`, and test files; (2) HTTP decoupling touches `jellyfin_library.py` only; (3) regex dedup touches `routers/proxy.py` only. They can be decomposed into separate issues and landed in any order.
- **CONTEXT.md has been updated.** The Vault glossary entry no longer references `create_session()` in `auth.py`. No new domain terms are introduced — these cleanups are structural, not conceptual.
- **Relationship to Architecture Deepening PRD.** The HTTP path consolidation (item 2) is a prerequisite to the Architecture Deepening PRD's provider split. When the provider is eventually split, the library I/O module will own `self._session` end-to-end with no stray `make_http_request` call to account for.
