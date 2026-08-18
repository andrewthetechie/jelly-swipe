# Jelly-Swipe — Domain Context

> Living glossary for the language Jelly-Swipe uses internally. Update inline as decisions sharpen terminology. For runtime structure see [`ARCHITECTURE.md`](./ARCHITECTURE.md); for product cleanup decisions see [`.planning/`](./.planning/).

---

## Authentication & Identity

### Delegate identity flow

The only supported user-login flow. The browser hits `POST /auth/jellyfin-use-server-identity`, the server authenticates itself to Jellyfin once on the user's behalf, and the resulting token is stored in the server-side vault and bound to the browser's session cookie. There is no per-user Jellyfin login from the browser.

### Server delegate token

The single Jellyfin access token that the server uses to talk to Jellyfin. It is set directly from the operator-provided `JELLYFIN_API_KEY` (see `JellyfinVault._login_from_env` in `jellyswipe/jellyfin/vault.py`). This token represents the _operator's_ Jellyfin user; every authenticated browser session in Jelly-Swipe acts as that user against Jellyfin.

### Vault

Server-side store binding a session cookie to a Jellyfin token (and Jellyfin user id). Populated during delegate login in the `POST /auth/jellyfin-use-server-identity` route handler. In the current model the vault always contains the server delegate token — there are no per-browser tokens.

### `user.jf_token`

The token retrieved from the vault for an authenticated request. **This is always the server delegate token, not a per-user token.** The name is a remnant of the old per-user-token model; it does not identify the swiping user.

Since issue #299, no code interprets the token as a per-user token: the watchlist writer (`JellyfinWatchlistWriter.add_to_favorites`) uses the vault's delegate token and delegate user id directly, and the swipe path makes no Jellyfin calls at all (match metadata comes from the room deck).

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

### Room session

A client (browser)'s participation in a Room, from join/create until quit or `session_closed`. Frontend term for the slice of state that lifetime owns: the deck, swipe history, match state, and server-mirrored room settings (`genre`, `hide_watched`, readiness). Distinct from `currentRoomCode`, which is client-side membership/routing state written by the room-creation flow, and from the SSE "session" (`session_bootstrap` / `session_ready` / `session_closed` events), which is the server's broadcast vocabulary for the same lifetime.

### Deck

A room's ordered card list plus each participant's swipe cursor. A single `Deck` domain object (`jellyswipe/domain/deck.py`) is the one owner of deck JSON parsing, cursor advance, page slicing, card lookup, and serialization for the `movie_data` / `deck_position` room columns. Every consumer — the repository seam (`RoomRepository`), `deck_pipeline` (build/persist), `room_lifecycle` (page/genre/watched), and `session_match_mutation` (swipe) — shares this one contract.

### Swipe cursor

A participant's integer position into the Deck. Advanced by one on each accepted swipe; reset to 0 on join and on any deck rebuild (genre / watched-filter change). Persisted per user in the room's `deck_position` column. Malformed/empty stored cursors degrade to 0 rather than erroring.

---

## Transaction & Notify

### Request boundary

The single place where a request's transaction is _completed_. On a clean route
return it commits; on an error or an explicit abort it rolls back; and it wakes
subscribers only _after_ a successful commit. Routes never commit themselves —
they write through the unit of work and let the boundary finish. This is what
makes the commit-before-notify ordering and the "no silently-lost writes"
guarantee structural, not advisory.

### Wake intent

A route or service declaring that the subscribers of a room must be woken once
this request's transaction has committed. The requester merely records the room
code (`wake_on_commit`); the request boundary performs the actual wake after the
commit. This keeps the wake decision at the code that knows the room while
keeping the act of notifying inside the boundary.

---

## Out of scope here

This file describes domain language only. Implementation details (file paths, function names, schema columns) belong in `ARCHITECTURE.md`. Decisions and the reasoning behind them belong in PRDs under `.planning/` and (when appropriate) ADRs under `docs/adr/`.
