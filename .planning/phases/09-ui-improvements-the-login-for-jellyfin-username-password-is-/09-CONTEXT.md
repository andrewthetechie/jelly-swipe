# Phase 9: UI improvements (Jellyfin login + posters) — Context

**Gathered:** 2026-04-24  
**Status:** Ready for planning  
**Source:** Roadmap Phase 9 + codebase inspection (`app.py`, `templates/index.html`, `media_provider/jellyfin_library.py`)

<domain>

## Phase boundary

Deliver two user-visible outcomes when `MEDIA_PROVIDER=jellyfin`:

1. **Server-side Jellyfin identity in the browser** — Operators already configure `JELLYFIN_API_KEY` and/or `JELLYFIN_USERNAME` + `JELLYFIN_PASSWORD` in the environment; the Flask app authenticates the provider at startup. The web UI must **not** ask end users for Jellyfin username/password via `prompt()` when the server already holds usable credentials. Instead, the browser binds to the **same** Jellyfin identity the server uses (single shared “household” user for this deployment).

2. **Poster framing** — Main swipe card and related poster surfaces use `object-fit: cover`, which crops wide theatrical one-sheets. Prefer showing the **full** poster (letterboxing acceptable) on primary deck surfaces unless CONTEXT defers.

Out of scope for this phase: multi-tenant Jellyfin with distinct per-browser users without env credentials; redesign of non-poster layout; Plex login flow changes beyond any shared copy/CSS.

</domain>

<decisions>

## Implementation decisions

### Jellyfin / auth

- **D-01 (locked):** “Server credentials present” means the same condition as today’s startup: `JELLYFIN_API_KEY` **or** (`JELLYFIN_USERNAME` and `JELLYFIN_PASSWORD`) in the environment when `MEDIA_PROVIDER=jellyfin`. In that configuration, the product treats Jellyfin as **operator-configured**; the browser must not collect username/password.
- **D-02 (locked):** Use a **Flask session** flag (e.g. `jf_delegate_server_identity`) set by an explicit `POST` route (e.g. `/auth/jellyfin-use-server-identity`) called once on load when the server advertises delegate mode. `_jellyfin_user_token_from_request()` and `_provider_user_id_from_request()` in `app.py` must honor this flag by using the provider’s already-authenticated server token and resolved primary user id — **never** echo the API key or env password in JSON responses.
- **D-03 (locked):** Extend `GET /auth/provider` JSON with a stable field such as `jellyfin_browser_auth: "delegate" | "interactive"`. Value `delegate` when server env satisfies D-01 (always true for running Jellyfin deployments today). Value `interactive` reserved for a hypothetical future where browser-only auth exists without env user secrets; until then `delegate` is the default for jellyfin.
- **D-04:** When entering delegate mode, clear or ignore stale `localStorage` provider keys if they would conflict (document exact keys in the plan: `provider_token`, `provider_user_id`, legacy `plex_token` / `plex_id`).

### Posters / CSS

- **D-05 (locked):** For `.movie-card img` and `.mini-front img` (and match popup poster if it shares the same issue), switch from `object-fit: cover` to `object-fit: contain` (keep `width`/`height` 100% within existing aspect-ratio boxes) so full artwork is visible; allow pillarboxing/letterboxing with a neutral background (`#000` or existing card backing).
- **D-06:** Apply the same poster rules in **`templates/index.html` and `data/index.html`** per project convention (parallel PWA copy).

### Claude’s discretion

- Exact route names and session key string literals.  
- Whether delegate bootstrap runs on `DOMContentLoaded` or after `/auth/provider` fetch — either is fine if acceptance criteria hold.  
- Optional one-line status string in UI (“Using server Jellyfin account”) — nice-to-have, not required for phase closure.

</decisions>

<canonical_refs>

## Canonical references

**Downstream agents MUST read these before implementing.**

### Project rules

- `.cursor/rules/gsd-project.md` — dual `templates/` + `data/` HTML copies.

### Prior Jellyfin auth / parity

- `.planning/phases/03-jellyfin-authentication-http-client/03-CONTEXT.md` — JAUTH decisions.  
- `.planning/phases/03-jellyfin-authentication-http-client/03-VERIFICATION.md` — route and error-shape expectations.  
- `media_provider/jellyfin_library.py` — env login, `authenticate_user_session`, `resolve_user_id_from_token`.

### Operator notes

- `.planning/notes/2026-04-24-aspect-ratio-displayed-posters.md` — poster crop pain point.

</canonical_refs>

<specifics>

## Specifics

- Current Jellyfin login UX: `loginWithPlex()` in `templates/index.html` calls `prompt("Jellyfin username:")` and `prompt("Jellyfin password:")` then `POST /auth/jellyfin-login`.  
- `POST /auth/jellyfin-login` in `app.py` returns `authToken` + `userId` — should remain for **interactive** fallback if ever needed, but delegate path must bypass prompts.  
- Swipe path uses `_provider_user_id_from_request()`; watchlist uses `_jellyfin_user_token_from_request()` — both must work without client-supplied Jellyfin token when session delegate is active.

</specifics>

<deferred>

## Deferred ideas

- Per-guest Jellyfin accounts without operator env secrets.  
- OAuth / SSO for Jellyfin.  
- Replacing `prompt()` with a styled modal while still collecting creds (explicitly unwanted for delegate mode).

</deferred>

---

*Phase: 09-ui-improvements-the-login-for-jellyfin-username-password-is-*
