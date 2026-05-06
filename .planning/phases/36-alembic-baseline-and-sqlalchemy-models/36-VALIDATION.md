---
phase: 36
slug: alembic-baseline-and-sqlalchemy-models
status: draft
nyquist_compliant: false
wave_0_complete: true
created: 2026-05-05
---

# Phase 36 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/test_models_metadata.py tests/test_db.py -q --no-cov` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~45 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_models_metadata.py tests/test_db.py -q --no-cov`
- **After every plan wave:** Run `uv run pytest tests/test_auth.py tests/test_dependencies.py tests/test_route_authorization.py tests/test_error_handling.py tests/test_infrastructure.py -q --no-cov`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 36-01-01 | 01 | 1 | SCH-03 / MIG-03 | T-36-01 | metadata import stays outside app startup | unit | `python -c "from jellyswipe.models.metadata import target_metadata"` | ✅ | ⬜ pending |
| 36-01-02 | 01 | 1 | SCH-01 / SCH-02 | T-36-02 | model constraints reflect current behavior without unsafe FKs | unit | `uv run pytest tests/test_models_metadata.py -q --no-cov` | ✅ | ⬜ pending |
| 36-02-01 | 02 | 2 | MIG-03 | T-36-05 | Alembic env imports pure metadata only | unit | `rg -n "jellyswipe.__init__" alembic/env.py` | ✅ | ⬜ pending |
| 36-02-02 | 02 | 2 | MIG-01 / MIG-02 | T-36-04 / T-36-06 | blank SQLite DB reaches baseline schema via Alembic | integration | `uv run pytest tests/test_db.py -q --no-cov` | ✅ | ⬜ pending |
| 36-03-01 | 03 | 3 | MIG-02 | T-36-08 | runtime helpers enforce SQLite FK/PRAGMA policy without schema creation | unit | `rg -n "PRAGMA foreign_keys=ON" jellyswipe/db.py` | ✅ | ⬜ pending |
| 36-03-02 | 03 | 3 | SCH-02 | T-36-07 / T-36-09 | fixtures and auth SQL use Alembic/auth_sessions path only | integration | `uv run pytest tests/test_auth.py tests/test_dependencies.py tests/test_route_authorization.py tests/test_error_handling.py tests/test_infrastructure.py -q --no-cov` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] Existing pytest infrastructure covers all phase requirements.
- [x] Existing temp SQLite fixtures can be reused after bootstrap-path substitution.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Alembic CLI smoke path from a clean repo checkout | MIG-01 | useful maintainer sanity check beyond in-process command API | `uv run alembic upgrade head` against a disposable SQLite path, then inspect tables with `sqlite3` or `PRAGMA table_info` |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or existing infrastructure support
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all missing references
- [x] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
