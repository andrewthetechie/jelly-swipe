---
phase: 26
slug: rate-limiting
status: verified
threats_open: 0
asvs_level: 1
created: 2026-04-27
---

# Phase 26 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Client → rate_limiter.check() | Untrusted IP address from request.remote_addr (behind ProxyFix) | IP address (low sensitivity) |
| Client → rate_limit decorator | Untrusted input: IP from request.remote_addr, endpoint name from Flask | IP address, endpoint name (low sensitivity) |
| rate_limit decorator → make_error_response | Trusted internal call | Error message, status code (internal) |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-26-01 | S (Spoofing) | rate_limiter.check() | accept | IP spoofing via X-Forwarded-For: ProxyFix with x_for=1 already configured; operator configures reverse proxy to strip untrusted headers | closed |
| T-26-02 | D (DoS) | RateLimiter._buckets | mitigate | Max bucket cap of 10,000 prevents memory exhaustion from unique IP flood | closed |
| T-26-03 | D (DoS) | RateLimiter.check() | mitigate | Lazy stale eviction removes idle buckets after 5 minutes (300s) | closed |
| T-26-04 | S (Spoofing) | rate_limit decorator | accept | IP spoofing: already mitigated by ProxyFix config; operator sets reverse proxy to strip untrusted X-Forwarded-For | closed |
| T-26-05 | I (Info Disclosure) | 429 response body | mitigate | make_error_response() includes only generic message + request_id, no internal state leaked | closed |
| T-26-06 | D (DoS) | rate_limit decorator | mitigate | Per-endpoint limits prevent any single endpoint from being abused to exhaustion; independent buckets prevent cross-endpoint amplification | closed |
| T-26-07 | D (DoS) | rate_limiter singleton memory | accept | Max 10,000 bucket cap and stale eviction limit memory growth; ~1MB max for a home-server app is acceptable | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-26-01 | T-26-01, T-26-04 | IP spoofing via X-Forwarded-For headers cannot be fully prevented at the application layer. ProxyFix with x_for=1 is already configured; the operator is responsible for configuring the reverse proxy (nginx/Caddy) to strip untrusted X-Forwarded-For headers before they reach the app. This is standard practice for self-hosted apps. | gsd-security-auditor | 2026-04-27 |
| AR-26-02 | T-26-07 | Rate limiter memory bounded to ~1MB (10,000 buckets × ~100 bytes each) via max bucket cap and 5-minute stale eviction. For a home-server app, this memory ceiling is acceptable and does not warrant additional complexity. | gsd-security-auditor | 2026-04-27 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-04-27 | 7 | 7 | 0 | gsd-security-auditor |

### Verification Evidence

| Threat ID | Evidence |
|-----------|----------|
| T-26-01 | Accepted — see AR-26-01 |
| T-26-02 | `jellyswipe/rate_limiter.py:66` max_buckets=10000, `:99-100` cap enforcement, `:120-125` _evict_oldest() |
| T-26-03 | `jellyswipe/rate_limiter.py:66` stale_seconds=300.0, `:91` _evict_stale() called on every check, `:110-118` implementation |
| T-26-04 | Accepted — see AR-26-01 |
| T-26-05 | `jellyswipe/__init__.py:136-140` make_error_response("Rate limit exceeded", 429), `:64-77` only {error, request_id, retry_after} in body |
| T-26-06 | `jellyswipe/__init__.py:293` @rate_limit(20), `:328` @rate_limit(20), `:369` @rate_limit(30), `:670` @rate_limit(10) — 4 independent per-endpoint buckets |
| T-26-07 | Accepted — see AR-26-02 |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-04-27
