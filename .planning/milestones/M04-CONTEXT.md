# Milestone Context: v1.6 — Harden Outbound HTTP

**Created:** 2026-04-26
**Status:** Planning
**Epic ID:** EPIC-04

---

## Milestone Goal

Harden outbound HTTP security by addressing timeout issues, API key exposure, exception information leakage, SSRF vulnerabilities, and add rate limiting to sensitive endpoints.

---

## Severity: High

**Affected files:**
- `jellyswipe/__init__.py` — `/get-trailer`, `/cast`, `/proxy` routes
- `jellyswipe/jellyfin_library.py` — `fetch_library_image`, `server_info` methods

---

## Problems

### 1. No Timeout on TMDB Requests
**Severity: High**
**Location:** `jellyswipe/__init__.py:187, 191, 206, 210`

Multiple `requests.get()` calls for TMDB API lack timeout parameters:
- `get_trailer()` — lines 187, 191
- `get_cast()` — lines 206, 210

A slow TMDB response stalls a gunicorn-gevent worker indefinitely (effectively forever). The Jellyfin client uses `timeout=30/60/90`, but module-level `requests.get` in `__init__.py` does not.

**Impact:** Worker exhaustion, denial of service, degraded application performance.

---

### 2. TMDB API Key in URL Query String
**Severity: High**
**Location:** `jellyswipe/__init__.py:186, 190, 205, 209`

TMDB API key is exposed in URL query parameters:
```python
search_url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={item.title}&year={item.year}"
```

**Impact:**
- Logged by every reverse proxy
- Visible in any intermediate request logs
- Credential leakage in access logs

**Fix:** Move to header `Authorization: Bearer <v4-token>` (TMDB v4 supports it) or POST body.

---

### 3. Raw Exception Message Leak
**Severity: Medium**
**Location:** Multiple routes

Pattern: `except Exception as e: return jsonify({'error': str(e)}), 500`

Affected routes:
- `/get-trailer` — lines 198, 199
- `/cast` — lines 223, 225
- `/watchlist/add` (similar pattern)
- `/plex/server-info` (indirectly via Response of stored JSON)
- `/movies` (indirectly via Response of stored JSON)

**Impact:** `str(e)` may include:
- Upstream URLs
- IP addresses
- Partial request bodies
- Internal file paths
- Stack traces

**Fix:** Return a redacted message with RequestId + structured server-side logging.

---

### 4. /Proxy Allowlist Unrate-Limited and Unauthenticated
**Severity: High**
**Location:** `jellyswipe/__init__.py` — `/proxy` route

The `/proxy` endpoint:
- Has correct allowlist validation
- Lacks rate limiting
- Lacks authentication requirements
- Allows anyone who can reach the app to drive arbitrary `Items/{id}/Images/Primary` traffic to the operator's Jellyfin server
- Bypasses Jellyfin's own auth (request is signed with operator's API key by the app)

**Impact:**
- Resource exhaustion attacks
- Abuse of operator's Jellyfin server bandwidth
- Potential privacy violations

**Fix:** Add low-effort rate limit and require authenticated session at minimum.

---

### 5. server_info() Fallback with Limited Error Handling
**Severity: Medium**
**Location:** `jellyswipe/jellyfin_library.py:354`

```python
r = requests.get(f"{self._base}/System/Info/Public", timeout=15)
```

**Issues:**
- Falls back to `/System/Info/Public` with no error handling
- Limited timeout sanity (only 15 seconds)
- Endpoint name `/plex/server-info` kept for back-compat (see EPIC-08)

**Impact:** Potential timeout hangs, unclear error states.

---

### 6. No URL Validation (SSRF Vulnerability)
**Severity: High**
**Location:** Environment variable usage throughout

`JELLYFIN_URL` is:
- Whatever the operator sets
- Concatenated into requests calls without scheme/host validation
- No validation against private/loopback ranges

**Attack Vector:** Misconfigured or malicious operator can point this at:
- `http://169.254.169.254/...` (cloud metadata service)
- `http://localhost:631/` (local services)
- `http://10.0.0.1/` (internal network)
- Other internal infrastructure

**Fix:** Validate scheme is `http` or `https` and host is not in private/loopback ranges unless `ALLOW_PRIVATE_JELLYFIN=1` is explicitly set.

---

## Fix Outline

### 1. Centralize Outbound HTTP
Create one helper function that:
- Always sets `timeout=(connect, read)`
- Applies consistent User-Agent header
- Logs structured outcome (success/failure, duration, status code)
- Handles exceptions properly

**Impact:** Single point of control for all outbound HTTP.

---

### 2. Replace TMDB v3 URL-Key with v4 Bearer Token
- Migrate from TMDB API v3 (URL parameter) to v4 (Bearer token)
- Update all TMDB API calls to use `Authorization: Bearer <token>` header
- Remove `api_key=` from URL strings

**Impact:** Credential protection from logs and intermediaries.

---

### 3. Replace Exception Exposure with RequestId + Structured Logging
- Generate unique RequestId per request
- Log full exception details server-side with RequestId
- Return only RequestId + generic error message to client
- Update all error handling to follow this pattern

**Impact:** Better debugging for operators, no information leakage to users.

---

### 4. Add Rate Limiting
Implement token-bucket rate limiter for sensitive routes:
- `/proxy`
- `/get-trailer`
- `/cast`
- `/watchlist/add`

Use either:
- Flask-Limiter (if already available)
- Tiny in-memory bucket implementation

**Impact:** Prevent abuse and resource exhaustion.

---

### 5. Add JELLYFIN_URL Validator
Create boot-time validation that:
- Checks URL scheme is `http` or `https`
- Parses hostname and validates against private/loopback ranges
- Rejects metadata-service IPs (`169.254.169.254`)
- Allows private ranges only if `ALLOW_PRIVATE_JELLYFIN=1` is set
- Fails fast on startup if validation fails

**Impact:** SSRF protection, clear configuration errors.

---

## Acceptance Criteria

### 1. Timeout Coverage
✅ All `requests.*` calls in the project have timeouts
- Audit via `grep` for `requests\.`
- Every call must include `timeout=` parameter

---

### 2. TMDB Key Protection
✅ TMDB key never appears in URL strings
- Audit via `grep` for `api_key=`
- All TMDB calls use Authorization header

---

### 3. Error Message Sanitization
✅ 5xx responses contain RequestId, not upstream exception
- Audit error handling in all routes
- Verify `str(e)` is never returned to client

---

### 4. SSRF Protection
✅ Unit test asserts metadata-IP base URLs are rejected
- Test `169.254.169.254` is rejected
- Test `localhost` is rejected without env var
- Test `10.0.0.1` is rejected without env var
- Test valid URLs are accepted

---

### 5. Rate Limiting
✅ Sensitive endpoints have rate limits
- Verify rate limiter is configured
- Test rate limit enforcement

---

## Discovery Level

**Level 1 (Light Research)** — External API docs and patterns:
- TMDB v4 API authentication docs
- Flask-Limiter or rate limiting best practices
- URL validation libraries and private IP ranges
- RequestId generation patterns

---

## Security Context

This milestone addresses multiple high-severity security issues:

1. **Worker exhaustion** via untimeouted requests
2. **Credential leakage** via URL query parameters
3. **Information disclosure** via exception messages
4. **Resource abuse** via unrate-limited proxy
5. **SSRF attacks** via unvalidated URLs

**Risk if deferred:** High — these are exploitable vulnerabilities that could lead to:
- Denial of service
- Credential compromise
- Internal network scanning
- Data exfiltration

---

## Dependencies

- None — this can be started immediately after v1.5 completion
- May benefit from existing testing infrastructure from v1.3

---

## Known Constraints

### From TESTING.md
- Use pytest for all tests
- Mock external HTTP requests
- Test validation logic independently

### From CONVENTIONS.md
- Follow existing error handling patterns where possible
- Use structured logging
- Maintain backward compatibility where feasible

---

## Open Questions / Gray Areas

1. **TMDB v4 Compatibility:** Does the operator's TMDB API key support v4 authentication, or do we need to stay with v3 and use POST body for key protection?

2. **Rate Limit Thresholds:** What are appropriate rate limits for `/proxy`, `/get-trailer`, `/cast`, `/watchlist/add`? Need to balance usability vs. abuse prevention.

3. **RequestId Storage:** Should RequestIds be stored in memory for debugging, or just logged? If stored, for how long?

4. **Flask-Limiter Dependency:** Is Flask-Limiter acceptable, or should we implement a tiny in-memory bucket to avoid new dependencies?

---

*Context created: 2026-04-26*