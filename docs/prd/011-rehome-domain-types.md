# Rehome domain types — eliminate `room_types.py` and `auth_types.py`

## Problem Statement

Two dedicated "types" modules — `jellyswipe/room_types.py` (75 lines, 7 dataclasses) and `jellyswipe/auth_types.py` (13 lines, 1 dataclass) — hold domain-model dataclasses that have no behavioural logic of their own. The files have no interface other than "export everything," and there is no rule that tells a contributor which types belong here versus in `schemas/`, `models/`, or alongside a specific repository.

This creates a concrete navigation problem: when a type needs to change, the contributor must first figure out which file defines it, then trace outward to understand which module gives it meaning. The answer is never in `room_types.py` itself.

A secondary problem is that two of the seven types in `room_types.py` — `SessionInstanceRecord` and `SessionEventRecord` — are dead code. The `session_events` repository, which was supposed to produce them, returns raw SQLAlchemy ORM objects directly and never constructs these records. Nothing imports them.

## Solution

Apply a single placement rule: **a type lives in the module that produces it.** For types returned by repository methods, that is the repository file. This eliminates both dedicated types files and absorbs all surviving types into existing modules, with one net new file to give `AuthSessionRepository` its own home (see Implementation Decisions).

The rule resolves the navigation question: a contributor who wants to understand `MatchRecord` opens `repositories/matches.py`, which is where `MatchRecord` is constructed and where every query that returns one lives.

## User Stories

1. As a developer debugging a field on a `MatchRecord`, I want to open `repositories/matches.py` and find the type definition alongside the query that produces it, so that I do not need to cross-reference a separate types file.
2. As a developer changing `RoomStatusSnapshot`, I want to edit `repositories/rooms.py`, so that the type and the query that builds it are modified in the same diff.
3. As a developer onboarding to the codebase, I want to find any domain type by looking in the module that creates it, so that I have a reliable navigation heuristic from day one.
4. As a developer reading `db_uow.py`, I want it to be a pure aggregator of repositories, so that I do not need to scan it for type definitions or repository implementations.
5. As a developer grepping for `AuthRecord`, I want to land in `repositories/auth_sessions.py`, so that the type and the repository that creates it are co-located.
6. As a developer reviewing a PR, I want type changes and the query changes that necessitate them to appear in the same file, so that the scope of the diff is self-evident.

## Implementation Decisions

### Dead code deletion

`SessionInstanceRecord` and `SessionEventRecord` are removed from `room_types.py` without replacement. No file in the codebase imports either type; the `SessionInstanceRepository` and `SessionEventRepository` return raw SQLAlchemy ORM objects (`SessionInstance`, `SessionEvent`) and never construct these dataclasses.

### Type placement

Each surviving type moves into the repository file that produces it. The dataclass definition is inlined at the top of the target file, above the repository class, replacing the import from `room_types`.

| Type                 | Moves to                                               |
| -------------------- | ------------------------------------------------------ |
| `RoomRecord`         | `repositories/rooms.py`                                |
| `RoomStatusSnapshot` | `repositories/rooms.py`                                |
| `MatchRecord`        | `repositories/matches.py`                              |
| `SwipeCounterparty`  | `repositories/swipes.py`                               |
| `TmdbCacheRecord`    | `repositories/tmdb_cache.py`                           |
| `AuthRecord`         | `repositories/auth_sessions.py` (new file — see below) |

### New file: `repositories/auth_sessions.py`

`AuthSessionRepository` is currently defined inside `db_uow.py`, unlike every other repository which has its own file. `db_uow.py`'s responsibility is to aggregate repositories into a typed unit-of-work facade — defining a repository class there is a structural seam.

A new `repositories/auth_sessions.py` is created containing:

- The `AuthRecord` dataclass (moved from `auth_types.py`)
- The `AuthSessionRepository` class (moved from `db_uow.py`)

`db_uow.py` is updated to import `AuthSessionRepository` from its new location. The `AuthRecord` import in `db_uow.py` is removed. The net file count across the three changes (`-room_types.py`, `-auth_types.py`, `+repositories/auth_sessions.py`) is **−1**.

### Import updates

All call sites are updated to import from the new locations. No re-exports or compatibility shims are added.

| File                                 | Old import                                                         | New import                                                                |
| ------------------------------------ | ------------------------------------------------------------------ | ------------------------------------------------------------------------- |
| `repositories/rooms.py`              | `from jellyswipe.room_types import RoomRecord, RoomStatusSnapshot` | _(definition inlined — import removed)_                                   |
| `repositories/matches.py`            | `from jellyswipe.room_types import MatchRecord`                    | _(definition inlined — import removed)_                                   |
| `repositories/swipes.py`             | `from jellyswipe.room_types import SwipeCounterparty`              | _(definition inlined — import removed)_                                   |
| `repositories/tmdb_cache.py`         | `from jellyswipe.room_types import TmdbCacheRecord`                | _(definition inlined — import removed)_                                   |
| `services/room_lifecycle.py`         | `from jellyswipe.room_types import MatchRecord`                    | `from jellyswipe.repositories.matches import MatchRecord`                 |
| `services/session_match_mutation.py` | `from jellyswipe.room_types import SwipeCounterparty`              | `from jellyswipe.repositories.swipes import SwipeCounterparty`            |
| `routers/auth.py`                    | `from jellyswipe.auth_types import AuthRecord`                     | `from jellyswipe.repositories.auth_sessions import AuthRecord`            |
| `db_uow.py`                          | `from jellyswipe.auth_types import AuthRecord`                     | `from jellyswipe.repositories.auth_sessions import AuthSessionRepository` |

### File deletions

`jellyswipe/room_types.py` and `jellyswipe/auth_types.py` are deleted after all imports are updated.

### No logic changes

Every dataclass definition is moved verbatim. No field names, field types, default values, or `slots=True` annotations change. This is a pure structural move.

### Execution

The entire change is delivered in a single atomic PR. Every change is a mechanical move or import update with no logic delta; the existing test suite catches any wiring mistake immediately. Staged PRs would add overhead without adding safety.

## Testing Decisions

### Test import updates

Three test files import from the deleted modules and must be updated:

| Test file                       | Old import                                                                      | New import                                                     |
| ------------------------------- | ------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| `tests/test_repositories.py`    | `from jellyswipe.room_types import MatchRecord, RoomRecord, RoomStatusSnapshot` | split across `repositories.matches`, `repositories.rooms`      |
| `tests/test_room_lifecycle.py`  | `from jellyswipe.room_types import MatchRecord`                                 | `from jellyswipe.repositories.matches import MatchRecord`      |
| `tests/test_sse_persistence.py` | `from jellyswipe.room_types import RoomStatusSnapshot`                          | `from jellyswipe.repositories.rooms import RoomStatusSnapshot` |
| `tests/test_dependencies.py`    | `from jellyswipe.auth_types import AuthRecord`                                  | `from jellyswipe.repositories.auth_sessions import AuthRecord` |

### No new tests required

This change introduces no new behaviour. The existing test suite exercises every repository, service, and route that uses these types. Passing the full suite after the import updates is the acceptance criterion.

## Out of Scope

- **ORM model changes.** `models/room.py`, `models/match.py`, `models/swipe.py`, `models/auth_session.py`, and `models/session_event.py` are untouched.
- **Schema changes.** Nothing in `schemas/` is affected. The HTTP request/response shapes are unchanged.
- **Type annotation coverage.** `services/room_lifecycle.py` uses `RoomRecord` and `RoomStatusSnapshot` implicitly (through `uow.rooms` return values) without naming them in annotations. Adding explicit annotations is a separate concern and is not required by this PRD.
- **`DatabaseUnitOfWork` interface.** `uow.auth_sessions` continues to expose `AuthSessionRepository` under the same attribute name. No call site changes beyond the import update in `db_uow.py` itself.
- **Session event repositories.** `SessionInstanceRepository` and `SessionEventRepository` remain in `repositories/session_events.py` unchanged.
- **API contract.** All route paths, response shapes, and HTTP status codes are unchanged.

## Further Notes

- **This change is a pure structural move.** No user-visible behaviour changes. The git diff will show: two deleted files, one new file (`repositories/auth_sessions.py`), inline additions to four repository files, and updated imports in three service/router files and four test files.
- **The placement rule.** "A type lives in the module that produces it" is the durable rule this PRD encodes. Future types should not get their own `*_types.py` file — they earn their module by proximity to the code that gives them meaning.
- **Relationship to architecture deepening.** This PRD is independent of PRDs 003, 007, and 010. It can be landed before or after any of them.
