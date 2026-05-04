---
phase: 32
slug: auth-rewrite-and-dependency-injection-layer
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-04
---

# Phase 32 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_auth.py tests/test_dependencies.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -q` |
| **Estimated runtime** | ~1 second (DI tests only) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_auth.py tests/test_dependencies.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 1 second

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 32-01-01 | 01 | 1 | ARCH-03 | T-32-01 | require_auth raises 401 for invalid/missing session | unit | `uv run pytest tests/test_dependencies.py::TestRequireAuth -x -q` | ✅ | ✅ green |
| 32-01-02 | 01 | 1 | ARCH-03 | — | get_db_dep yields connection and closes on exit | unit | `uv run pytest tests/test_dependencies.py::TestGetDbDep -x -q` | ✅ | ✅ green |
| 32-01-03 | 01 | 1 | ARCH-03 | T-32-04 | check_rate_limit raises 429 when limit exceeded | unit | `uv run pytest tests/test_dependencies.py::TestCheckRateLimit -x -q` | ✅ | ✅ green |
| 32-01-04 | 01 | 1 | ARCH-03 | — | destroy_session_dep delegates to auth.destroy_session | unit | `uv run pytest tests/test_dependencies.py::TestDestroySessionDep -x -q` | ✅ | ✅ green |
| 32-01-05 | 01 | 1 | ARCH-03 | — | get_provider returns singleton via lazy import | unit | `uv run pytest tests/test_dependencies.py::TestGetProvider -x -q` | ✅ | ✅ green |
| 32-01-06 | 01 | 1 | ARCH-03 | — | AuthUser dataclass has jf_token and user_id fields | unit | `uv run pytest tests/test_dependencies.py::TestAuthUser -x -q` | ✅ | ✅ green |
| 32-02-01 | 01 | 1 | ARCH-03 | T-32-01 | create_session inserts into user_tokens | integration | `uv run pytest tests/test_auth.py::TestCreateSession -x -q` | ✅ | ✅ green |
| 32-02-02 | 01 | 1 | ARCH-03 | — | get_current_token returns token for valid session | integration | `uv run pytest tests/test_auth.py::TestGetCurrentToken -x -q` | ✅ | ✅ green |
| 32-02-03 | 01 | 1 | ARCH-03 | T-32-01 | require_auth via TestClient returns 401 or AuthUser | integration | `uv run pytest tests/test_auth.py::TestRequireAuth -x -q` | ✅ | ✅ green |
| 32-02-04 | 01 | 1 | ARCH-03 | — | Zero Flask imports in test_auth.py | structural | `grep -c "from flask" tests/test_auth.py` returns 0 | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements:
- `tests/test_dependencies.py` — 11 tests for all DI callables
- `tests/test_auth.py` — 14 tests for auth module via FastAPI TestClient
- `tests/conftest.py` — shared fixtures (db_path, seed_vault)

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Audit 2026-05-04

| Metric | Count |
|--------|-------|
| Gaps found | 1 |
| Resolved | 1 |
| Escalated | 0 |

**Gap resolved:** `TestCheckRateLimit::test_raises_429_when_limit_exceeded` was flaky due to token-bucket refill during 200-request loop. Fixed by patching `_RATE_LIMITS` to use limit of 5 and adding `setup_method` reset.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 1s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-04
