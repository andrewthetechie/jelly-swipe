---
phase: 30-package-deployment-infrastructure
plan: 01
subsystem: infra
tags: [fastapi, uvicorn, uv, docker, pyproject, dependencies]

# Dependency graph
requires: []
provides:
  - FastAPI 0.136.1 + Uvicorn 0.46.0 stack resolved in uv.lock
  - Dockerfile CMD updated to single-process Uvicorn on port 5005
  - Flask import guard in jellyswipe/__init__.py enabling framework-agnostic submodule imports
  - httpx>=0.28.1 added to dev dependencies for Phase 35 TestClient use
  - --cov-fail-under=70 removed from pytest addopts
affects: [31-app-factory, 32-auth-router, 33-media-proxy-router, 34-sse-router, 35-test-migration]

# Tech tracking
tech-stack:
  added: [fastapi==0.136.1, uvicorn==0.46.0, uvloop==0.22.1, itsdangerous==2.2.0, jinja2==3.1.6, python-multipart==0.0.27, pydantic==2.13.3, starlette==1.0.0, httpx==0.28.1 (dev)]
  patterns: [try/except ImportError guard for transitional Flask imports, try/except NameError for Flask-dependent class definitions, string annotations to avoid NameError on unbound Flask types]

key-files:
  created: []
  modified:
    - pyproject.toml
    - uv.lock
    - Dockerfile
    - jellyswipe/__init__.py
    - jellyswipe/auth.py

key-decisions:
  - "httpx added to dev deps now so Phase 35 TestClient imports are available without another lockfile churn"
  - "String annotation used for _check_rate_limit return type to avoid NameError when Flask is absent"
  - "_XSSSafeJSONProvider class guarded with try/except NameError so module-level class definition does not fail without Flask"
  - "app = create_app() guarded with try/except NameError enabling import jellyswipe.db without Flask installed"
  - "auth.py Flask imports also guarded (cascade fix) since __init__.py imports auth at module level"

patterns-established:
  - "Flask import guard pattern: try/except ImportError wrapping flask/werkzeug imports; try/except NameError wrapping Flask-dependent class bodies — removes naturally when Phase 31 replaces __init__.py"
  - "String annotations for Flask type hints in function signatures to defer evaluation until call time"

requirements-completed: [DEP-01]

# Metrics
duration: 5min
completed: 2026-05-02
---

# Phase 30 Plan 01: Package and Deployment Infrastructure Summary

**FastAPI 0.136.1 + Uvicorn 0.46.0 stack installed via uv sync, Dockerfile CMD switched to single-process Uvicorn, and transitional Flask import guards added so `import jellyswipe.db` succeeds without Flask installed**

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-02T20:54:57Z
- **Completed:** 2026-05-02T20:59:30Z
- **Tasks:** 2
- **Files modified:** 5 (pyproject.toml, uv.lock, Dockerfile, jellyswipe/__init__.py, jellyswipe/auth.py)

## Accomplishments

- Swapped Flask/Gunicorn/gevent/werkzeug for FastAPI/Uvicorn/itsdangerous/jinja2/python-multipart in pyproject.toml; uv.lock regenerated (41 packages resolved)
- Dockerfile CMD updated from gunicorn+gevent to single-process uvicorn (`/app/.venv/bin/uvicorn jellyswipe:app --host 0.0.0.0 --port 5005`); Docker build succeeds
- Flask imports in jellyswipe/__init__.py and jellyswipe/auth.py guarded with try/except so `import jellyswipe.db` succeeds without Flask installed (D-01)
- `--cov-fail-under=70` removed from pytest addopts; coverage reporting remains active (D-03)
- httpx>=0.28.1 added to dev dependencies for Phase 35 TestClient use (D-08)

## Resolved Package Versions

From uv.lock (FastAPI stack):

| Package | Version |
|---------|---------|
| fastapi | 0.136.1 |
| uvicorn | 0.46.0 |
| uvloop | 0.22.1 (standard extra) |
| itsdangerous | 2.2.0 |
| jinja2 | 3.1.6 |
| python-multipart | 0.0.27 |
| pydantic | 2.13.3 (transitive) |
| starlette | 1.0.0 (transitive) |
| httpx | 0.28.1 (dev dep) |

Flask, gunicorn, gevent, werkzeug: absent from lockfile and resolved environment.

## Docker Image Verification

`docker inspect jellyswipe-test --format '{{json .Config.Cmd}}'` returns:
```
["/app/.venv/bin/uvicorn","jellyswipe:app","--host","0.0.0.0","--port","5005"]
```
No `--workers`, no `--reload` flags. Single-process Uvicorn only (D-05, D-06, D-07).

## Framework-Agnostic Import Status

- `import jellyswipe.db` — succeeds with Flask absent (D-01 satisfied)
- Flask-dependent fixtures (`flask_app`, `client`) — will error at fixture setup (expected per D-04, acceptable until Phase 35)

## Task Commits

Each task was committed atomically:

1. **Task 1: Update pyproject.toml and regenerate uv.lock** - `edf87cf` (chore)
2. **Task 2: Update Dockerfile CMD and add Flask import guard** - `1623725` (feat)

**Plan metadata:** (see final commit below)

## Files Created/Modified

- `pyproject.toml` — Runtime deps: Flask stack removed, FastAPI stack added; httpx added to dev; --cov-fail-under=70 removed
- `uv.lock` — Regenerated with 41-package FastAPI dependency tree
- `Dockerfile` — CMD line replaced: gunicorn → uvicorn single-process
- `jellyswipe/__init__.py` — Flask/werkzeug imports wrapped in try/except ImportError; _XSSSafeJSONProvider class guarded with try/except NameError; app = create_app() guarded; string annotation for _check_rate_limit return type
- `jellyswipe/auth.py` — Flask imports (session, g, jsonify) wrapped in try/except ImportError (cascade fix, Rule 1)

## Decisions Made

- String annotations used for `_check_rate_limit(endpoint: str) -> "Optional[Tuple[Response, int]]"` to avoid NameError at module load time when Flask (and Response) is not installed
- `_XSSSafeJSONProvider` class definition wrapped in `try/except NameError: _XSSSafeJSONProvider = None` — the class inherits from `DefaultJSONProvider` (Flask) which is not bound when Flask is absent
- `app = create_app()` wrapped in `try/except NameError: app = None` — `create_app()` uses Flask internally; the guard allows module import to succeed without Flask
- `jellyswipe/auth.py` imports also guarded — `__init__.py` imports auth at module level (line 102); without the auth.py guard the cascade would still fail with ModuleNotFoundError

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Cascading Flask NameError/ModuleNotFoundError prevented D-01 from being achieved**
- **Found during:** Task 2 (Flask import guard in __init__.py)
- **Issue:** The plan specified guarding only the 3 Flask import lines in `__init__.py`. However, three additional Flask-dependent constructs at module level caused NameError: (a) `_check_rate_limit` return type annotation `Optional[Tuple[Response, int]]`, (b) `class _XSSSafeJSONProvider(DefaultJSONProvider)` class definition, and (c) `app = create_app()` at module bottom. Additionally, `jellyswipe/auth.py` (imported at module level from `__init__.py`) has bare Flask imports that also fail.
- **Fix:** Applied string annotation to _check_rate_limit return type; wrapped _XSSSafeJSONProvider class in try/except NameError; wrapped app = create_app() in try/except NameError; wrapped Flask imports in auth.py with try/except ImportError
- **Files modified:** jellyswipe/__init__.py, jellyswipe/auth.py
- **Verification:** `import jellyswipe.db` exits 0 with Flask absent
- **Committed in:** 1623725 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 bug — plan underestimated cascade depth of Flask module-level dependencies)
**Impact on plan:** Fix was necessary to achieve D-01 (the stated correctness requirement). No scope creep — all fixes are transitional and disappear when Phase 31 replaces __init__.py with the FastAPI app factory.

## Issues Encountered

None beyond the auto-fixed cascade described above.

## Known Stubs

None — this plan makes no application logic changes. No UI, no routes, no data sources modified.

## Threat Flags

None — all threat register items (T-30-01 through T-30-05) were reviewed:
- T-30-01 (supply chain tampering): mitigated — uv.lock committed, Docker build uses `uv sync --frozen`
- T-30-02 through T-30-05: accepted per plan's threat model; no new surface introduced

## Next Phase Readiness

- FastAPI and Uvicorn are now available in the resolved environment — Phase 31 (app factory) can proceed
- Docker build produces a Uvicorn-based container — operators get the new server on next image build
- Flask import guard is transitional and disappears naturally when Phase 31 replaces `jellyswipe/__init__.py`
- `jellyswipe/auth.py` Flask import guard similarly disappears when Phase 32 rewrites auth for FastAPI
- `jellyswipe.db` and `jellyswipe.jellyfin_library` import cleanly for framework-agnostic test use

---
*Phase: 30-package-deployment-infrastructure*
*Completed: 2026-05-02*
