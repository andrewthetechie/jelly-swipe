---
phase: 35
slug: test-suite-migration-and-full-validation
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-03
validated: 2026-05-05
audit_state: State A - existing validation audited and updated
---

# Phase 35 - Validation Strategy

Retroactive Nyquist validation for the FastAPI TestClient migration and final v2.0 validation gate.

## Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/test_routes_room.py tests/test_routes_xss.py tests/test_route_authorization.py tests/test_routes_auth.py tests/test_routes_proxy.py tests/test_error_handling.py --no-cov -q` |
| Full suite command | `uv run pytest tests/ --no-cov -q` |
| Estimated runtime | ~8 seconds full suite; Docker build/startup varies |

## Sampling Rate

- After every task commit: run the relevant migrated test file with `uv run pytest <file> -x --no-cov -q`.
- After every plan wave: run the quick command above.
- Before `$gsd-verify-work`: run `uv run pytest tests/ --no-cov -q`, legacy-pattern grep, and Docker build/startup smoke test.
- Max feedback latency: ~10 seconds for pytest; Docker feedback depends on cache state.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 35-01-01 | 01 | 1 | TST-01, FAPI-01 | T-auth-leak | FastAPI `TestClient` fixtures construct isolated apps, configure `SECRET_KEY`, and clear `dependency_overrides` after each test. | integration | `uv run pytest tests/test_auth.py tests/test_dependencies.py --no-cov -q` | yes | green |
| 35-02-01 | 02 | 2 | TST-01 | - | Room and XSS route tests use Starlette session cookies and FastAPI response APIs. | integration | `uv run pytest tests/test_routes_room.py tests/test_routes_xss.py --no-cov -q` | yes | green |
| 35-03-01 | 03 | 3 | TST-01 | T-auth-leak | Real-auth route tests use `client_real_auth`, vault-backed sessions, and no Flask session transaction helper. | integration | `uv run pytest tests/test_route_authorization.py tests/test_routes_auth.py --no-cov -q` | yes | green |
| 35-04-01 | 04 | 4 | TST-01 | - | SSE and supporting route tests use FastAPI `TestClient` request/stream patterns. | integration | `uv run pytest tests/test_routes_sse.py --no-cov -q` | yes | green |
| 35-05-01 | 05 | 5 | TST-01 | - | Proxy and error-handling tests use FastAPI response APIs and `raise_server_exceptions=False` where needed. | integration | `uv run pytest tests/test_routes_proxy.py tests/test_error_handling.py --no-cov -q` | yes | green |
| 35-06-01 | 06 | 6 | TST-01 | - | Full migrated suite collects and runs under pytest with zero failures and zero skips. | suite | `uv run pytest tests/ --no-cov -q` | yes | green |
| 35-06-02 | 06 | 6 | TST-01 | - | No active test code uses Flask client APIs. | structural | `rg -n "session_transaction\\(|\\.get_json\\(|response\\.data\\b|from flask\\b|app\\.test_client\\(" tests` | yes | green |
| 35-06-03 | 06 | 6 | FAPI-01 | - | Docker image builds and starts Uvicorn on port 5005. | smoke | `docker build -t jelly-swipe-test .` plus short `docker run` startup log check | yes | green |

## Requirement Coverage

| Requirement | Coverage | Evidence |
|-------------|----------|----------|
| TST-01 | COVERED | Current collection is 327 tests. `uv run pytest tests/ --no-cov -q` returned 327 passed with zero failures and zero skips. Legacy Flask test-client pattern scan found one comment mentioning `session_transaction`, with no active code matches. |
| FAPI-01 | COVERED | `pyproject.toml` declares FastAPI/Uvicorn and excludes Flask/Gunicorn/gevent/Werkzeug. `Dockerfile` uses Uvicorn on port 5005. Docker build completed successfully and container logs showed Uvicorn running on `http://0.0.0.0:5005`. |

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

## Manual-Only Verifications

All phase behaviors have automated verification.

## Validation Audit 2026-05-05

| Metric | Count |
|--------|-------|
| Input state | State A - existing validation audited |
| Requirements audited | 2 |
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
| Generated test files | 0 |

## Latest Automated Runs

Full pytest command:

```bash
uv run pytest tests/ --no-cov -q
```

Result on 2026-05-05: 327 collected; 327 passed; 0 failed; 0 skipped.

Legacy-pattern scan:

```bash
rg -n "session_transaction\(|\.get_json\(|response\.data\b|from flask\b|app\.test_client\(" tests
```

Result: one comment-only match in `tests/test_error_handling.py`; no active Flask client API usage.

Docker build/startup:

```bash
docker build -t jelly-swipe-test .
docker run -d -e FLASK_SECRET=test-secret -e JELLYFIN_URL=http://localhost:8096 -e JELLYFIN_API_KEY=test -e TMDB_ACCESS_TOKEN=test -e ALLOW_PRIVATE_JELLYFIN=1 -p 5005:5005 jelly-swipe-test
```

Result: build succeeded. Container logs showed `Started server process`, `Application startup complete`, and `Uvicorn running on http://0.0.0.0:5005`.

## Validation Sign-Off

- [x] All tasks have automated verification.
- [x] Sampling continuity has no three-task gap without automated verification.
- [x] Wave 0 dependencies are already present.
- [x] No watch-mode flags.
- [x] Feedback latency is under 30 seconds for the pytest suite.
- [x] `nyquist_compliant: true` set in frontmatter.

Approval: approved 2026-05-05
