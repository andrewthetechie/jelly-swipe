# Domain Pitfalls — v2.0 Architecture Tier Fix

**Domain:** Flask + SQLite + SSE (gevent) monolith, refactoring tier responsibilities between server and client
**Researched:** 2026-04-26
**Codebase analyzed:** `jellyswipe/__init__.py` (563 lines), `jellyswipe/templates/index.html` (1072 lines), `jellyswipe/db.py` (52 lines), `jellyswipe/jellyfin_library.py` (482 lines)

---

## Critical Pitfalls

Mistakes that cause silent data loss, broken sessions, or undetectable regressions.

### Pitfall 1: SSE Generator Session Stale-Read / Context Loss

**What goes wrong:** The `/room/stream` SSE generator captures `code = session.get('active_room')` once in the view function (line 469), then runs for up to 3600 seconds polling the database. If the refactoring introduces session reads *inside* the generator (e.g., checking auth state on each poll cycle), two failures occur:
1. Without `stream_with_context()`, the generator has no Flask request context — accessing `session` or `request` raises `RuntimeError: Working outside of request context`.
2. Even with `stream_with_context()`, Flask docs explicitly warn: **"Do not modify the session in the generator, as the Set-Cookie header will already be sent."**

**Why it happens:** The current generator is context-free by design — it only uses the `code` local variable captured by closure. Refactoring to check auth state per-cycle is a natural impulse when moving identity server-side.

**Consequences:** Silent 500 errors in the SSE stream (caught by the generic `except Exception` on line 517), causing the client to stop receiving match notifications with no visible error.

**Prevention:**
- Keep the SSE generator context-free. Pass all needed data (room code, user id) as arguments from the view function.
- If the generator must check mutable state, read from the database (already the pattern), not from `session`.
- Never call `session.modify()` inside the generator.

**Detection:** SSE stream stops sending events but doesn't close (client sees no `closed: true` event). Match overlays stop appearing for one user but not the other.

**Where in code:** `__init__.py` lines 467–521 (`room_stream` route and `generate()` closure).

---

### Pitfall 2: Match Detection TOCTOU Race in SQLite

**What goes wrong:** The swipe endpoint (lines 343–378) performs a non-atomic check-then-insert sequence:
1. `INSERT INTO swipes` (line 344)
2. `SELECT user_id FROM swipes WHERE ... AND user_id != ?` (line 358)
3. `INSERT INTO matches` (lines 362–371)

When two users swipe right on the same movie simultaneously:
- User A: INSERT swipe → SELECT (no other right swipe yet) → no match
- User B: INSERT swipe → SELECT (finds A's right swipe) → creates match
- Result: Match is only created for User B's perspective. User A's swipe is orphaned — they never see the match.

**Why it happens:** SQLite default journal mode allows concurrent reads during writes, but the check-then-insert is not wrapped in a transaction with `BEGIN IMMEDIATE`. The `with get_db() as conn:` context manager uses autocommit, not an explicit transaction.

**Consequences:** Silent match loss. Two users both swiped right, but only one sees the match notification. No error is raised.

**Prevention:**
- Wrap the swipe+match logic in `BEGIN IMMEDIATE` transaction to serialize concurrent swipes on the same movie.
- Or use `INSERT ... SELECT` pattern to atomically detect and create matches.
- Alternative: After both users swipe, have the *second* swipe always create matches for *both* user_ids (which is partially the current pattern on lines 366–371, but the first user's match insert is skipped because the SELECT found nothing).

**Detection:** Two users report swiping right on the same movie but only one sees a match. Intermittent — only occurs under timing coincidence.

**Where in code:** `__init__.py` lines 343–378 (swipe endpoint).

---

### Pitfall 3: Dual Identity Migration Orphans Existing Swipes

**What goes wrong:** The current system has **two distinct identity keys** used in different contexts:
- `uid = session.get('my_user_id')` — format `host_<hex>` or `guest_<hex>`, used as `user_id` in the `swipes` table (line 345)
- `user_id = _provider_user_id_from_request()` — Jellyfin UUID, used as `user_id` in the `matches` table (lines 352, 354, 364)

The match detection query (line 358) uses `uid` to find "other user's swipes", but match records are stored with `user_id` (Jellyfin ID). If the refactoring consolidates to a single identity (e.g., always use Jellyfin user_id for swipes), existing `swipes` rows with `host_*`/`guest_*` values become unreachable. Conversely, if the refactoring changes the `matches.user_id` column semantics, existing match history breaks.

**Why it happens:** The dual-ID system evolved incrementally. Swipes use session-derived anonymous IDs; matches use provider-verified IDs. There's no foreign key or migration path between them.

**Consequences:**
- Active rooms during migration: swipes recorded under old IDs, matches looked up under new IDs → matches silently stop working mid-session.
- Historical matches: `/matches?view=history` queries by Jellyfin `user_id` but rows contain different identity formats → empty history after migration.

**Prevention:**
- Write a one-time migration that backfills `swipes.user_id` with the Jellyfin user_id where possible (requires mapping `host_`/`guest_` IDs back to Jellyfin IDs — which may not exist).
- Alternatively: keep both identity columns and add a migration that copies the session-ID to a new column while adding the Jellyfin ID alongside.
- **Safest approach:** Add a `jellyfin_user_id` column to both tables; populate it going forward; keep the old `user_id` column for backward compatibility during a transition period.

**Detection:** After migration, match history appears empty for existing users. New matches work but old ones are invisible.

**Where in code:** `__init__.py` lines 313–378 (swipe + match logic); `db.py` schema (lines 22–28).

---

### Pitfall 4: EventSource Cannot Send Authorization Headers

**What goes wrong:** The browser `EventSource` API (used on line 997: `new EventSource('/room/stream')`) does **not** support custom headers. It only sends cookies. If the refactoring changes the SSE endpoint to require `Authorization` header verification (instead of relying on the session cookie), the SSE connection will fail with 401 on every request.

**Why it happens:** A natural refactoring instinct is "all authenticated endpoints should verify the token in the Authorization header." But `EventSource` doesn't support `withCredentials` in the same way as `XMLHttpRequest` — it always sends cookies for same-origin requests, but never sends custom headers.

**Consequences:** SSE stream returns 401 or empty response. Client never receives room-ready notifications, match notifications, or genre changes. The room appears stuck in "waiting for partner" state.

**Prevention:**
- SSE endpoint must authenticate via session cookie only, not `Authorization` header.
- The current pattern is correct: `room_stream()` reads `session.get('active_room')` (line 469).
- If HttpOnly session cookies are adopted, SSE will work automatically since `EventSource` sends cookies same-origin.
- Do **not** add `_provider_user_id_from_request()` to the SSE endpoint — it reads `Authorization` headers which `EventSource` cannot send.

**Detection:** Browser console shows `EventSource` error events. Network tab shows 401 on `/room/stream`. Room never transitions from "waiting" to active.

**Where in code:** `__init__.py` line 467–521 (SSE route); `index.html` line 997 (`new EventSource('/room/stream')`).

---

### Pitfall 5: Session Cookie Last-Write-Wins Under gevent Concurrency

**What goes wrong:** Flask's default `SecureCookieSessionInterface` stores the entire session as a single signed cookie. Flask docs warn: **"Multiple requests with the same session may be sent and handled concurrently. There is no guarantee on the order in which the session for each request is opened or saved."**

Under gevent, each SSE connection holds a greenlet open for up to 3600 seconds. During that time, the same browser may make concurrent requests that modify the session (e.g., `/room/swipe` while the SSE generator is running). The last response to save the session cookie wins — the other's changes are silently lost.

**Why it happens:** gevent's cooperative scheduling means requests interleave at I/O boundaries. Two requests from the same browser share the same session cookie. Flask signs the entire session dict into one cookie — there's no per-key merging.

**Consequences:** `session['active_room']` or `session['my_user_id']` gets overwritten with stale data. User appears to leave the room randomly, or their identity flips to an empty value.

**Prevention:**
- Minimize session writes. Set identity and room data once (on create/join) and never modify them during the SSE lifecycle.
- If session writes during SSE are unavoidable, consider server-side sessions (Flask-Session with SQLAlchemy or filesystem backend) which support per-key updates.
- Read session data before returning the response, not in background tasks.
- The current code is mostly safe because session writes happen on create/join only, but the refactoring may introduce new session writes (e.g., storing the Jellyfin token in session).

**Detection:** User is in a room, swiping works, then suddenly their session reverts to the pre-join state. Intermittent, only under concurrent request patterns.

**Where in code:** Any route that writes to `session` — `create_room` (line 282), `join_room` (line 304), `go_solo` (line 294), `jellyfin_use_server_identity` (line 257).

---

## Moderate Pitfalls

### Pitfall 6: HttpOnly Cookie Migration — No Backward Bridge

**What goes wrong:** Current flow: `/auth/jellyfin-login` returns `{"authToken": "...", "userId": "..."}` as JSON (line 270). Client stores in `localStorage` and sends as `Authorization` header on every request. If the refactoring changes this to set an HttpOnly session cookie instead, existing deployed clients will:
1. Still have tokens in `localStorage` from their last session
2. Still send `Authorization` headers
3. But the server now expects the session cookie, not the header
4. If the server stops reading `Authorization` headers, every existing user's session breaks immediately

**Prevention:**
- Build a **dual-read migration period**: server checks both session cookie and `Authorization` header during transition.
- Add a `/auth/migrate-session` endpoint that the client calls once to move the `localStorage` token into the session cookie.
- Client-side: on `window.onload`, if `localStorage` has tokens but session doesn't, call the migration endpoint.
- After migration, clear `localStorage` tokens and use only session cookie.

**Where in code:** `__init__.py` lines 96–111 (`_jellyfin_user_token_from_request`); `index.html` lines 326–349 (client auth functions).

---

### Pitfall 7: SameSite Cookie + Reverse Proxy HTTPS Termination

**What goes wrong:** Docker deployments typically use a reverse proxy (Traefik, nginx, Caddy) that terminates TLS and forwards HTTP to the Flask container. If `SESSION_COOKIE_SECURE=True` is set (recommended for HttpOnly cookies), the browser will only send the cookie over HTTPS. But Flask sees the request as HTTP (no `X-Forwarded-Proto` or incorrect `ProxyFix` config), so it won't set the `Secure` flag — or worse, it sets the flag but the cookie isn't sent on the next request because the browser sees the proxy as HTTP.

**Prevention:**
- Verify `ProxyFix` is configured (already present on line 46: `ProxyFix(app.wsgi_app, x_for=1, x_proto=1, ...)`) and that `x_proto=1` is included.
- Test cookie flags in the actual deployment: `curl -v https://your-app/` and check `Set-Cookie` headers.
- If `SESSION_COOKIE_SECURE=True` and users access via IP (not HTTPS), the cookie is never sent — provide clear deployment docs.

**Where in code:** `__init__.py` line 46 (ProxyFix); line 47 (secret_key — session signing).

---

### Pitfall 8: Deck State Divergence Between Server and Client

**What goes wrong:** Currently the server shuffles the deck in `fetch_deck()` (jellyfin_library.py line 326: `random.shuffle(movie_list)`) and stores it as a JSON blob in `rooms.movie_data`. The client receives the full deck from `/movies` and manages a local `movieStack` array. The client modifies this array on swipe (line 950: `movieStack.shift()`) and undo (line 715: `movieStack.unshift(lastMovie)`).

If the refactoring makes the server the single source of truth for "which card is current," the client's local array will diverge from the server's state whenever:
1. The user swipes faster than the server responds (optimistic animation already consumed the card)
2. An undo request fails but the client already put the card back
3. Genre change arrives via SSE while the user is mid-swipe

**Prevention:**
- Keep the deck as a server-ordered list that the client renders without re-ordering.
- Track "swiped up to index N" on the server, not the specific card order.
- Undo should be a server-first operation: client sends undo, server responds with the card to restore, client adds it back.
- Or: accept that deck state is eventually-consistent and design for idempotent operations.

**Where in code:** `jellyfin_library.py` lines 272–327 (`fetch_deck`); `index.html` lines 924–951 (swipe handler), 707–717 (undo handler).

---

### Pitfall 9: CSP Blocks Inline Event Handlers After Template Refactor

**What goes wrong:** The CSP header (lines 52–59) sets `script-src 'self'` which blocks inline event handlers. The HTML template currently has several inline `onclick` attributes:
- Line 206: `<button ... onclick="confirmQuit()">`
- Line 267: `<div ... onclick="selectGenre('All')">`
- Line 268: `<div ... onclick="selectGenre('Recently Added')">`
- Line 281: `<button ... onclick="...classList.add('hidden')">`
- Line 629: `plexLink` with inline URL construction

If the template is refactored or CSP is tightened (e.g., adding nonce support), these inline handlers will silently break — buttons become non-functional with no console error in some browsers.

**Prevention:**
- Migrate all inline handlers to `addEventListener` calls in the `<script>` block during the refactor.
- Or add `'unsafe-inline'` to `script-src` (not recommended for security).
- Or implement CSP nonce support: `script-src 'nonce-{{ csp_nonce }}'`.

**Where in code:** `__init__.py` lines 49–60 (CSP middleware); `index.html` lines 206, 267, 281, etc.

---

### Pitfall 10: SSE Reconnection Drops Match State

**What goes wrong:** When the SSE connection drops and `EventSource` auto-reconnects, the server starts a fresh `generate()` loop with `last_match_ts = None`. This means:
1. If a match happened while the client was disconnected, the server will re-send the `last_match` event
2. The client's `lastSeenMatchTs` JS variable persists across reconnects (it's a global, not reset)
3. If the reconnected SSE sends a match with `ts > lastSeenMatchTs`, the match overlay re-appears — even if the user already dismissed it

Conversely, if `lastSeenMatchTs` is somehow *ahead* of the server's `last_match.ts` (e.g., clock skew, page was open during a previous session), matches are silently dropped.

**Prevention:**
- On SSE reconnect, reset `lastSeenMatchTs` to the current time to avoid replaying old matches.
- Or: the server should track per-user "last seen match" and only send new ones.
- The current pattern of using `last_match_data` on the room row (shared between all users) is inherently imprecise for per-user match tracking.

**Where in code:** `__init__.py` lines 473–518 (SSE generator); `index.html` lines 995–1027 (SSE client).

---

## Minor Pitfalls

### Pitfall 11: Server Token Cache Becomes Stale on Password Change

**What goes wrong:** `_token_user_id_cache` (line 70) caches Jellyfin token→user_id mappings for 300 seconds. If a Jellyfin admin revokes or rotates a user's token (password change, session invalidate), the cache still maps the old token to a user_id. Swipes and matches could be attributed to the wrong identity.

**Prevention:** Reduce TTL or add a cache invalidation endpoint. The 300-second TTL is documented as a deliberate tradeoff (line 155 comment). For v2.0, document this risk and accept it — it's self-healing after TTL expiry.

---

### Pitfall 12: `session.pop()` Doesn't Cascade to SSE

**What goes wrong:** `/room/quit` (line 403) calls `session.pop('active_room')`. If the SSE stream is running, it still has the old `code` in its closure. The generator will continue polling for the now-deleted room, eventually emitting `{closed: true}` when the room row is gone (line 490). This is actually correct behavior, but only because the delete happens before the session pop. If the order were reversed, there'd be a window where a new room could get the same pairing code.

**Prevention:** Keep the current order: delete room rows first, then clear session. Don't refactor the order.

---

### Pitfall 13: Provider Singleton Not Thread/Greenlet-Safe

**What goes wrong:** `_provider_singleton` (line 68) is a module-level global. Under gevent, multiple greenlets call `get_provider()` concurrently. The `JellyfinLibraryProvider` uses `requests.Session()` (jellyfin_library.py line 44) which is documented as not thread-safe for concurrent requests. Under high concurrency, response data from one greenlet's request could leak into another's.

**Prevention:** Use `gevent.lock.Semaphore` around provider calls, or create per-request provider instances, or use `requests.Session` per-greenlet via thread-local storage (which gevent monkey-patches to be greenlet-local).

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation | Phase to Address |
|-------------|---------------|------------|-----------------|
| Server-side identity (session → Jellyfin user_id) | Dual-ID migration orphans swipes (#3) | Add `jellyfin_user_id` column; dual-write period | First phase — identity foundation |
| HttpOnly session cookies | EventSource can't send headers (#4) | SSE authenticates via cookie only | Same phase as identity |
| HttpOnly session cookies | Existing clients break without migration bridge (#6) | Dual-read period + `/auth/migrate-session` | First phase — must ship before old auth removed |
| Server-owned deck | Client/server state divergence (#8) | Server tracks position; client renders server order | Deck phase |
| Server-owned match notification | TOCTOU race in SQLite (#2) | `BEGIN IMMEDIATE` transaction | Match logic phase |
| SSE restructuring | Generator session context loss (#1) | Keep generator context-free; pass data as args | SSE phase (late, after other changes stabilize) |
| SSE restructuring | Reconnection replay (#10) | Reset `lastSeenMatchTs` on reconnect | SSE phase |
| Session cookie security | ProxyFix + Secure flag (#7) | Verify in Docker deployment test | Final phase — deployment validation |
| Session writes under gevent | Last-write-wins cookie loss (#5) | Minimize session writes; consider server-side sessions | Identity phase (design) + SSE phase (validation) |
| CSP + template refactor | Inline handlers break (#9) | Migrate to addEventListener | Template phase |

---

## gevent-Specific Session Concerns

### Greenlet-Local vs Thread-Local

With `monkey.patch_all()`, Python's `threading.local()` becomes greenlet-local. Flask's request context uses Werkzeug's `LocalStack`, which is also greenlet-aware under gevent. This means:

1. **Session access is safe per-greenlet** — each SSE connection gets its own request context.
2. **Module-level state is shared** — `_token_user_id_cache`, `_provider_singleton` are shared across all greenlets. No synchronization exists.
3. **SQLite connections are safe** — `get_db()` creates a new connection per call, not shared.

### Session Cookie Size Under gevent

Flask's default signed-cookie sessions have a practical size limit (~4KB). If the refactoring stores more data in the session (Jellyfin token, user_id, room code, solo mode, etc.), the cookie could exceed browser limits. Monitor session size during development.

---

## Migration Risk Matrix

| Data Being Migrated | Risk Level | Rollback Complexity | Data Loss Risk |
|---------------------|------------|-------------------|----------------|
| `localStorage` → session cookie (auth token) | **High** | Medium — need to keep dual-read | No data loss, but sessions break without migration bridge |
| `host_`/`guest_` IDs → Jellyfin user_id in swipes | **High** | Hard — requires re-mapping old swipes | Existing match history becomes unreachable |
| Client deck order → server deck order | **Medium** | Easy — revert to client shuffle | No persistent data affected (deck is ephemeral) |
| Client match detection → server match detection | **Low** | Easy — match logic is server-side already | Only concurrent swipe race (#2) |
| Client deep link construction → server deep links | **Low** | Easy — template change only | No data affected |

---

## Sources

- Flask session concurrency warning: [Flask API docs — `SessionInterface`](https://flask.palletsprojects.com/api/#flask.sessions.SessionInterface) — "Multiple requests with the same session may be sent and handled concurrently."
- Flask streaming session caveat: [Flask API docs — `stream_with_context`](https://flask.palletsprojects.com/api/#flask.stream_with_context) — "Do not modify the session in the generator."
- Flask cookie security: [Flask web security docs](https://flask.palletsprojects.com/security/) — `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY`, `SESSION_COOKIE_SAMESITE`.
- gevent greenlet isolation: [gevent docs — monkey patching](https://gevent.readthedocs.io/en/stable/monkey.html) — thread-local storage becomes greenlet-local.
- Codebase: `jellyswipe/__init__.py`, `jellyswipe/templates/index.html`, `jellyswipe/db.py`, `jellyswipe/jellyfin_library.py` (direct analysis).
- Existing concerns: `.planning/codebase/CONCERNS.md` — SSE polling loop, CSRF, session safety.
- Confidence: **HIGH** — all pitfalls derived from codebase analysis verified against official Flask/gevent documentation.
