# Phase 27: Client Simplification + Cleanup - Context

**Gathered:** 2026-04-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Strip client JavaScript of all server-responsibility code: token storage, identity headers, match detection logic, deep link construction. Update client to use new RESTful routes, session-cookie auth, and SSE-driven match notifications. This is the client-side counterpart to Phases 24-26.

**Requirements:** CLNT-01 (no localStorage tokens), CLNT-02 (no client-side match detection)

**Depends on:** Phase 26 (all server-side endpoints stable and producing correct responses)

</domain>

<decisions>
## Implementation Decisions

### Login UX Flow
- **D-01:** Auto-delegate first — client always tries `/auth/jellyfin-use-server-identity` on load. If delegate succeeds (env credentials configured), user skips login form. Falls back to username/password form if delegate unavailable.
- **D-02:** On page load, client calls `GET /me` to check if session is active. If active, show main UI. If not, show login/delegate flow.
- **D-03:** No token ever stored in `localStorage` or accessible to JavaScript. All auth is session-cookie based.

### Match Popup Trigger
- **D-04:** Match popup renders exclusively from SSE events. The existing `EventSource` on `/room/{code}/stream` already receives `last_match` events (enriched in Phase 26). Client renders popup from SSE event data alone.
- **D-05:** Client-side match detection code removed entirely — no checking swipe HTTP response for match data.

### Route Updates
- **D-06:** All client fetch() calls updated to use new RESTful routes from Phase 25:
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

### Removed Code
- **D-07:** Remove all `localStorage.getItem("provider_token")` and `localStorage.getItem("plex_token")` calls
- **D-08:** Remove `jellyfinAuthorizationHeader()` function
- **D-09:** Remove client-side Plex deep link construction (the `openMatches` URL builder)
- **D-10:** Remove `Authorization` header from all client fetch() calls
- **D-11:** Remove `X-Provider-User-Id` and other identity alias headers from all client requests

### the agent's Discretion
- Exact login/delegate UI layout
- Error handling for failed login/delegate attempts
- Loading state transitions between auth and main UI

</decisions>

<canonical_refs>
## Canonical References

### Phase requirements and research
- `.planning/REQUIREMENTS.md` §Client Cleanup — CLNT-01, CLNT-02 acceptance criteria
- `.planning/ROADMAP.md` §Phase 27 — Success criteria and plan outline
- `.planning/research/PITFALLS.md` — HttpOnly migration bridge (localStorage → session cookie)

### Existing codebase
- `jellyswipe/templates/index.html` — All client JS that needs modification (login, auth, swipe, match, routes)
- `jellyswipe/__init__.py:249-272` — Server auth endpoints that client calls

### Prior phase decisions
- `.planning/phases/24-auth-module-server-identity/24-CONTEXT.md` — Login returns minimal response
- `.planning/phases/25-restful-routes-deck-ownership/25-CONTEXT.md` — New route URL patterns
- `.planning/phases/26-match-notification-deep-links/26-CONTEXT.md` — SSE-only match delivery, deep links in SSE

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Existing `EventSource` setup in client JS — already listening for `last_match` events. Just needs enriched payload handling.
- Login form UI already exists — just needs to stop storing/showing tokens.

### Established Patterns
- Client uses `fetch()` for all API calls with `Authorization` header — these headers get removed
- Client stores tokens in `localStorage` and re-sends on every mutation — this entire pattern gets removed
- Match popup already renders from data — just needs to use SSE payload instead of swipe response

### Integration Points
- `data/index.html` — Parallel PWA copy that also needs the same updates
- Service worker (`data/sw.js`) — May need cache path updates for new routes

</code_context>

<specifics>
## Specific Ideas

- The auto-delegate flow preserves the current UX where users with env credentials configured skip login entirely
- The SSE listener for match popups is already wired — the change is removing the duplicate HTTP response path, not adding new event handling

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 27-client-simplification-cleanup*
*Context gathered: 2026-04-26*
