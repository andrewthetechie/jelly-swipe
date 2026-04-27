# Feature Research

**Domain:** Outbound HTTP hardening for a self-hosted Flask media-swipe app
**Researched:** 2026-04-26
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Security & Reliability Baseline)

These are non-negotiable for any app making outbound HTTP calls to third-party APIs and user-configured internal servers. Missing them = app hangs silently, leaks secrets, or is exploitable.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Enforced timeouts on all HTTP calls** | Without timeouts, a hung upstream (TMDB, Jellyfin) blocks the gevent worker indefinitely. Users see spinning UI, no error, no recovery. Every production HTTP client mandates timeouts. | LOW | **Current state:** 4 of 15 `requests.*` calls have no timeout (lines 187, 191, 206, 210 in `__init__.py`). The `jellyfin_library.py` session calls all have timeouts (30s–90s). Fix: create a centralized `http_get()` / `http_request()` helper that wraps `requests` and requires `timeout=(connect, read)`. The `requests` library has **no session-level timeout default** — it must be passed per-call. A helper enforces this at the import boundary. |
| **TMDB Bearer token auth (no key in URLs)** | API keys in query strings appear in server logs, browser DevTools, proxy logs, and Referer headers. TMDB's v3 API supports `Authorization: Bearer <read_access_token>` as a direct replacement for `?api_key=` on all read endpoints. The Bearer token IS the same credential as the API key — TMDB calls it a "read access token" in settings. | LOW | **Current state:** 4 URLs in `__init__.py` embed `TMDB_API_KEY` in query strings (lines 186, 190, 205, 209). **Fix:** Replace `api_key={TMDB_API_KEY}` with `headers={"Authorization": f"Bearer {TMDB_API_KEY}"}`. No API version change needed — TMDB v3 endpoints accept Bearer header interchangeably with query-param key. No new env var needed — `TMDB_API_KEY` already holds the read access token. |
| **SSRF-safe JELLYFIN_URL validation at boot** | `JELLYFIN_URL` is user-configured and points to an internal server. If an operator sets it to a cloud metadata endpoint (169.254.169.254 on AWS/GCP/Azure), the app becomes an SSRF probe. Boot-time validation catches misconfiguration before any request fires. | MEDIUM | **Current state:** `JELLYFIN_URL` is read from env and used directly — no IP validation anywhere. **Fix:** Parse URL with `urllib.parse.urlparse()`, resolve hostname to IP, then check against a blocklist: reject 169.254.0.0/16 (link-local/metadata), 0.0.0.0, [::], and any DNS-rebinding patterns. Allow 127.0.0.0/8 (loopback), 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16 (RFC 1918). Run once at module load, raise `RuntimeError` on failure (consistent with existing env validation pattern at lines 24–41 of `__init__.py`). Must handle hostnames that resolve to multiple IPs (check all). |
| **Error redaction (no upstream exception text in 5xx)** | Current code returns `jsonify({'error': str(e)})` on 500 — this leaks Jellyfin hostnames, TMDB URLs, Python tracebacks, and internal state to the browser. Attackers use error messages for reconnaissance. | LOW | **Current state:** 6 catch-all handlers return `str(e)` in JSON responses (lines 198–199, 224–225, 240, 434 in `__init__.py`). **Fix:** Generate a short request ID (`uuid4()[:8]` or `secrets.token_hex(4)`), log the full exception server-side with that ID, and return `{'error': 'Internal error', 'request_id': 'abc12345'}` to the client. The request ID lets operators correlate browser errors with server logs. Wrap in a Flask `@app.errorhandler(500)` or replace the inline handlers. |

### Differentiators (Defense-in-Depth, Not Universally Expected)

Features that go beyond baseline security. Self-hosted apps rarely implement these, but they're valuable for an app that proxies user-configured internal servers.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **In-memory token-bucket rate limiter** | Prevents a single client or bot from burning through TMDB API quota (40 req/10s for free tier) or hammering the Jellyfin proxy. Most self-hosted apps don't rate-limit internal endpoints. | MEDIUM | **Scope:** Applied to `/proxy`, `/get-trailer`, `/cast`, `/watchlist/add` (per PROJECT.md HTTP-04). **Implementation:** Custom in-memory token-bucket, NOT Flask-Limiter (avoids new dependency). Token bucket = fixed capacity, refills at constant rate. Key on `request.remote_addr`. Per-route limits: stricter for TMDB-backed routes (`/get-trailer`, `/cast`), looser for proxy. Store in a module-level dict with thread-safe access (Flask + gevent = cooperative multitasking, so `threading.Lock` is appropriate). **Limitation:** In-memory means rate limits reset on process restart and don't share across gunicorn workers. Acceptable trade-off for a self-hosted single-user app. |
| **Centralized HTTP helper with User-Agent + structured logging** | A single `http_get()`/`http_request()` function ensures consistent User-Agent, timeout enforcement, and request logging across all outbound calls. This is the foundation that makes all other hardening features work — timeouts, redaction, and logging all funnel through one code path. | MEDIUM | **Current state:** TMDB calls use bare `requests.get()` in `__init__.py`; Jellyfin calls use `self._session` in `jellyfin_library.py`. Two different patterns, no centralized logging. **Fix:** Create `jellyswipe/http.py` (or `jellyswipe/http_client.py`) with a `SafeHttpClient` class that wraps a `requests.Session`. Provides `get()`, `post()`, `request()` methods that: (1) enforce timeout, (2) set User-Agent, (3) log request URL + duration + status at INFO level, (4) redact URL secrets before logging. Both TMDB calls in `__init__.py` and Jellyfin calls in `jellyfin_library.py` migrate to this client. |
| **Security-focused unit tests** | Validates that hardening actually works: SSRF rejection catches metadata IPs, timeout enforcement kills hung requests, error responses don't leak internals, rate limiter blocks excess traffic. | MEDIUM | **Current state:** 48 tests exist for db and jellyfin_library modules. No security-focused tests. **New tests:** (1) SSRF: parametrize over 169.254.x.x, 0.0.0.0, [::], public IPs, RFC 1918 — assert only RFC 1918 + loopback pass. (2) Timeouts: mock `requests.get` to raise `Timeout`, assert handler returns 504 not 500. (3) Redaction: trigger exception paths, assert response body has no traceback/hostname. (4) Rate limiter: rapid-fire requests, assert 429 after bucket drains. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Flask-Limiter or Redis-backed rate limiting** | "Use a well-tested library instead of hand-rolling" | Adds a hard dependency (`flask-limiter` + `limits` + `deprecated` transitive deps) for a feature that's 40 lines of token-bucket code. Redis backend requires infrastructure. Flask-Limiter's in-memory mode has the same per-worker limitation as a custom implementation — no advantage for single-process self-hosted use. | Custom in-memory token-bucket. Same per-worker limitation, zero new deps, trivially auditable. |
| **requests retry with exponential backoff** | "Auto-retry failed requests for resilience" | Jellyfin auth calls already have a retry-on-401 pattern. Adding blanket retries to TMDB calls risks amplifying rate-limit violations (409 → retry → 409 → retry). Retry logic must be endpoint-aware, not blanket. | Explicit per-endpoint retry where needed (already exists for Jellyfin 401). No blanket retry on TMDB. |
| **DNS rebinding protection (TOCTOU-safe SSRF)** | "Validate URL right before the request, not just at boot" | Requires overriding `requests` internals or a custom transport adapter. Complex, fragile, and unnecessary for a self-hosted app where `JELLYFIN_URL` changes only on restart. The threat model is operator misconfiguration, not adversarial DNS. | Boot-time validation is sufficient. Document that JELLYFIN_URL changes require restart. |
| **Circuit breaker pattern** | "Stop calling a failing upstream entirely" | Adds significant complexity (state machine, half-open probes, cold/warm resets) for a small Flask app with at most 2 upstreams. Gunicorn's worker timeout already kills stuck workers. | Timeouts + 5xx error responses are sufficient. Workers recycle automatically. |
| **HTTProxy / outbound request proxying** | "Route all outbound through a corporate proxy" | Self-hosted media app operators don't typically run outbound proxies. Adds env var surface (`HTTP_PROXY`, `HTTPS_PROXY`) that interacts poorly with internal Jellyfin URLs. | `requests.Session` respects proxy env vars already if operators set them. Don't add explicit proxy support. |

## Feature Dependencies

```
[HTTP-01: Centralized HTTP helper]
    └──enables──> [HTTP-02: TMDB Bearer token] (helper constructs headers)
    └──enables──> [HTTP-03: Error redaction] (helper catches/wraps exceptions)
    └──enables──> [HTTP-04: Rate limiting] (helper provides single choke point)
    └──required──> [HTTP-06: Security tests] (tests mock the centralized client)

[HTTP-02: TMDB Bearer token]
    └──depends on──> [HTTP-01] (needs helper to enforce header-only auth)

[HTTP-03: Error redaction]
    └──depends on──> [HTTP-01] (helper generates request IDs, logs internally)
    └──conflicts──> [inline str(e) in handlers] (must replace all jsonify({'error': str(e)}))

[HTTP-04: Rate limiter]
    └──independent──> [HTTP-01] (can be Flask decorator, not HTTP client feature)
    └──enhances──> [HTTP-01] (rate limit checked before HTTP call fires)

[HTTP-05: SSRF validation]
    └──independent──> [HTTP-01] (runs at boot, before any HTTP client exists)

[HTTP-06: Security tests]
    └──requires──> [HTTP-01, 02, 03, 04, 05] (tests validate each feature)
```

### Dependency Notes

- **HTTP-01 enables HTTP-02, HTTP-03:** The centralized HTTP helper is the backbone. TMDB Bearer auth needs the helper to construct `Authorization` headers consistently. Error redaction needs the helper to catch exceptions in one place and generate request IDs. Build HTTP-01 first.
- **HTTP-04 is independent of HTTP-01:** Rate limiting is a Flask-layer concern (decorator on routes), not an HTTP client concern. It can be built in parallel but should be tested after HTTP-01 so the test infrastructure is ready.
- **HTTP-05 is fully independent:** SSRF validation runs at module import time, before the HTTP client is instantiated. No dependencies on any other feature. Good candidate for parallel implementation.
- **HTTP-06 requires all others:** Security tests validate the behavior of each hardening feature. Must be built last, after the features under test exist.
- **HTTP-03 conflicts with inline `str(e)`:** Every `jsonify({'error': str(e)})` in `__init__.py` must be replaced. This is a mechanical change but touches 6 catch blocks.

## MVP Definition

### Launch With (v1.6)

Minimum viable hardening — every outbound call is safe, no secrets leak, no SSRF surface.

- [x] **HTTP-01: Centralized HTTP helper** — All 15 outbound calls go through one client with enforced timeouts, User-Agent, and request logging
- [x] **HTTP-02: TMDB Bearer token** — `TMDB_API_KEY` moves from query strings to `Authorization` header on all 4 TMDB calls
- [x] **HTTP-03: Error redaction** — 5xx responses return `{'error': 'Internal error', 'request_id': '...'}`; full exception logged server-side
- [x] **HTTP-04: Rate limiter** — In-memory token-bucket on `/proxy`, `/get-trailer`, `/cast`, `/watchlist/add`
- [x] **HTTP-05: SSRF validation** — `JELLYFIN_URL` validated at boot against metadata-IP blocklist
- [x] **HTTP-06: Security tests** — Unit tests for SSRF rejection, timeout enforcement, error redaction, rate limiting

### Add After Validation (v1.x)

- [ ] **Request duration metrics** — Track p50/p99 latency per upstream (Jellyfin vs TMDB) via structured logs
- [ ] **Adaptive rate limits** — Adjust TMDB rate limits based on 429 responses from upstream
- [ ] **Health check endpoint** — `/health` that probes Jellyfin connectivity on demand

### Future Consideration (v2+)

- [ ] **Circuit breaker** — Only if upstream flakiness becomes a recurring operator complaint
- [ ] **Redis-backed rate limiting** — Only if multi-worker rate sharing is needed (unlikely for self-hosted)
- [ ] **mTLS to Jellyfin** — Only if operators run cert-based Jellyfin auth

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| HTTP-01: Centralized HTTP helper | HIGH (prevents hangs) | MEDIUM (new module + migrate 15 call sites) | P1 |
| HTTP-02: TMDB Bearer token | HIGH (prevents secret leaks) | LOW (4 URL changes + header construction) | P1 |
| HTTP-03: Error redaction | HIGH (prevents info disclosure) | LOW (replace 6 handlers + add request ID) | P1 |
| HTTP-05: SSRF validation | HIGH (prevents cloud metadata attacks) | MEDIUM (IP parsing + DNS resolution + edge cases) | P1 |
| HTTP-04: Rate limiter | MEDIUM (prevents TMDB quota burn) | MEDIUM (token-bucket impl + Flask decorator) | P2 |
| HTTP-06: Security tests | HIGH (validates everything works) | MEDIUM (parametrized test fixtures) | P2 |

**Priority key:**
- P1: Must have — security vulnerabilities if missing
- P2: Should have — defense-in-depth, can ship in same milestone but after P1s

**Suggested build order:** HTTP-05 (independent, boot-time) → HTTP-01 (foundation) → HTTP-02 (uses foundation) → HTTP-03 (uses foundation) → HTTP-04 (independent Flask layer) → HTTP-06 (validates all)

## Competitor Feature Analysis

| Feature | Typical Self-Hosted App | Enterprise SaaS | Jelly Swipe Approach |
|---------|------------------------|-----------------|---------------------|
| HTTP timeouts | Often missing | Required, enforced via middleware | Centralized helper with enforced `(connect, read)` tuple |
| API key in URL | Common (convenient) | Never — always headers | Migrate to Bearer header |
| Error redaction | `str(e)` to browser | Structured errors with correlation IDs | Request ID + server-side log + generic client message |
| Rate limiting | Rare | Redis-backed, per-tenant | In-memory token-bucket, per-IP |
| SSRF validation | Almost never | DNS rebinding + allowlist | Boot-time IP blocklist (metadata + dangerous ranges) |

## Codebase Impact Assessment

### Files to Create
| File | Purpose | Lines (est.) |
|------|---------|-------------|
| `jellyswipe/http_client.py` | Centralized HTTP client with timeout enforcement, User-Agent, structured logging | ~80 |
| `jellyswipe/rate_limiter.py` | In-memory token-bucket rate limiter | ~60 |
| `jellyswipe/ssrf.py` | SSRF URL validation (boot-time) | ~50 |
| `tests/test_http_hardening.py` | Security tests for all hardening features | ~200 |

### Files to Modify
| File | Changes | Scope |
|------|---------|-------|
| `jellyswipe/__init__.py` | Replace 4 bare `requests.get()` calls with centralized client; replace TMDB `api_key=` with Bearer header; replace 6 `str(e)` error handlers with redacted responses; add rate limiter decorators to 4 routes; add SSRF validation at boot | HIGH — most route handlers touched |
| `jellyswipe/jellyfin_library.py` | Migrate `self._session` usage to centralized client (optional — existing timeouts are OK, but logging/redaction benefit) | MEDIUM — internal API calls refactored |
| `pyproject.toml` | No new dependencies needed | NONE |

### Migration Path

The centralized HTTP helper should be introduced incrementally:

1. **Phase 1:** Create `http_client.py` — standalone, no imports changed yet
2. **Phase 2:** Migrate TMDB calls in `__init__.py` (the 4 bare `requests.get()` calls) — highest impact, all missing timeouts + all leaked API keys
3. **Phase 3:** Migrate error handlers in `__init__.py` — replace `str(e)` with redacted responses
4. **Phase 4:** Add rate limiter decorators to routes
5. **Phase 5:** (Optional) Migrate `jellyfin_library.py` internal calls to centralized client for logging benefit
6. **Phase 6:** Add SSRF validation at boot
7. **Phase 7:** Write security tests

## Sources

- **requests library timeout documentation** — Context7 /psf/requests: timeout must be passed per-request, no session-level default exists. HIGH confidence.
- **TMDB v3 API authentication** — Context7 /websites/developer_themoviedb_reference: all v3 endpoints accept `Authorization: Bearer <access_token>` header as alternative to `?api_key=`. HIGH confidence.
- **TMDB API key vs read access token** — TMDB developer settings: the "API Key (v3 auth)" and "Read Access Token" are separate values, but the Read Access Token works as a Bearer token for all read endpoints. HIGH confidence.
- **Flask-Limiter in-memory storage** — Context7 /alisaifee/flask-limiter: `storage_uri="memory://"` available but per-process, same limitation as custom impl. HIGH confidence.
- **RFC 1918 / link-local IP ranges** — Standard networking: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16 (private), 169.254.0.0/16 (link-local/metadata), 127.0.0.0/8 (loopback). HIGH confidence.
- **Codebase analysis** — Direct reading of `jellyswipe/__init__.py`, `jellyswipe/jellyfin_library.py`, `jellyswipe/base.py`, `pyproject.toml`. HIGH confidence.

---
*Feature research for: Jelly Swipe v1.6 Outbound HTTP Hardening*
*Researched: 2026-04-26*
