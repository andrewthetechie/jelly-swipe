# Phase 26: Match Notification + Deep Links + Metadata - Context

**Gathered:** 2026-04-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Unified SSE-only match delivery, enriched match metadata (rating, duration, year), Jellyfin deep link generation, GET /me endpoint, POST /room/solo endpoint, and SQLite transaction safety for match detection.

**Requirements:** MTCH-01 (SSE-only match), MTCH-02 (enriched metadata), MTCH-03 (BEGIN IMMEDIATE), API-02 (Jellyfin deep links), API-03 (GET /me), API-04 (POST /room/solo)

**Depends on:** Phase 25 (RESTful routes and server-owned identity in place)

</domain>

<decisions>
## Implementation Decisions

### Match Notification Channel
- **D-01:** Swipe endpoint returns `{accepted: true}` always — no match payload in the HTTP response. Match notification (title, thumb, metadata, deep_link) goes only via SSE to BOTH users. The swiper gets visual feedback from card animation; match popup comes from SSE.
- **D-02:** The SSE match event includes full metadata: `{type: "match", title, thumb, movie_id, rating, duration, year, deep_link}`. Client renders the popup from this event alone.

### Deep Link Format
- **D-03:** Jellyfin deep link format: `{JELLYFIN_URL}/web/#/details?id={itemId}`. Verified from jellyfin-web source code.
- **D-04:** Deep link included in BOTH the SSE match event AND the GET matches endpoint responses. Client just renders the server-provided link.
- **D-05:** Deep link stored in `matches.deep_link` column at match creation time.

### Solo Mode
- **D-06:** `POST /room/solo` creates a solo room directly — no join step, no partner expected. Room has `solo_mode=1` and `ready=1` set at creation.
- **D-07:** Solo is a room-level concept (not user/session-level). Same room table, different creation path. No "convert to solo" from a two-player room.

### GET /me Endpoint
- **D-08:** `GET /me` returns `{userId, displayName, serverName, serverId}`. Enough for client to show "Connected as X on Server Y". Requires `@login_required`.

### Match Metadata
- **D-09:** Match responses enriched with `rating`, `duration`, `year` via server-side join through movies data. The server resolves these from the Jellyfin item metadata at match creation time.
- **D-10:** Metadata stored in `matches` table columns (added in Phase 23) at match creation.

### Transaction Safety
- **D-11:** Match check-and-insert wrapped in `BEGIN IMMEDIATE` transaction to prevent TOCTOU race where two concurrent right-swipes could miss creating a match. The swipe endpoint is the critical section.

### the agent's Discretion
- Exact SSE event format for match notifications
- How to resolve enriched metadata (from stored movie_data JSON vs Jellyfin API call)
- Server info fields for /me response

</decisions>

<canonical_refs>
## Canonical References

### Phase requirements and research
- `.planning/REQUIREMENTS.md` §Match & Notification — MTCH-01, MTCH-02, MTCH-03; §RESTful API — API-02, API-03, API-04
- `.planning/ROADMAP.md` §Phase 26 — Success criteria and plan outline
- `.planning/research/SUMMARY.md` §Expected Features — Single-channel match notification, Jellyfin deep links
- `.planning/research/FEATURES.md` — Feature landscape with deep link format verified from jellyfin-web source
- `.planning/research/PITFALLS.md` — TOCTOU race in match detection, SSE generator caveats

### Existing codebase
- `jellyswipe/__init__.py:310-378` — Current `/room/swipe` with match detection logic
- `jellyswipe/__init__.py:380-393` — Current `/matches` endpoint
- `jellyswipe/__init__.py:467-521` — Current `/room/stream` SSE generator
- `jellyswipe/__init__.py:286-295` — Current `/room/go-solo` (being replaced)

### Prior phase decisions
- `.planning/phases/23-database-schema-token-vault/23-CONTEXT.md` — matches.deep_link, matches.rating, matches.duration, matches.year columns added
- `.planning/phases/24-auth-module-server-identity/24-CONTEXT.md` — g.user_id, @login_required
- `.planning/phases/25-restful-routes-deck-ownership/25-CONTEXT.md` — RESTful route patterns

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `jellyswipe/__init__.py:347-378` — Match detection logic (check for other_swipe, insert matches, update last_match_data). Core algorithm is correct, needs SSE-only adaptation + transaction safety.
- `jellyswipe/__init__.py:467-521` — SSE generator already pushes `last_match` events. This is the correct channel — just needs enriched payload.
- `jellyswipe/jellyfin_library.py` — `resolve_item_for_tmdb()` returns item with title, year, rating, duration — source for enriched metadata

### Established Patterns
- `last_match_data` JSON on rooms table drives SSE match events — this pattern stays
- `INSERT OR IGNORE INTO matches` handles duplicate match prevention — stays with BEGIN IMMEDIATE wrapper
- SSE generator polls SQLite every 1.5s, emits JSON when state changes

### Integration Points
- Swipe endpoint must stop returning match data in HTTP response
- SSE match event payload must include deep_link + metadata
- Matches endpoint must join through movie data for enriched fields
- Solo room creation reuses `create_room()` logic with different flags

</code_context>

<specifics>
## Specific Ideas

- The deep link format `{JELLYFIN_URL}/web/#/details?id={itemId}` is verified from jellyfin-web source — not guessed
- Rich metadata can be resolved from the stored `movie_data` JSON in rooms table (contains all movie fields) rather than making a Jellyfin API call at match time
- The TOCTOU race is in the current code at `__init__.py:358-375` — `SELECT` then `INSERT` without transaction isolation

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 26-match-notification-deep-links*
*Context gathered: 2026-04-26*
