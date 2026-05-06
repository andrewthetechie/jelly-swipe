---
phase: 39
slug: room-swipe-match-and-sse-persistence-conversion
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-06
---

# Phase 39 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest 9.0.3` with `anyio 4.13.0` and `pytest-cov 7.1.0` |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_dependencies.py::TestGetDbUow::test_yields_uow_and_commits_on_success -q` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~120 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_dependencies.py -q` plus the touched room-domain route or service tests
- **After every plan wave:** Run `uv run pytest tests/test_routes_room.py tests/test_route_authorization.py tests/test_routes_sse.py tests/test_routes_xss.py tests/test_error_handling.py -x`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 39-01-01 | 01 | 1 | MVC-02, PAR-02 | T-39-01 | Room lifecycle persistence preserves multiplayer and solo behavior with eager stale-room cleanup | route + service | `uv run pytest tests/test_routes_room.py tests/test_route_authorization.py -x` | ✅ | ⬜ pending |
| 39-02-01 | 02 | 1 | MVC-03, PAR-03, PAR-04 | T-39-02 | Swipe writes stay serialized and preserve match, cursor, undo, and delete parity | route + unit | `uv run pytest tests/test_routes_room.py tests/test_dependencies.py tests/test_route_authorization.py tests/test_routes_xss.py -x` | ✅ | ⬜ pending |
| 39-03-01 | 03 | 2 | MVC-04, PAR-05 | T-39-03 | Routes delegate persistence through services/repositories and SSE remains async, non-blocking, and cleanup-safe | route + service | `uv run pytest tests/test_routes_sse.py tests/test_error_handling.py -x` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_room_services.py` — service coverage for create, solo create, join, quit, genre, deck, and status delegation
- [ ] `tests/test_room_repositories.py` — repository coverage for room reads/writes, deck cursor, and history/status queries
- [ ] `tests/test_swipe_service.py` — focused coverage for serialized swipe orchestration plus undo/delete recomputation
- [ ] `tests/test_sse_persistence.py` or equivalent — unit coverage for extracted SSE snapshot access logic if planner factors it out

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | — | All identified Phase 39 behaviors should be automatable through existing route tests plus new service/repository coverage | N/A |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
