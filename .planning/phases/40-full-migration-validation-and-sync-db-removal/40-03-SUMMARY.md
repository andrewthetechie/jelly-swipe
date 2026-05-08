---
phase: 40-full-migration-validation-and-sync-db-removal
plan: 03
subsystem: database
tags: [sqlite-removal, async, maintenance, ADB-03, VAL-03]

requires:
  - plan: "40-02"
    provides: Tests and migrations no longer depend on sync `get_db` / `get_db_closing` from `jellyswipe.db`.
provides:
  - `jellyswipe/db.py` without `sqlite3`, without `get_db` / `get_db_closing`
  - Async-oriented maintenance entry points; sync `cleanup_expired_auth_sessions` refuses an active event loop (callers use async variant)
affects:
  - plan: "40-04"
    note: VAL-04 guard and sign-off rely on empty `sqlite3` seam in application package.

tech-stack:
  added: []
  patterns:
    - Lifespan/async cleanup replaces legacy sync DB context managers for auth session expiry

key-files:
  modified:
    - jellyswipe/db.py
    - jellyswipe/__init__.py
    - jellyswipe/bootstrap.py (if wired in same commit arc)
    - jellyswipe/db_runtime.py (if wired in same commit arc)
    - tests/test_db.py
    - tests/test_infrastructure.py
    - tests/test_routes_sse.py

key-decisions:
  - "`run_sync` remains on **`DatabaseUnitOfWork`** for SQLAlchemy bridge (D-12); documented in CONTEXT/VALIDATION — not raw `sqlite3`."

patterns-established:
  - "**`monkeypatch.setattr(..., raising=False)`** where tests previously patched removed **`get_db`**."

requirements-completed: [ADB-03, VAL-03]

duration: ~50min
completed: 2026-05-07
---

# Phase 40 — Plan 03 Summary

**Remove synchronous raw SQLite connectors and legacy **`get_db`** / **`get_db_closing`** from the **`jellyswipe`** package while keeping maintenance and tests green.**

## Performance

- **Commit:** `2f8bdbc`
- **`uv run pytest`:** 331 passed (recorded at verification)

## Accomplishments

- Rewrote **`jellyswipe/db.py`** so application maintenance uses async helpers and wrappers; **`get_db`** / **`get_db_closing`** removed.
- SSE and infrastructure tests adjusted for removed **`get_db`** (including **`raising=False`** on obsolete monkeypatch targets).
- Documented **`DatabaseUnitOfWork.run_sync`** retention under D-12 in phase CONTEXT (technical debt rationale).

## Issues encountered

SSE regression tests that still targeted **`get_db`** required **`raising=False`** on **`monkeypatch.setattr`**.

---

*Phase: 40-full-migration-validation-and-sync-db-removal · Completed: 2026-05-07*
