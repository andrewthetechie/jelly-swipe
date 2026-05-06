---
phase: 39-room-swipe-match-and-sse-persistence-conversion
plan: "01"
subsystem: database
tags: [sqlite, sqlalchemy, alembic, async, repositories, rooms, matches, swipes]

requires:
  - phase: 37-async-database-infrastructure
    provides: async SQLAlchemy runtime, `DatabaseUnitOfWork`, Alembic-backed test bootstrap
  - phase: 38-auth-persistence-conversion
    provides: request-scoped UoW pattern and auth-session repository precedent
provides:
  - shared `room_types` dataclasses for room, status, stream, match, and swipe-counterparty payloads
  - async `RoomRepository`, `SwipeRepository`, and `MatchRepository` modules
  - `DatabaseUnitOfWork` registry for `rooms`, `swipes`, and `matches`
  - repository parity tests independent of room routes
affects: [39-02, 39-03, 39-04, room-routes, sse]

tech-stack:
  added: []
  patterns:
    - thin async repositories on `AsyncSession` with SQLAlchemy Core/ORM only (no string-built SQL)
    - SQLite `matches.rowid` exposed as `MatchRecord.match_order` for deterministic newest-active ordering
    - JSON persistence columns stay raw strings in `RoomRecord`; status snapshots parse `last_match_data` to `dict | None`

key-files:
  created:
    - jellyswipe/room_types.py
    - jellyswipe/repositories/__init__.py
    - jellyswipe/repositories/rooms.py
    - jellyswipe/repositories/swipes.py
    - jellyswipe/repositories/matches.py
    - tests/test_repositories.py
  modified:
    - jellyswipe/db_uow.py

key-decisions:
  - "`SwipeRepository` lives under `jellyswipe.repositories.swipes`; `delete_orphans()` remains available for bootstrap maintenance alongside swipe match helpers."
  - "Match newest-active selection orders by SQLite `rowid` descending so downstream `last_match_data.ts` rebuilds can reuse a stable persisted token."

patterns-established:
  - "Room-domain reads return `RoomRecord` / snapshot types; mutations return affected row counts as `int`."
  - "Session-aware swipe counterparty lookup excludes the caller session when present, otherwise uses `user_id` inequality."

requirements-completed: [MVC-02, MVC-03]

duration: 12 min
completed: "2026-05-06T22:33:28Z"
---

# Phase 39 Plan 01: Room Domain Repository Foundation Summary

**Typed async repositories for rooms, swipes, and matches plus shared `room_types` contracts, all registered on `DatabaseUnitOfWork` and covered by standalone parity tests.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-05-06T22:21:00Z
- **Completed:** 2026-05-06T22:33:28Z
- **Tasks:** 2
- **Files touched:** 7

## Accomplishments

- Added `jellyswipe/room_types.py` with `RoomRecord`, `RoomStatusSnapshot`, `StreamSnapshot`, `MatchRecord`, and `SwipeCounterparty` (`@dataclass(slots=True)`).
- Implemented `RoomRepository`, `SwipeRepository` (including `delete_orphans` for existing bootstrap callers), and `MatchRepository` with archive-to-`HISTORY` semantics and `rowid`-based `match_order`.
- Wired `self.rooms`, `self.swipes`, and `self.matches` on `DatabaseUnitOfWork`.
- Added `tests/test_repositories.py` exercising create/status round-trip, match active/history/archive ordering, and swipe counterparty session vs. user fallback.

## Verification

- `uv run python -c "from jellyswipe.room_types import RoomRecord, RoomStatusSnapshot, StreamSnapshot, MatchRecord, SwipeCounterparty; ..."` — exit 0
- `uv run pytest tests/test_repositories.py -q` — **3 passed**

## Task Commits

Single atomic delivery commit (types, repositories, UoW wiring, tests) plus a documentation commit for this summary (see git log with `39-01`).

## Files Created/Modified

- `jellyswipe/room_types.py` — cross-layer room-domain dataclasses (D-13).
- `jellyswipe/repositories/rooms.py` — room CRUD, status fetch, deck/genre updates.
- `jellyswipe/repositories/swipes.py` — counterparty lookup, room/movie/session deletes, orphan cleanup.
- `jellyswipe/repositories/matches.py` — active/history lists, archive, deletes, `latest_active_for_room`.
- `jellyswipe/repositories/__init__.py` — package exports.
- `jellyswipe/db_uow.py` — registers room-domain repositories.
- `tests/test_repositories.py` — Alembic-backed async parity tests.

## Decisions Made

None beyond the plan — followed D-13 payload contracts and Phase 36 JSON-as-text persistence for room columns.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Repository seams are stable for Plan 39-02+ (service and route migration off raw SQL). `DatabaseUnitOfWork` exposes `rooms`, `swipes`, and `matches` as required.

## Self-Check: PASSED

- Task 1 acceptance: `room_types` classes present; import smoke test passes.
- Task 2 acceptance: repository classes and UoW wiring present; tests import `jellyswipe.room_types` and call `archive_active_for_room` / `find_other_right_swipe`; pytest green.
- Plan `<verification>`: repository tests run; UoW exposes new repositories.

---
*Phase: 39-room-swipe-match-and-sse-persistence-conversion*
*Completed: 2026-05-06*
