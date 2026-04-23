# Phase 3 — Research notes (concise)

**Date:** 2026-04-23  
**Scope:** Jellyfin server authentication for unattended + interactive login paths used by Kino Swipe.

## Findings (implementation-aligned)

1. **API key path** — Jellyfin accepts the access token in the **`Authorization: MediaBrowser … Token="<token>"`** header shape (see Jellyfin server OpenAPI / client conventions). Treating `JELLYFIN_API_KEY` as the bearer token value is consistent with common operator setups.
2. **Username/password path** — Stable REST entrypoint: **`POST /Users/AuthenticateByName`** with JSON body `Username` / `Pw` (server returns JSON containing **`AccessToken`**). Initial request uses `Token=""` in the MediaBrowser client string.
3. **Session proof** — After login, a minimal **`GET /Items?Limit=1`** (or equivalent) validates the token before the app serves traffic; **401** implies invalid/expired credentials → clear session and allow one bounded re-auth (mirror Plex `reset()` story).
4. **Security** — Never log full `Authorization` headers, response bodies from auth endpoints, or raw tokens in `jsonify` errors (JAUTH-03).

## References (consult during execution)

- Jellyfin **OpenAPI** / server REST docs for the major version you run in production (10.8+ per `PROJECT.md`).
- In-repo contracts: `03-CONTEXT.md` (D-01–D-12), `01-CONTEXT.md` (env), `02-CONTEXT.md` (provider boundary).
