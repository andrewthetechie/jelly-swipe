---
status: complete
phase: 04-jellyfin-library-media
source:
  - 04-01-SUMMARY.md
  - 04-02-SUMMARY.md
started: "2026-04-24T16:13:10Z"
updated: "2026-04-24T16:31:32Z"
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running server/service. Clear ephemeral state (temp DBs, caches, lock files). Start the application from scratch. Server boots without errors, any seed/migration completes, and a primary query (health check, homepage load, or basic API call) returns live data.
result: pass

### 2. Jellyfin deck card shape parity
expected: In Jellyfin mode, creating or joining a room returns/swaps to a deck where each movie card has the expected fields (`id`, `title`, `summary`, `thumb`, `rating`, `duration`, `year`) and cards render without schema errors.
result: pass

### 3. Genres + Recently Added behavior parity
expected: Genre list loads with Sci-Fi normalization, selecting a genre refetches a filtered deck, and selecting Recently Added yields date-ordered items without random shuffle behavior.
result: pass

### 4. Jellyfin poster proxy path validation
expected: Valid Jellyfin poster thumbs load through `/proxy?path=jellyfin/{id}/Primary`, while malformed or traversal-like paths are rejected (403) and missing provider config yields 503.
result: pass

### 5. Trailer and cast endpoints with Jellyfin movie id
expected: From a Jellyfin-backed movie card, trailer and cast requests resolve via TMDB using provider metadata (`title`/`year`) and return data or documented not-found behavior without crashing.
result: pass

### 6. Server info parity in Jellyfin mode
expected: Calling `/plex/server-info` in Jellyfin mode returns a stable `{machineIdentifier, name}` payload shape suitable for existing UI parity assumptions.
result: pass

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "From a Jellyfin-backed movie card, trailer and cast requests resolve via TMDB using provider metadata (`title`/`year`) and return data or documented not-found behavior without crashing."
  status: passed
  reason: "User reported: Trailer button always shows \"not found\" and the cast does not show. The get for the trailer returns a 500 error 127.0.0.1 - - [24/Apr/2026 11:25:23] \"GET /cast/1dbe36a485869be750b281831de2395a HTTP/1.1\" 500 -
127.0.0.1 - - [24/Apr/2026 11:25:24] \"GET /get-trailer/1dbe36a485869be750b281831de2395a HTTP/1.1\" 500 -
127.0.0.1 - - [24/Apr/2026 11:25:47] \"GET /get-trailer/1dbe36a485869be750b281831de2395a HTTP/1.1\" 500 -"
  severity: blocker
  test: 5
  root_cause: "Jellyfin item ids from the room deck can fail `resolve_item_for_tmdb()` on `GET /Items/{movie_id}` for this server profile, causing trailer/cast to throw and return 500 before TMDB lookup."
  artifacts:
    - path: "media_provider/jellyfin_library.py"
      issue: "`resolve_item_for_tmdb()` uses only `/Items/{movie_id}`; no user-scoped fallback path when the server rejects that lookup"
    - path: "app.py"
      issue: "`/get-trailer` and `/cast` bubble provider exceptions as HTTP 500"
  missing: []
  debug_session: ".planning/debug/jellyfin-tmdb-item-lookup-500.md"
