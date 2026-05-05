---
phase: 34
slug: sse-route-migration
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-04
---

# Phase 34 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_routes_sse.py -v` |
| **Full suite command** | `uv run pytest tests/ -v` |
| **Estimated runtime** | ~1 second |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_routes_sse.py -v`
- **After every plan wave:** Run `uv run pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 1 second

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 34-01-01 | 01 | 1 | FAPI-03 (dependency) | T-34-01-01 | sse-starlette pinned via uv.lock hashes | infra | `grep 'sse-starlette' pyproject.toml uv.lock` | N/A | ✅ green |
| 34-02-01 | 02 | 2 | FAPI-03 (async generator) | — | Non-blocking sleep via await asyncio.sleep | integration | `uv run pytest tests/test_routes_sse.py::test_stream_jitter_applied -v` | ✅ | ✅ green |
| 34-02-02 | 02 | 2 | FAPI-03 (SSE headers) | — | Cache-Control + X-Accel-Buffering present | integration | `uv run pytest tests/test_routes_sse.py::test_stream_response_headers -v` | ✅ | ✅ green |
| 34-02-03 | 02 | 2 | FAPI-03 (disconnect) | T-34-02-01 | Loop breaks on client disconnect before DB query | integration | `uv run pytest tests/test_routes_sse.py::test_stream_disconnect_breaks_loop_before_db_query -v` | ✅ | ✅ green |
| 34-02-04 | 02 | 2 | FAPI-03 (conn cleanup) | T-34-02-04 | finally: conn.close() fires on all exit paths | integration | `uv run pytest tests/test_routes_sse.py::test_stream_connection_closed_on_all_exit_paths -v` | ✅ | ✅ green |
| 34-02-05 | 02 | 2 | FAPI-03 (CancelledError) | T-34-02-05 | CancelledError re-raised, not swallowed | unit | `uv run pytest tests/test_routes_sse.py::test_stream_cancelled_error_not_swallowed -v` | ✅ | ✅ green |
| 34-02-06 | 02 | 2 | FAPI-03 (auth) | T-34-02-02 | Unauthenticated requests get 401 | integration | `uv run pytest tests/test_routes_sse.py::test_stream_unauthenticated_request_returns_401 -v` | ✅ | ✅ green |
| 34-02-07 | 02 | 2 | FAPI-03 (state events) | — | Initial + change events emitted correctly | integration | `uv run pytest tests/test_routes_sse.py::test_stream_initial_state_events -v` | ✅ | ✅ green |
| 34-02-08 | 02 | 2 | FAPI-03 (dedup) | — | Stable state not repeated | integration | `uv run pytest tests/test_routes_sse.py::test_stream_stable_state_no_repeat -v` | ✅ | ✅ green |
| 34-02-09 | 02 | 2 | FAPI-03 (heartbeat) | — | Ping sent after 15s idle | integration | `uv run pytest tests/test_routes_sse.py::test_stream_heartbeat_on_idle -v` | ✅ | ✅ green |
| 34-02-10 | 02 | 2 | FAPI-03 (room closed) | — | Room disappearance yields closed:true | integration | `uv run pytest tests/test_routes_sse.py::test_stream_room_disappearance_immediate_exit -v` | ✅ | ✅ green |
| 34-02-11 | 02 | 2 | FAPI-03 (cleanup) | — | __init__.py has no inline SSE block | structural | `grep "def room_stream" jellyswipe/__init__.py` (returns empty) | N/A | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Audit 2026-05-04

| Metric | Count |
|--------|-------|
| Gaps found | 4 |
| Resolved | 4 |
| Escalated | 0 |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 1s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-04
