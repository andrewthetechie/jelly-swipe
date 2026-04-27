# Phase 24: Frontend Plex Cleanup - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-26
**Phase:** 24-frontend-plex-cleanup
**Areas discussed:** CSS class naming, "Open In" button replacement, Login function & button, Provider abstraction

---

## CSS Class Naming

| Option | Description | Selected |
|--------|-------------|----------|
| `.accent-text` | Describes the role (accent), not the color. Works even if the color changes later. | ✓ |
| `.amber-text` | Names the color directly. Clear but ties the class name to this specific hue. | |
| `.highlight` | Generic. Could conflict if other highlight styles are added later. | |

**User's choice:** `.accent-text`
**Notes:** User chose role-based naming over color-based naming.

### `.plex-open-btn` naming

| Option | Description | Selected |
|--------|-------------|----------|
| `.cta-btn` | Describes the role (call-to-action). Standard pattern. | ✓ |
| `.open-btn` | Describes the action. Simple but could be confused with other open/expand buttons. | |
| `.match-action-btn` | Ties it to match cards. More specific but less reusable. | |

**User's choice:** `.cta-btn`
**Notes:** Role-based naming consistent with `.accent-text` decision.

---

## "Open In" Button Replacement

| Option | Description | Selected |
|--------|-------------|----------|
| Build Jellyfin link | Add new backend endpoint, construct Jellyfin deep link in JS. Keeps the feature alive. | ✓ |
| Remove the button | Delete the "Open In" button entirely from match cards. Simplest, but loses functionality. | |
| Replace with thumbnail click | Make the mini-poster image itself a link to the movie in Jellyfin. | |

**User's choice:** Build Jellyfin link

### How to get Jellyfin server URL

| Option | Description | Selected |
|--------|-------------|----------|
| New backend endpoint | `GET /jellyfin/server-info` returns `{ baseUrl, webUrl }`. Frontend fetches once and caches. | ✓ |
| Template variable injection | Embed URL in HTML at render time. No extra fetch, but URL visible in page source. | |
| Extend existing `server_info()` | Reuse provider method, extend to return web URL. | |

**User's choice:** New backend endpoint

---

## Login Function & Button

### Function name

| Option | Description | Selected |
|--------|-------------|----------|
| `loginWithJellyfin()` | Direct and clear. Matches the product. | ✓ |
| `login()` | Provider-agnostic. Could work if auth methods change later. | |
| `handleLogin()` | Describes the pattern. Generic but less descriptive. | |

**User's choice:** `loginWithJellyfin()`

### Button text

| Option | Description | Selected |
|--------|-------------|----------|
| Login | Shorter. Assumes user knows they're using Jellyfin. | ✓ |
| Login with Jellyfin | Clear and specific. Matches the function name. | |
| Connect | Action-oriented. Works for both delegate and manual login. | |

**User's choice:** "Login"
**Notes:** Delegate mode already shows "Continue" per existing line 1048.

---

## Provider Abstraction

| Option | Description | Selected |
|--------|-------------|----------|
| Remove variable, hardcode Jellyfin | Remove `mediaProvider` entirely. Inline Jellyfin behavior. Simplest code. | ✓ |
| Keep variable, remove Plex branches | `mediaProvider` stays but checks become no-ops. Room for future backends. | |
| Keep as documentation | Variable and checks preserved to show where backend-specific logic lives. | |

**User's choice:** Remove variable, hardcode Jellyfin
**Notes:** Clean simplification for a single-backend app. All `mediaProvider === 'plex'` branches deleted, all `mediaProvider === 'jellyfin'` guards removed with Jellyfin code inlined.

---

## Agent's Discretion

- Exact Jellyfin deep link URL format (hash vs path routing)
- Exact button label for "Open In" in match cards
- Whether to remove unused `{{ media_provider }}` Jinja2 template tag
- Whether to clear stale `plex_token`/`plex_id` localStorage values on page load

## Deferred Ideas

- Rename/remove `server_info()` method on provider base class — evaluate post-Phase 24
- Rename `machineIdentifier` field to Jellyfin-idiomatic name — future cleanup
