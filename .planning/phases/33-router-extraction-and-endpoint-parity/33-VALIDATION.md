---
phase: 33
slug: router-extraction-and-endpoint-parity
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-04
validated: 2026-05-04
reconstructed_from:
  - 33-01-PLAN.md
  - 33-01-SUMMARY.md
  - 33-02-PLAN.md
  - 33-02-SUMMARY.md
  - 33-VERIFICATION.md
---

# Phase 33 - Validation Strategy

Retroactive Nyquist validation for router extraction and endpoint parity.

## Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | pytest 9.x |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/test_routes_auth.py tests/test_routes_room.py tests/test_routes_proxy.py tests/test_route_authorization.py -q` |
| Full suite command | `uv run pytest` |
| Estimated runtime | ~4 seconds focused route slice; full suite varies |

## Sampling Rate

- After every task commit: run the quick route slice above.
- After every plan wave: run `uv run pytest`.
- Before `$gsd-verify-work`: run the quick route slice plus structural route registration checks.
- Max feedback latency: ~4 seconds for focused router parity feedback.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 33-01-01 | 01 | 1 | ARCH-01 | T-33-07 | Shared runtime state lives in `config.py`; router package exists without route prefixes. | structural | `JELLYFIN_URL=http://test.jellyfin.local JELLYFIN_API_KEY=test-api-key TMDB_ACCESS_TOKEN=test-tmdb-token FLASK_SECRET=test-secret-key ALLOW_PRIVATE_JELLYFIN=1 uv run python -c "from jellyswipe.config import TMDB_AUTH_HEADERS, JELLYFIN_URL; from jellyswipe.routers import __doc__; print('config/router package OK')"` | yes | green |
| 33-01-02 | 01 | 1 | ARCH-01, FAPI-02 | T-33-07 | Auth, static, media, and proxy routers expose original paths and use FastAPI dependencies instead of monolith globals. | integration | `uv run pytest tests/test_routes_auth.py tests/test_routes_proxy.py tests/test_error_handling.py::TestAdditionalRoutes -q` | yes | green |
| 33-02-01 | 02 | 2 | ARCH-01, FAPI-02 | T-33-05 | Rooms router preserves room lifecycle, match detection, auth rejection, and swipe transaction behavior. | integration | `uv run pytest tests/test_routes_room.py tests/test_route_authorization.py -q` | yes | green |
| 33-02-02 | 02 | 2 | ARCH-01, FAPI-02 | T-33-07 | App factory mounts all domain routers, preserves original URL paths, and excludes dead `/plex/server-info`. | structural | `JELLYFIN_URL=http://test.jellyfin.local JELLYFIN_API_KEY=test-api-key TMDB_ACCESS_TOKEN=test-tmdb-token FLASK_SECRET=test-secret-key ALLOW_PRIVATE_JELLYFIN=1 uv run python <route parity structural check>` | yes | green |

## Requirement Coverage

| Requirement | Coverage | Evidence |
|-------------|----------|----------|
| ARCH-01 | COVERED | `jellyswipe/routers/auth.py`, `rooms.py`, `media.py`, `proxy.py`, and `static.py` exist and are mounted from `create_app()`. Structural check reported route counts: auth 6, static 4, media 4, proxy 1, rooms 12 in the current codebase. The extra rooms route is the later Phase 34 SSE migration, not a Phase 33 regression. |
| FAPI-02 | COVERED | Focused route suite passed across auth, room lifecycle, proxy, and authorization tests. Structural check verified all original paths are registered and `/plex/server-info` is absent. |

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

## Manual-Only Verifications

All phase behaviors have automated verification.

## Validation Audit 2026-05-04

| Metric | Count |
|--------|-------|
| Input state | State B - reconstructed from PLAN/SUMMARY/VERIFICATION |
| Requirements audited | 2 |
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
| Generated test files | 0 |

## Latest Automated Run

Command:

```bash
uv run pytest tests/test_routes_auth.py tests/test_routes_room.py tests/test_routes_proxy.py tests/test_route_authorization.py -q
```

Result: 124 passed on 2026-05-04. Pytest emitted existing SQLite `ResourceWarning` messages, but no test failed.

Structural route check:

```bash
JELLYFIN_URL=http://test.jellyfin.local JELLYFIN_API_KEY=test-api-key TMDB_ACCESS_TOKEN=test-tmdb-token FLASK_SECRET=test-secret-key ALLOW_PRIVATE_JELLYFIN=1 uv run python <route parity structural check>
```

Result: route counts matched expectations for auth/static/media/proxy; rooms had 12 routes because Phase 34 later migrated SSE into `rooms.py`. Required paths were present, `/plex/server-info` was absent, and the swipe route still exposes a `conn` dependency.

## Validation Sign-Off

- [x] All tasks have automated verification.
- [x] Sampling continuity has no three-task gap without automated verification.
- [x] Wave 0 dependencies are already present.
- [x] No watch-mode flags.
- [x] Feedback latency is under 5 seconds for the focused route slice.
- [x] `nyquist_compliant: true` set in frontmatter.

Approval: approved 2026-05-04
