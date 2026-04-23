# Testing Patterns

**Analysis Date:** 2026-04-23

## Test Framework

**Runner:**
- Not detected — No `pytest`, `unittest` discovery layout, or `tox`/`nox` configuration in the repository.

**Assertion Library:**
- Not applicable until a runner is adopted.

**Run Commands:**
```bash
# Not defined — add after introducing a framework, e.g.:
# pytest
# pytest -q
# pytest --cov=app
```

## Test File Organization

**Location:**
- No `tests/`, `test_*.py`, or `*_test.py` files present at repository root or subdirectories.

**Naming:**
- When introducing tests, prefer `tests/test_<feature>.py` or `tests/test_app.py` for Flask route tests.

**Structure:**
```
# Recommended future layout (not present today):
tests/
├── conftest.py          # Flask test client fixture, tmp_path for SQLite
└── test_room_flow.py    # Example: room create/join/swipe
```

## Test Structure

**Suite Organization:**
- Not established — Mirror route groupings from `app.py` (`/room/*`, `/matches`, Plex proxy) when adding tests.

**Patterns:**
- Use Flask `app.test_client()` against `app` from `app.py` with environment variables set in fixtures (avoid real `PLEX_TOKEN` in CI — mock `plexapi` and `requests`).
- For SQLite, point `DB_PATH` at a temporary file in tests (requires small refactor to make path injectable or env-overridable).

## Mocking

**Framework:** Not chosen — `unittest.mock` or `pytest-mock` are typical choices for Python.

**Patterns:**
- Mock `PlexServer` and `requests.get` for unit tests of `fetch_plex_movies`, `/proxy`, and TMDB routes.
- Patch globals `_plex_instance` and `_genre_cache` carefully — they retain state across requests in production.

**What to Mock:**
- All outbound HTTP (Plex, TMDB, plex.tv) in automated tests.
- `random.randint` if pairing code collisions matter for assertions.

**What NOT to Mock:**
- SQLite when writing integration tests for room lifecycle — use ephemeral DB file.

## Fixtures and Factories

**Test Data:**
- Not present — Future tests should factory-insert `rooms`/`swipes` rows matching `init_db()` schema in `app.py`.

**Location:**
- Place under `tests/fixtures/` if JSON payloads for swipe/match endpoints are reused.

## Coverage

**Requirements:** None enforced in CI (`.github/workflows/docker-image.yml` only builds Docker image).

**View Coverage:**
```bash
# After adding pytest-cov:
# pytest --cov=app --cov-report=term-missing
```

## Test Types

**Unit Tests:**
- Target pure helpers if extracted from `app.py` (genre mapping, JSON shaping).

**Integration Tests:**
- Exercise Flask routes with test client and temp SQLite; verify `/room/stream` yields events when DB rows change (may require threading or shorter poll in test config).

**E2E Tests:**
- Not used — Playwright/Cypress could target `templates/index.html` flows if UI regressions become costly.

## Common Patterns

**Async Testing:**
- Not applicable — Flask routes are synchronous; SSE generator can be tested by iterating `generate()` with controlled DB state.

**Error Testing:**
- Assert JSON error payloads and status codes from routes that wrap broad `Exception` handlers (`get_trailer`, `get_cast`).

---

*Testing analysis: 2026-04-23*
