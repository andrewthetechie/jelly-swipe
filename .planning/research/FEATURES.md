# Feature Research: Architecture Tier Separation (v2.0)

**Domain:** Client/server responsibility boundaries in a collaborative swipe-matching app
**Researched:** 2026-04-26
**Confidence:** HIGH

## Executive Summary

Jelly Swipe v2.0 addresses 7 specific tier responsibility violations where client code performs work that belongs to the server, or where server and client duplicate the same logic. In properly-tiered swipe-matching apps, the server is the single source of truth for identity, deck composition/order, match detection, and deep link generation. The client owns only animation, optimistic UI updates, and rendering.

Research confirms that Jellyfin Web uses **hash-based routing** (`createHashRouter`) with item detail pages at the `details` path, accepting `?id={itemId}` as a query parameter. The correct deep link format is `{JELLYFIN_URL}/web/#/details?id={itemId}` — the server already has `JELLYFIN_URL` as an env var, so it must generate these links rather than delegating URL construction to the client.

Flask's built-in `session` (signed cookies backed by `app.secret_key`) is sufficient for server-owned identity. No additional library is needed — `Flask-Login` would add unnecessary abstraction for a system with two identity modes (delegate server identity vs. user-supplied credentials).

## Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels broken or insecure.

| # | Feature | Why Expected | Complexity | Current Violation | Notes |
|---|---------|--------------|------------|-------------------|-------|
| 1 | **Server-owned user identity** | Users expect a single consistent identity across sessions, not parallel IDs | MEDIUM | Violation #1: Server generates `host_xxx`/`guest_xxx` IDs in session while client sends Jellyfin user_id via headers — two parallel identity systems | Store `user_id` in Flask session after auth; remove client-supplied identity headers from all API calls. Server resolves identity once at login, persists in `session['user_id']`. |
| 2 | **Server-side token storage (HttpOnly)** | Modern apps don't expose auth tokens to client JavaScript | MEDIUM | Violation #3: Client computes `Authorization: MediaBrowser ...` headers and persists tokens in `localStorage` | After `/auth/jellyfin-login` or delegate bootstrap, store the Jellyfin token server-side in `session['jf_token']` (Flask signed cookie). Client never sees the token. Return `session` cookie (already HttpOnly by default with `app.secret_key`). |
| 3 | **Server-owned deck composition + order** | Deck content must be deterministic; all participants see the same cards | LOW | Violation #5: Server returns shuffled deck but client can re-fetch `/movies` and get a different shuffle | Server stores deck JSON blob in `rooms.movie_data` (already does this). Client must not re-fetch or re-shuffle. Genre changes trigger server-side deck regeneration only. |
| 4 | **Single-channel match notification** | Match events should arrive from exactly one source | MEDIUM | Violation #4: Client decides match UX from `/room/swipe` response AND SSE pushes `last_match` — duplicate notification paths | `/room/swipe` should return `{matched: true/false}` without triggering a popup. The match popup should only fire from SSE `last_match` events. This eliminates race conditions and ensures both host and guest see matches. |
| 5 | **Correct Jellyfin deep links** | "Open in Jellyfin" must actually open the movie | LOW | Violation #2: Client computes Plex deep links (`https://app.plex.tv/desktop/#!/server/...`) — completely wrong for Jellyfin | Server generates `{JELLYFIN_URL}/web/#/details?id={movie_id}` and includes it in match/deck responses. Client just uses `href` from server data. |
| 6 | **Match cards with full metadata** | Users expect to see rating, duration, and year on matched movies | LOW | Violation #7: `get_matches()` returns `title, thumb, movie_id` only, but UI tries to render `rating`, `duration`, `year` badges (rendering empty) | Server-side join: `get_matches()` should return all card fields by re-querying Jellyfin or storing them in the `matches` table. |
| 7 | **RESTful swipe endpoint** | Standard REST semantics for swipe actions | LOW | Violation (general): `/room/swipe` is a generic endpoint without room context in URL | Refactor to `POST /room/{code}/swipe` with body `{movie_id, direction}` only. Session provides identity; URL provides room context. |
| 8 | **Solo mode as user property** | Solo mode is about how one person swipes, not a room property | MEDIUM | Violation #6: `go-solo` sets `rooms.solo_mode=1` which means both users in the room are forced into solo mode | Solo mode should be a session/user-level flag, not a room-level flag. `session['solo_mode'] = True` for the requesting user only. Match logic checks the swiping user's solo flag, not the room's. |

## Differentiators (Beyond Basic Expectations)

Features that set the app apart from a naive implementation. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **ADR documenting tier responsibilities** | Prevents future violations by codifying which tier owns what | LOW | Single markdown file: "Server owns: identity, deck, matches, deep links, tokens. Client owns: animation, DOM, optimistic UI." Future developers reference this. |
| **Server-side deck cursor** | Prevents clients from seeing cards out of order or skipping ahead | MEDIUM | Store per-user position in deck (which card index each user is on). Server returns only the next card(s) rather than the full deck. Prevents client-side deck manipulation. |
| **Idempotent swipe processing** | Prevents duplicate swipes from network retries | LOW | Add `UNIQUE(room_code, movie_id, user_id)` constraint on `swipes` table (already exists on `matches`). Use `INSERT OR IGNORE` pattern. |

## Anti-Features (Commonly Requested, Often Problematic)

Features to explicitly NOT build.

| Anti-Feature | Why Requested | Why Problematic | What to Do Instead |
|--------------|---------------|-----------------|-------------------|
| **Client-side deck shuffling** | Feels faster to shuffle locally without waiting for server | Creates divergent decks between users; defeats collaborative matching | Server owns deck order. Client requests cards from server. |
| **localStorage token persistence** | Survives page refresh; seems convenient | Tokens accessible to XSS (even with CSP); violates defense-in-depth; `session` cookie already handles persistence | Use Flask `session` (signed, HttpOnly by default). Set `session.permanent = True` for persistence across browser close. |
| **Client-computed deep links** | Avoids a server round-trip | Ties client to specific media server URL formats (Plex vs Jellyfin); client doesn't know server base URL | Server generates `{JELLYFIN_URL}/web/#/details?id={itemId}`. Client just navigates to the `href`. |
| **Dual notification path (SSE + HTTP response)** | Instant feedback on own swipe + partner notification | Race conditions; duplicate popups; divergent state between users | Single channel: SSE for ALL match notifications. HTTP response returns only `{matched: bool}` for the swiping user's optimistic UI. |
| **Room-level solo mode flag** | Simplest implementation | Forces all participants into solo mode when only one user wanted it; couples a user preference to room state | Session-level solo flag: `session['solo_mode'] = True`. Match logic checks the individual user's flag. |

## Feature Dependencies

```
[Server-Owned Identity (Feature 1)]
    └──requires──> [Server-Side Token Storage (Feature 2)]
    └──enables──> [RESTful Swipe Endpoint (Feature 7)]
                       └──requires──> [Session user_id, not client headers]

[Solo Mode as User Property (Feature 8)]
    └──requires──> [Server-Owned Identity (Feature 1)]
    └──requires──> [Session-level solo flag]

[Single-Channel Match Notification (Feature 4)]
    └──requires──> [SSE-only match display logic]
    └──requires──> [Swipe response returns matched:bool only]

[Correct Jellyfin Deep Links (Feature 5)]
    └──requires──> [Server knows JELLYFIN_URL (already has env var)]
    └──enables──> [Match cards with full metadata (Feature 6)]

[Match Cards with Full Metadata (Feature 6)]
    └──requires──> [Correct Jellyfin Deep Links (Feature 5)] — deep link is part of metadata
    └──requires──> [Store rating/duration/year in matches table or server-side join]

[Server-Owned Deck (Feature 3)]
    └──conflicts──> [Client-side re-fetch of /movies]
    └──requires──> [Remove client shuffle logic]
```

### Dependency Notes

- **Feature 1 requires Feature 2:** Identity resolution depends on the server holding the Jellyfin token. If the token is in `localStorage`, the client must send it on every request — which means the client controls identity. Moving the token server-side into `session` is a prerequisite for server-owned identity.

- **Feature 7 requires Feature 1:** The RESTful swipe endpoint (`POST /room/{code}/swipe`) needs the user identity from session, not from client headers. This can't work until identity is session-based.

- **Feature 8 requires Feature 1:** Solo mode must be per-user, which requires per-user session identity. With room-level solo mode, you can't have one user in solo and another in collaborative mode.

- **Feature 4 is independent of others but affects client behavior:** The SSE-only notification pattern is a client-side refactoring that removes the match popup trigger from the swipe response handler. It doesn't require identity or deck changes, but it's cleaner to do after the swipe endpoint is simplified.

- **Feature 5 is independent:** Deep link generation only needs `JELLYFIN_URL` (already available) and `movie_id`. No dependency on identity or deck changes.

- **Feature 6 depends on Feature 5:** Match metadata should include the deep link URL. If we're already augmenting the matches response, include all fields at once.

## MVP Definition

### Launch With (v2.0)

Minimum tier separation fixes — what's needed to eliminate all 7 violations.

- [ ] **Feature 2: Server-side token storage** — After auth (delegate or login), store Jellyfin token in `session['jf_token']`; clear `localStorage` tokens; set `session.permanent = True`
- [ ] **Feature 1: Server-owned identity** — On auth, resolve `user_id` from token and store in `session['user_id']`; remove all client identity headers from API calls; remove `X-Provider-User-Id` / `X-Jellyfin-User-Id` header support
- [ ] **Feature 7: RESTful swipe endpoint** — Refactor to `POST /room/{code}/swipe` with `{movie_id, direction}` body only; identity from session
- [ ] **Feature 3: Server-owned deck** — Remove client-side re-fetch/shuffle; client uses deck from server only; genre changes go through server
- [ ] **Feature 4: Single-channel match notification** — Remove match popup trigger from swipe response; match display comes only from SSE events
- [ ] **Feature 5: Correct Jellyfin deep links** — Server generates `{JELLYFIN_URL}/web/#/details?id={itemId}` in match/deck responses; remove Plex URL construction from client
- [ ] **Feature 6: Full match metadata** — Augment `get_matches()` to return `rating`, `duration`, `year`, and `deep_link` for each match
- [ ] **Feature 8: Solo mode as user property** — Move `solo_mode` from `rooms` table to `session` scope; match logic checks `session['solo_mode']`
- [ ] **ADR documenting tier responsibilities** — Codify which tier owns what

### Add After Validation (v2.1)

Features to add once core tier separation is verified.

- [ ] **Server-side deck cursor** — Per-user card position; prevents deck manipulation
- [ ] **Idempotent swipe processing** — `UNIQUE` constraint on `swipes` table; `INSERT OR IGNORE`
- [ ] **Rate limiting on swipe endpoint** — Prevent rapid-fire automated swipes

### Future Consideration (v3+)

Features to defer until architecture is stable.

- [ ] **WebSocket upgrade** — Replace SSE polling with WebSocket for lower latency
- [ ] **Multi-device session support** — Same user from multiple browsers
- [ ] **Playback status integration** — Track which matched movies have been watched

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority | Addresses Violation |
|---------|------------|---------------------|----------|---------------------|
| Server-side token storage | HIGH (security) | MEDIUM | P1 | #3 |
| Server-owned identity | HIGH (correctness) | MEDIUM | P1 | #1 |
| RESTful swipe endpoint | MEDIUM (clean API) | LOW | P1 | General |
| Server-owned deck | MEDIUM (consistency) | LOW | P1 | #5 |
| Single-channel match notification | HIGH (UX reliability) | MEDIUM | P1 | #4 |
| Correct Jellyfin deep links | HIGH (core functionality) | LOW | P1 | #2 |
| Full match metadata | MEDIUM (UX completeness) | LOW | P1 | #7 |
| Solo mode as user property | MEDIUM (multi-user correctness) | MEDIUM | P1 | #6 |
| ADR document | LOW (maintainability) | LOW | P1 | All |
| Server-side deck cursor | LOW (anti-cheat) | MEDIUM | P2 | — |
| Idempotent swipes | MEDIUM (reliability) | LOW | P2 | — |

**Priority key:**
- P1: Must have for v2.0 (eliminates all 7 violations)
- P2: Should have, add when possible (hardening)

## Responsibility Area Deep Dives

### Area 1: Identity (Violations #1, #3)

**Current state:** Two parallel identity systems operate simultaneously:
- Server: `session['my_user_id'] = 'host_' + secrets.token_hex(8)` — random, not tied to Jellyfin
- Client: `localStorage['provider_user_id']` — Jellyfin user_id, sent via `X-Provider-User-Id` header

**Correct behavior:** After authentication (either delegate or login), the server resolves the Jellyfin `user_id` from the token and stores it in `session['user_id']`. All subsequent endpoints read identity from `session['user_id']`. The token is stored in `session['jf_token']` (server-side, signed cookie). Client never sees or sends the token.

**Implementation pattern (Flask session, verified via Context7):**
```python
@app.route('/auth/jellyfin-login', methods=['POST'])
def jellyfin_login():
    # ... validate credentials ...
    out = get_provider().authenticate_user_session(username, password)
    session['user_id'] = out['user_id']
    session['jf_token'] = out['token']
    session.permanent = True
    return jsonify({'status': 'ok'})  # No token in response

@app.route('/auth/jellyfin-use-server-identity', methods=['POST'])
def jellyfin_use_server_identity():
    # ... resolve server identity ...
    session['user_id'] = uid
    session['jf_token'] = get_provider().server_access_token_for_delegate()
    session['jf_delegate_server_identity'] = True
    session.permanent = True
    return jsonify({'status': 'ok'})
```

**Client changes:** Remove `providerIdentityHeaders()`, `providerToken()`, `providerUserId()`, `jellyfinAuthorizationHeader()`. All API calls become simple `fetch('/endpoint')` with `credentials: 'same-origin'` (session cookie). Remove `localStorage` token storage entirely.

### Area 2: Deep Links (Violation #2)

**Current state:** Client constructs Plex URLs:
```javascript
// index.html line 629
const plexLink = `https://app.plex.tv/desktop/#!/server/${serverId}/details?key=%2Flibrary%2Fmetadata%2F${m.movie_id}`;
```
This produces URLs like `https://app.plex.tv/desktop/#!/server/abc123/details?key=/library/metadata/xyz789` — completely non-functional for Jellyfin.

**Correct behavior (verified from jellyfin-web source):**
- Jellyfin Web uses `createHashRouter` from react-router-dom (confirmed in `src/RootAppRouter.tsx`)
- Item detail pages use the route path `details` (confirmed in both `src/apps/stable/routes/legacyRoutes/user.ts` and `src/apps/experimental/routes/legacyRoutes/user.ts`)
- The item ID is passed as `?id={itemId}` query parameter
- The `BangRedirect` component handles deprecated `!/details?id=` URLs with a warning

**Correct URL format:**
```
{JELLYFIN_URL}/web/#/details?id={itemId}
```
Example: `http://192.168.1.100:8096/web/#/details?id=a1b2c3d4e5f6...`

**Server-side generation:**
```python
def _jellyfin_deep_link(movie_id: str) -> str:
    return f"{JELLYFIN_URL}/web/#/details?id={movie_id}"
```

The server already has `JELLYFIN_URL` as a module-level constant. Include `deep_link` in deck items and match responses.

### Area 3: Match Notification (Violation #4)

**Current state:** Two paths trigger match popups:
1. **HTTP response path:** `/room/swipe` returns `{match: true, title: "...", thumb: "..."}` → client immediately shows match overlay (index.html lines 934-949)
2. **SSE path:** `/room/stream` emits `last_match` event → client also shows match overlay (index.html lines 1015-1025)

This creates race conditions and duplicate popups. The swiping user sees the match from the HTTP response, then again from SSE. The partner only sees it from SSE.

**Correct behavior:**
- `/room/swipe` returns `{matched: true/false}` — a simple boolean for optimistic UI (e.g., green glow on swipe)
- Match popup/overlay is triggered **only** from SSE `last_match` events
- This ensures both users see the match at the same time (via SSE) and avoids duplicate notifications

**Implementation:** Remove match overlay logic from the swipe `fetch().then()` handler. Keep only the SSE handler for match display. The swipe response still returns `matched: bool` for the animation layer (green/red glow feedback).

### Area 4: Deck Management (Violation #5)

**Current state:** Server stores shuffled deck in `rooms.movie_data`. Client fetches `/movies` and gets the server deck. But:
- Client can re-fetch `/movies` at any time, getting the same stored deck
- Genre change triggers `GET /movies?genre=X` which regenerates the deck server-side but also re-shuffles
- Client's `selectGenre()` function re-fetches and overwrites local `movieStack`

**Correct behavior:**
- Server stores deck in `rooms.movie_data` on create (already does this)
- Client fetches deck once when game starts
- Genre changes go through server: `POST /room/{code}/genre` → server regenerates deck → SSE notifies with `genre` change → both clients fetch the new deck
- Client never triggers deck regeneration independently

**Key change:** Remove `selectGenre()` client-side re-fetch logic. Genre selection should be a server-side operation that updates `rooms.movie_data` and notifies via SSE.

### Area 5: Solo Mode (Violation #6)

**Current state:** `go-solo` sets `rooms.solo_mode = 1` in the database. This is a room-level flag, so when the host goes solo, the guest is also forced into solo mode. The match logic checks `room['solo_mode']` to decide if right-swipes create immediate matches.

**Correct behavior:** Solo mode is a per-user preference stored in session:
```python
@app.route('/room/go-solo', methods=['POST'])
def go_solo():
    session['solo_mode'] = True
    return jsonify({'status': 'solo'})
```

Match logic checks the swiping user's session, not the room:
```python
is_solo = session.get('solo_mode', False)
if is_solo and direction == 'right':
    # Create match for this user only
```

This allows one user to be in solo mode while another swipes collaboratively (or both in solo mode independently).

### Area 6: Match Metadata (Violation #7)

**Current state:** `get_matches()` SQL:
```sql
SELECT title, thumb, movie_id FROM matches WHERE ...
```

Client UI tries to render `m.rating`, `m.duration`, `m.year` (index.html lines 608-625) — these are `undefined`, producing empty badge spans.

**Correct behavior:** Two approaches:
1. **Store metadata in matches table:** Add `rating`, `duration`, `year` columns to `matches` and populate them when creating matches (preferred — avoids re-querying Jellyfin for every match list fetch)
2. **Server-side join at query time:** Re-resolve items from Jellyfin when fetching matches (expensive, slow)

**Recommended approach:** Store all card fields when creating the match. The `resolve_item_for_tmdb()` method already exists. Extend the match creation to store `rating`, `duration`, `year`, `deep_link` alongside `title` and `thumb`.

## Tier Responsibility Matrix

Clear ownership for each responsibility area.

| Responsibility | Server Owns | Client Owns |
|---------------|-------------|-------------|
| **User identity** | Resolves Jellyfin user_id from token; stores in session | Sends credentials once at login; receives session cookie |
| **Auth tokens** | Stores Jellyfin token in session (HttpOnly) | Never sees token |
| **Deck composition** | Fetches from Jellyfin, shuffles, stores in DB | Receives deck via API; renders cards |
| **Deck order** | Determines and persists order | Respects server order; no re-shuffle |
| **Match detection** | Queries swipes table for mutual right-swipes | Receives match notification via SSE |
| **Match notification** | Pushes via SSE `last_match` event | Displays overlay when SSE event arrives |
| **Deep link generation** | Constructs `{JELLYFIN_URL}/web/#/details?id={id}` | Navigates to `href` from server data |
| **Swipe recording** | Validates identity from session; inserts into DB | Sends `{movie_id, direction}` only |
| **Solo mode** | Stores per-user in session; checks per-user for match logic | Toggles UI; sends request to server |
| **Match metadata** | Stores/enriches with rating, duration, year, deep_link | Renders badges from server data |
| **Animation/UX** | — | Card drag, flip, glow effects, swipe animations |
| **Optimistic UI** | Returns `{matched: bool}` | Shows green/red glow based on response |

## Competitor Feature Analysis

| Feature | Tinder (reference app) | Typical Swipe Apps | Jelly Swipe Approach |
|---------|----------------------|--------------------|---------------------|
| Identity | Server-owned (OAuth/Facebook) | Server-owned session | Server-owned session via Jellyfin token |
| Deck | Server-shuffled, paginated | Server-owned cursor | Server-owned, stored in SQLite |
| Match detection | Server-side background job | Server-side on swipe | Server-side on swipe (immediate) |
| Match notification | Push notification or in-app | WebSocket or SSE | SSE (polling-based generator) |
| Deep link | N/A (in-app) | N/A (in-app) | Server-generated Jellyfin URL |

## Sources

**Jellyfin Web Source Code (HIGH confidence):**
- `src/RootAppRouter.tsx`: Confirms `createHashRouter` — hash-based routing (`/web/#/path`)
- `src/apps/stable/routes/legacyRoutes/user.ts`: `path: 'details'` for item detail pages
- `src/apps/experimental/routes/legacyRoutes/user.ts`: Same `path: 'details'` in experimental layout
- `src/components/router/BangRedirect.tsx`: Handles deprecated `!/details` URLs, confirms hash-based routing

**Flask Documentation (HIGH confidence via Context7):**
- `session` object: Cryptographically signed cookies, `session.permanent = True` for persistence
- `app.secret_key`: Required for session signing (already configured in Jelly Swipe)
- Session is dict-like: `session['user_id'] = value` / `session.pop('key', None)`

**Jellyfin API (HIGH confidence via Context7):**
- `AuthenticationResult` schema: Returns `AccessToken` and `User.Id` — confirms token+user_id pattern
- `/Users/AuthenticateByName`: Standard auth endpoint for user login
- `/Users/Me`: Returns current user info from token — used for token-to-user-id resolution

**Direct Code Analysis (HIGH confidence):**
- `jellyswipe/__init__.py`: Current route handlers, identity resolution, session usage
- `jellyswipe/templates/index.html`: Client-side identity headers, Plex deep link construction, match popup triggers
- `jellyswipe/jellyfin_library.py`: Provider with auth, deck fetch, item resolution
- `jellyswipe/db.py`: Schema with `rooms`, `swipes`, `matches` tables
- `jellyswipe/base.py`: Abstract `LibraryMediaProvider` contract

---
*Feature research for: Architecture Tier Separation in Jelly Swipe v2.0*
*Researched: 2026-04-26*
