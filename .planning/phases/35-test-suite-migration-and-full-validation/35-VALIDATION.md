---
phase: 35
slug: test-suite-migration-and-full-validation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-03
---

# Phase 35 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 |
| **Config file** | `pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `uv run pytest tests/test_routes_room.py -x --no-cov` |
| **Full suite command** | `uv run pytest tests/` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x --no-cov -q`
- **After every plan wave:** Run `uv run pytest tests/ --no-cov -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 35-01-01 | 01 | 1 | TST-01 | — | N/A | structural | `uv run pytest tests/ -x --no-cov -q` | ✅ | ⬜ pending |
| 35-01-02 | 01 | 1 | TST-01 | — | N/A | structural | `grep -rn "session_transaction" tests/ \| wc -l` (expect 0) | ✅ | ⬜ pending |
| 35-01-03 | 01 | 1 | TST-01 | — | N/A | structural | `grep -rn "get_json()" tests/ \| wc -l` (expect 0) | ✅ | ⬜ pending |
| 35-01-04 | 01 | 1 | TST-01 | T-auth-leak | Auth state cleared between tests | integration | `uv run pytest tests/ --no-cov -q` | ✅ | ⬜ pending |
| 35-02-01 | 02 | 2 | FAPI-01 | — | N/A | smoke | `docker build -t jelly-swipe-test .` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.* All 18 test files and the pytest framework already exist. The broken `client` fixture in conftest.py is the primary Wave 1 work, not a Wave 0 gap.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Container starts with Uvicorn on port 5005 | FAPI-01 | Requires live Docker container | `docker run --rm -e FLASK_SECRET=test -e JELLYFIN_URL=http://localhost -e JELLYFIN_API_KEY=test -e TMDB_ACCESS_TOKEN=test -p 5005:5005 jelly-swipe-test`; verify `Started server process` in logs |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
