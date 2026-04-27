# Phase 25: RESTful Routes + Deck Ownership - Context

**Gathered:** 2026-04-26
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
- **D-01:** Big switch — all routes migrated at once. Old route patterns removed, new RESTful routes active. Client must update in Phase 27 to match new endpoints.
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

### the agent's Discretion
- Exact genre change endpoint design (query param vs body)
- Whether deck endpoint returns all cards or paginated
- How to handle stale cursor (user at end of deck)

</decisions>

<canonical_refs>
## Canonical References

### Phase requirements and research
- `.planning/REQUIREMENTS.md` §RESTful API — API-01 acceptance criteria; §Deck Management — DECK-01, DECK-02
- `.planning/ROADMAP.md` §Phase 25 — Success criteria and plan outline
- `.planning/research/SUMMARY.md` §Expected Features — RESTful endpoint restructuring, server-owned deck
- `.planning/research/ARCHITECTURE.md` §MODIFIED: Routes — Before/after route mapping

### Existing codebase
- `jellyswipe/__init__.py:274-308` — Current `/room/create`, `/room/join` routes
- `jellyswipe/__init__.py:310-378` — Current `/room/swipe` route
- `jellyswipe/__init__.py:436-447` — Current `/movies` route
- `jellyswipe/__init__.py:467-521` — Current `/room/stream` SSE route

### Prior phase decisions
- `.planning/phases/23-database-schema-token-vault/23-CONTEXT.md` — deck_position column added
- `.planning/phases/24-auth-module-server-identity/24-CONTEXT.md` — g.user_id available, @login_required on all mutations

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `jellyswipe/__init__.py:274-284` — `create_room()` — room creation logic (code generation, deck fetch, DB insert)
- `jellyswipe/__init__.py:310-378` — `swipe()` — match detection logic (will be further refactored in Phase 26)
- Flask `<variable>` URL converters handle `/room/{code}/swipe` patterns natively

### Established Patterns
- `with get_db() as conn:` context manager for all DB access
- `session.get('active_room')` for room lookup — URL path replaces this as primary
- `jsonify()` for all API responses

### Integration Points
- SSE stream reads `session.get('active_room')` — needs to accept room code from URL or session
- Client JS in `templates/index.html` calls all these routes — must update in Phase 27

</code_context>

<specifics>
## Specific Ideas

- Route restructuring should maintain the same logical behavior — only URL patterns change
- The `fetch_deck()` call in `create_room()` already does `random.shuffle()` server-side — this is correct and stays

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 25-restful-routes-deck-ownership*
*Context gathered: 2026-04-26*
