---
phase: 38
slug: auth-persistence-conversion
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-05
---

# Phase 38 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest 9.0.3` with AnyIO plugin |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `./.venv/bin/pytest tests/test_auth.py tests/test_dependencies.py tests/test_route_authorization.py -q` |
| **Full suite command** | `./.venv/bin/pytest` |
| **Estimated runtime** | ~35 seconds |

---

## Sampling Rate

- **After every task commit:** Run `./.venv/bin/pytest tests/test_auth.py tests/test_dependencies.py -q`
- **After every plan wave:** Run `./.venv/bin/pytest tests/test_auth.py tests/test_dependencies.py tests/test_route_authorization.py -q`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 35 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 38-01-01 | 01 | 1 | MVC-01 | T-38-01 / T-38-03 | Auth vault CRUD moves behind async repository/service seams and returns a typed auth record instead of raw tuple persistence details | unit/integration | `./.venv/bin/pytest tests/test_auth.py tests/test_dependencies.py -q` | ✅ extend | ⬜ pending |
| 38-01-02 | 01 | 1 | PAR-01 | T-38-02 / T-38-04 | Session creation still performs request-driven expired-token cleanup and preserves the existing user-visible login/session behavior | unit/integration | `./.venv/bin/pytest tests/test_auth.py -q` | ✅ extend | ⬜ pending |
| 38-02-01 | 02 | 2 | PAR-01 | T-38-05 / T-38-06 | `require_auth` clears stale or invalid session state aggressively, returns the unchanged `401` contract, and keeps returning a lightweight auth user object | integration | `./.venv/bin/pytest tests/test_dependencies.py tests/test_route_authorization.py -q` | ✅ extend | ⬜ pending |
| 38-02-02 | 02 | 2 | PAR-01 | T-38-06 / T-38-07 | Logout/destroy clears local cookie/session state immediately while best-effort vault cleanup failures are swallowed and logged | integration | `./.venv/bin/pytest tests/test_auth.py tests/test_route_authorization.py -q` | ✅ extend | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Coverage File Ownership

- [ ] `tests/test_auth.py` — expand around async auth service CRUD, cleanup-on-create, and best-effort destroy failure handling
- [ ] `tests/test_dependencies.py` — verify `require_auth` async dependency behavior, stale-session clearing, and unchanged `401` contract
- [ ] `tests/test_route_authorization.py` — keep route-level parity checks light but explicit for login-required behavior and invalid-session cleanup

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify with owned coverage files
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Coverage ownership resolves the auth-service and session-clearing gaps from research
- [ ] No watch-mode flags
- [ ] Feedback latency < 35s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
