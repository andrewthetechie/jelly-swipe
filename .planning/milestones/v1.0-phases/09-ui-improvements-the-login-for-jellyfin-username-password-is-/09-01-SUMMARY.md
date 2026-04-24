---
phase: 09-ui-improvements-the-login-for-jellyfin-username-password-is-
plan: "01"
subsystem: jellyfin-auth-ui
tags: [jellyfin, flask, session, spa]

requires: []
provides:
  - Server-delegated Jellyfin browser identity without exposing API tokens in JSON
affects: [jellyfin-login-ux, watchlist, swipe]

tech-stack:
  added: []
  patterns: [Flask session flag + provider-only token resolution]

key-files:
  created: []
  modified:
    - app.py
    - media_provider/jellyfin_library.py
    - templates/index.html
    - data/index.html

key-decisions:
  - "Delegate path returns only userId from POST /auth/jellyfin-use-server-identity; session jf_delegate_server_identity gates _jellyfin_user_token_from_request / _provider_user_id_from_request"
  - "PWA data/index.html probes /auth/provider at load to set mediaProvider and mirrors templates Jellyfin flows"

patterns-established:
  - "JellyfinLibraryProvider.server_access_token_for_delegate / server_primary_user_id_for_delegate for in-process use only"

requirements-completed: []

duration: 45min
completed: 2026-04-24
---

# Phase 09 plan 01 summary

**Jellyfin delegate login:** env-authenticated server supplies MediaBrowser token and primary user id via Flask session after `POST /auth/jellyfin-use-server-identity`. `GET /auth/provider` exposes `jellyfin_browser_auth: delegate` for the SPA. No API key or access token fields are returned in JSON on the delegate route.

**Front-end:** `bootstrapJellyfinDelegate()` performs provider GET → delegate POST, clears stale `provider_token` / `plex_token`, stores `userId` in `provider_user_id` / `plex_id`, and skips `prompt("Jellyfin username` (fallback prompts use distinct copy if delegate is unavailable).

## Verification

- Plan acceptance greps for new symbols in `app.py`, `jellyfin_library.py`, both HTML files; `jf_delegate_server_identity` absent from shipped HTML; `python3 -m py_compile` on modified Python modules passed.
- Full `Flask.test_client` sequence against a live Jellyfin (Phase 3 style `env -i` partial exports) remains operator-run: assert `GET /auth/provider` includes `jellyfin_browser_auth`, `POST /auth/jellyfin-use-server-identity` returns `userId` only and response body does not echo `JELLYFIN_API_KEY` / `Token=` material.

## Self-Check: PASSED
