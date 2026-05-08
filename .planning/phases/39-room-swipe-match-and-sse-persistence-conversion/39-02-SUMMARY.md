---
phase: 39-room-swipe-match-and-sse-persistence-conversion
plan: "02"
subsystem: application
tags: [async, rooms, service-layer, mvc]

requires:
  - plan: "39-01"
    provides: async room/swipe/match repositories on `DatabaseUnitOfWork`

provides:
  - `RoomLifecycleService` for create/join/quit/deck/genre/status/`get_matches`
  - async non-swipe room routes delegating to the service plus `DBUoW`

affects:
  - routes: `/room`, `/room/solo`, join/quit/deck/genre/status, `/matches` (reads)

tech-stack:
  patterns:
    - thin routers; request-scoped UoW commit boundary unchanged (`get_db_uow`)

requirements-completed:
  [MVC-02, MVC-04, PAR-02]

completed: "2026-05-06"
---

# Phase 39 Plan 02: Room lifecycle service migration

**Non-swipe room flows now use `RoomLifecycleService` atop async repositories while swipe, undo, delete-match, and SSE routes stay on their legacy paths.**

## Verification

- `uv run pytest tests/test_room_lifecycle.py -q` — **4 passed**
- `uv run pytest tests/test_room_lifecycle.py tests/test_routes_room.py tests/test_route_authorization.py tests/test_routes_xss.py tests/test_error_handling.py -q -k "room or deck or solo or active_room or matches or history or xss or error" --no-cov` — **107 passed**

## Files

- Added `jellyswipe/services/room_lifecycle.py` (`RoomLifecycleService`, `UniqueRoomCodeExhaustedError`)
- Added `jellyswipe/services/__init__.py`
- Added `tests/test_room_lifecycle.py`
- Updated `jellyswipe/routers/rooms.py` — async controllers for lifecycle routes; `swipe`/undo/delete/SSE untouched

## Deviances

None material — FastAPI signatures use `uow` before defaulted `Depends(require_auth)` to satisfy Python 3 argument ordering.

## Next

Plan **39-03**: `SwipeMatchService` for swipe/undo/match-delete paths.
