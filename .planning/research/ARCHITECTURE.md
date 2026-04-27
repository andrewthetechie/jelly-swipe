# Architecture: Server-Owned Identity and State in Flask SSE

**Domain:** Flask SSE application tier restructuring
**Researched:** 2026-04-26
**Overall confidence:** HIGH (based on Context7-verified Flask/Flask-Session docs + existing codebase analysis)

## Recommended Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        BROWSER                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Client JS (animation, optimistic UI, drag/drop only)    │ │
│  │ • No token storage, no identity headers                 │ │
│  │ • No match detection logic                               │ │
│  │ • No deep link construction                              │ │
│  │ • Sends: {movie_id, direction} on swipe                 │ │
│  │ • Receives: deck, matches, notifications via SSE        │ │
│  └───────────────┬──────────────────────┬─────────────────┘ │
│                  │ HTTP (session cookie)│ EventSource        │
└──────────────────┼──────────────────────┼───────────────────┘
                   │                      │
┌──────────────────┼──────────────────────┼───────────────────┐
│  FLASK SERVER    │                      │                    │
│                  ▼                      ▼                    │
│  ┌──────────────────────┐  ┌────────────────────────────┐   │
│  │ REST API Routes      │  │ SSE Stream                 │   │
│  │ POST /auth/login     │  │ GET /room/{code}/stream    │   │
│  │ POST /auth/delegate  │  │ • Reads session in view    │   │
│  │ POST /room           │  │ • Yields match/genre/ready │   │
│  │ POST /room/{c}/join  │  │ • No session modification  │   │
│  │ POST /room/{c}/swipe │  └────────────────────────────┘   │
│  │ GET  /room/{c}/deck  │                                    │
│  │ POST /room/{c}/genre │  ┌────────────────────────────┐   │
│  │ GET  /room/{c}/match │  │ Auth Module                │   │
│  │ POST /room/{c}/solo  │  │ • Login → token → SQLite   │   │
│  │ POST /room/{c}/quit  │  │ • Session cookie only      │   │
│  └──────────┬───────────┘  │ • Token lookup per request │   │
│             │              │ • User_id resolution cache │   │
│             │              └──────────┬─────────────────┘   │
│             ▼                         ▼                      │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                    SQLite                               │  │
│  │  user_tokens: session_id → jf_token, jf_user_id        │  │
│  │  rooms: code, deck_json, deck_position, genre, solo    │  │
│  │  swipes: room_code, movie_id, jf_user_id, direction    │  │
│  │  matches: room_code, movie_id, jf_user_id, metadata    │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              JellyfinLibraryProvider                    │  │
│  │  Server-side auth, deck fetch, metadata, images        │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

## Component Boundaries

### NEW: `jellyswipe/auth.py` — Identity Module

| Responsibility | Detail |
|---------------|--------|
| Login flow | Accept username/password, call `JellyfinLibraryProvider.authenticate_user_session()`, store resulting token in `user_tokens` table |
| Delegate flow | Accept server-identity request, use existing `server_access_token_for_delegate()`, store in `user_tokens` |
| Token lookup | On every request, read `session['session_id']` → look up token from `user_tokens` → resolve/cache `jf_user_id` |
| Session creation | Generate `session_id` (secrets.token_hex), set `session['session_id']`, store token mapping |
| Logout | Delete `user_tokens` row, clear Flask session |
| Require-auth decorator | `@login_required` that populates `g.user_id` and `g.jf_token` |

### MODIFIED: `jellyswipe/__init__.py` — Routes Refactored

| Change | Before | After |
|--------|--------|-------|
| Identity source | Client `Authorization` header + `X-Provider-User-Id` header | Server `session['session_id']` → token lookup |
| Route structure | `/room/create`, `/room/swipe`, `/movies` | `/room`, `/room/{code}/swipe`, `/room/{code}/deck` |
| Auth decorator | Inline `_provider_user_id_from_request()` calls | `@login_required` reads from `g.user_id` |
| SSE session | Reads `session['active_room']` (works already) | Same, plus reads deck position for per-user progress |
| Match notification | Client detects match from swipe response JSON | Server pushes match via SSE; swipe returns `{accepted: true}` only |
| Deep links | Client constructs Plex/Jellyfin URLs | Server includes `deep_link` in match metadata |

### MODIFIED: `jellyswipe/db.py` — Schema Migration

| Change | Detail |
|--------|--------|
| New table: `user_tokens` | `(session_id TEXT PK, jellyfin_token TEXT, jellyfin_user_id TEXT, created_at REAL, expires_at REAL)` |
| Remove: `my_user_id` from session | No more `host_`/`guest_` synthetic IDs; use Jellyfin `user_id` everywhere |
| `swipes.user_id` | Already stores Jellyfin user_id (migrated from plex_id); no schema change needed |
| `matches.user_id` | Already stores Jellyfin user_id; no schema change needed |
| New: `rooms.deck_position` | Per-room deck cursor (which card index is current); replaces client-side `movieStack.shift()` |
| New: `matches.deep_link` | Server-generated Jellyfin deep link URL |

### MODIFIED: `jellyswipe/templates/index.html` — Client Simplified

| Remove | Reason |
|--------|--------|
| `providerToken()`, `providerUserId()` | Server owns tokens |
| `providerIdentityHeaders()` | No identity headers sent from client |
| `localStorage.setItem('provider_token', ...)` | Token never reaches client |
| `localStorage.setItem('plex_token', ...)` | Legacy Plex key |
| Match detection from swipe response | Server notifies via SSE |
| Deep link construction (`plexLink = ...`) | Server provides `deep_link` field |
| `fetchAndStoreProviderId()` | Server resolves identity |

| Keep | Reason |
|------|--------|
| Drag/drop handlers, swipe animation | Client-owned UI |
| EventSource SSE listener | Receives match/genre notifications |
| Card rendering, flip, trailer | Client-owned presentation |
| Genre modal, match modal display | Client-owned UI |

## Data Flow

### Login (NEW Flow)

```
1. User clicks "Login" → POST /auth/login {username, password}
2. Server calls JellyfinLibraryProvider.authenticate_user_session()
3. Server generates session_id, stores {session_id → token, user_id} in user_tokens
4. Server sets session['session_id'] = session_id  (HttpOnly, signed cookie)
5. Server returns {user_id} → client stores nothing sensitive
6. Client transitions to main menu
```

### Delegate Login (EXISTING, Modified)

```
1. Client POST /auth/delegate
2. Server calls get_provider().server_access_token_for_delegate()
3. Server generates session_id, stores in user_tokens
4. Server sets session['session_id']
5. Client receives {user_id}, no token stored
```

### Swipe (NEW Flow)

```
1. Client drags card → POST /room/{code}/swipe {movie_id: "...", direction: "right"}
   - No Authorization header, no identity headers, no title/thumb
2. Server @login_required reads g.user_id from session
3. Server resolves metadata via resolve_item_for_tmdb(movie_id) → title, thumb
4. Server INSERT into swipes
5. If direction == "right":
   a. Solo mode: INSERT match immediately, UPDATE rooms.last_match_data, SSE pushes match
   b. Paired mode: SELECT other right-swipe → if found, INSERT match for both users, SSE pushes match
6. Server returns {accepted: true} — no match data in response body
7. Client removes card from deck (optimistic), SSE delivers match popup
```

### SSE Match Notification (UNIFIED Path)

```
Both solo matches and mutual matches follow the same SSE path:

1. Swipe inserts match → UPDATE rooms.last_match_data with {title, thumb, deep_link, ts}
2. SSE generator polls rooms table every 1.5s
3. When last_match.ts changes → yield SSE event with full match payload
4. Client receives SSE event → displays match overlay
5. No more inline match detection from swipe response
```

### Deck Ownership (NEW)

```
1. POST /room → server fetches deck from Jellyfin, stores as JSON in rooms.movie_data
2. GET /room/{code}/deck → server returns deck cards starting from rooms.deck_position
3. POST /room/{code}/swipe → server increments deck_position
4. POST /room/{code}/genre → server re-fetches deck with genre filter, resets deck_position
5. Client never reorders; only renders what server provides
```

## Patterns to Follow

### Pattern 1: Session-Based Token Vault

**What:** Store Jellyfin tokens in SQLite keyed by session ID, never expose to client.
**When:** Every authenticated request.
**Why:** Eliminates client-side token theft vector; server has full control over token lifecycle.

```python
# jellyswipe/auth.py
from flask import session, g, request
from functools import wraps
import secrets, time

def create_session(db, jf_token: str, jf_user_id: str) -> str:
    """Store token in vault, set session cookie, return session_id."""
    sid = secrets.token_hex(32)
    now = time.time()
    db.execute(
        'INSERT INTO user_tokens (session_id, jellyfin_token, jellyfin_user_id, created_at, expires_at) '
        'VALUES (?, ?, ?, ?, ?)',
        (sid, jf_token, jf_user_id, now, now + 86400)
    )
    session['session_id'] = sid
    return sid

def get_current_token(db) -> tuple[str, str] | None:
    """Return (jf_token, jf_user_id) for current session, or None."""
    sid = session.get('session_id')
    if not sid:
        return None
    row = db.execute(
        'SELECT jellyfin_token, jellyfin_user_id FROM user_tokens WHERE session_id = ?',
        (sid,)
    ).fetchone()
    if not row:
        return None
    return row['jellyfin_token'], row['jellyfin_user_id']

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        from .db import get_db
        result = get_current_token(get_db())
        if not result:
            return jsonify({'error': 'Unauthorized'}), 401
        g.jf_token, g.user_id = result
        return f(*args, **kwargs)
    return decorated
```

### Pattern 2: SSE Generator Reads Session Before Streaming

**What:** Access session data in the view function, pass values into the generator. Never access `session` inside the generator.
**When:** `/room/{code}/stream` endpoint.
**Why:** Flask's SSE + session docs explicitly warn: "access session in the view function, do not modify in generator."

```python
@app.route('/room/<code>/stream')
def room_stream(code):
    # Read session BEFORE returning Response
    session_id = session.get('session_id')
    user_id = g.get('user_id')  # or resolve inline
    active_room = session.get('active_room')

    if not active_room or active_room != code:
        return Response("data: {}\n\n", mimetype='text/event-stream')

    def generate(room_code, uid):
        last_match_ts = None
        while True:
            with get_db() as conn:
                row = conn.execute(
                    'SELECT last_match_data FROM rooms WHERE pairing_code = ?',
                    (room_code,)
                ).fetchone()
            if row is None:
                yield f"data: {json.dumps({'closed': True})}\n\n"
                return
            # ... yield match updates
            time.sleep(1.5)

    return Response(
        generate(code, user_id),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )
```

### Pattern 3: RESTful Route Structure

**What:** Resource-oriented URLs with nested resources.
**When:** All route definitions.

```python
# Room lifecycle
@app.route('/room', methods=['POST'])           # create
@app.route('/room/<code>', methods=['DELETE'])  # quit/destroy

# Room membership
@app.route('/room/<code>/join', methods=['POST'])
@app.route('/room/<code>/solo', methods=['POST'])

# Room actions
@app.route('/room/<code>/swipe', methods=['POST'])   # {movie_id, direction}
@app.route('/room/<code>/deck', methods=['GET'])     # current deck state
@app.route('/room/<code>/genre', methods=['POST'])   # {genre}
@app.route('/room/<code>/matches', methods=['GET'])  # active matches
@app.route('/room/<code>/stream')                    # SSE

# Auth
@app.route('/auth/login', methods=['POST'])          # {username, password}
@app.route('/auth/delegate', methods=['POST'])        # server identity
@app.route('/auth/logout', methods=['POST'])          # clear session

# User resources
@app.route('/matches', methods=['GET'])               # history (no room context)
@app.route('/matches/<movie_id>', methods=['DELETE']) # delete from history
@app.route('/watchlist/<movie_id>', methods=['POST']) # add to Jellyfin favorites
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Accessing `session` Inside SSE Generator

**What:** Reading `session['active_room']` inside the `generate()` function.
**Why bad:** Flask's streaming docs explicitly warn against this. The request context may not be preserved in the generator under gevent. The `Vary: Cookie` header won't be set correctly.
**Instead:** Read all session values in the view function, pass them as arguments to the generator.

### Anti-Pattern 2: Storing Tokens in Flask Session Cookie

**What:** `session['jf_token'] = token` (signed cookie, ~4KB limit).
**Why bad:** Flask's default session is a signed (not encrypted) cookie — the user can decode and read the contents. Jellyfin tokens in a decodable cookie is a credential leak. Also bloats the cookie size.
**Instead:** Store a `session_id` in the cookie; keep the actual token in `user_tokens` SQLite table.

### Anti-Pattern 3: Dual Identity (host_/guest_ + Jellyfin user_id)

**What:** Current code generates synthetic IDs (`host_abc123`, `guest_def456`) for room participants, AND resolves Jellyfin `user_id` for match tracking.
**Why bad:** Two identity systems creates confusion — swipes use `session['my_user_id']` (synthetic), matches use `_provider_user_id_from_request()` (Jellyfin). When both users have the same Jellyfin account (delegate mode), match detection breaks because `user_id` is the same for both.
**Instead:** Use Jellyfin `user_id` as the single canonical identity. For delegate mode (same account), use `session_id` as a disambiguator for room operations (who swiped what), but use `jf_user_id` for match ownership.

### Anti-Pattern 4: Client-Side Match Detection

**What:** Client checks `if (data.match)` in the swipe response to show the overlay.
**Why bad:** Match logic is split between server (creating the match record) and client (displaying it). In multi-user scenarios, only the second swiper's client gets the match notification; the first swiper never sees it unless SSE delivers it.
**Instead:** Swipe endpoint returns `{accepted: true}` only. All match notifications go through the unified SSE channel. Both users receive the match simultaneously.

### Anti-Pattern 5: Client-Supplied Deck Position

**What:** Client maintains `movieStack` array and calls `movieStack.shift()` after each swipe.
**Why bad:** If two clients in a room have different deck positions (race condition, page reload), they're swiping on different movies. Server has no way to enforce deck synchronization.
**Instead:** Server tracks `deck_position` per room. Swipe endpoint increments it. Deck endpoint returns cards from current position. On reload, client resumes where it left off.

## gevent + Session Compatibility

**Verdict: YES, fully compatible.** HIGH confidence (verified via Context7 Flask docs + existing production setup).

Key findings:

1. **Flask's default `SecureCookieSessionInterface` is stateless** — it decodes the session cookie on each request and re-encodes on response. No server-side state to conflict with gevent's cooperative greenlets.

2. **SSE streaming under gevent already works** — the Dockerfile uses `gunicorn -k gevent --worker-connections 1000`. The current `/room/stream` endpoint works with this setup.

3. **Session reads in SSE view function are safe** — Flask explicitly documents this pattern. Read session before returning `Response(generate())`, pass values as generator arguments.

4. **SQLite with gevent** — `sqlite3` module is a C extension that blocks the OS thread. Under gevent, this means one greenlet per DB call. For Jelly Swipe's scale (<100 concurrent users), this is fine. If scaling beyond that, switch to `gevent.socket.wait_read` on the SQLite file descriptor, or use a connection-per-greenlet pattern.

5. **`user_tokens` table access under gevent** — Same as current SQLite access pattern (one connection per request via `get_db()`). No new concurrency concerns.

## Migration Path: Current → New Architecture

### Phase 1: Database Schema Migration
**Scope:** `db.py` only
**Changes:**
- Add `user_tokens` table
- Add `rooms.deck_position` column (default 0)
- Add `matches.deep_link` column
- Keep all existing columns for backward compatibility

**Risk:** LOW. Additive-only schema changes. No data loss.

### Phase 2: Auth Module + Token Vault
**Scope:** New `auth.py`, modified `__init__.py` login routes
**Changes:**
- Implement `create_session()`, `get_current_token()`, `login_required`
- Refactor `/auth/jellyfin-login` to store token in vault, not return to client
- Refactor `/auth/jellyfin-use-server-identity` to use vault
- Session cookie now carries `session_id` + `active_room` only

**Dependency:** Phase 1 (user_tokens table)
**Risk:** MEDIUM. Login flow changes; existing sessions invalidated (users re-login).

### Phase 3: Identity Unification
**Scope:** `__init__.py` route handlers
**Changes:**
- Replace all `_provider_user_id_from_request()` calls with `g.user_id` from `@login_required`
- Remove `_jellyfin_user_token_from_request()`, `_request_has_identity_alias_headers()`, etc.
- Remove `session['my_user_id']` synthetic ID generation
- `swipes.user_id` becomes `g.user_id` (Jellyfin user_id) everywhere

**Dependency:** Phase 2 (auth module provides `g.user_id`)
**Risk:** HIGH. Changes the identity of every swipe/match. Requires careful testing of:
  - Solo mode matches (same user, same room)
  - Paired mode matches (two different Jellyfin accounts)
  - Delegate mode (two browsers, same Jellyfin account — need `session_id` disambiguator)

### Phase 4: RESTful Endpoint Restructuring
**Scope:** `__init__.py` routes, `templates/index.html` fetch URLs
**Changes:**
- Rename routes to RESTful pattern
- Update all client `fetch()` calls to new URLs
- Add `/room/{code}/deck` endpoint
- Add `/room/{code}/genre` POST endpoint

**Dependency:** Phase 3 (identity source stable)
**Risk:** MEDIUM. Mechanical URL changes, but must update both server and client in lockstep.

### Phase 5: Server-Owned Deck State
**Scope:** `__init__.py` deck routes, `templates/index.html` deck fetching
**Changes:**
- `/room/{code}/deck` returns cards from `rooms.deck_position`
- `/room/{code}/swipe` increments `deck_position`
- Genre change resets `deck_position` and refetches deck
- Client no longer maintains `movieStack` ordering; renders what server provides

**Dependency:** Phase 4 (RESTful routes)
**Risk:** MEDIUM. Changes how the client manages card stack. Must handle edge cases:
  - Empty deck (all swiped)
  - Browser reconnect (resume from deck_position)
  - Genre mid-session change

### Phase 6: Unified Match Notification
**Scope:** `__init__.py` swipe handler, SSE generator, `templates/index.html` event handler
**Changes:**
- Swipe endpoint returns `{accepted: true}` only, no match data
- All matches (solo + mutual) push through SSE via `rooms.last_match_data`
- Client removes inline match detection from swipe response handler
- Client shows match overlay only when SSE delivers match event

**Dependency:** Phase 3 (identity) + Phase 5 (deck state)
**Risk:** MEDIUM. Match UX changes from instant (swipe response) to near-instant (SSE poll ~1.5s). May feel slightly slower. Mitigation: optimistic card animation continues, match popup arrives within 1.5s.

### Phase 7: Client Simplification
**Scope:** `templates/index.html`
**Changes:**
- Remove `providerToken()`, `providerUserId()`, `providerIdentityHeaders()`
- Remove `localStorage` token/user_id storage
- Remove client-side deep link construction
- Server includes `deep_link` in match metadata
- Login response sets no client-side tokens

**Dependency:** All previous phases
**Risk:** LOW. Purely subtractive client changes. Server already provides all needed data.

## Scalability Considerations

| Concern | At 10 users (current) | At 100 users | At 1K+ users |
|---------|----------------------|--------------|--------------|
| SSE polling (1.5s SQLite) | ~7 DB reads/sec | ~67 DB reads/sec | ~667 DB reads/sec |
| Token vault lookups | Insignificant | 1 per request, cached `g.user_id` | Same, cached |
| SQLite concurrency | Single writer, fine | Fine with WAL mode | Needs connection pooling or Postgres |
| Session cookie size | ~200 bytes (session_id + room code) | Same | Same |
| gevent workers | 1 worker, 1000 connections | 1 worker sufficient | 2-4 workers with `--preload` |

**Verdict:** Current architecture (1 gevent worker, SQLite, SSE polling) handles 100+ concurrent users comfortably. No infrastructure changes needed for v2.0.

## Integration Points

### New Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `flask-session` | `>=0.8` | Considered but NOT recommended (see rationale) |

**Rationale for NOT using Flask-Session:** Flask-Session adds server-side session storage backends (Redis, Memcached, filesystem). For Jelly Swipe, the session cookie only needs to hold `session_id` + `active_room` — ~100 bytes. Flask's built-in `SecureCookieSessionInterface` handles this fine. The actual sensitive data (Jellyfin token) goes in the `user_tokens` SQLite table, which is a domain-specific concern, not a generic session storage problem. Adding Flask-Session would introduce an unnecessary abstraction layer.

### Existing Dependencies (No Changes)

| Package | Role | Compatibility |
|---------|------|--------------|
| `flask>=3.1` | Core framework | Session + SSE patterns verified |
| `gevent>=24.10` | SSE worker | Already working with session cookies |
| `gunicorn>=25.3` | WSGI server | Same `gevent` worker class |
| `sqlite3` (stdlib) | Data store | New table, same access pattern |

## Sources

- Flask session docs (Context7, `/pallets/flask`): HIGH confidence — signed cookie behavior, `stream_with_context` caveats for SSE generators
- Flask-Session docs (Context7, `/pallets-eco/flask-session`): HIGH confidence — server-side session backends, filesystem/cachelib options
- Flask streaming docs (Context7): HIGH confidence — "access session in view function, not in generator" warning
- Existing codebase (`__init__.py`, `db.py`, `jellyfin_library.py`, `templates/index.html`): HIGH confidence — analyzed line by line
