---
phase: 23-database-schema-token-vault
plan: 01
subsystem: database
tags: [sqlite, schema-migration, token-vault, prisma-guards]

# Dependency graph
requires: []
provides:
  - user_tokens table with session_id PK, jellyfin_token, jellyfin_user_id, created_at columns
  - rooms.deck_position and rooms.deck_order nullable TEXT columns
  - matches.deep_link, matches.rating, matches.duration, matches.year nullable TEXT columns
  - Idempotent init_db() with PRAGMA table_info guards for all new columns
affects: [24-auth-module-server-identity, 25-restful-routes-deck-ownership, 26-match-notification-deep-links]

# Tech tracking
tech-stack:
  added: []
  patterns: [additive-only-migration, pragma-table-info-guards]

key-files:
  created: []
  modified:
    - jellyswipe/db.py
    - tests/test_db.py

key-decisions:
  - "Proactively added all v2.0 columns across all tables in one migration pass (per D-04)"
  - "Used separate PRAGMA table_info cursor for match metadata columns since first cursor was consumed"

patterns-established:
  - "Additive-only migration: CREATE TABLE IF NOT EXISTS + PRAGMA table_info + ALTER TABLE ADD COLUMN with guards"

requirements-completed: [AUTH-02]

# Metrics
duration: 6min
completed: 2026-04-27
---

# Phase 23 Plan 01: Database Schema Extension Summary

**user_tokens table + 6 nullable columns added to rooms/matches via idempotent PRAGMA-guarded migration**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-27T05:19:56Z
- **Completed:** 2026-04-27T05:26:08Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 2

## Accomplishments
- Created user_tokens table for server-side Jellyfin token storage (token vault pattern)
- Added deck_position and deck_order columns to rooms table for Phase 25 server-owned deck
- Added deep_link, rating, duration, year columns to matches table for Phase 26 enriched matches
- All 89 tests pass (25 test_db + 64 other), zero regressions
- Migration is fully idempotent — init_db() can be called repeatedly with no errors

## Task Commits

Each task was committed atomically (TDD):

1. **RED: Failing tests for user_tokens + v2.0 columns** - `330bb8e` (test)
2. **GREEN: Implement user_tokens table + column migrations** - `a1e6f68` (feat)

## Files Created/Modified
- `jellyswipe/db.py` - Added user_tokens CREATE TABLE, deck_position/deck_order on rooms, deep_link/rating/duration/year on matches
- `tests/test_db.py` - 8 new tests: user_tokens schema/columns, rooms columns, matches columns, CRUD, isolation update

## Decisions Made
- Used a separate PRAGMA table_info cursor for match metadata columns since the first cursor for matches was consumed by status/user_id checks — ensures all guards see correct column state
- All new columns are nullable TEXT (no NOT NULL, no DEFAULT) per D-02 additive-only safety

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Schema foundation complete for all v2.0 phases
- user_tokens table ready for Phase 24 auth module to populate
- rooms columns ready for Phase 25 server-owned deck
- matches columns ready for Phase 26 match metadata enrichment

---
*Phase: 23-database-schema-token-vault*
*Completed: 2026-04-27*
