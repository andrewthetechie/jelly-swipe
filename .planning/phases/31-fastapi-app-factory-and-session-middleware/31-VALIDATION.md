---
phase: 31
slug: fastapi-app-factory-and-session-middleware
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-04
validated: 2026-05-04
reconstructed_from:
  - 31-01-PLAN.md
  - 31-01-SUMMARY.md
  - 31-VERIFICATION.md
---

# Phase 31 - Validation Strategy

Retroactive Nyquist validation for the FastAPI app factory and session middleware phase.

## Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | pytest 9.x |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/test_infrastructure.py tests/test_error_handling.py::TestRequestIdGeneration tests/test_error_handling.py::TestRequestIdPropagation tests/test_routes_xss.py::TestLayer3CSPHeader -q` |
| Full suite command | `uv run pytest` |
| Estimated runtime | ~1 second focused slice; full suite varies |

## Sampling Rate

- After every task commit: run the quick command above.
- After every plan wave: run `uv run pytest`.
- Before `$gsd-verify-work`: full suite must be green or documented with pre-existing failures.
- Max feedback latency: ~1 second for focused middleware/app-factory feedback.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 31-01-01 | 01 | 1 | FAPI-01 | T-31-03 | FastAPI/Uvicorn stack replaces Flask/Gunicorn/gevent and app boots through `create_app()`/`TestClient`. | integration | `uv run pytest tests/test_infrastructure.py -q` | yes | green |
| 31-01-02 | 01 | 1 | FAPI-04 | T-31-01 | Starlette `SessionMiddleware` signs and reads the `session` cookie with the configured `FLASK_SECRET`/test secret. | integration | `uv run pytest tests/test_auth.py tests/test_routes_room.py tests/test_route_authorization.py -q` | yes | green |
| 31-01-03 | 01 | 1 | ARCH-04 | T-31-02/T-31-04/T-31-05 | App factory wires middleware, request IDs, CSP headers, and XSS-safe JSON response behavior. | integration | `uv run pytest tests/test_error_handling.py::TestRequestIdGeneration tests/test_error_handling.py::TestRequestIdPropagation tests/test_routes_xss.py::TestLayer3CSPHeader -q` | yes | green |

## Requirement Coverage

| Requirement | Coverage | Evidence |
|-------------|----------|----------|
| FAPI-01 | COVERED | `tests/test_infrastructure.py` asserts FastAPI/Uvicorn runtime dependencies and Docker Uvicorn CMD while excluding Flask/Gunicorn/gevent. Route fixtures instantiate the app with FastAPI `TestClient`. |
| FAPI-04 | COVERED | `tests/conftest.py::set_session_cookie` reproduces Starlette `SessionMiddleware` signing and route/auth tests exercise session persistence, login, room state, and logout. |
| ARCH-04 | COVERED | `jellyswipe/__init__.py` exposes `create_app()` and module-level `app`, mounts routers, and registers `RequestIdMiddleware`, `SessionMiddleware`, and `ProxyHeadersMiddleware`; request/CSP tests verify observable behavior. |

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

## Manual-Only Verifications

All phase behaviors have automated verification.

## Validation Audit 2026-05-04

| Metric | Count |
|--------|-------|
| Input state | State B - reconstructed from PLAN/SUMMARY/VERIFICATION |
| Requirements audited | 3 |
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
| Generated test files | 0 |

## Latest Automated Run

Command:

```bash
uv run pytest tests/test_infrastructure.py tests/test_error_handling.py::TestRequestIdGeneration tests/test_error_handling.py::TestRequestIdPropagation tests/test_routes_xss.py::TestLayer3CSPHeader -q
```

Result: 13 passed on 2026-05-04. Pytest emitted existing SQLite `ResourceWarning` messages, but no test failed.

## Validation Sign-Off

- [x] All tasks have automated verification.
- [x] Sampling continuity has no three-task gap without automated verification.
- [x] Wave 0 dependencies are already present.
- [x] No watch-mode flags.
- [x] Feedback latency is under 5 seconds for the focused validation slice.
- [x] `nyquist_compliant: true` set in frontmatter.

Approval: approved 2026-05-04
