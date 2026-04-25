---
phase: 10-uv-python-3-13-lockfile
plan: "01"
subsystem: infra
tags: [uv, python-3.13, lockfile, pyproject]

requires:
  - phase: prior milestones
    provides: requirements.txt dependency list
provides:
  - Root pyproject.toml with jellyswipe app metadata and CPython 3.13-only bound
  - Committed uv.lock resolved for 3.13
  - .python-version pin for local uv and editors
affects:
  - Phase 11 (package layout migration)
  - Phase 12 (Docker uv-first)

tech-stack:
  added: [uv, flask, plexapi, werkzeug, requests, python-dotenv, gunicorn]
  patterns:
    - "Application pyproject (not publishable wheel); dependencies managed via uv add / uv lock"

key-files:
  created:
    - pyproject.toml
    - uv.lock
    - .python-version
  modified: []

key-decisions:
  - "Kept init default version 0.1.0 in pyproject (plan allowed 0.1.0 or 1.2.0)."
  - "Tracked .python-version with git add -f because repository .gitignore listed it (file is required for uv pin)."

patterns-established:
  - "Authoritative deps live in pyproject.toml + uv.lock; requirements.txt unchanged in this plan."

requirements-completed: [UV-01, UV-02, DEP-01]

duration: 15min
completed: 2026-04-24
---

# Phase 10 Plan 01: pyproject, uv.lock, Python 3.13 pin — Summary

**Root project now resolves on uv with a 3.13-only `requires-python` bound and a checked-in lockfile matching the former pip requirements list.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-04-24T22:45:00Z
- **Completed:** 2026-04-24T23:00:00Z
- **Tasks:** 1
- **Files modified:** 3

## Accomplishments

- Added application `pyproject.toml` (`jellyswipe`, `requires-python = ">=3.13,<3.14"`) with runtime deps migrated from `requirements.txt` via `uv add`.
- Generated `uv.lock` with `uv lock --python 3.13` and verified `uv sync` from repo root.
- Pinned `.python-version` to `3.13` for consistent local/CI interpreter selection.

## Task Commits

1. **Task 10-01-01: pyproject, lock, pin** — `b8d01ce` (feat)

## Files Created/Modified

- `pyproject.toml` — uv project metadata and dependency list
- `uv.lock` — resolver output for CPython 3.13
- `.python-version` — local Python 3.13 pin

## Verification

- `uv sync` — PASS (resolver OK, venv at `.venv`).

## Self-Check: PASSED

## Deviations from Plan

**[Rule 3 - Tracking]** `.python-version` was listed in `.gitignore`; used `git add -f .python-version` so the pin is committed without editing ignore policy.

**Total deviations:** 1 documented workaround. **Impact:** None on runtime; clones receive the pin.

## Next

Ready for plan 10-02 (sync smoke, `py_compile`, deprecate pip-first narrative in `requirements.txt`).
