# Phase 27: Client Simplification + Cleanup - Context

**Gathered:** 2026-04-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Strip client JavaScript of all server-responsibility code: token storage, identity headers, match detection logic, deep link construction. Update client to use new RESTful routes, session-cookie auth, and SSE-driven match notifications. This is the client-side counterpart to Phases 24-26.

**Requirements:** CLNT-01 (no localStorage tokens), CLNT-02 (no client-side match detection)

**Depends on:** Phase 26 (all server-side endpoints stable and producing correct responses)

</domain>

<decisions>
## Implementation Decisions

### Dead Code Removal
- **D-01:** Remove all Plex OAuth flow code: `loginWithPlex()` Plex branch, `/auth/plex-url` call, `/auth/check-returned-pin` call, `pin_id` URL param handling in `window.onload`. These server routes no longer exist.
- **D-02:** Remove client-side deep link construction entirely (line 629 — `https://app.plex.tv/desktop/...` URL builder). Server now provides `deep_link` in SSE match events and `/matches` response.
- **D-03:** Remove ALL localStorage token/identity keys — both `provider_token`+`plex_token` pairs and `provider_user_id`+`plex_id` pairs. No tokens stored in JavaScript-accessible storage at all (CLNT-01).
- **D-04:** Remove `fetchAndStoreProviderId()` function entirely — identity now comes from `GET /me` via session cookie.
- **D-05:** Remove `jellyfinAuthorizationHeader()` function and `providerIdentityHeaders()` function. All auth is session-cookie based — no Authorization or identity headers sent by client.
- **D-06:** Remove `providerToken()` and `providerUserId()` helper functions — they read from localStorage which is being eliminated.

### Auth Flow Rewire
- **D-07:** Page load sequence: call `GET /me` first. If 200 → show main UI (user has active session). If 401 → show login screen. No more `providerToken()` check on load.
- **D-08:** Login flow is two-path: (1) Always try `POST /auth/jellyfin-use-server-identity` (delegate) first. If delegate succeeds → show main UI. If fails → show username/password form via `POST /auth/jellyfin-login`.
- **D-09:** Keep existing username/password form UI as-is — just remove the Plex branch. No layout changes to the form.
- **D-10:** Delegate mode UX preserved: login button text changes to "Continue" in delegate mode, auto-attempts bootstrap. Form users see "Login" button.
- **D-11:** New `POST /auth/logout` endpoint needed on server: clears session and user_tokens vault entry. Client calls this, then clears session cookie client-side, then reloads. Replaces current `localStorage.clear(); location.reload()`.

### Match Popup Rewire
- **D-12:** Match popup renders exclusively from SSE `last_match` events. Remove the `data.match` check in swipe HTTP response handler entirely (CLNT-02).
- **D-13:** Match popup shows enriched metadata from SSE event: title, poster, rating, duration, year, and deep_link as the "OPEN IN JELLYFIN" button href.
- **D-14:** Remove `lastSeenMatchTs` dedup guard — SSE is the single source of truth for matches. No need to deduplicate between HTTP response and SSE.
- **D-15:** Add SSE auto-reconnection: `onerror` handler on EventSource that retries `startPolling()` after ~3 second delay. Prevents silent disconnection.

### Route Migration
- **D-16:** Apply all route changes in a single batch pass. Old→new mapping:
  - `/room/create` → `POST /room`
  - `/room/join` (body) → `POST /room/{code}/join`
  - `/room/swipe` → `POST /room/{code}/swipe`
  - `/movies` → `GET /room/{code}/deck`
  - `/movies?genre=X` → `POST /room/{code}/genre`
  - `/room/status` → `GET /room/{code}/status`
  - `/room/stream` → `GET /room/{code}/stream`
  - `/room/quit` → `POST /room/{code}/quit`
  - `/undo` → `POST /room/{code}/undo`
  - `/room/go-solo` → `POST /room/solo`
- **D-17:** Swipe fetch body trimmed to `{movie_id, direction}` only. Remove `title`, `thumb`, `plex_id` from payload.
- **D-18:** Remove server-side `/room/<code>/go-solo` route — replaced by `POST /room/solo` from Phase 26.

### Error Handling
- **D-19:** On 401 from any fetch(): show a "Session expired" banner with a "Re-login" button. Do NOT auto-redirect or auto-attempt re-auth.
- **D-20:** SSE reconnection uses simple retry — no exponential backoff needed for a self-hosted app on local network.

### the agent's Discretion
- Exact session expired banner styling/positioning
- SSE reconnection delay (3-5 seconds is fine)
- Loading state transitions between auth and main UI
- Whether to add a loading spinner during delegate bootstrap

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase requirements and research
- `.planning/REQUIREMENTS.md` §Client Cleanup — CLNT-01, CLNT-02 acceptance criteria
- `.planning/ROADMAP.md` §Phase 27 — Success criteria and plan outline
- `.planning/research/PITFALLS.md` — HttpOnly migration bridge (localStorage → session cookie)

### Existing codebase (client — all changes happen here)
- `jellyswipe/templates/index.html` — All client JS (1072 lines). Every section needs modification.
  - Lines 322-347: `providerToken()`, `providerUserId()`, `jellyfinAuthorizationHeader()`, `providerIdentityHeaders()` — all removed
  - Lines 352-399: `bootstrapJellyfinDelegate()`, `fetchAndStoreProviderId()` — simplified
  - Lines 412-446: `loginWithPlex()` — Plex branches removed, Jellyfin-only
  - Lines 484-490: `/watchlist/add` — remove identity headers
  - Lines 554-555: `/matches` — remove identity headers
  - Lines 629: Plex deep link construction — removed, use server `deep_link`
  - Lines 695-712: `/matches/delete`, `/undo` — remove identity headers, update routes
  - Lines 926-947: `/room/swipe` — update route, trim body, remove match detection
  - Lines 962-974: `/room/create`, `/room/join` — update routes
  - Lines 993-1025: SSE `startPolling()` — add onerror reconnect, update route, use enriched match data
  - Lines 1029-1068: `window.onload` — remove Plex OAuth callback, simplify auth check

### Existing codebase (server — minor additions)
- `jellyswipe/__init__.py` — Add `POST /auth/logout` route; remove `/room/<code>/go-solo` route
- `jellyswipe/auth.py` — Logout clears session + user_tokens vault entry

### Prior phase decisions
- `.planning/phases/24-auth-module-server-identity/24-CONTEXT.md` — @login_required, g.user_id, session cookie auth
- `.planning/phases/25-restful-routes-deck-ownership/25-CONTEXT.md` — RESTful route patterns, deck endpoint, cursor tracking
- `.planning/phases/26-match-notification-deep-links/26-CONTEXT.md` — SSE match event format `{title, thumb, movie_id, rating, duration, year, deep_link}`, GET /me, POST /room/solo

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Existing `EventSource` setup in client JS (line 995-996) — already listening for `last_match` events. Needs enriched payload handling + onerror reconnect.
- Login form UI already exists (username/password fields) — just needs Plex branch removal.
- `bootstrapJellyfinDelegate()` (lines 352-381) — core logic is correct, just needs localStorage removal.
- Match popup overlay (`#match-overlay`) — HTML structure can stay, just render from SSE data.

### Established Patterns
- Client uses `fetch()` with `credentials: 'same-origin'` on some calls — this pattern is correct for session cookies and should be used consistently on ALL calls going forward.
- SSE uses `new EventSource(url)` — stays the same, just needs `/room/{code}/stream` path and onerror handler.
- Room code stored in client variable for route construction — this pattern continues.

### Integration Points
- All 22 fetch() endpoints in client JS need review — ~8 need route updates, ~4 need header removal, ~2 need body changes.
- Server needs two additions: `POST /auth/logout` route, removal of `/room/<code>/go-solo`.
- No `data/index.html` exists — only `jellyswipe/templates/index.html` needs updating.
- No service worker route caching to worry about.

### Key File Structure
- Single file change: `jellyswipe/templates/index.html` (all client JS is inline)
- Minor server changes: `jellyswipe/__init__.py` (logout route, remove go-solo), `jellyswipe/auth.py` (logout helper)

</code_context>

<specifics>
## Specific Ideas

- The auto-delegate flow preserves the current UX where users with env credentials configured skip login entirely
- The SSE listener for match popups is already wired — the change is removing the duplicate HTTP response path and using enriched SSE data
- Session expired banner should be non-blocking — user can dismiss it or click "Re-login" to return to login screen
- The logout endpoint should clear both the Flask session and the user_tokens vault entry to fully clean up

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 27-client-simplification-cleanup*
*Context gathered: 2026-04-27*
