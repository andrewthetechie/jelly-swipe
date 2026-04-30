# Phase 28: SSE Reliability - Context

**Gathered:** 2026-04-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Add SSE reliability features to the `/room/stream` endpoint: poll jitter to desynchronize thundering-herd queries, heartbeat comments to prevent proxy connection reaping, and graceful exit when a room disappears from the database.

**In scope:**
- SSE poll interval jitter (0–0.5s random delay per cycle) per SSE-01
- SSE heartbeat comment (`: ping\n\n`) every ~15s during idle periods per SSE-02
- Immediate SSE generator exit when room record disappears per SSE-03
- Existing SSE event formats remain unchanged and functional
- Tests for all three features

**Out of scope:**
- WAL mode and persistent SSE connection (completed in Phase 27)
- WebSocket migration (SSE stays)
- Redis/Postgres migration (SQLite stays)
- Message bus architecture for `last_match_data` overwrites
- Rate limiting on SSE endpoint

</domain>

<decisions>
## Implementation Decisions

### Poll Jitter (SSE-01)
- **D-01:** Add `random.uniform(0, 0.5)` to each `time.sleep(POLL)` call in the SSE generator — jitter stacks on top of the 1.5s base interval, so each cycle waits 1.5–2.0s total. Standard approach used by AWS, GCP, and Stripe for thundering-herd desynchronization.
- **D-02:** Use Python stdlib `random` module — already available, no new dependency. Import at module level in `__init__.py`.
- **D-03:** Jitter applies to every sleep cycle, including the `except Exception` recovery path — ensures desynchronization even during error states.

### Heartbeat Mechanism (SSE-02)
- **D-04:** Track `_last_event_time = time.time()` at generator start. On each poll iteration, if `time.time() - _last_event_time >= 15` and no data event was emitted this cycle, yield `: ping\n\n` (SSE comment format). Reset `_last_event_time` whenever a data event is emitted OR a heartbeat is sent.
- **D-05:** Use SSE comment format (`: ping\n\n`) rather than a data event — comments are ignored by `EventSource` on the client side (per SSE spec), so no client-side changes are needed. This is the standard keepalive pattern used by nginx, Cloudflare, and Rails ActionCable.
- **D-06:** 15-second interval provides ~4 heartbeats per minute, well within the typical 60-second proxy idle timeout. No configuration needed — hard-code the interval.

### Room Disappearance Handling (SSE-03)
- **D-07:** Current behavior already yields `closed: True` when `row is None` — verify this path is immediate (no sleep before re-query). The existing implementation after Phase 27 already exits immediately on null row with `yield f"data: {json.dumps({'closed': True})}\n\n"` followed by `return`.
- **D-08:** Accept the current behavior as sufficient for SSE-03 — no additional change needed beyond verifying and testing the existing immediate-exit path.

### Test Strategy
- **D-09:** Add new tests to `tests/test_routes_sse.py` for jitter, heartbeat, and room disappearance. Follow existing SSE test patterns (mock `time.sleep` and `time.time`).
- **D-10:** Test jitter by asserting `time.sleep` is called with a value >= 1.5 and <= 2.0 (base POLL + jitter).
- **D-11:** Test heartbeat by controlling `time.time()` return values to simulate 15+ second gaps and assert `: ping\n\n` appears in the stream.

### gevent Compatibility
- **D-12:** Substitute `gevent.sleep()` for `time.sleep()` in the SSE generator if and only if gevent is importable. The current deployment uses gunicorn with gevent workers — `gevent.sleep()` yields the worker thread instead of blocking it. This was deferred from Phase 27 context.
- **D-13:** Implementation: `try: from gevent import sleep as gevent_sleep; except ImportError: gevent_sleep = None` at module level. In the generator, use `gevent_sleep(delay) if gevent_sleep else time.sleep(delay)`. This gracefully degrades in test environments without gevent.

### the agent's Discretion
- Variable naming for heartbeat state tracker (`_last_event_time` vs `last_heartbeat`)
- Whether to extract jitter/heartbeat logic into a helper function or keep inline
- Whether to add a comment explaining the gevent sleep fallback
- Ordering of jitter calculation (before or after data event check)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v1.7 Requirements
- `.planning/REQUIREMENTS.md` — SSE-01, SSE-02, SSE-03 requirements with success criteria

### v1.7 Roadmap
- `.planning/ROADMAP.md` §Phase 28 — Phase boundary, success criteria, dependencies on Phase 27

### Codebase — SSE Generator (MUST read)
- `jellyswipe/__init__.py` lines 623-684 — `/room/stream` SSE endpoint with the refactored persistent connection from Phase 27
- `jellyswipe/__init__.py` line 1-30 — Module imports (need to add `import random`, gevent sleep fallback)
- `jellyswipe/db.py` — WAL mode already active (Phase 27 dependency fulfilled)

### Prior Phase Context (locked decisions that apply here)
- `.planning/phases/27-database-architecture/27-CONTEXT.md` — D-03 (persistent connection inline in generator), D-04 (raw sqlite3.connect, not get_db_closing), D-05 (non-SSE routes unchanged), D-06/D-07 (WAL mode and test compatibility)

### SSE Test Patterns (MUST read)
- `tests/test_routes_sse.py` — Existing SSE test patterns: mock `time.sleep` and `time.time`, `_seed_stream_room` helper, `client` fixture with session
- `tests/conftest.py` — Shared test fixtures (`app`, `client`, `FakeProvider`)

### Codebase Conventions
- `.planning/codebase/TESTING.md` — pytest patterns, mock conventions, fixture structure
- `.planning/codebase/CONVENTIONS.md` — Module pattern for new features

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **SSE generator (Phase 27 refactored)**: `generate()` in `__init__.py` lines 628-681 already uses a persistent `sqlite3.connect()` with `row_factory = sqlite3.Row` and `finally: conn.close()`. Jitter and heartbeat changes are surgical additions to this existing structure.
- **Test fixtures (`conftest.py`)**: `app` fixture creates temp DB, `client` fixture provides Flask test client with session. `_seed_stream_room()` helper in `test_routes_sse.py` seeds room data for SSE tests.
- **`time` module already imported**: `__init__.py` line 1 area imports `time` — used for `time.sleep()` and `time.time()` in the SSE generator and rate limiter.

### Established Patterns
- **Module pattern**: New features go in `jellyswipe/<module>.py` (from Phase 26 rate_limiter.py, Phase 27 ssrf_validator.py). For this phase, changes stay in `__init__.py` — no new module needed.
- **Zero new dependencies**: Follows Phase 25-27 pattern — stdlib only (`random` is stdlib).
- **SSE test mocking**: `test_routes_sse.py` uses `monkeypatch.setattr(time, 'time', ...)` and `monkeypatch.setattr(time, 'sleep', ...)` to control time in SSE generator tests. Phase 28 tests should follow this exact pattern.
- **Phase 27 gevent note**: Phase 27 CONTEXT.md explicitly deferred `gevent.sleep()` migration to Phase 28. This is captured in D-12/D-13.

### Integration Points
- **SSE generator import section**: `__init__.py` lines 1-30 — need to add `import random` and the gevent sleep fallback import
- **SSE generator `generate()` function**: `__init__.py` lines 628-681 — the modification target. Changes are:
  1. Replace `POLL = 1.5` constant with jittered sleep `time.sleep(POLL + random.uniform(0, 0.5))`
  2. Add heartbeat state tracker and SSE comment emission before `time.sleep()`
  3. Swap `time.sleep()` for gevent-aware sleep
- **Error recovery `except Exception` handler**: `__init__.py` line 678-679 — sleeps `POLL` seconds. Must also use jitter and gevent-aware sleep.

### Current Coverage Baseline
```
jellyswipe/__init__.py:          34% (after Phase 27 changes)
jellyswipe/base.py:             100%
jellyswipe/db.py:                78%
jellyswipe/jellyfin_library.py:  12%
jellyswipe/http_client.py:       35%
jellyswipe/rate_limiter.py:      37%
jellyswipe/ssrf_validator.py:    36%
TOTAL:                           30%
Tests: 27 passed, 1 skipped (with --cov-fail-under=70 threshold)
```

</code_context>

<specifics>
## Specific Ideas

- The jitter implementation is straightforward: `time.sleep(POLL + random.uniform(0, 0.5))`. The `random` module is stdlib and low-overhead.
- Heartbeat uses SSE comment syntax (`: ping\n\n`) which is specifically designed for keepalive — clients ignore it per the SSE specification (RFC 8895 §4).
- The gevent sleep migration was explicitly deferred from Phase 27. A try/except import at module level with a runtime fallback is the cleanest approach — it works in both gunicorn+gevent and dev server environments.
- Room disappearance (SSE-03) appears to already be handled by the Phase 27 refactored code: `if row is None: yield f"data: {json.dumps({'closed': True})}\n\n"; return`. The task is to verify this and add a test for it.

</specifics>

<deferred>
## Deferred Ideas

- Message bus for `last_match_data` overwrites (multiple matches in one poll cycle) — future milestone
- `/movies` endpoint blob read optimization — future milestone
- Redis/Postgres migration — out of scope for v1.7 (SQLite is appropriate at this scale)
- WebSocket migration — SSE works; this milestone fixes the existing pattern
- SSE reconnection logic on the client side — client-side EventSource auto-reconnects by spec
- Configurable heartbeat interval — hard-code 15s for now, add config if needed later

</deferred>

---

*Phase: 28-coverage-enforcement*
*Context gathered: 2026-04-30 (updated for v1.7 SSE Reliability scope)*