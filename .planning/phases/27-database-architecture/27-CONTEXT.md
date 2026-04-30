# Phase 27: Database Architecture - Context

**Gathered:** 2026-04-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Enable WAL mode in SQLite (`PRAGMA journal_mode=WAL` + `PRAGMA synchronous=NORMAL`) to eliminate file-lock contention, and refactor the SSE generator in `/room/stream` to hold one persistent SQLite connection per client session instead of opening and closing a connection every 1.5-second poll cycle. Non-SSE code paths (`get_db_closing()`) continue to work as before.

**In scope:**
- `init_db()` sets `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL`
- SSE generator opens one SQLite connection at stream start, reuses across all poll cycles, closes on generator exit
- Non-SSE routes continue using `get_db_closing()` (unchanged API)
- All existing tests pass without modification

**Out of scope:**
- SSE jitter, heartbeat, graceful room exit (Phase 28)
- Message bus architecture for `last_match_data` overwrites
- Redis/Postgres migration
- WebSocket migration

</domain>

<decisions>
## Implementation Decisions

### WAL Mode Configuration
- **D-01:** Set `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL` in `init_db()` only — WAL mode persists at the database file level, so subsequent connections inherit it automatically. No need to set PRAGMA on every connection.
- **D-02:** Use `synchronous=NORMAL` alongside WAL — this is the SQLite-recommended setting for WAL mode, reducing disk flushes from every commit to WAL checkpoint intervals while maintaining crash recovery guarantees.

### SSE Persistent Connection
- **D-03:** Manage the persistent SSE connection inline in the `room_stream()` generator — open `sqlite3.connect()` at generator start, close in `finally` block on generator exit. No new `db.py` API surface needed.
- **D-04:** The persistent SSE connection does NOT use `get_db_closing()` — it creates a raw `sqlite3.connect()` with `row_factory = sqlite3.Row` to match the existing pattern, and manages its own lifecycle.
- **D-05:** Non-SSE routes continue using `with get_db_closing() as conn:` exactly as before — no API changes to `db.py` for this phase.

### Test Compatibility
- **D-06:** WAL mode persists across connections for a given database file — existing test fixtures that create temp databases via `create_app(test_config={})` will automatically get WAL mode when `init_db()` runs. No test modifications needed.
- **D-07:** Verify WAL mode is active in a new integration test assertion: after `init_db()`, query `PRAGMA journal_mode` and assert it returns `"wal"`.

### the agent's Discretion
- Exact variable naming in the SSE generator refactored code
- Whether to add a `_set_wal_pragmas(conn)` helper in `db.py` or inline the PRAGMA statements in `init_db()`
- Whether to add a comment explaining the WAL+NORMAL rationale

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v1.7 Requirements
- `.planning/REQUIREMENTS.md` — DB-01 and DB-02 requirements with success criteria

### v1.7 Roadmap
- `.planning/ROADMAP.md` §Phase 27 — Phase boundary, success criteria, dependencies

### Codebase — SSE and DB (MUST read)
- `jellyswipe/__init__.py` lines 622-676 — `/room/stream` SSE endpoint with the per-poll-cycle `get_db_closing()` pattern
- `jellyswipe/db.py` — `get_db()`, `get_db_closing()`, `init_db()` functions to modify
- `jellyswipe/__init__.py` lines 203-213 — DB import and `DB_PATH` setup in `create_app()`

### Prior Phase Context (module pattern reference)
- `.planning/phases/26-rate-limiting/26-CONTEXT.md` — New modules go in `jellyswipe/<module>.py`, imported by `__init__.py`
- `.planning/phases/27-ssrf-protection/27-CONTEXT.md` — Boot-time validation pattern, zero new deps

### Codebase Conventions
- `.planning/codebase/TESTING.md` — pytest patterns, mock conventions, fixture structure
- `tests/conftest.py` — Shared test fixtures (`app`, `client`, `FakeProvider`)

### Integration Points
- `jellyswipe/db.py:10-14` — `get_db()` creates a new connection each call (used by `get_db_closing()` and SSE refactor)
- `jellyswipe/db.py:31-65` — `init_db()` — insertion point for WAL PRAGMA statements
- `jellyswipe/__init__.py:638` — `with get_db_closing() as conn:` inside SSE generator loop — the line to refactor

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`get_db()` in `db.py`**: Creates `sqlite3.connect(DB_PATH)` with `row_factory = sqlite3.Row`. The SSE persistent connection will use the same pattern (raw connect with Row factory).
- **`get_db_closing()` context manager**: The pattern `with get_db_closing() as conn:` is used by all non-SSE routes. This stays unchanged.
- **Test fixtures (`conftest.py`)**: `app` fixture creates temp DB, `client` fixture provides test client. SSE tests from Phase 27 v1.6 (`test_routes_sse.py`) mock `time.sleep` and `time.time` — these tests need to pass after the refactor.

### Established Patterns
- **Module pattern**: New features go in `jellyswipe/<module>.py` (from Phase 26 rate_limiter.py, Phase 27 ssrf_validator.py). For this phase, changes are localized to `db.py` and `__init__.py` — no new module needed.
- **Boot-time validation**: `init_db()` runs at app startup, similar to env-var validation. WAL PRAGMA is a natural addition to `init_db()`.
- **Zero new dependencies**: Follows Phase 25-27 pattern — stdlib only.
- **PRAGMA `table_info` for migrations**: `init_db()` already uses `PRAGMA table_info()` for schema migrations. Adding `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL` follows the same pattern of executing PRAGMA statements during initialization.

### Integration Points
- **SSE generator refactored**: `__init__.py` lines 628-673 — the `generate()` inner function in `room_stream()` currently opens/closes a DB connection every 1.5s. The refactor moves connection creation outside the `while` loop and into the generator's lifecycle (open at top, close in `finally`).
- **`init_db()` modification**: `db.py` lines 31-65 — add two `conn.execute()` calls after schema setup: `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL`.
- **`/movies` route**: `__init__.py` line 589-601 — still uses `get_db_closing()` for its single query. Not in scope for refactoring but worth noting since it's one of the other hot paths (reads `movie_data` blob).

</code_context>

<specifics>
## Specific Ideas

- SQLite WAL mode is a persistent setting at the database file level — once set, all subsequent connections to that database file use WAL journal mode automatically. No need to set it on every connection.
- `synchronous=NORMAL` with WAL mode is the SQLite documentation's recommended configuration — it provides good crash recovery while reducing disk flush overhead.
- The SSE generator refactor is minimal: move `conn = sqlite3.connect(DB_PATH)` / `conn.row_factory = sqlite3.Row` above the `while` loop, and add a `finally: conn.close()` to the generator function's exception handling. The `try/except GeneratorExit/Exception` blocks stay, just without the `with get_db_closing()` context manager.
- gevent compatibility: the SSE generator runs inside a gevent coroutine. SQLite's `time.sleep()` should be replaced with `gevent.sleep()` in the generator to avoid blocking the worker, but this is a Phase 28 concern (jitter/heartbeat territory), not Phase 27.

</specifics>

<deferred>
## Deferred Ideas

- SSE jitter (0-0.5s random delay on poll interval) — Phase 28 (SSE Reliability)
- SSE heartbeat (`: ping\n\n` every ~15s) — Phase 28 (SSE Reliability)
- Graceful room disappearance exit — Phase 28 (SSE Reliability)
- gevent.sleep() migration for SSE generator — Phase 28 (the current `time.sleep()` works but blocks the gevent worker)
- Message bus for `last_match_data` overwrites — future milestone
- `/movies` endpoint blob read optimization — future milestone

</deferred>

---

*Phase: 27-database-architecture*
*Context gathered: 2026-04-29*