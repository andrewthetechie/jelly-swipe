# ADR 0001 — Remove username/password authentication

**Status:** Accepted
**Date:** 2026-05-10
**Deciders:** project owner
**Supersedes:** the implicit "either API key or username+password" auth model present in earlier versions of `JellyfinLibraryProvider._login_from_env` and the live `POST /auth/jellyfin-login` route.

---

## Context

Jelly-Swipe originally supported two ways for the server to authenticate to Jellyfin:

1. `JELLYFIN_API_KEY` — an operator-provisioned token.
2. `JELLYFIN_USERNAME` + `JELLYFIN_PASSWORD` — env-var credentials proxied to `/Users/AuthenticateByName` at boot.

It also supported two ways for a browser session to be established:

1. **Server-delegate flow** — `POST /auth/jellyfin-use-server-identity` binds the browser session to the server's own Jellyfin token.
2. **Per-user login flow** — `POST /auth/jellyfin-login` proxied user-supplied creds to Jellyfin and stored a per-user token in the browser's `localStorage`.

A previous round of work moved the system toward "API tokens only" but did not finish: the `/auth/jellyfin-login` route was still live (and reachable to any HTTP client even though no UI invokes it), the provider still had `authenticate_user_session`, the JS shell still had a `prompt(...)` fallback, and the env-var password branch still worked. Additionally, `JELLYFIN_USERNAME` had a *third* role unrelated to credentials: a "preferred user" disambiguation hint at `jellyfin_library.py:204` and `:640`, used when Jellyfin's `/Users/Me` returns 400 under API-key auth and the server falls back to `GET /Users`.

The remaining surfaces:

- expanded the HTTP attack surface (a live unauthenticated endpoint that proxies arbitrary credentials at the configured Jellyfin),
- left dead JS code paths (`prompt("Jellyfin account name")`),
- entangled three semantically-different uses of `JELLYFIN_USERNAME` (credential, "preferred user," delegate identity hint) under one variable name.

## Decision

1. **`JELLYFIN_API_KEY` is the only supported way for the server to authenticate to Jellyfin.** The username/password fallback in `_login_from_env` is removed. The boot-time validator in `config.py` requires `JELLYFIN_API_KEY` and produces a migration-aware error for operators upgrading from the old shape.
2. **The server-delegate flow is the only supported way for a browser session to be established.** `POST /auth/jellyfin-login`, `JellyfinLibraryProvider.authenticate_user_session`, and the JS `prompt(...)` fallback are all deleted.
3. **`GET /auth/provider` is also deleted.** It returned a hard-coded constant and the only consumer (the SPA shell) no longer needs to read it now that there is one supported flow.
4. **The `JELLYFIN_USERNAME` "preferred user" disambiguation hint is dropped.** When `/Users/Me` returns 400, the `/Users` fallback unconditionally selects `users[0]`. We do **not** introduce a replacement env var (e.g. `JELLYFIN_USER_ID`).
5. **Per-user-token-shaped helper methods (`user_auth_header`, `resolve_user_id_from_token`, `add_to_user_favorites`) are kept.** They are still used by `routers/media.py:165` for the watchlist-add route, although the `user_token` they receive is now always the server delegate token (see `CONTEXT.md`). Cleaning up that semantic remnant is a separate ticket.

## Alternatives considered

### A. Leave `JELLYFIN_USERNAME` + `JELLYFIN_PASSWORD` as a documented fallback
Keep the elif branch in `_login_from_env`. Document it as "the server's own credentials, not user-facing login." Smaller diff.

**Rejected because:** it leaves password-handling code in the tree under the same env-var names that previously meant per-user login. Future readers and operators conflate the two — a footgun without a corresponding benefit, since operators capable of setting USERNAME/PASSWORD can equally set an API key.

### B. Replace `JELLYFIN_USERNAME` with `JELLYFIN_USER_ID` (a Jellyfin GUID)
Preserve the disambiguation function but under a name that doesn't carry password-auth baggage.

**Rejected because:** it adds a new env var that 99% of operators (single-user Jellyfin or admin-owned API key) will never set, and the failure mode of *not* setting it (silently picking `users[0]`) is identical to dropping the feature outright. The cost (new var to document, support, validate) outweighs the benefit (one extra config knob for multi-user-server operators who could equally provision a dedicated user and create the API key under that account).

### C. Stage item 4 (env-var password fallback removal) into a follow-up ticket
Land items 1–3 (route + dead method + JS prompt) first; move the breaking config change into its own PR for migration messaging.

**Rejected because:** the four items are conceptually one cleanup ("password auth, gone"), and splitting them produces an awkward intermediate state where the public route is gone but the env-var still works. A single PR with a clear migration error is easier to communicate than two PRs with overlapping scopes.

## Consequences

### Positive
- **Smaller attack surface.** No live endpoint will proxy unauthenticated credentials to Jellyfin. No JS path that prompts a user for a Jellyfin password.
- **Simpler boot model.** One required env var (`JELLYFIN_API_KEY`) for Jellyfin auth; one supported browser-login flow.
- **Less semantic entanglement.** `JELLYFIN_USERNAME` no longer carries three different meanings.
- **Less dead code.** The `/auth/provider` constant-shape endpoint and the `bootstrapJellyfinDelegate` provider-shape gate are gone.

### Negative
- **Breaking config change for upgraders.** Any deployment still running on `JELLYFIN_USERNAME`+`JELLYFIN_PASSWORD` will fail to boot until the operator creates an API key. Mitigated by the migration-aware error message; not mitigated by a deprecation period.
- **Multi-user Jellyfin foot-gun.** When `/Users/Me` returns 400 and the API key has access to multiple users, the server now silently picks `users[0]` as the delegate. If that is not the intended user, every match and watchlist-add will be recorded against the wrong Jellyfin account. Mitigation: README guidance to create the API key under the desired delegate user; ideally on a single-user Jellyfin server.
- **External tooling that probed `/auth/provider`** will now receive 404. The known consumer is the SPA only, so the impact is expected to be zero in practice.
- **`add_to_user_favorites` retains its `user_token` parameter shape** even though the token is now always the delegate token. This is a semantic smell (the watchlist write is recorded under the operator's user, not the swiper's) but is preserved by this ADR; reconsidering it is the subject of a future decision.

## Implementation reference

See `.planning/quick/remove-username-password-auth.md` for the implementation plan (file-by-file changes, test cleanup, acceptance criteria). See `CONTEXT.md` for the resulting auth glossary.
