# Phase 26: Rate Limiting - Context

**Gathered:** 2026-04-27
**Status:** Ready for planning
**Source:** ROADMAP Phase 26 specification + M04-REQUIREMENTS.md + Phase 25 error handling infrastructure

<domain>
## Phase Boundary

Implement rate limiting on sensitive endpoints (`/proxy`, `/get-trailer`, `/cast`, `/watchlist/add`) to prevent abuse, resource exhaustion, and TMDB API quota depletion. In-memory token-bucket rate limiter with zero new dependencies. Returns 429 with Retry-After header when limits exceeded. Logs violations for operator visibility.

**In scope:**
- Token-bucket rate limiter implementation (in-memory, zero new pip dependencies)
- Per-endpoint rate limits keyed by (IP, endpoint)
- 429 response with `Retry-After` header using existing `make_error_response()` from Phase 25
- Rate limit violation logging using existing `log_exception()` / `app.logger` patterns
- Unit tests for rate limiter logic and per-endpoint enforcement
- Integration with Flask routes via decorator or before_request check

**Out of scope:**
- SSRF protection (Phase 27)
- External rate limiting (Redis, database-backed)
- Rate limiting on non-sensitive endpoints (room management, auth, static files)
- Custom header support for IP identification (ProxyFix is sufficient)
- Distributed rate limiting across multiple worker processes
</domain>

<decisions>
## Implementation Decisions

### Rate Limiting Algorithm
- **D-01:** Token bucket algorithm — allows bursts within the per-minute budget (e.g., all 10 /proxy requests in 2 seconds, then wait ~60s for refill)
- **D-02:** Refill rate = limit/60 tokens per second (continuous refill, not per-minute batch)
- **D-03:** Each bucket starts full at capacity equal to the per-minute limit
- **D-04:** Zero new pip dependencies — implement token bucket in pure Python stdlib (collections, time, threading.Lock or no locking since gevent)

### Rate Limit Scope
- **D-05:** Independent per-endpoint buckets — each endpoint tracks its own bucket keyed by `(ip_address, endpoint_path)`
- **D-06:** Hitting the limit on `/proxy` does NOT affect the limit on `/get-trailer` — fully isolated
- **D-07:** Bucket key format: `(remote_addr, route_rule)` where route_rule is the Flask endpoint string (e.g., `'proxy'`, `'get_trailer'`)

### Per-Endpoint Thresholds (locked from ROADMAP)
- **D-08:** `/proxy` — 10 requests/minute/IP
- **D-09:** `/get-trailer/<movie_id>` — 20 requests/minute/IP
- **D-10:** `/cast/<movie_id>` — 20 requests/minute/IP
- **D-11:** `/watchlist/add` — 30 requests/minute/IP

### IP Identification
- **D-12:** Use `request.remote_addr` directly — ProxyFix with `x_for=1` already populates it from X-Forwarded-For first value
- **D-13:** No custom header support (no CF-Connecting-IP, X-Real-IP, etc.) — zero config approach
- **D-14:** If operator needs different IP extraction, they configure their reverse proxy to set X-Forwarded-For correctly (standard practice)

### Error Response Format
- **D-15:** 429 response uses existing `make_error_response()` from Phase 25 — returns `{"error": "Rate limit exceeded", "request_id": "req_..."}, 429`
- **D-16:** Include `Retry-After` header with seconds until next token is available
- **D-17:** Response Content-Type is `application/json` (handled by `make_error_response()`)

### Logging
- **D-18:** Log rate limit violations at WARNING level using `app.logger.warning()`
- **D-19:** Log fields: request_id, endpoint, ip_address, limit, current_usage, retry_after_seconds
- **D-20:** Do NOT log on every allowed request — only on violations (429 responses)

### Memory Management
- **D-21:** Evict stale buckets (no requests for >5 minutes) to prevent unbounded memory growth
- **D-22:** Lazy eviction — check on each rate limit evaluation, no background thread
- **D-23:** Max bucket count cap (e.g., 10,000) — if exceeded, evict oldest-accessed buckets

### Integration Pattern
- **D-24:** Apply rate limiting via a Flask decorator or a per-route before_request check on the 4 target endpoints only
- **D-25:** Rate limit check happens BEFORE the route handler logic (before auth, before upstream calls)
- **D-26:** Rate limiter module lives in `jellyswipe/rate_limiter.py` (new file, not inline in `__init__.py`)

### the agent's Discretion
- Exact decorator implementation (function decorator vs `@app.before_request` with endpoint filtering)
- Whether to use `threading.Lock` or rely on gevent cooperative scheduling for thread safety
- Exact eviction algorithm (LRU, oldest-timestamp, etc.)
- Test file name and organization (new file vs extending existing)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v1.6 Requirements
- `.planning/milestones/M04-REQUIREMENTS.md` — RL-01 through RL-04 requirements with success criteria
- `.planning/milestones/M04-CONTEXT.md` — Problem analysis including rate limiting rationale (section 4: /Proxy Unrate-Limited)

### v1.6 Roadmap
- `.planning/ROADMAP.md` §Phase 26 — Phase boundary, success criteria, dependencies

### Phase 25 Infrastructure (MUST read — rate limiter uses these directly)
- `jellyswipe/__init__.py` — `make_error_response()`, `get_request_id()`, `log_exception()`, `@app.before_request` / `@app.after_request` hooks
- `.planning/phases/25-error-handling-requestid/25-CONTEXT.md` — Error handling decisions (D-01 through D-06)

### Testing Conventions
- `.planning/codebase/TESTING.md` — pytest patterns, mock conventions, fixture structure
- `tests/conftest.py` — Shared test fixtures and Flask test client setup
- `tests/test_error_handling.py` — Example test patterns for error response assertions

### Existing Codebase
- `jellyswipe/__init__.py` — All 4 target routes (`/proxy` line 613, `/get-trailer` line 239, `/cast` line 273, `/watchlist/add` line 313)
- `jellyswipe/http_client.py` — Established structured logging pattern to follow

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `make_error_response(message, status_code)` from Phase 25 — handles JSON formatting, request_id inclusion, 4xx vs 5xx message logic. Use for 429 responses.
- `get_request_id()` — returns request-scoped ID for logging and response inclusion
- `app.logger.warning()` / `app.logger.error()` — structured logging with `extra={}` dict pattern established in `http_client.py`
- Flask `@app.before_request` / `@app.after_request` hooks — already used for request_id and CSP

### Established Patterns
- ProxyFix middleware: `app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, ...)` — `request.remote_addr` is already the X-Forwarded-For first value
- Env var validation at boot: `missing = []` loop pattern in `__init__.py` lines 27-44
- Test isolation: all HTTP mocked via conftest.py, Flask test client for route tests
- Module layout: new features go in `jellyswipe/<module>.py`, imported by `__init__.py`

### Integration Points
- `jellyswipe/__init__.py` line 46-49: Flask app creation + ProxyFix setup (rate limiter init goes after this)
- `jellyswipe/__init__.py` line 613: `/proxy` route handler — rate limit check before `request.args.get('path')`
- `jellyswipe/__init__.py` line 239: `/get-trailer/<movie_id>` route handler — rate limit before Jellyfin resolve
- `jellyswipe/__init__.py` line 273: `/cast/<movie_id>` route handler — rate limit before Jellyfin resolve
- `jellyswipe/__init__.py` line 313: `/watchlist/add` route handler — rate limit before auth check + Jellyfin call
- Runtime: gevent workers via Gunicorn — cooperative concurrency, no true parallel threads, but `threading.Lock` is gevent-aware

</code_context>

<specifics>
## Specific Ideas

- Token bucket is the natural fit — web UI triggers parallel requests on page load (poster images, trailer lookup, cast lookup), so allowing bursts within budget matches real usage patterns
- The 4 endpoints are all "read" or "light write" operations — rate limits protect upstream services (Jellyfin, TMDB) and prevent image proxy abuse, not protect against data corruption
- Memory footprint: 10,000 unique IP × endpoint combinations at ~100 bytes each = ~1MB max — negligible for a home-server app

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 26-rate-limiting*
*Context gathered: 2026-04-27*
