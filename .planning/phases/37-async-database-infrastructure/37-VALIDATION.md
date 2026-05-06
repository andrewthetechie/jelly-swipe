---
phase: 37
slug: async-database-infrastructure
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-05
---

# Phase 37 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest 9.0.3` with AnyIO plugin |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `./.venv/bin/pytest tests/test_auth.py tests/test_dependencies.py -q` |
| **Full suite command** | `./.venv/bin/pytest` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `./.venv/bin/pytest tests/test_auth.py tests/test_dependencies.py -q`
- **After every plan wave:** Run `./.venv/bin/pytest tests/test_auth.py tests/test_dependencies.py tests/test_db.py -q`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 37-01-01 | 01 | 1 | MIG-04 | T-37-01 / — | Bootstrap runs Alembic before serving and exits on migration failure | integration | `./.venv/bin/pytest tests/test_bootstrap.py -q` | ❌ W0 | ⬜ pending |
| 37-01-02 | 01 | 1 | ADB-01 | T-37-02 | Async engine/sessionmaker resolves configured SQLite URL and opens sessions without global sharing | unit | `./.venv/bin/pytest tests/test_db_runtime.py -q` | ❌ W0 | ⬜ pending |
| 37-02-01 | 02 | 1 | ADB-02 | T-37-03 | Dependency layer yields a request-scoped unit of work and commits/rolls back at the boundary | integration | `./.venv/bin/pytest tests/test_dependencies.py -q` | ✅ rewrite | ⬜ pending |
| 37-02-02 | 02 | 1 | ADB-04 | T-37-02 | Session lifecycle closes cleanly after each request/unit of work and avoids shared global sessions | unit/integration | `./.venv/bin/pytest tests/test_db_runtime.py tests/test_dependencies.py -q` | ❌ partial | ⬜ pending |
| 37-03-01 | 03 | 2 | VAL-01 | T-37-04 | Temp test databases are provisioned through Alembic instead of `init_db()` table creation | integration | `./.venv/bin/pytest tests/test_auth.py tests/test_dependencies.py -q` | ✅ extend | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_bootstrap.py` — stubs for MIG-04 bootstrap success/fail-fast coverage
- [ ] `tests/test_db_runtime.py` — shared runtime/session lifecycle coverage for ADB-01 and ADB-04
- [ ] `tests/test_dependencies.py` — rewrite around async unit-of-work fixtures
- [ ] `tests/test_auth.py` — remove sync-first `init_db()` assumptions from low-level coverage

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
