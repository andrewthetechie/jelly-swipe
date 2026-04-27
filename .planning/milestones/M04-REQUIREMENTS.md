# Requirements: Jelly Swipe — v1.6 Harden Outbound HTTP

**Milestone:** v1.6 Harden Outbound HTTP
**Theme:** Harden outbound HTTP: TMDB calls, image proxy, and SSRF surface
**Total Requirements:** 20
**Status:** Gap Closure — 3/20 verified, 4 assigned to Phase 28, 13 in Phases 25-27

---

## Requirement Categories

- **HTTP-** — HTTP client security and reliability
- **TMDB-** — TMDB API integration security
- **ERR-** — Error handling and information disclosure
- **RL-** — Rate limiting and abuse prevention
- **SSRF-** — Server-Side Request Forgery protection
- **TEST-** — Test coverage and validation

---

## HTTP-01: Centralized HTTP Client Helper

**Description:** All outbound HTTP requests must use a centralized helper function that enforces security best practices.

**Success Criteria:**
- [ ] Helper function `make_http_request()` exists in `jellyswipe/http_client.py`
- [ ] Helper accepts `method`, `url`, `headers`, `params`, `json`, `timeout=(connect, read)` parameters
- [ ] Helper sets default User-Agent header: `JellySwipe/1.6 (+https://github.com/andrewthetechie/jelly-swipe)`
- [ ] Helper enforces timeout: default `(5, 30)` for connect/read
- [ ] Helper logs structured outcome: method, url, status_code, duration_ms, success/failure
- [ ] Helper catches requests exceptions and re-raises with context

**Validation:** Code review + unit tests for helper function.

---

## HTTP-02: All requests.get Calls Use Helper

**Description:** Replace all direct `requests.get()` calls with the centralized helper.

**Success Criteria:**
- [ ] No direct `requests.get()` calls remain in codebase (grep audit)
- [ ] All TMDB API calls use `make_http_request()`
- [ ] All Jellyfin API calls use `make_http_request()`
- [ ] All image proxy calls use `make_http_request()`

**Validation:** Grep for `requests\.get` and verify all use helper.

---

## HTTP-03: All requests.post Calls Use Helper

**Description:** Replace all direct `requests.post()` calls with the centralized helper.

**Success Criteria:**
- [ ] No direct `requests.post()` calls remain in codebase (grep audit)
- [ ] All POST requests use `make_http_request()`

**Validation:** Grep for `requests\.post` and verify all use helper.

---

## HTTP-04: All requests Calls Have Timeouts

**Description:** Ensure every HTTP request has explicit timeout parameters.

**Success Criteria:**
- [ ] `make_http_request()` requires timeout parameter
- [ ] Default timeout is `(5, 30)` for connect/read
- [ ] TMDB calls use appropriate timeout (e.g., `(5, 15)`)
- [ ] Jellyfin calls use existing timeout values (30/60/90)
- [ ] Image proxy calls use short timeout (e.g., `(3, 10)`)

**Validation:** Code review + test for timeout enforcement.

---

## TMDB-01: TMDB v4 Bearer Token Authentication

**Description:** Migrate TMDB API from v3 URL parameter to v4 Bearer token authentication.

**Success Criteria:**
- [ ] Environment variable `TMDB_ACCESS_TOKEN` added for v4 token
- [ ] Fallback to `TMDB_API_KEY` if v4 token not available (backward compatibility)
- [ ] All TMDB API calls use `Authorization: Bearer <token>` header
- [ ] No TMDB API calls include `api_key=` in URL query string
- [ ] Documentation updated to explain v4 token requirement

**Validation:** Grep for `api_key=` in TMDB URLs (should be none) + manual testing.

---

## TMDB-02: TMDB API Key Never in URL

**Description:** Ensure TMDB API credentials are never exposed in URL query strings.

**Success Criteria:**
- [ ] No `?api_key=` or `&api_key=` in any TMDB URL construction
- [ ] TMDB credentials only in Authorization header
- [ ] Log redaction ensures Authorization header is not logged
- [ ] Access logs show only path, not full query string with credentials

**Validation:** Grep audit + log inspection test.

---

## ERR-01: RequestId Generation

**Description:** Generate unique RequestId for each incoming request to enable error tracing.

**Success Criteria:**
- [ ] RequestId generation function exists (UUID v4 or similar)
- [ ] RequestId stored in Flask request context (`request.request_id`)
- [ ] RequestId included in all server-side log entries
- [ ] RequestId format: `req_<timestamp>_<random>` (e.g., `req_1714123456_abc123`)

**Validation:** Unit test for RequestId generation + log inspection.

---

## ERR-02: Structured Error Logging

**Description:** Log full exception details server-side with RequestId, return only generic message to client.

**Success Criteria:**
- [ ] All exception handlers log full details with RequestId
- [ ] Log includes: timestamp, request_id, route, method, exception_type, exception_message, stack_trace
- [ ] Log level is ERROR for 5xx, WARNING for 4xx
- [ ] Client receives only: `{"error": "Internal server error", "request_id": "req_..."}`

**Validation:** Code review + test error logging behavior.

---

## ERR-03: No str(e) in Client Responses

**Description:** Remove all instances where exception messages are directly returned to clients.

**Success Criteria:**
- [ ] No `return jsonify({'error': str(e)})` patterns remain
- [ ] No `str(e)` in any JSON response body
- [ ] All error responses use generic messages + RequestId
- [ ] Debug information only in server logs

**Validation:** Grep for `str(e)` in return statements (should be none).

---

## ERR-04: Error Response Consistency

**Description:** Ensure all error responses follow consistent format across all routes.

**Success Criteria:**
- [ ] All 4xx responses: `{"error": "<specific message>", "request_id": "..."}`
- [ ] All 5xx responses: `{"error": "Internal server error", "request_id": "..."}`
- [ ] All error responses include appropriate HTTP status code
- [ ] All error responses include RequestId

**Validation:** Test all error paths in all routes.

---

## RL-01: Rate Limiting Infrastructure

**Description:** Implement rate limiting infrastructure to prevent abuse of sensitive endpoints.

**Success Criteria:**
- [ ] Rate limiter implemented (Flask-Limiter or in-memory token bucket)
- [ ] Rate limiter configuration: 10 requests per minute per IP for sensitive endpoints
- [ ] Rate limiter returns 429 status with `Retry-After` header
- [ ] Rate limiter logs rate limit violations

**Validation:** Unit tests for rate limiter + integration tests.

---

## RL-02: /proxy Rate Limiting

**Description:** Apply rate limiting to the `/proxy` endpoint to prevent abuse.

**Success Criteria:**
- [ ] `/proxy` endpoint has rate limit: 10 requests/minute/IP
- [ ] Rate limit applies before allowlist validation
- [ ] Rate limit exceeded returns 429 with Retry-After header
- [ ] Rate limit violations are logged

**Validation:** Test rate limit enforcement on `/proxy`.

---

## RL-03: TMDB Endpoints Rate Limiting

**Description:** Apply rate limiting to TMDB API endpoints to prevent API abuse.

**Success Criteria:**
- [ ] `/get-trailer` has rate limit: 20 requests/minute/IP
- [ ] `/cast` has rate limit: 20 requests/minute/IP
- [ ] Rate limits prevent TMDB API quota exhaustion
- [ ] Rate limit violations are logged

**Validation:** Test rate limit enforcement on TMDB endpoints.

---

## RL-04: /watchlist/add Rate Limiting

**Description:** Apply rate limiting to the `/watchlist/add` endpoint to prevent spam.

**Success Criteria:**
- [ ] `/watchlist/add` has rate limit: 30 requests/minute/IP
- [ ] Rate limit applies before watchlist modification
- [ ] Rate limit exceeded returns 429 with Retry-After header
- [ ] Rate limit violations are logged

**Validation:** Test rate limit enforcement on `/watchlist/add`.

---

## SSRF-01: JELLYFIN_URL Scheme Validation

**Description:** Validate that JELLYFIN_URL uses only http or https schemes.

**Success Criteria:**
- [ ] Boot-time validation function exists
- [ ] Validation rejects non-http/https schemes (ftp, file, etc.)
- [ ] Validation fails fast on startup if scheme is invalid
- [ ] Error message clearly indicates the problem

**Validation:** Unit tests for scheme validation.

---

## SSRF-02: JELLYFIN_URL Private IP Rejection

**Description:** Reject JELLYFIN_URL hosts in private/loopback IP ranges unless explicitly allowed.

**Success Criteria:**
- [ ] Validation rejects 127.0.0.0/8 (loopback)
- [ ] Validation rejects 10.0.0.0/8 (private Class A)
- [ ] Validation rejects 172.16.0.0/12 (private Class B)
- [ ] Validation rejects 192.168.0.0/16 (private Class C)
- [ ] Validation rejects 169.254.169.254 (metadata service)
- [ ] Validation allows private ranges only if `ALLOW_PRIVATE_JELLYFIN=1` is set
- [ ] localhost hostname rejected unless env var set

**Validation:** Unit tests for IP range validation.

---

## SSRF-03: JELLYFIN_URL Hostname Resolution

**Description:** Resolve JELLYFIN_URL hostname to IP and validate the resolved address.

**Success Criteria:**
- [ ] Hostname is resolved to IP address
- [ ] Resolved IP is validated against private ranges
- [ ] DNS rebinding attacks are prevented (validate after resolution)
- [ ] Caching considerations: resolve once at startup, not per-request

**Validation:** Unit tests for hostname resolution + security review.

---

## SSRF-04: SSRF Unit Tests

**Description:** Comprehensive unit tests for SSRF protection.

**Success Criteria:**
- [ ] Test `169.254.169.254` is rejected
- [ ] Test `http://localhost:8096` is rejected without env var
- [ ] Test `http://127.0.0.1:8096` is rejected without env var
- [ ] Test `http://10.0.0.1:8096` is rejected without env var
- [ ] Test `http://172.16.0.1:8096` is rejected without env var
- [ ] Test `http://192.168.1.1:8096` is rejected without env var
- [ ] Test valid public URLs are accepted
- [ ] Test private URLs accepted when `ALLOW_PRIVATE_JELLYFIN=1` is set
- [ ] Test invalid schemes (ftp, file) are rejected

**Validation:** All SSRF tests pass.

---

## TEST-01: HTTP Client Helper Tests

**Description:** Unit tests for the centralized HTTP client helper.

**Success Criteria:**
- [ ] Test timeout enforcement
- [ ] Test User-Agent header setting
- [ ] Test structured logging on success
- [ ] Test structured logging on failure
- [ ] Test exception handling and re-raising
- [ ] Test different HTTP methods (GET, POST)

**Validation:** All HTTP client helper tests pass.

---

## TEST-02: Error Handling Tests

**Description:** Unit tests for error handling and RequestId propagation.

**Success Criteria:**
- [ ] Test RequestId generation and propagation
- [ ] Test error logging with RequestId
- [ ] Test client error responses contain RequestId
- [ ] Test no exception details in client responses
- [ ] Test all error paths in main routes

**Validation:** All error handling tests pass.

---

## Requirement Traceability Matrix

| Req ID | Category | Description | Priority | Status |
|--------|----------|-------------|----------|--------|
| HTTP-01 | HTTP | Centralized HTTP Client Helper | High | Phase 28 (Gap Closure) |
| HTTP-02 | HTTP | All requests.get Calls Use Helper | High | Phase 23/24 (Verified) |
| HTTP-03 | HTTP | All requests.post Calls Use Helper | Medium | Phase 28 (Gap Closure) |
| HTTP-04 | HTTP | All requests Calls Have Timeouts | High | Phase 28 (Gap Closure) |
| TMDB-01 | TMDB | TMDB v4 Bearer Token Authentication | High | Phase 24 (Verified) |
| TMDB-02 | TMDB | TMDB API Key Never in URL | High | Phase 24 (Verified) |
| ERR-01 | Error | RequestId Generation | High | Pending |
| ERR-02 | Error | Structured Error Logging | High | Pending |
| ERR-03 | Error | No str(e) in Client Responses | High | Pending |
| ERR-04 | Error | Error Response Consistency | Medium | Pending |
| RL-01 | Rate Limit | Rate Limiting Infrastructure | High | Pending |
| RL-02 | Rate Limit | /proxy Rate Limiting | High | Pending |
| RL-03 | Rate Limit | TMDB Endpoints Rate Limiting | High | Pending |
| RL-04 | Rate Limit | /watchlist/add Rate Limiting | Medium | Pending |
| SSRF-01 | SSRF | JELLYFIN_URL Scheme Validation | High | Pending |
| SSRF-02 | SSRF | JELLYFIN_URL Private IP Rejection | High | Pending |
| SSRF-03 | SSRF | JELLYFIN_URL Hostname Resolution | High | Pending |
| SSRF-04 | SSRF | SSRF Unit Tests | High | Pending |
| TEST-01 | Test | HTTP Client Helper Tests | Medium | Phase 28 (Gap Closure) |
| TEST-02 | Test | Error Handling Tests | Medium | Pending |

---

**Total Requirements:** 20
**High Priority:** 16
**Medium Priority:** 4
**Status:** All Pending

---

*Requirements created: 2026-04-26*