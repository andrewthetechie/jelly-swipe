---
phase: 27-client-simplification-cleanup
plan: 01
subsystem: client-auth
tags: [cleanup, auth, session-cookie, sse, rest-routes, tdd]
dependency_graph:
  requires: [phase-26-complete]
  provides: [clean-client-js, logout-endpoint, active-room-in-me, no-go-solo-route]
  affects: [jellyswipe/auth.py, jellyswipe/__init__.py, jellyswipe/templates/index.html]
tech_stack:
  added: [apiFetch-401-handler, showMatchMetadata, SSE-onerror-reconnect]
  patterns: [session-cookie-auth, restful-routes, sse-only-match-popup]
key_files:
  created: []
  modified:
    - jellyswipe/auth.py
    - jellyswipe/__init__.py
    - jellyswipe/templates/index.html
    - tests/test_route_authorization.py
decisions:
  - Rewrote client JS holistically rather than 20+ individual edits for correctness
  - Kept plex-yellow/plex-open-btn CSS class names (styling only, no functional Plex code)
  - apiFetch wrapper handles 401 globally with session-expired banner
  - SSE auto-reconnect with 3s delay (simple retry, no exponential backoff per D-20)
metrics:
  duration: ~10 minutes
  completed: 2026-04-27
  tasks: 2
  files_modified: 4
  tests_added: 6
  lines_added: 181
  lines_removed: 199
  net_change: -18
---

# Phase 27 Plan 01: Dead Code Removal + Auth Rewire + Route Migration Summary

Removed all localStorage token storage, identity headers, Plex dead code, and client-side URL construction. Rewired auth flow to use GET /me + session cookies. Updated all fetch routes to RESTful patterns. Added POST /auth/logout server endpoint.

## What Was Done

### Task 1 (TDD): POST /auth/logout + extend GET /me + remove go-solo route
- **RED:** Added 6 failing tests for logout, activeRoom, go-solo removal
- **GREEN:** Implemented `destroy_session()` in auth.py, POST /auth/logout route, extended GET /me with activeRoom field, removed go-solo route
- All 136 tests passing (130 baseline + 6 new)

### Task 2: Client dead code removal + auth rewire + route migration
- Removed: providerToken(), providerUserId(), jellyfinAuthorizationHeader(), providerIdentityHeaders(), fetchAndStoreProviderId(), fetchPlexServerId(), loginWithPlex()
- Removed: all localStorage.setItem/getItem/removeItem/clear calls
- Removed: Plex OAuth callback in window.onload, Plex deep link construction in openMatches()
- Removed: HTTP response match detection in swipe handler (CLNT-02)
- Added: apiFetch() with 401 session-expired banner, showMatchMetadata() helper
- Added: SSE onerror auto-reconnect (3s delay), match metadata display in popup
- Rewired: login() (Jellyfin-only), checkActiveRoom(), doLogout(), all route URLs to /room/{code}/action
- Swipe body trimmed to {movie_id, direction} only

## Commits

| Hash | Message |
|------|---------|
| 9618fec | test(27-01): add failing tests for logout, activeRoom, go-solo removal |
| 766ff2f | feat(27-01): add POST /auth/logout, extend GET /me with activeRoom, remove go-solo |
| 01ae9fa | feat(27-01): client dead code removal, auth rewire, route migration |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all functionality is wired end-to-end.
