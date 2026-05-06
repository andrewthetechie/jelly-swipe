---
phase: 37
slug: async-database-infrastructure
status: draft
nyquist_compliant: true
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
| **Quick run command** | `./.venv/bin/pytest tests/test_bootstrap.py tests/test_db_runtime.py tests/test_dependencies.py -q` |
| **Full suite command** | `./.venv/bin/pytest` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `./.venv/bin/pytest tests/test_bootstrap.py tests/test_db_runtime.py tests/test_dependencies.py -q`
- **After every plan wave:** Run `./.venv/bin/pytest tests/test_bootstrap.py tests/test_db_runtime.py tests/test_dependencies.py tests/test_db.py -q`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 37-01-01 | 01 | 1 | ADB-01 | T-37-01 / T-37-03 | Async engine/sessionmaker resolves configured SQLite URL, initializes once, and opens isolated sessions without global sharing | unit/integration | `./.venv/bin/pytest tests/test_db_runtime.py -q` | ✅ planned in 37-01-01 | ⬜ pending |
| 37-01-02 | 01 | 1 | ADB-02, ADB-04 | T-37-01 / T-37-03 | Dependency layer yields a request-scoped unit of work, commits on success, rolls back on error, and closes its session | integration | `./.venv/bin/pytest tests/test_db_runtime.py tests/test_dependencies.py -q` | ✅ rewrite in 37-01-02 | ⬜ pending |
| 37-02-01 | 02 | 2 | MIG-04 | T-37-04 / T-37-05 | Bootstrap runs Alembic before serving, reuses the resolved DB target for runtime setup, and exits on migration failure | integration | `./.venv/bin/pytest tests/test_bootstrap.py -q` | ✅ planned in 37-02-01 | ⬜ pending |
| 37-02-02 | 02 | 2 | ADB-04 | T-37-06 | Compatibility maintenance delegates through the async runtime path and app shutdown disposes runtime state cleanly | integration | `./.venv/bin/pytest tests/test_db.py tests/test_infrastructure.py -q` | ✅ extend | ⬜ pending |
| 37-03-01 | 03 | 3 | VAL-01 | T-37-07 / T-37-09 | Temp test databases are provisioned through Alembic plus the async runtime path instead of `init_db()` table creation | integration | `./.venv/bin/pytest tests/test_auth.py tests/test_dependencies.py -q` | ✅ extend | ⬜ pending |
| 37-03-02 | 03 | 3 | ADB-02 | T-37-08 / T-37-09 | Auth-focused low-level tests consume the shared bootstrap helper and runtime rebinds cleanly across distinct temp databases | integration | `./.venv/bin/pytest tests/test_auth.py -q` | ✅ extend | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Coverage File Ownership

- [ ] `tests/test_db_runtime.py` — created in Plan `37-01` Task `37-01-01` for ADB-01 runtime/session lifecycle coverage
- [ ] `tests/test_bootstrap.py` — created in Plan `37-02` Task `37-02-01` for MIG-04 bootstrap success/fail-fast coverage
- [ ] `tests/test_dependencies.py` — rewrite around async unit-of-work fixtures
- [ ] `tests/test_auth.py` — remove sync-first `init_db()` assumptions from low-level coverage

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify with owned coverage files
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Coverage ownership resolves all formerly missing references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
