---
status: diagnosed
phase: 05-user-parity-packaging
source:
  - 05-01-SUMMARY.md
  - 05-02-SUMMARY.md
started: "2026-04-23T19:34:56Z"
updated: "2026-04-23T19:46:58Z"
---

## Current Test

[testing paused — blocked on Jellyfin `/proxy` poster 403 (see Gaps diagnosis)]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running server/service. Clear ephemeral state (temp DBs, caches, lock files). Start the application from scratch. Server boots without errors, any seed/migration completes, and a primary query (health check, homepage load, or basic API call) returns live data.
result: issue
reported: "I was able to launch the app, login to jellyfish and start and join a room. When I join, the poster shows a broken image and there are errors in the console Failed to load ‘http://localhost:5005/room/stream’. A ServiceWorker intercepted the request and encountered an unexpected error. and in the logs for the server 127.0.0.1 - - [23/Apr/2026 14:37:25] \"GET /proxy?path=jellyfin/0f5eaf1feae9280ec9cc6738af658a4e/Primary HTTP/1.1\" 403 - ... (multiple GET /proxy?path=jellyfin/.../Primary HTTP/1.1 403) ..."
severity: major

### 2. Jellyfin login + token persistence (UI)
expected: In Jellyfin mode, you can complete the Jellyfin login flow in the UI, the app stores the provider token/id locally (same browser session), and subsequent actions do not silently revert to an unauthenticated state.
result: pass

### 3. Provider-aware request headers from the browser (Jellyfin vs Plex)
expected: After logging in (Jellyfin mode), normal UI actions send the provider identity headers described in README (provider-neutral + legacy compatibility as documented). In Plex mode, behavior remains compatible with the prior Plex-only header expectations.
result: pass

### 4. Add-to-watchlist / favorites (Jellyfin user token path)
expected: From the swipe UI, adding a matched title to the watchlist succeeds in Jellyfin mode when a Jellyfin user token is present, and the server accepts the request without requiring Plex-only identity inputs.
result: blocked
blocked_by: prior-phase
reason: "Unable to test because the UI durrecntly does not work to show posters"

### 5. Match/history/delete/undo identity routing (Jellyfin)
expected: In Jellyfin mode, match/history/delete/undo operations resolve identity consistently from the provider-neutral + legacy headers (no “wrong user” behavior when only the Jellyfin-side identity headers are present).
result: blocked
blocked_by: prior-phase
reason: "blocked until outstanding issues are fixed"

### 6. Dual-browser identity isolation (Jellyfin)
expected: Two separate browser profiles (or incognito + normal) logged in as different Jellyfin identities do not cross-contaminate match/history rows (analogous to dual `plex_id` isolation).
result: blocked
blocked_by: prior-phase
reason: "blocked until outstanding issues are fixed"

### 7. README contract matches runtime behavior
expected: The README’s documented Jellyfin user identity/header contract matches what you observe in the browser network requests and what the server accepts (no undocumented required headers).
result: blocked
blocked_by: prior-phase
reason: "blocked until outstanding issues are fixed"

### 8. Dependency install path still works (packaging)
expected: A clean environment install using `requirements.txt` succeeds (or matches the documented install path), and the app starts with the updated dependencies.
result: blocked
blocked_by: prior-phase
reason: "blocked until outstanding issues are fixed"

## Summary

total: 8
passed: 2
issues: 1
pending: 0
skipped: 0
blocked: 5

## Gaps

- truth: "Kill any running server/service. Clear ephemeral state (temp DBs, caches, lock files). Start the application from scratch. Server boots without errors, any seed/migration completes, and a primary query (health check, homepage load, or basic API call) returns live data."
  status: failed
  reason: "User reported: I was able to launch the app, login to jellyfish and start and join a room. When I join, the poster shows a broken image and there are errors in the console Failed to load ‘http://localhost:5005/room/stream’. A ServiceWorker intercepted the request and encountered an unexpected error. and in the logs for the server 127.0.0.1 - - [23/Apr/2026 14:37:25] \"GET /proxy?path=jellyfin/0f5eaf1feae9280ec9cc6738af658a4e/Primary HTTP/1.1\" 403 - (multiple similar /proxy?path=jellyfin/.../Primary 403 lines) ..."
  severity: major
  test: 1
  root_cause: "Jellyfin item IDs are 32-hex strings without hyphens in this environment, but `/proxy` + `JellyfinLibraryProvider.fetch_library_image` only allow canonical UUID-with-hyphens (36 chars). That makes `/proxy?path=jellyfin/<32hex>/Primary` fail Flask's allowlist and return HTTP 403 before any upstream image fetch."
  artifacts:
    - path: "app.py"
      issue: "Jellyfin `/proxy` allowlist regex requires `{36}` UUID-with-hyphens only"
    - path: "media_provider/jellyfin_library.py"
      issue: "`_JF_IMAGE_PATH` regex requires `{36}` UUID-with-hyphens only"
  missing:
    - "Update Jellyfin image path allowlist/parsing to accept both 32-hex ids and canonical UUID ids (still fixed `jellyfin/.../Primary` shape)."
    - "Re-test posters + room UI after `/proxy` succeeds."
  debug_session: ".planning/debug/jellyfin-proxy-thumb-403.md"
