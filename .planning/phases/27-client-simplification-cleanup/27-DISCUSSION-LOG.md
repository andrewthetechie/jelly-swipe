# Phase 27: Client Simplification + Cleanup - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-27
**Phase:** 27-client-simplification-cleanup
**Areas discussed:** Dead code removal scope, Auth flow rewire, SSE + match popup rewire, Route migration + error handling

---

## Dead Code Removal Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Remove all Plex code | Plex OAuth flow, Plex deep links, dual-key localStorage aliases, fetchAndStoreProviderId() | ✓ |
| Selective removal | Keep some Plex compat aliases for safety | |

**User's choice:** Remove all Plex code
**Notes:** App has been Jellyfin-only since v1.2. Server Plex routes no longer exist. Complete removal of all Plex-related client code, localStorage token patterns, and identity helper functions.

---

## Auth Flow Rewire

| Option | Description | Selected |
|--------|-------------|----------|
| /me check → delegate → form | Call GET /me on load, delegate-first, form fallback | ✓ |
| /me check → form only | Call GET /me on load, always show form if no session | |
| Delegate only (no form) | Auto-delegate, no manual login | |

**User's choice:** /me check → delegate → form
**Notes:** Keeps existing form UI unchanged (just remove Plex branch). Delegate mode shows "Continue" button. New POST /auth/logout endpoint needed — clears server session + vault, client clears cookie and reloads.

---

## SSE + Match Popup Rewire

| Option | Description | Selected |
|--------|-------------|----------|
| SSE-only with enriched data + reconnect | Render from SSE last_match events, show rating/duration/year/deep_link, add onerror reconnection | ✓ |
| SSE-only, minimal changes | Just remove HTTP match check, keep existing SSE handling | |
| SSE + keep HTTP as fallback | SSE primary, HTTP response as backup | |

**User's choice:** SSE-only with enriched data + reconnect
**Notes:** Remove lastSeenMatchTs dedup guard — SSE is single source. Match popup shows all enriched metadata from Phase 26. Auto-reconnect on SSE error (~3 second delay).

---

## Route Migration + Error Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Batch migration + banner | All routes at once, session expired banner with re-login button on 401 | ✓ |
| Batch migration + redirect | All routes at once, auto-redirect to login on 401 | |
| Batch migration + silent | All routes at once, silent reload on 401 | |

**User's choice:** Batch migration + banner
**Notes:** Swipe body trimmed to {movie_id, direction} only. Remove server-side /room/<code>/go-solo route. Session expired banner is non-blocking with re-login button.

---

## the agent's Discretion

- Session expired banner styling/positioning
- SSE reconnection delay (3-5 seconds)
- Loading state transitions between auth and main UI
- Loading spinner during delegate bootstrap

## Deferred Ideas

None — discussion stayed within phase scope.
