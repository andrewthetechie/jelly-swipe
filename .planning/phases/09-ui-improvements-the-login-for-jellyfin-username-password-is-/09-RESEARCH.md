# Phase 9 — Technical research

**Phase:** 09 — UI improvements (Jellyfin login + posters)  
**Question:** What do we need to know to plan server-delegated Jellyfin browser auth and poster framing?

## Stack and constraints

- **Flask** serves `templates/index.html` with embedded CSS/JS; duplicate asset `data/index.html` must stay aligned (`.cursor/rules/gsd-project.md`).
- **Jellyfin** provider (`JellyfinLibraryProvider`) authenticates once from env: API key **or** username/password (`_login_from_env`). After `ensure_authenticated()`, `_access_token` and `_user_id()` back library and user-scoped API calls.
- Browser today stores `provider_token` / `provider_user_id` from `POST /auth/jellyfin-login` and sends `Authorization: MediaBrowser ... Token="<user token>"` on same-origin requests via `providerIdentityHeaders()`.

## Recommended approach (server delegate)

1. **Advertise mode** — Extend `GET /auth/provider` with `jellyfin_browser_auth: "delegate"` whenever `MEDIA_PROVIDER=jellyfin` (env creds are already mandatory for app boot).
2. **Session bind** — New `POST /auth/jellyfin-use-server-identity` (no secrets in body): sets `session["jf_delegate_server_identity"] = True` (or equivalent). CSRF: same-origin POST from existing page only; optional future `SameSite` tightening out of scope.
3. **Request helpers** — In `app.py`, when session flag is set:
   - `_jellyfin_user_token_from_request()` returns the provider’s server access token (new narrow public accessor on `JellyfinLibraryProvider`, e.g. `server_access_token_for_delegate()` calling `ensure_authenticated()`).
   - `_provider_user_id_from_request()` returns the provider’s resolved user id (new accessor e.g. `server_primary_user_id()` wrapping `_user_id()` logic) when delegate session is active **before** trying headers/local resolution.
4. **Frontend** — On load, if `mediaProvider === "jellyfin"` and `jellyfin_browser_auth === "delegate"`, call `POST /auth/jellyfin-use-server-identity`, then skip `prompt()` flow. Optionally skip populating `localStorage` tokens entirely when delegate succeeds; ensure `providerIdentityHeaders()` still works — either continue setting headers from values returned by a minimal JSON bootstrap (`userId` only + rely on session for server-side routes) **or** return opaque app token; simplest v1: after POST, fetch `userId` from JSON and store **only** `provider_user_id` in `localStorage` while relying on **session** for token resolution server-side so `Authorization` header can be omitted for same-origin API if all routes use `_jellyfin_user_token_from_request`. **Correction:** watchlist route requires token from request today — so either (a) keep sending server token to client (bad for API key) or (b) ensure all Jellyfin-proxied routes read token from session when delegate flag set. **(b) is required** for API key safety.

## Poster framing

- Root cause: `object-fit: cover` on `.movie-card img` and `.mini-front img` inside fixed aspect-ratio containers crops wide posters.
- Fix: `object-fit: contain` + dark background on the image container so letterboxing is visually acceptable; verify match popup `.match-poster-preview` if it crops similarly.

## Risks

| Risk | Mitigation |
|------|------------|
| API key exfiltration if returned to browser | Never return `_access_token` in JSON; only session + server-side resolution |
| Session fixation | Use Flask signed session cookie; delegate route only upgrades session for authenticated server config |
| `data/index.html` drift | Same edits as `templates/index.html` in one phase |

## Alternatives considered

- **Return server token to JS** — Rejected for API key deployments.  
- **Prompt-only UX polish** — Does not meet roadmap “server side creds” intent.

## Validation Architecture

Phase 9 validation should prove:

1. **Delegate path** — With `MEDIA_PROVIDER=jellyfin` and env creds, `GET /auth/provider` includes `jellyfin_browser_auth` and `POST /auth/jellyfin-use-server-identity` returns 200; subsequent `POST /room/swipe` succeeds without prior `localStorage` provider_token (or with cleared storage) — document exact `test_client` sequence in `09-VALIDATION.md`.
2. **No secret leakage** — `grep` JSON responses in tests do not include substrings of `JELLYFIN_API_KEY`.
3. **Poster CSS** — Automated or manual checklist: main deck poster shows full image for a known wide one-sheet fixture (manual acceptable with screenshot note in SUMMARY).
4. **Dual HTML** — `grep` for `object-fit: contain` counts match between `templates/index.html` and `data/index.html` for the targeted selectors.

---

## RESEARCH COMPLETE
