# Phase 24: TMDB Security - Context

**Gathered:** 2026-04-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Migrate TMDB API from v3 URL parameter authentication (`api_key=` in query strings) to v4 Bearer token, eliminating credential exposure in logs, browser network tabs, and intermediate systems. Covers code changes, test updates, documentation, and deployment config.

</domain>

<decisions>
## Implementation Decisions

### TMDB Authentication Strategy
- **D-01:** Use TMDB v4 Bearer token authentication exclusively — `Authorization: Bearer <TMDB_ACCESS_TOKEN>` header on all TMDB API calls
- **D-02:** New env var `TMDB_ACCESS_TOKEN` replaces `TMDB_API_KEY` entirely (no dual support)
- **D-03:** All 4 TMDB URL constructions in `jellyswipe/__init__.py` (lines 187, 196, 216, 225) must remove `api_key=` query parameter and pass token via `headers` parameter to `make_http_request()`
- **D-04:** TMDB API endpoints stay on v3 paths (`/3/search/movie`, `/3/movie/{id}/videos`, `/3/movie/{id}/credits`) — v4 auth works with v3 endpoints per TMDB docs

### Backward Compatibility
- **D-05:** Hard break with clear error — app refuses to start if `TMDB_ACCESS_TOKEN` is missing
- **D-06:** Remove `TMDB_API_KEY` from required env var validation at boot (line 26 of `__init__.py`)
- **D-07:** Add `TMDB_ACCESS_TOKEN` to required env var validation at boot
- **D-08:** Error message should explain how to get a v4 read access token from TMDB settings

### Log Redaction
- **D-09:** No extra logging work needed — v4 Bearer auth moves credentials out of URLs entirely
- **D-10:** Current `http_client.py` does not log headers, so Authorization token will not appear in logs
- **D-11:** Verify via test that URL logged by `make_http_request()` contains no credentials

### Documentation & Config Updates
- **D-12:** Update ALL references to `TMDB_API_KEY` in this phase (no deferred docs):
  - `README.md` — env var table, setup instructions, docker examples, TMDB API instructions section
  - `docker-compose.yml` — env var definitions
  - `docker run.txt` — example command
  - `unraid_template/jelly-swipe.html` — template variable name and description
  - `scripts/lint-unraid-template.py` — env var validation list (line 17)
  - `tests/conftest.py` — `TMDB_API_KEY` default → `TMDB_ACCESS_TOKEN` (lines 10, 73)
  - `tests/test_infrastructure.py` — test assertions for env var (lines 43, 47)
  - `tests/test_routes_xss.py` — test env var setup (line 42)
- **D-13:** Update README TMDB API instructions to explain how to find the "Read Access Token" in TMDB account settings

### the agent's Discretion
- Exact helper function structure for building TMDB request headers
- Whether to create a `tmdb_headers()` helper or inline the Authorization header
- Test file organization (extend existing test files vs. new test file)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v1.6 Requirements
- `.planning/milestones/M04-REQUIREMENTS.md` — TMDB-01, TMDB-02 requirements with success criteria
- `.planning/milestones/M04-CONTEXT.md` — Problem analysis including TMDB credential exposure details (section 2)

### v1.6 Roadmap
- `.planning/ROADMAP.md` §Phase 24 — Phase boundary, success criteria, dependencies

### Codebase Reference
- `jellyswipe/http_client.py` — Centralized HTTP helper (prerequisite from Phase 23)
- `jellyswipe/__init__.py` — TMDB call sites at lines 183-246 (get_trailer, get_cast routes)

### Testing Conventions
- `.planning/codebase/TESTING.md` — pytest patterns, mock conventions, fixture structure
- `tests/conftest.py` — Shared test fixtures and env var setup

### Deployment Config
- `unraid_template/jelly-swipe.html` — Unraid template with TMDB_API_KEY env var
- `scripts/lint-unraid-template.py` — Required env var validation for Unraid template

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `jellyswipe/http_client.py` `make_http_request()`: Already accepts `headers` parameter — just need to pass `Authorization: Bearer <token>` via this param
- `tests/conftest.py`: Monkeypatch pattern for env vars already established — change `TMDB_API_KEY` → `TMDB_ACCESS_TOKEN` in fixture setup
- `tests/test_routes_xss.py`: Pattern for mocking TMDB API calls with `make_http_request` — extend for v4 auth tests

### Established Patterns
- Env var validation at boot: `missing = []` loop in `__init__.py` lines 25-42
- `make_http_request()` call pattern: method, url, headers, timeout — already used for all TMDB calls
- Test isolation: all HTTP mocked, env vars via monkeypatch

### Integration Points
- `jellyswipe/__init__.py` line 64: `TMDB_API_KEY = os.getenv("TMDB_API_KEY")` → change to `TMDB_ACCESS_TOKEN = os.getenv("TMDB_ACCESS_TOKEN")`
- `jellyswipe/__init__.py` lines 187, 196, 216, 225: URL construction with `api_key=` → remove, add header
- All TMDB calls pass through `make_http_request()` already — just need to add `headers` param

</code_context>

<specifics>
## Specific Ideas

- TMDB v4 Read Access Token is found in TMDB Account Settings > API > "Read Access Token" section
- The v3 API paths (`/3/...`) work with v4 Bearer auth — no URL path changes needed
- Current code has 4 TMDB URL constructions that embed the API key — all in `get_trailer` and `get_cast` routes

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 24-tmdb-security*
*Context gathered: 2026-04-26*
