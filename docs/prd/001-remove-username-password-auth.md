# PRD: Remove residual username/password auth code paths

**Status:** ready for implementation
**Date:** 2026-05-10
**Driver:** finish the conversion to "server-side API token only" by deleting the dead/unreachable username/password code that survived the original migration.

---

## 1. Why

The conversion to API-token-only auth was substantially completed in earlier work, but three (now four) residual surfaces of the old username/password flow remain in the tree. None re-introduce the original credential-spraying vulnerability against the configured Jellyfin server, but they:

- expand the HTTP attack surface (a live `/auth/jellyfin-login` endpoint is reachable by any client and would proxy creds straight at Jellyfin),
- leave dead code paths and confusing client-side fallbacks (`prompt(...)` flows that no UI invokes),
- keep a server-to-Jellyfin password fallback that contradicts the stated "API tokens only" goal.

This PRD defines the cleanup to make the tree match the intended model: **the only way the server authenticates to Jellyfin is `JELLYFIN_API_KEY`; the only way a browser session is established is the server-delegate flow.**

## 2. Scope

### In scope
1. Delete `POST /auth/jellyfin-login` route and its tests.
2. Delete `JellyfinLibraryProvider.authenticate_user_session` (`jellyfin_library.py:581–610`) and its tests.
3. Collapse `login()` in `static/app.js` to call `bootstrapJellyfinDelegate()` directly; remove `prompt(...)` fallbacks and the `/auth/jellyfin-login` fetch.
4. Make `JELLYFIN_API_KEY` strictly required at boot. Delete the `elif username and password:` branch in `_login_from_env` (`jellyfin_library.py:90–122`) and tighten env-var validation in `config.py:37–42`.
5. Delete the `JELLYFIN_USERNAME` "preferred user" disambiguation logic at **both** `jellyfin_library.py:204` (`_user_id`) and `jellyfin_library.py:640` (`resolve_user_id_from_token`). Both fall back unconditionally to `users[0]`.
6. Delete `GET /auth/provider` route and remove all client-side calls/checks for it (collapsing `bootstrapJellyfinDelegate` to skip the provider-shape gate).
7. Update `README.md` env-var table and example `.env`.
8. Test cleanup (see §5).
9. Add a single new automated end-to-end test for the delegate login → authenticated request → logout flow.

### Explicitly out of scope (but flagged for follow-up tickets)
- `ARCHITECTURE.md` §4.3, §4.5, §7, §8 will be factually wrong after this lands. Follow-up doc-refresh ticket required.
- `docker-compose.yml:12–13` retains commented USERNAME/PASSWORD examples. Trivial follow-up.
- `unraid_template/jelly-swipe.html` and `scripts/lint-unraid-template.py:15–16` reference USERNAME/PASSWORD. User-facing for Unraid installers; follow-up ticket.
- `user_auth_header`, `resolve_user_id_from_token`, and `add_to_user_favorites` are **not deleted**. They are used by the watchlist-add route (`routers/media.py:165`) and remain load-bearing.
- The watchlist-add semantic question (it currently writes favorites under the server delegate user, not the swiping user) is recorded as a "Follow-ups" smell — not addressed here.

## 3. Detailed changes

### 3.1 `jellyswipe/routers/auth.py`
- Delete handler `jellyfin_login` (lines 75–93).
- Delete handler `auth_provider` (lines 55–59).

### 3.2 `jellyswipe/jellyfin_library.py`
- Delete `authenticate_user_session` (581–610).
- In `_login_from_env` (83–124): collapse to `if api_key: self._access_token = api_key; else: raise RuntimeError("Jellyfin authentication failed (JELLYFIN_API_KEY required)")`. Drop the `elif username and password:` branch entirely. Remove unused `username`/`password` reads.
- In `_user_id` (around 192–216): drop the `preferred = os.getenv("JELLYFIN_USERNAME")` block; the `/Users` fallback simply returns `users[0]["Id"]` if present.
- In `resolve_user_id_from_token` (around 625–650): drop the `preferred = os.getenv("JELLYFIN_USERNAME")` block; the 400-fallback returns `users[0]["Id"]` if present.
- Keep `user_auth_header` (575–579), `resolve_user_id_from_token` (612–659), `add_to_user_favorites` (661–672).

### 3.3 `jellyswipe/config.py`
- Replace lines 37–42 with a strict check: if `JELLYFIN_API_KEY` is missing, append `"JELLYFIN_API_KEY"` to `missing`.
- The eventual `RuntimeError` message must include a migration hint. Format:
  ```
  Missing env vars: ['JELLYFIN_API_KEY']. JELLYFIN_API_KEY is required;
  username/password authentication has been removed. Create an API key
  in your Jellyfin Dashboard → Advanced → API Keys.
  ```
  Implementation: when `JELLYFIN_API_KEY` is in `missing` AND the deprecated `JELLYFIN_USERNAME`/`JELLYFIN_PASSWORD` env vars are set, append the migration sentence; otherwise show the plain message. No separate deprecation warn channel.

### 3.4 `jellyswipe/static/app.js`
- Remove the `provData.jellyfin_browser_auth !== "delegate"` early return inside `bootstrapJellyfinDelegate` (lines 25–27) and the `await fetch("/auth/provider", ...)` call that precedes it.
- Replace `login()` (lines 49–75) with a one-liner: `async function login() { await bootstrapJellyfinDelegate(); }` — or inline the body and delete `login()` entirely if no caller remains. Delete both `prompt(...)` calls and the `fetch("/auth/jellyfin-login", ...)` block.

### 3.5 `README.md`
- Drop `JELLYFIN_USERNAME` and `JELLYFIN_PASSWORD` rows from the env-var table (lines 49–50).
- Update example `.env` block (lines 84–85) to remove those two vars. Mark `JELLYFIN_API_KEY` as **required**.

## 4. Boot-time behavior

| Env state | Outcome |
| --- | --- |
| `JELLYFIN_API_KEY` set | Boot succeeds. `JELLYFIN_USERNAME`/`JELLYFIN_PASSWORD`, if also set, are ignored silently. |
| `JELLYFIN_API_KEY` unset, `JELLYFIN_USERNAME`+`JELLYFIN_PASSWORD` set | Boot fails fast with migration-aware error. |
| `JELLYFIN_API_KEY` unset, no other Jellyfin auth vars | Boot fails fast with plain "Missing env vars" error. |

## 5. Test cleanup

### Delete entirely
- `tests/test_routes_auth.py`: all `/auth/jellyfin-login` cases (lines 87–167) and any `/auth/provider` cases.
- `tests/test_routes_auth.py` module docstring: drop the "and `/auth/jellyfin-login`" mention.
- `tests/test_jellyfin_library.py`: `test_authenticate_user_session_*` (1047, 1063) and any test whose body sets `JELLYFIN_USERNAME`/`JELLYFIN_PASSWORD` to exercise the password branch (43–44, 80–81, 105–106, 134–135). Tests that exercise the `JELLYFIN_USERNAME`-as-disambiguation behaviour (around 285, 325, 335) are also dead — delete.
- `tests/test_routes_xss.py:532`: drop `/auth/jellyfin-login` from the route list.
- `tests/test_error_handling.py:333`: drop the `/auth/jellyfin-login` empty-body case.
- `tests/test_route_authorization.py`: drop entries at 116, 131, 151, 164.
- `tests/conftest.py`: remove `authenticate_user_session` from the fake provider (line 307).

### Add
- One new test asserting `POST /auth/jellyfin-login` returns 404 (regression fence).
- One new test asserting `GET /auth/provider` returns 404.
- One new end-to-end test in `tests/test_routes_auth.py`:
  ```
  POST /auth/jellyfin-use-server-identity → 200, body has userId
  GET  /me                                 → 200, body has userId
  POST /auth/logout                        → 200, "logged_out"
  GET  /me                                 → 401
  ```

## 6. Acceptance criteria

1. `POST /auth/jellyfin-login` returns 404.
2. `GET /auth/provider` returns 404.
3. `grep -rn "authenticate_user_session\|/auth/jellyfin-login\|provider_token\|plex_token" jellyswipe/` returns no hits.
4. `grep -rn "JELLYFIN_USERNAME\|JELLYFIN_PASSWORD" jellyswipe/` returns no hits.
5. `static/app.js` `login()` contains no `prompt(...)` calls and no reference to `/auth/jellyfin-login` or `/auth/provider`.
6. Booting with only `JELLYFIN_API_KEY` set succeeds. Booting with only `JELLYFIN_USERNAME`+`JELLYFIN_PASSWORD` set fails fast with the migration-aware error message.
7. The new E2E delegate-login → /me → logout test passes in CI.
8. The new 404 guard tests pass in CI.
9. All previously-passing auth/session tests still pass.

## 7. Risks

- **Multi-user Jellyfin servers where the API key has access to multiple users and the desired delegate user is not `users[0]` will silently resolve to the wrong identity.** This is a deliberate trade-off (chosen during PRD review over introducing a new `JELLYFIN_USER_ID` env var). Mitigation: README note recommending the API key be created by the desired delegate user account.
- **External tools probing `/auth/provider` will start receiving 404s.** Known consumer is the SPA shell only.
- **Any operator upgrading from the password-auth deployment shape needs to read the boot error.** The migration-aware error string is the only signal — no separate warning, no email, no changelog enforcement.

## 8. Follow-ups (not part of this PRD)

- Refresh `ARCHITECTURE.md` §4.3, §4.5, §7, §8 to match the post-cleanup reality.
- Strip USERNAME/PASSWORD examples from `docker-compose.yml`, `unraid_template/jelly-swipe.html`, and `scripts/lint-unraid-template.py` allowlist.
- Investigate whether `add_to_user_favorites` writing favorites under the server delegate user (rather than the swiping user) is intentional in the new model.
