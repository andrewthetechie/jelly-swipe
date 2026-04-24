---
status: complete
phase: 05-user-parity-packaging
source:
  - 05-01-SUMMARY.md
  - 05-02-SUMMARY.md
started: "2026-04-23T19:34:56Z"
updated: "2026-04-23T20:11:16Z"
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running server/service. Clear ephemeral state (temp DBs, caches, lock files). Start the application from scratch. Server boots without errors, any seed/migration completes, and a primary query (health check, homepage load, or basic API call) returns live data.
result: pass

### 2. Jellyfin login + token persistence (UI)
expected: In Jellyfin mode, you can complete the Jellyfin login flow in the UI, the app stores the provider token/id locally (same browser session), and subsequent actions do not silently revert to an unauthenticated state.
result: pass

### 3. Provider-aware request headers from the browser (Jellyfin vs Plex)
expected: After logging in (Jellyfin mode), normal UI actions send the provider identity headers described in README (provider-neutral + legacy compatibility as documented). In Plex mode, behavior remains compatible with the prior Plex-only header expectations.
result: pass

### 4. Add-to-watchlist / favorites (Jellyfin user token path)
expected: From the swipe UI, adding a matched title to the watchlist succeeds in Jellyfin mode when a Jellyfin user token is present, and the server accepts the request without requiring Plex-only identity inputs.
result: pass

### 5. Match/history/delete/undo identity routing (Jellyfin)
expected: In Jellyfin mode, match/history/delete/undo operations resolve identity consistently from the provider-neutral + legacy headers (no “wrong user” behavior when only the Jellyfin-side identity headers are present).
result: pass

### 6. Dual-browser identity isolation (Jellyfin)
expected: Two separate browser profiles (or incognito + normal) logged in as different Jellyfin identities do not cross-contaminate match/history rows (analogous to dual `plex_id` isolation).
result: pass

### 7. README contract matches runtime behavior
expected: The README’s documented Jellyfin user identity/header contract matches what you observe in the browser network requests and what the server accepts (no undocumented required headers).
result: pass

### 8. Dependency install path still works (packaging)
expected: A clean environment install using `requirements.txt` succeeds (or matches the documented install path), and the app starts with the updated dependencies.
result: pass

## Summary

total: 8
passed: 8
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none yet]
