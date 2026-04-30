---
phase: 27-database-architecture
plan: "01"
subsystem: database
tags: [sqlite, wal, sse, persistent-connection, flask]

# Dependency graph
requires: []
provides:
  - WAL mode enabled in SQLite (PRAGMA journal_mode=WAL + PRAGMA synchronous=NORMAL)
  - Persistent SQLite connection for SSE generator (connection opened once, reused across poll cycles, closed in finally block)
affects: [28-sse-reliability]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - SQLite WAL mode for concurrent read/write without file-lock contention
    - Persistent connection lifecycle in SSE generator (open before loop, close in finally)
    - PRAGMA execution before transaction start (wal mode must be set outside the with-block transaction)

key-files:
  created: []
  modified:
    - jellyswipe/db.py - Added WAL mode PRAGMAs to init_db()
    - jellyswipe/__init__.py - Refactored SSE generator to use persistent connection
    - tests/test_db.py - Added TestWalMode class with 3 WAL assertion tests

key-decisions:
  - "WAL mode PRAGMAs must execute before the with-block transaction — 'cannot change into wal mode from within a transaction'"
  - "Persistent connection opened with raw sqlite3.connect() + row_factory set manually, not via get_db_closing()"
  - "finally: conn.close() guarantees cleanup on GeneratorExit and unhandled exceptions"

patterns-established:
  - "Pattern: WAL mode init — PRAGMA journal_mode=WAL and PRAGMA synchronous=NORMAL execute before schema creation"
  - "Pattern: SSE persistent connection — open conn before while loop, close in finally"

requirements-completed: [DB-01, DB-02]

# Metrics
duration: 8min
completed: 2026-04-30
---

# Phase 27: Database Architecture Summary

**WAL mode enabled in SQLite with persistent SSE generator connection — eliminates file-lock contention and per-cycle connection overhead**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-30T03:49:00Z
- **Completed:** 2026-04-30T03:57:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- WAL mode (PRAGMA journal_mode=WAL) and synchronous=NORMAL set during init_db(), persisting across all subsequent connections
- SSE generator `generate()` now opens one SQLite connection before the poll loop and reuses it for all cycles, closing only at generator exit via `finally`
- TestWalMode class with 3 tests verifying WAL mode, synchronous=NORMAL, and persistence across connection reopens
- Non-SSE routes continue using `get_db_closing()` unchanged

## Task Commits

Each task was committed atomically:

1. **Task 1: Enable WAL mode in init_db() and add WAL assertion test** - `0664520` (feat)
2. **Task 2: Refactor SSE generator to use persistent SQLite connection** - `33668b2` (feat)

**Plan metadata:** `7294c6b` (docs(27): create phase plan — WAL mode + persistent SSE connection)

## Files Created/Modified
- `jellyswipe/db.py` - Added WAL mode PRAGMAs before schema creation; PRAGMAs must be outside the with-block transaction
- `jellyswipe/__init__.py` - Refactored generate() inner function: conn opened before while loop, closed in finally; all payload logic dedented out of with-block
- `tests/test_db.py` - Added TestWalMode class (test_init_db_sets_wal_mode, test_init_db_sets_synchronous_normal, test_wal_mode_persists_across_connections)

## Decisions Made

- WAL mode PRAGMAs must execute before the `with sqlite3.connect(DB_PATH) as conn:` block — SQLite rejects `PRAGMA journal_mode` inside an implicit transaction, so PRAGMAs are now the first statements after acquiring the connection
- Used raw `sqlite3.connect(jellyswipe.db.DB_PATH)` with manual `conn.row_factory = sqlite3.Row` in SSE generator (not `get_db_closing()`) to keep connection persistent for the full stream lifetime
- `finally: conn.close()` guarantees cleanup even when GeneratorExit is raised or an exception occurs mid-poll-cycle

## Deviations from Plan

**1. [Rule 3 - Blocking] WAL PRAGMA execution order**
- **Found during:** Task 1 (Enable WAL mode)
- **Issue:** `sqlite3.OperationalError: cannot change into wal mode from within a transaction` — initial placement was after DELETE inside the with-block transaction
- **Fix:** Moved `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL` to be the first statements after acquiring the connection, before any schema creation or data manipulation
- **Files modified:** jellyswipe/db.py
- **Verification:** All 3 TestWalMode tests pass
- **Committed in:** 0664520 (part of Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Deviation was required for correctness — WAL mode cannot be set within a transaction, so PRAGMAs must execute before the implicit transaction begins.

## Issues Encountered
- WAL mode PRAGMA rejected inside transaction (fixed by moving before with-block body)
- No other issues encountered

## Next Phase Readiness
- WAL mode foundation is solid — Phase 28 (SSE reliability) can proceed
- Persistent SSE connection pattern established — ready for jitter/heartbeat work in Phase 28
- No blockers

---
*Phase: 27-database-architecture*
*Completed: 2026-04-30*
