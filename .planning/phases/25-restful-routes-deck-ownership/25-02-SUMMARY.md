---
phase: 25-restful-routes-deck-ownership
plan: 02
subsystem: api
tags: [deck, cursor, pagination, flask, sqlite]

# Dependency graph
requires:
  - phase: 25-restful-routes-deck-ownership
    plan: 01
    provides: "RESTful route handlers with /room/{code}/action patterns"
provides:
  - "Server-owned deck cursor tracking via per-user JSON map in rooms.deck_position"
  - "Cursor-based pagination on GET /room/{code}/deck (20 cards per page)"
  - "Cursor advancement on POST /room/{code}/swipe (per D-06)"
  - "Cursor reset on POST /room/{code}/genre (per genre change)"
  - "Cursor initialization for creator, joiner, and solo users"
affects: [26-match-metadata, 27-client-cleanup, frontend]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Per-user cursor map in JSON column", "Server-owned deck pagination with page_size=20"]

key-files:
  created: []
  modified:
    - "jellyswipe/__init__.py"
    - "tests/test_route_authorization.py"

key-decisions:
  - "Deck position stored as JSON map {user_id: int} in rooms.deck_position column"
  - "Cursor advances on swipe (not on view) per D-06"
  - "Genre change resets all users' cursors by setting deck_position to {}"
  - "get_deck now requires @login_required since cursor is user-specific"

patterns-established:
  - "_get_cursor/_set_cursor helpers encapsulate deck_position JSON read/write"
  - "Page-based pagination: cursor_pos + (page-1) * page_size to start offset"

requirements-completed: [DECK-01, DECK-02]

# Metrics
duration: 5min
completed: 2026-04-27
---

# Phase 25 Plan 02: Server-Owned Deck Cursor Tracking Summary

**Server-owned deck composition with per-user cursor tracking in JSON map, 20-card paginated delivery, and cursor advance on swipe**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-27T18:07:07Z
- **Completed:** 2026-04-27T18:11:55Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added `_get_cursor` and `_set_cursor` helper functions for per-user deck position management
- `create_room` initializes creator's cursor to 0 in `deck_position` JSON map
- `join_room` initializes joiner's cursor to 0 (independent of other users)
- `go_solo` ensures cursor entry exists for solo users
- `get_deck` returns 20-card paginated results starting from user's cursor position (added `@login_required`)
- `swipe` advances cursor by 1 after each swipe record insert
- `set_genre` resets all users' cursors by setting `deck_position` to `{}`
- 7 new tests covering all cursor tracking behaviors (117 total tests pass)

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement per-user cursor tracking and pagination** - `11933fc` (feat)
2. **Task 2: Add tests for deck cursor tracking and pagination** - `8a03cdb` (test)

## Files Created/Modified
- `jellyswipe/__init__.py` - Added cursor helpers, pagination in get_deck, cursor init in create/join/solo, cursor advance in swipe, cursor reset in genre (46 additions, 2 deletions)
- `tests/test_route_authorization.py` - Added fetch_deck to FakeProvider, 7 tests in TestDeckCursorTracking class (196 additions)

## Decisions Made
- Deck position stored as JSON map `{user_id: int}` in existing `rooms.deck_position` TEXT column — no schema migration needed
- Cursor advances on swipe only (not on deck view), ensuring user has actively decided on each card before advancing
- `get_deck` now requires `@login_required` because cursor is user-specific
- Genre change resets ALL users' cursors to `{}` — users will be re-initialized to 0 on next `_get_cursor` call

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Server owns deck composition and order (DECK-01) — complete
- Per-user cursor tracking for reconnect (DECK-02) — complete
- Ready for Plan 03 (match metadata enrichment) which builds on authenticated routes and deck system
- Frontend will need to handle paginated deck response (array subset) instead of full deck JSON

## Self-Check: PASSED

All files verified present. All commit hashes verified in git log.
