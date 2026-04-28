# Project Research Summary

**Project:** Jelly Swipe v2.0 — Architecture Tier Fix
**Domain:** Flask + SQLite + SSE (gevent) collaborative swipe-matching app
**Researched:** 2026-04-26
**Confidence:** HIGH

## Executive Summary

Jelly Swipe is a self-hosted collaborative movie-swiping app that pairs with a Jellyfin media server. Research identified 7 specific tier responsibility violations where the client performs work that belongs on the server — from storing auth tokens in `localStorage` to constructing broken Plex deep links instead of Jellyfin URLs. The recommended fix is a server-owned identity vault: after authentication, the Jellyfin token is stored in a new `user_tokens` SQLite table keyed by session ID, and the client receives only an opaque `session_id` in Flask's built-in signed cookie. This eliminates token exposure to client-side JavaScript while requiring only one new dependency (`flask-session` considered but rejected in favor of a leaner custom approach using the existing SQLite database).

The migration must be carefully sequenced because the current codebase has two parallel identity systems (`host_`/`guest_` synthetic IDs for swipes vs. Jellyfin UUIDs for matches). Switching to a single identity will orphan existing swipes if not handled with a dual-write transition period. The biggest technical risk is the SSE generator under gevent — Flask explicitly warns against reading or modifying `session` inside streaming generators, and the current code correctly captures values by closure. The refactoring must preserve this context-free generator pattern while passing identity data as arguments from the view function.

## Key Findings

### Recommended Stack

Only one new concept is needed: a `user_tokens` SQLite table for storing Jellyfin tokens server-side. No new Python packages are required. Flask's built-in signed cookie session (`SecureCookieSessionInterface`) is sufficient because the session only holds a `session_id` (~100 bytes total). The actual sensitive data lives in SQLite, which is a domain-specific concern better suited to a custom table than a generic Flask-Session backend.

**Core technologies (existing, no changes):**
- **Flask >=3.1.3** — Session signing, SSE streaming, RESTful routing — all built-in
- **gevent >=24.10** — Cooperative I/O for SSE; filesystem I/O is safe under monkey patching
- **SQLite (stdlib)** — New `user_tokens` table alongside existing `rooms`/`swipes`/`matches` tables
- **requests >=2.33.1** — Jellyfin API client, unchanged

**NOT recommended:**
- **Flask-Session** — Adds a cachelib/filesystem abstraction when the session cookie only needs to hold `session_id` + `active_room` (~100 bytes). The sensitive token goes in a custom SQLite table, which is simpler and more consistent with the existing codebase that uses raw `sqlite3`.
- **Flask-Login** — Requires a User model; Jelly Swipe identity comes from Jellyfin, not a local user table.
- **Redis** — External service dependency, overkill for a self-hosted single-server Docker app.

### Expected Features

**Must have (table stakes — all P1):**
- Server-side token storage — tokens never leave the server, stored in `user_tokens` table
- Server-owned user identity — single canonical `user_id` from Jellyfin, resolved once at login
- RESTful endpoint restructuring — `/room/{code}/swipe`, `/room/{code}/deck`, etc.
- Server-owned deck composition + order — client never re-shuffles or re-fetches independently
- Single-channel match notification — SSE-only match popups, not dual HTTP+SSE paths
- Correct Jellyfin deep links — `{JELLYFIN_URL}/web/#/details?id={itemId}` from server
- Full match metadata — `rating`, `duration`, `year`, `deep_link` in match responses
- Solo mode as per-user session flag — not a room-level property

**Should have (v2.1 hardening):**
- Server-side deck cursor — per-user position tracking prevents deck manipulation
- Idempotent swipe processing — `UNIQUE(room_code, movie_id, user_id)` constraint
- ADR documenting tier responsibilities — prevents future violations

**Defer (v3+):**
- WebSocket upgrade (replacing SSE)
- Multi-device session support
- Playback status integration

### Architecture Approach

The architecture introduces a "token vault" pattern: a new `user_tokens` SQLite table maps `session_id → (jellyfin_token, jellyfin_user_id)`. A `@login_required` decorator reads the session cookie, looks up the token vault, and populates `g.user_id` + `g.jf_token` for every authenticated request. The SSE generator remains context-free — all session values are captured in the view function and passed as closure arguments. Route structure moves to RESTful patterns with room code in the URL path rather than session.

**Major components:**
1. **`auth.py` (NEW)** — Token vault CRUD, `create_session()`, `get_current_token()`, `@login_required` decorator
2. **`__init__.py` (MODIFIED)** — Routes refactored to RESTful patterns, identity from `g.user_id` instead of client headers
3. **`db.py` (MODIFIED)** — New `user_tokens` table, `rooms.deck_position` column, `matches.deep_link` column
4. **`templates/index.html` (SIMPLIFIED)** — Remove token storage, identity headers, match detection from swipe response, deep link construction

### Critical Pitfalls

1. **SSE generator session context loss** — Never read `session` inside the SSE `generate()` function. Pass all values as arguments from the view function. Flask docs explicitly warn against this; violations cause silent 500 errors that kill the match notification stream. *(PITFALLS.md #1)*

2. **Match detection TOCTOU race in SQLite** — Two simultaneous right-swipes on the same movie can silently miss a match because the check-then-insert is not wrapped in `BEGIN IMMEDIATE`. Fix: wrap swipe+match logic in an explicit transaction. *(PITFALLS.md #2)*

3. **Dual identity migration orphans existing swipes** — Current code uses `host_`/`guest_` synthetic IDs in `swipes` and Jellyfin UUIDs in `matches`. Switching to Jellyfin-only IDs makes old swipes unreachable. Fix: dual-write period with a `jellyfin_user_id` column added alongside the existing `user_id`. *(PITFALLS.md #3)*

4. **EventSource cannot send Authorization headers** — The browser `EventSource` API only sends cookies, never custom headers. SSE endpoint must authenticate via session cookie, never `Authorization` header. *(PITFALLS.md #4)*

5. **Session cookie last-write-wins under gevent** — Flask's signed-cookie session is a single blob; concurrent requests from the same browser can silently overwrite each other's session changes. Mitigation: minimize session writes (set identity/room once, never modify during SSE lifecycle). *(PITFALLS.md #5)*

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Database Schema + Token Vault
**Rationale:** All other changes depend on the `user_tokens` table and schema migration. This is the foundation that server-owned identity builds on. Additive-only schema changes have the lowest risk.
**Delivers:** `user_tokens` table, `rooms.deck_position` column, `matches.deep_link` column, migration script
**Addresses:** Features 2 (server-side token storage), prerequisites for Features 1, 3, 5, 6, 8
**Avoids:** Pitfall #3 (dual identity orphans) — new columns added alongside existing ones, no data loss
**Stack:** SQLite schema migration only, no new packages

### Phase 2: Auth Module + Server-Owned Identity
**Rationale:** Once the token vault exists, the auth module can store tokens and resolve user identity. This unblocks all downstream features that depend on server-owned identity. Must include a dual-read migration period for existing clients.
**Delivers:** `auth.py` with `create_session()`, `get_current_token()`, `@login_required`; refactored login/delegate routes; client migration bridge
**Addresses:** Features 1 (server-owned identity), 2 (server-side token storage), 8 (solo mode as user property)
**Avoids:** Pitfall #4 (EventSource can't send headers) — auth via session cookie only; Pitfall #5 (last-write-wins) — minimize session writes
**Stack:** Flask built-in session, SQLite user_tokens table
**Research flag:** Delegate mode (two browsers, same Jellyfin account) needs careful design — the `session_id` disambiguator pattern should be validated during planning

### Phase 3: RESTful Endpoint Restructuring + Server-Owned Deck
**Rationale:** With identity stable in `g.user_id`, routes can be refactored to RESTful patterns with room code in the URL. Deck ownership moves server-side at the same time since both require route changes and client-side URL updates.
**Delivers:** All routes refactored to `/room/{code}/...` pattern, server-tracked `deck_position`, genre changes through server
**Addresses:** Features 3 (server-owned deck), 7 (RESTful endpoints)
**Avoids:** Pitfall #8 (deck state divergence) — server tracks position, client renders server order
**Stack:** Flask URL converters, SQLite schema changes
**Research flag:** Deck state edge cases (empty deck, reconnect resume, mid-session genre change) need detailed planning

### Phase 4: Match Notification + Deep Links + Metadata
**Rationale:** Match logic depends on stable identity (Phase 2) and RESTful routes (Phase 3). Deep links and metadata enrichment are independent but naturally group with match changes since they affect the same code paths.
**Delivers:** Unified SSE-only match notifications, server-generated Jellyfin deep links, enriched match metadata
**Addresses:** Features 4 (single-channel match), 5 (correct deep links), 6 (full match metadata)
**Avoids:** Pitfall #1 (SSE generator context loss) — generator stays context-free; Pitfall #2 (TOCTOU race) — wrap in `BEGIN IMMEDIATE`
**Stack:** Flask SSE, SQLite transactions, Jellyfin URL format

### Phase 5: Client Simplification + Cleanup
**Rationale:** Client changes are subtractive — removing token storage, identity headers, match detection from swipe responses, deep link construction. Must come last because all server-side changes must be stable first.
**Delivers:** Stripped-down client with no token handling, no identity headers, no match detection, no URL construction
**Addresses:** All features (client side of each), anti-features list
**Avoids:** Pitfall #6 (migration bridge) — dual-read period ensures smooth transition; Pitfall #9 (CSP + inline handlers) — migrate to addEventListener during cleanup
**Stack:** Vanilla JS, no new dependencies

### Phase 6: Deployment Validation + ADR
**Rationale:** Final validation that the entire flow works end-to-end in Docker, cookie security is correct behind reverse proxies, and the tier responsibility decisions are documented for future developers.
**Delivers:** Docker volume mount for sessions, ProxyFix verification, ADR document
**Avoids:** Pitfall #7 (SameSite + HTTPS termination) — verify in actual deployment
**Stack:** Docker, existing gunicorn config

### Phase Ordering Rationale

- **Identity before everything else:** Server-owned identity (Phase 2) is a hard dependency for RESTful routes, solo mode, and match notification. It must come first because downstream features read `g.user_id`.
- **Schema before logic:** Phase 1 (schema migration) is additive-only and has zero risk of breaking existing functionality. It creates the tables and columns that Phase 2 populates.
- **Routes before deck:** Phase 3 combines RESTful restructuring with deck ownership because both require coordinated server+client URL changes. Doing them together avoids touching the same files twice.
- **Match logic after identity + routes:** Match notification depends on correct identity resolution and the new route structure. Deep links and metadata naturally group here since they affect the match/deck responses.
- **Client cleanup last:** The client simplification is purely subtractive. It must come after all server-side changes are stable because the client needs to work with both old and new server endpoints during the migration window.

### Research Flags

**Phases needing deeper research during planning:**
- **Phase 2:** Delegate mode identity disambiguation — two browsers with the same Jellyfin account need a reliable `session_id`-based disambiguator for room operations. The research identified this as a gap; the exact implementation (separate `swipes.user_session_id` column? room participant list?) needs design during planning.
- **Phase 3:** Deck cursor resume-on-reconnect behavior — if a user reloads mid-session, the server must serve cards from `deck_position` without re-shuffling. Edge cases around concurrent swipes advancing the cursor need careful specification.
- **Phase 4:** `BEGIN IMMEDIATE` transaction pattern for swipe+match atomicity — need to verify that this works correctly with gevent's cooperative I/O and the existing `get_db()` connection-per-request pattern.

**Phases with standard patterns (skip research-phase):**
- **Phase 1:** Additive SQLite schema migration — well-documented, no research needed
- **Phase 5:** Client JS simplification — purely subtractive, no new patterns
- **Phase 6:** Deployment validation — standard Docker/nginx configuration

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Only one new concept (user_tokens table); all existing deps verified compatible. STACK.md and ARCHITECTURE.md agree on keeping existing deps unchanged. |
| Features | HIGH | 8 P1 features with clear dependency graph and direct codebase line references. Jellyfin deep link format verified from jellyfin-web source code. |
| Architecture | HIGH | Token vault pattern validated against Flask docs (Context7). SSE+session compatibility confirmed. Migration path mapped phase-by-phase with risk levels. |
| Pitfalls | HIGH | 13 pitfalls identified with exact line references in codebase. All critical pitfalls verified against Flask/gevent official documentation. |

**Overall confidence:** HIGH

### Gaps to Address

- **Delegate mode identity:** The research recommends using `session_id` as a disambiguator when two browsers share the same Jellyfin account, but the exact schema (new column? separate participant tracking table?) is unresolved. This needs design during Phase 2 planning.
- **Session cookie size:** Flask's signed-cookie session has a ~4KB practical limit. The research estimates ~100 bytes for `session_id` + `active_room`, but if additional flags are added (solo_mode, preferences), the size should be monitored during development.
- **Provider singleton thread safety:** `_provider_singleton` is a module-level global shared across gevent greenlets. `requests.Session()` is not thread-safe. This is a pre-existing issue, not introduced by v2.0, but the refactoring may exacerbate it if auth lookups increase provider usage. Low priority but should be tracked.

### Architectural Tension: STACK.md vs. ARCHITECTURE.md

STACK.md recommends Flask-Session (cachelib/filesystem backend) for server-side session storage. ARCHITECTURE.md recommends against Flask-Session in favor of a custom `user_tokens` SQLite table with Flask's built-in signed cookies.

**Recommendation: Follow ARCHITECTURE.md's approach.** The custom SQLite token vault is simpler, more consistent with the existing codebase (which uses raw `sqlite3` throughout), and avoids adding a dependency. Flask's built-in signed cookie only needs to hold `session_id` + `active_room` — well under the 4KB limit. Flask-Session's cachelib/filesystem backend would add an unnecessary abstraction layer for what is fundamentally a domain-specific data concern.

## Sources

### Primary (HIGH confidence)
- Flask session docs (Context7, `/pallets/flask`) — signed cookie behavior, streaming session caveats, cookie security config
- Flask-Session docs (Context7, `/pallets-eco/flask-session`) — server-side backends, cachelib configuration, deprecated `filesystem` backend
- Flask streaming docs (Context7) — "access session in view function, not in generator" warning
- Gevent docs (Context7, `/gevent/gevent`) — monkey patching, cooperative I/O, greenlet-local storage
- Jellyfin Web source code — `RootAppRouter.tsx` (hash-based routing), `user.ts` routes (`details` path), `BangRedirect.tsx`
- Jellyfin API (Context7) — `AuthenticationResult` schema, `/Users/AuthenticateByName` endpoint

### Secondary (HIGH confidence — direct codebase analysis)
- `jellyswipe/__init__.py` (563 lines) — route handlers, identity resolution, SSE generator, session usage
- `jellyswipe/templates/index.html` (1072 lines) — client identity headers, Plex deep links, match popup triggers
- `jellyswipe/db.py` (52 lines) — schema with `rooms`, `swipes`, `matches` tables
- `jellyswipe/jellyfin_library.py` (482 lines) — provider auth, deck fetch, item resolution

---
*Research completed: 2026-04-26*
*Ready for roadmap: yes*
