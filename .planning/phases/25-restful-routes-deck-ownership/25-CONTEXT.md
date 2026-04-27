# Phase 25: RESTful Routes + Deck Ownership - Context

**Gathered:** 2026-04-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Restructure Flask routes to RESTful patterns with room code in URL path (e.g., `POST /room/{code}/swipe`). Server owns deck composition and shuffle order — client never re-fetches or re-shuffles. Per-user deck cursor tracking for reconnect support.

**Requirements:** API-01 (POST /room/{code}/swipe with movie_id + direction only), DECK-01 (server owns deck), DECK-02 (server tracks cursor)

**Depends on:** Phase 24 (stable server-owned identity via g.user_id)

</domain>

<decisions>
## Implementation Decisions

### Route Migration Strategy
- **D-01:** Big switch — all routes migrated at once. Old route patterns removed, new RESTful routes active. Client must update in Phase 27 to match new endpoints. Acceptable that app is broken between Phase 25 and Phase 27 — no active users during development.
- **D-02:** New route patterns:
  - `POST /room` → create room (was `/room/create`)
  - `POST /room/{code}/join` → join room (was `/room/join` with body code)
  - `POST /room/{code}/swipe` → swipe (was `/room/swipe`)
  - `GET /room/{code}/deck` → get movies (was `/movies`)
  - `POST /room/{code}/genre` → set genre (was `/movies?genre=X`)
  - `GET /room/{code}/status` → room status (was `/room/status`)
  - `GET /room/{code}/stream` → SSE stream (was `/room/stream`)
  - `POST /room/{code}/quit` → quit room (was `/room/quit`)
  - `POST /room/{code}/undo` → undo swipe (was `/undo`)

### Deck Order Persistence
- **D-03:** Keep full JSON array in `movie_data` column (existing pattern). Server generates shuffle at room creation, stores once. Client receives cards from server without re-shuffling.
- **D-04:** Client never calls `/movies` to re-fetch or trigger a new deck fetch. Genre change still triggers server-side re-fetch of the full deck (existing behavior).

### Cursor Tracking
- **D-05:** Per-user JSON map in `rooms.deck_position` — e.g., `{"user_id_1": 5, "user_id_2": 3}`. On reconnect, user resumes at their stored index in the deck.
- **D-06:** Cursor advances when user swipes (not when they view). The deck endpoint returns cards starting from the user's cursor position.

### Swipe Endpoint
- **D-07:** `POST /room/{code}/swipe` accepts `{movie_id, direction}` only. No title, thumb, or metadata parameters.
- **D-08:** Room code comes from URL path, not session. Session still stores `active_room` for convenience but URL path is authoritative.

### Deck Delivery
- **D-09:** Deck endpoint returns paginated results — 20 cards per page from cursor position. Accepts optional `?page=N` query param for subsequent pages. Decks may grow large; pagination ensures the endpoint scales without payload bloat.
- **D-10:** When user reaches end of deck, deck endpoint returns empty array `[]`. Client shows "no more cards" state. No auto-loop or auto-fetch.

### SSE Stream Authentication
- **D-11:** SSE stream route `GET /room/{code}/stream` does NOT require `@login_required`. Room code in URL path serves as access control. Per Phase 24 D-12, the generator remains context-free — no session or vault reads inside the polling loop. No repeated vault lookups on every 1.5s poll cycle.

### Genre Change Endpoint
- **D-12:** `POST /room/{code}/genre` accepts JSON body `{"genre": "Action"}`. Consistent with other POST endpoints that accept JSON payloads.

### the agent's Discretion
- Exact pagination query param format (`?page=2` vs `?offset=20` vs `?cursor=movie_id`)
- Response envelope shape for paginated deck (`{cards: [...], has_more: true}` vs bare array with Link header)
- Whether to include total card count in deck response

</decisions>

<canonical_refs>
## Canonical References

### Phase requirements and research
- `.planning/REQUIREMENTS.md` §RESTful API — API-01 acceptance criteria; §Deck Management — DECK-01, DECK-02
- `.planning/ROADMAP.md` §Phase 25 — Success criteria and plan outline
- `.planning/research/SUMMARY.md` §Expected Features — RESTful endpoint restructuring, server-owned deck
- `.planning/research/ARCHITECTURE.md` §MODIFIED: Routes — Before/after route mapping

### Existing codebase (post-Phase 24)
- `jellyswipe/__init__.py:178-188` — Current `create_room()` route with `@login_required`
- `jellyswipe/__init__.py:215-280` — Current `swipe()` route with `g.user_id`
- `jellyswipe/__init__.py:332-343` — Current `/movies` route (will become `/room/{code}/deck`)
- `jellyswipe/__init__.py:363-417` — Current `/room/stream` SSE route (context-free generator)
- `jellyswipe/auth.py` — `create_session()`, `get_current_token()`, `login_required()`
- `jellyswipe/db.py` — `deck_position` TEXT column on rooms table (added in Phase 23, unused)

### Prior phase decisions
- `.planning/phases/23-database-schema-token-vault/23-CONTEXT.md` — deck_position column added
- `.planning/phases/24-auth-module-server-identity/24-CONTEXT.md` — g.user_id available, @login_required on all mutations, SSE generator must stay context-free (D-12)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `jellyswipe/__init__.py:178-188` — `create_room()` — room creation logic (code generation, deck fetch, DB insert). Already uses `@login_required`.
- `jellyswipe/__init__.py:215-280` — `swipe()` — uses `g.user_id` for swipe INSERT and match queries. Match detection logic will be further refactored in Phase 26.
- Flask `<variable>` URL converters handle `/room/<code>/swipe` patterns natively.
- `jellyswipe/db.py:69-70` — `deck_position` and `deck_order` columns exist on rooms table (TEXT), ready for use.

### Established Patterns
- `with get_db() as conn:` context manager for all DB access
- `session.get('active_room')` for room lookup — URL path replaces this as primary
- `jsonify()` for all API responses
- `g.user_id` and `g.jf_token` populated by `@login_required` (Phase 24)

### Integration Points
- SSE stream currently reads `session.get('active_room')` — new route accepts room code from URL path parameter instead
- Client JS in `templates/index.html` calls all current routes — will update in Phase 27
- Cursor tracking writes to `rooms.deck_position` JSON on each swipe; deck endpoint reads from it

</code_context>

<specifics>
## Specific Ideas

- Route restructuring should maintain the same logical behavior — only URL patterns change
- The `fetch_deck()` call in `create_room()` already does `random.shuffle()` server-side — this is correct and stays
- Paginated deck endpoint should support `?page=N` for fetching cards beyond the initial 20

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 25-restful-routes-deck-ownership*
*Context gathered: 2026-04-27*
