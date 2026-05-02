# Phase 30: Package and Deployment Infrastructure - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-02
**Phase:** 30-package-deployment-infrastructure
**Areas discussed:** Test bridging strategy, Uvicorn worker model

---

## Test Bridging Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| try/except guard in __init__.py | Add `try/except ImportError: pass` around Flask import block. Minimal shim, not a logic change. Framework-agnostic tests (test_db.py, test_jellyfin_library.py) run cleanly. Flask fixtures fail at fixture load, not import time. | ✓ |
| Selective pytest run, no coverage | Run `pytest tests/test_db.py tests/test_jellyfin_library.py --no-cov` only. No __init__.py change. Coverage threshold check skipped. | |
| Validate at Phase 31 end | Phase 30 only verifies uv sync completes cleanly. Docker start + full tests validated when Phase 31 delivers FastAPI app factory. | |

**User's choice:** try/except guard in __init__.py
**Notes:** User confirmed: "we can do this try/except guard, but it will need to be removed before the end of the milestone." Guard naturally disappears in Phase 31 when __init__.py becomes the FastAPI app factory.

---

## Coverage Threshold

| Option | Description | Selected |
|--------|-------------|----------|
| Temporarily lower threshold to 0 | Set `--cov-fail-under=0`. Coverage reporting stays on. Restore to 70+ after Phase 35. | |
| Run only db + jellyfin tests | Keep threshold at 70, run only the two high-coverage test files explicitly. | |
| Remove --cov-fail-under for now | Delete `--cov-fail-under=70` from pyproject.toml. Re-introduce in Phase 35 once numbers are known. | ✓ |

**User's choice:** Remove --cov-fail-under for now
**Notes:** Threshold will be restored in Phase 35 after full test suite migration.

---

## Uvicorn Worker Model

| Option | Description | Selected |
|--------|-------------|----------|
| Single process, no --workers | One Uvicorn process. Asyncio handles I/O concurrency. Safe for SQLite WAL. Workers can be added at deploy time via env override if needed. | ✓ |
| Multi-worker with --workers 4 | Four worker processes. Higher throughput but adds SQLite write contention risk during migration. | |

**User's choice:** Single process, no --workers
**CMD decided:** `CMD ["/app/.venv/bin/uvicorn", "jellyswipe:app", "--host", "0.0.0.0", "--port", "5005"]`
**Notes:** User confirmed single process is intentional for Phase 30.

---

## Claude's Discretion

- `--no-reload` flag in Dockerfile CMD (production image, no reload needed — obvious choice)
- Font file format, CSS class naming, etc. not applicable to this phase

## Deferred Ideas

None — discussion stayed within phase scope.
