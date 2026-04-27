# Roadmap: Jelly Swipe — v1.6 Harden Outbound HTTP

**Milestone:** v1.6 Harden Outbound HTTP
**Status:** Planning
**Theme:** Harden outbound HTTP: TMDB calls, image proxy, and SSRF surface
**Epic:** EPIC-04
**Phases:** 23–27 (HTTP client 23, TMDB security 24, error handling 25, rate limiting 26, SSRF protection 27)

**Phase archive:** [v1.6-phases/](v1.6-phases/) (Phases 23–27) — *To be created*

---

## Milestone Overview

This milestone hardens outbound HTTP security by addressing critical vulnerabilities: worker exhaustion via untimeouted requests, credential leakage via URL query parameters, information disclosure via exception messages, resource abuse via unrate-limited endpoints, and Server-Side Request Forgery (SSRF) via unvalidated URLs.

**Total Phases:** 5
**Total Requirements:** 20
**Severity:** High

---

## Phase 23: HTTP Client Centralization

**Goal:** All outbound HTTP requests use a centralized helper function that enforces security best practices: timeouts, User-Agent headers, structured logging, and proper error handling.

**Depends on:** Nothing (first phase of v1.6)

**Requirements:** HTTP-01, HTTP-02, HTTP-03, HTTP-04, TEST-01

**Success Criteria**:
1. Centralized `make_http_request()` helper function exists in `jellyswipe/http_client.py`
2. All `requests.get()` and `requests.post()` calls replaced with helper
3. Every HTTP request has explicit timeout parameters (default: 5s connect, 30s read)
4. Helper sets consistent User-Agent header and logs structured outcomes
5. Unit tests validate timeout enforcement, header setting, and error handling

**Plans:** *To be created*

**Status:** ⏳ **PLANNING**

---

## Phase 24: TMDB Security

**Goal:** Migrate TMDB API from v3 URL parameter authentication to v4 Bearer token, eliminating credential exposure in logs and intermediate systems.

**Depends on:** Phase 23 (HTTP client helper in place)

**Requirements:** TMDB-01, TMDB-02

**Success Criteria**:
1. Environment variable `TMDB_ACCESS_TOKEN` supported for v4 token authentication
2. All TMDB API calls use `Authorization: Bearer <token>` header
3. No `api_key=` appears in any TMDB URL query string
4. Backward compatibility maintained with `TMDB_API_KEY` fallback
5. Documentation updated to explain v4 token preference

**Plans:** *To be created*

**Status:** ⏳ **PLANNING**

---

## Phase 25: Error Handling & RequestId

**Goal:** Implement structured error handling with RequestId tracing; ensure clients receive generic error messages while operators get detailed logs.

**Depends on:** Phase 23 (HTTP client helper provides foundation for structured logging)

**Requirements:** ERR-01, ERR-02, ERR-03, ERR-04, TEST-02

**Success Criteria**:
1. Unique RequestId generated for each incoming request (format: `req_<timestamp>_<random>`)
2. All exceptions logged server-side with full details + RequestId
3. Client responses contain only generic error messages + RequestId
4. No `str(e)` or exception details returned to clients
5. All error responses follow consistent format across all routes
6. Unit tests validate RequestId propagation and error sanitization

**Plans:** *To be created*

**Status:** ⏳ **PLANNING**

---

## Phase 26: Rate Limiting

**Goal:** Implement rate limiting on sensitive endpoints to prevent abuse, resource exhaustion, and API quota depletion.

**Depends on:** Phase 25 (error handling provides foundation for 429 responses)

**Requirements:** RL-01, RL-02, RL-03, RL-04

**Success Criteria**:
1. Rate limiting infrastructure implemented (Flask-Limiter or in-memory token bucket)
2. `/proxy` endpoint: 10 requests/minute/IP
3. `/get-trailer` and `/cast` endpoints: 20 requests/minute/IP
4. `/watchlist/add` endpoint: 30 requests/minute/IP
5. Rate limit exceeded returns 429 with `Retry-After` header
6. Rate limit violations logged for operator visibility

**Plans:** *To be created*

**Status:** ⏳ **PLANNING**

---

## Phase 27: SSRF Protection

**Goal:** Validate JELLYFIN_URL to prevent Server-Side Request Forgery attacks; reject private/loopback IP ranges and metadata service endpoints unless explicitly allowed.

**Depends on:** Phase 25 (error handling provides foundation for validation errors)

**Requirements:** SSRF-01, SSRF-02, SSRF-03, SSRF-04

**Success Criteria**:
1. Boot-time validation of JELLYFIN_URL scheme (http/https only)
2. Hostname resolved to IP and validated against private ranges
3. Rejected by default: 127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.169.254
4. Private ranges allowed only if `ALLOW_PRIVATE_JELLYFIN=1` is set
5. DNS rebinding attacks prevented (post-resolution validation)
6. Comprehensive unit tests for all SSRF scenarios

**Plans:** *To be created*

**Status:** ⏳ **PLANNING**

---

## Milestone Acceptance Criteria

From EPIC-04 specification, the following must be TRUE when this milestone is complete:

1. ✅ All `requests.*` calls in the project have timeouts (grep audit)
2. ✅ TMDB key never appears in URL strings (grep audit + manual testing)
3. ✅ 5xx responses contain RequestId, not upstream exception (error response tests)
4. ✅ Unit test asserts metadata-IP base URLs are rejected (SSRF tests)

---

## Security Impact

This milestone addresses multiple high-severity security vulnerabilities:

| Vulnerability | Impact | Mitigation |
|--------------|--------|------------|
| Worker exhaustion | DoS via slow upstream responses | Timeouts on all HTTP calls |
| Credential leakage | TMDB key in proxy logs | Bearer token authentication |
| Information disclosure | Exception details to clients | RequestId + structured logging |
| Resource abuse | Unrate-limited proxy endpoint | Rate limiting on sensitive routes |
| SSRF attacks | Internal network scanning | URL validation + IP rejection |

**Risk if deferred:** HIGH — exploitable vulnerabilities leading to DoS, credential compromise, internal network access, and data exfiltration.

---

## Dependencies & Constraints

### Dependencies
- None — can start immediately after v1.5 completion
- Benefits from v1.3 testing infrastructure (pytest framework)

### Constraints
From TESTING.md and CONVENTIONS.md:
- Use pytest for all tests
- Mock external HTTP requests in tests
- Follow existing error handling patterns where possible
- Use structured logging
- Maintain backward compatibility (TMDB v3 fallback)
- Single-responsibility principle for HTTP client helper

---

## Open Questions

1. **TMDB v4 Compatibility:** Does operator's TMDB API key support v4, or stay with v3 + POST body?
2. **Rate Limit Thresholds:** Are 10/20/30 req/min appropriate for production use?
3. **RequestId Storage:** In-memory or transient only? Retention duration?
4. **Flask-Limiter Dependency:** Acceptable or prefer in-memory implementation?

---

## Notes

- This is a **high-severity security milestone** — prioritize over feature work
- SSRF protection is critical for deployments in cloud environments
- Rate limiting protects both the application and upstream APIs (TMDB, Jellyfin)
- RequestId tracing improves debuggability without compromising security
- HTTP client centralization provides foundation for future observability features

---

*Roadmap created: 2026-04-26*