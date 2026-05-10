# Jelly-Swipe — Domain Context

> Living glossary for the language Jelly-Swipe uses internally. Update inline as decisions sharpen terminology. For runtime structure see [`ARCHITECTURE.md`](./ARCHITECTURE.md); for product cleanup decisions see [`.planning/`](./.planning/).

---

## Authentication & Identity

### Delegate identity flow
The only supported user-login flow. The browser hits `POST /auth/jellyfin-use-server-identity`, the server authenticates itself to Jellyfin once on the user's behalf, and the resulting token is stored in the server-side vault and bound to the browser's session cookie. There is no per-user Jellyfin login from the browser.

### Server delegate token
The single Jellyfin access token that the server uses to talk to Jellyfin. Today it is set directly from the operator-provided `JELLYFIN_API_KEY` (see `JellyfinLibraryProvider._login_from_env`). This token represents the *operator's* Jellyfin user; every authenticated browser session in Jelly-Swipe acts as that user against Jellyfin.

### Vault
Server-side store binding a session cookie to a Jellyfin token (and Jellyfin user id). Populated by `create_session(token, uid, ...)` (`jellyswipe/auth.py`). In the current model the vault always contains the server delegate token — there are no per-browser tokens.

### `user.jf_token`
The token retrieved from the vault for an authenticated request. **Today this is always the server delegate token, not a per-user token.** The name is a remnant of the old per-user-token model; future readers should not assume it identifies the swiping user.

### API key (Jellyfin)
A long-lived token created in Jellyfin's Dashboard → Advanced → API Keys. The only supported way for the server to authenticate to Jellyfin. `JELLYFIN_API_KEY` is required at boot; username/password env-var auth has been removed (see `.planning/quick/remove-username-password-auth.md`).

### Delegate user
The Jellyfin user account that the server's API key resolves to. When `/Users/Me` returns 400 (some Jellyfin builds do this for API-key auth), the server falls back to `GET /Users` and picks `users[0]`. **Implication for operators:** create the API key as the user you want Jelly-Swipe to act as, ideally on a single-user Jellyfin server.

---

## Sessions & Rooms

### Room
A 4-digit pairing code that scopes two browsers (host + guest) to the same swiping deck. Stored in the `rooms` SQLite table.

### Solo mode
A room with only one participant. The guest-readiness gate is auto-satisfied; matches are recorded against the host's resolved user id only.

### Match
A movie that both participants right-swiped (or any movie a solo-mode user right-swiped). Two rows are inserted on a paired match — one per `user_id`.

### Swipe
A `(room_code, movie_id, user_id, direction)` record. `swipes.user_id` is a session-scoped string (`host_<hex>` / `guest_<hex>`), **not** a Jellyfin GUID. Do not join with `matches.user_id`, which holds Jellyfin GUIDs.

---

## Out of scope here
This file describes domain language only. Implementation details (file paths, function names, schema columns) belong in `ARCHITECTURE.md`. Decisions and the reasoning behind them belong in PRDs under `.planning/` and (when appropriate) ADRs under `docs/adr/`.
