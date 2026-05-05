---
phase: 30
slug: package-deployment-infrastructure
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-04
---

# Phase 30 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_infrastructure.py -v --no-cov` |
| **Full suite command** | `uv run pytest tests/ --no-cov -q` |
| **Estimated runtime** | ~1 second |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_infrastructure.py -v --no-cov`
- **After every plan wave:** Run `uv run pytest tests/ --no-cov -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 1 second

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 30-01-01 | 01 | 1 | DEP-01 | unit | `uv run pytest tests/test_infrastructure.py::test_pyproject_declares_fastapi_stack_and_excludes_flask_stack -v --no-cov` | yes | green |
| 30-01-02 | 01 | 1 | DEP-01 | unit | `uv run pytest tests/test_infrastructure.py::test_dockerfile_cmd_uses_uvicorn_on_port_5005 -v --no-cov` | yes | green |
| 30-01-03 | 01 | 1 | DEP-01 | unit | `uv run pytest tests/test_infrastructure.py::test_module_import -v --no-cov` | yes | green |

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. Two new smoke tests added retroactively to fill Nyquist gaps.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Docker build succeeds and container starts | DEP-01 | Docker daemon access required | `docker build -t jelly-swipe-test . && docker run --rm -e FLASK_SECRET=test -e JELLYFIN_URL=http://localhost:8096 -e JELLYFIN_API_KEY=test -e TMDB_ACCESS_TOKEN=test -p 5005:5005 jelly-swipe-test` |

---

## Validation Sign-Off

- [x] All tasks have automated verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 1s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-04

---

## Validation Audit 2026-05-04

| Metric | Count |
|--------|-------|
| Gaps found | 2 |
| Resolved | 2 |
| Escalated | 0 |
