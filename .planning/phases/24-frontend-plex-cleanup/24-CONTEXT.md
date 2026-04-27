# Phase 24: Frontend Plex Cleanup - Context

**Gathered:** 2026-04-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Strip all Plex-specific CSS classes, JavaScript functions, conditional branches, localStorage keys, URLs, and UI copy from `jellyswipe/templates/index.html` — leaving only Jellyfin code paths. Includes adding a new backend endpoint to support Jellyfin deep links in match cards. No new features beyond replacing the broken Plex deep-link button.

</domain>

<decisions>
## Implementation Decisions

### CSS Class Renaming
- **D-01:** Rename `.plex-yellow` to `.accent-text` — used 9 times for accent text (session codes, headings, instructions). Definition at line 43: `color: #e5a00d`.
- **D-02:** Rename `.plex-open-btn` to `.cta-btn` — used 1 time for the "Open In" link in match card back faces. Definition at line 122 with amber background styling.

### "Open In" Button Replacement
- **D-03:** Add new backend endpoint `GET /jellyfin/server-info` returning `{ "baseUrl": "...", "webUrl": "..." }`. Frontend fetches once on first `openMatches()` call and caches in a module variable (replaces `plexServerId`).
- **D-04:** Replace `fetchPlexServerId()` with `fetchJellyfinServerInfo()` that calls the new endpoint. Cache result to avoid repeated fetches.
- **D-05:** Construct Jellyfin deep link in match cards: `{webUrl}#!/details?id={movieId}`. Exact path format (hash-based vs path-based) is agent's discretion based on Jellyfin web client version.
- **D-06:** Remove `plexServerId` module variable (line 318) — replace with cached server info object.
- **D-07:** The `openMatches()` function (line 548) currently early-returns if `serverId` is null (line 551). After replacement, adjust the guard to handle missing server info gracefully (show matches without "Open In" button if server URL unavailable).

### Login Function & Button
- **D-08:** Delete `loginWithPlex()` function (line 412). Create `loginWithJellyfin()` containing only the Jellyfin delegate auth and username/password login logic (lines 413–441). The Plex redirect branch (lines 443–445) is removed entirely.
- **D-09:** Login button default text: "Login" (hardcoded, no conditional). Delegate mode already overrides to "Continue" at line 1048.
- **D-10:** Remove Plex auth PIN flow from `window.onload` (lines 1033–1041). The entire `if (mediaProvider === 'plex')` block is deleted.
- **D-11:** Update login button `onclick` attribute in HTML (line 211) from `loginWithPlex()` to `loginWithJellyfin()`. Update `window.onload` button binding (line 1061) similarly.

### Provider Abstraction Simplification
- **D-12:** Remove `const mediaProvider = "{{ media_provider }}";` (line 324) entirely. All code that branched on this variable becomes unconditional Jellyfin behavior.
- **D-13:** Remove all `mediaProvider === 'plex'` branches — delete the Plex code path entirely. Affected locations: `fetchAndStoreProviderId()` (lines 386–394), `window.onload` (lines 1033–1041, 1060), `loginWithPlex()` (lines 443–445).
- **D-14:** Remove all `mediaProvider === 'jellyfin'` guards — the Jellyfin code behind these checks becomes unconditional. Affected locations: `loginWithPlex()` (line 413), `providerIdentityHeaders()` (line 346), `addToWatchlist()` (line 486), match card button label (line 630), login button text (line 1060).
- **D-15:** Simplify `providerToken()` (line 326) to `return localStorage.getItem('provider_token');` — remove `plex_token` fallback.
- **D-16:** Simplify `providerUserId()` (line 330) to `return localStorage.getItem('provider_user_id');` — remove `plex_id` fallback.
- **D-17:** `providerIdentityHeaders()` (line 338): remove `X-Plex-User-ID` header (line 342), keep `X-Provider-User-Id` (line 343). Always include Jellyfin `Authorization` header (remove `mediaProvider === 'jellyfin'` guard at line 346).
- **D-18:** `addToWatchlist()` (line 477): always use `providerIdentityHeaders()` — remove Plex header branch (line 488).
- **D-19:** `fetchAndStoreProviderId()` (line 383): remove entire Plex branch (lines 386–394). The remaining Jellyfin path (lines 397–398) becomes unconditional. Remove `plex_id` localStorage write (line 398).
- **D-20:** `bootstrapJellyfinDelegate()` (line 352): remove `plex_token` cleanup (line 373) and `plex_id` write (line 375). Only write `provider_user_id`.
- **D-21:** `loginWithJellyfin()` (new): after successful Jellyfin login, only write `provider_token` and `provider_user_id` — remove `plex_token` and `plex_id` writes (lines 436–437).
- **D-22:** Remove `plex_id: providerUserId()` from `/room/swipe` request body (line 931). Backend ignores this field — uses `_provider_user_id_from_request()` instead.

### Agent's Discretion
- Exact Jellyfin deep link URL format (hash vs path routing depends on Jellyfin web client version)
- Exact button label for "Open In" in match cards (likely "OPEN IN JELLYFIN")
- Whether to remove the unused `{{ media_provider }}` Jinja2 template tag from the HTML
- Whether to clear stale `plex_token` / `plex_id` localStorage values on page load for existing users

</decisions>

<canonical_refs>
## Canonical References

### Phase requirements
- `.planning/REQUIREMENTS.md` — FE-01 through FE-08 requirements and acceptance criteria
- `.planning/ROADMAP.md` § Phase 24 — success criteria (5 items)

### Related source files
- `jellyswipe/templates/index.html` — primary file for this phase (1072 lines, 47 Plex references)
- `jellyswipe/__init__.py` — backend routes: `/room/swipe` at line 310, existing `server_info()` method on provider; new `/jellyfin/server-info` endpoint will be added here
- `jellyswipe/jellyfin_library.py` — `server_info()` at line 346 (returns `machineIdentifier`), can be extended for `webUrl`

### Prior phase context
- `.planning/phases/23-backend-source-cleanup/23-CONTEXT.md` — Phase 23 deleted `/plex/server-info` route; noted `server_info()` method and `machineIdentifier` field for post-Phase-24 evaluation

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `providerIdentityHeaders()` function (line 338) — already constructs correct Jellyfin auth headers; simplifies to unconditional Jellyfin after cleanup
- `jellyfinAuthorizationHeader()` function (line 334) — builds `MediaBrowser` Authorization header; used by `providerIdentityHeaders()`
- `bootstrapJellyfinDelegate()` function (line 352) — server-side credential delegation; works independently of Plex code
- `server_info()` method on `JellyfinLibraryProvider` (jellyfin_library.py:346) — currently returns `{ machineIdentifier, ... }`. Can be extended to include `webUrl` for the new endpoint.

### Established Patterns
- CSS: Single-file styles in `<style>` block; utility classes for colors (`.plex-yellow`), layout (`.hidden`, `.menu-btn`)
- JS: Module-level variables for state (`movieStack`, `swipeHistory`, `plexServerId`); localStorage for persistence; async/await for API calls
- Backend routes: Flask `@app.route()` decorators; JSON responses via `jsonify()`; identity from `_provider_user_id_from_request()`

### Integration Points
- `openMatches()` (line 548) → `fetchPlexServerId()` (line 550) → match card rendering (lines 628–637) — this chain needs replacement
- `window.onload` (line 1029) → Plex PIN flow (lines 1033–1041) + Jellyfin delegate boot (lines 1043–1058) + login button setup (lines 1060–1061) — Plex paths removed, Jellyfin paths simplified
- `/room/swipe` body (line 931) → `plex_id: providerUserId()` — remove field, backend ignores it
- Login button HTML (line 211) → `onclick="loginWithPlex()"` → renamed to `loginWithJellyfin()`

</code_context>

<specifics>
## Specific Ideas

- The `.plex-yellow` class color (`#e5a00d`) is the app's amber/gold accent used throughout — it's a design system color, not a Plex brand color. Renaming to `.accent-text` reflects its actual role.
- The `/jellyfin/server-info` endpoint should NOT expose credentials — only the public web URL needed for deep links. The `baseUrl` might be an internal Docker hostname; `webUrl` should be the user-facing URL.
- Existing users may have stale `plex_token` / `plex_id` in localStorage. After cleanup these keys are no longer read. If users also have `provider_token` / `provider_user_id` they're fine; otherwise they'll need to re-login. Consider adding a one-time cleanup of stale keys on page load.

</specifics>

<deferred>
## Deferred Ideas

- Rename or remove `server_info()` method on the provider base class — evaluate after Phase 24 (per Phase 23 CONTEXT.md)
- Rename `machineIdentifier` field in `server_info()` return dict to Jellyfin-idiomatic name — future cleanup
- Expose Jellyfin server URL via template context injection instead of a separate endpoint — alternative approach, not chosen

</deferred>

---

*Phase: 24-frontend-plex-cleanup*
*Context gathered: 2026-04-26*
