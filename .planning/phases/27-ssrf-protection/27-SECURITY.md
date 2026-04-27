---
phase: 27
slug: ssrf-protection
status: verified
threats_open: 0
asvs_level: 1
created: 2026-04-27
---

# Phase 27 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| env vars → ssrf_validator | JELLYFIN_URL and ALLOW_PRIVATE_JELLYFIN from environment (untrusted input) | URL string (attacker-controlled if env compromised) |
| ssrf_validator → DNS resolver | socket.getaddrinfo makes network call to configured DNS resolver | Hostname only (no credentials or paths) |
| ssrf_validator → app startup | RuntimeError prevents app from starting with invalid URL (fail-closed) | Validation result (pass / RuntimeError) |
| boot validation → app lifecycle | JELLYFIN_URL validated before any outbound HTTP request can be made | Validated URL string |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-27-01 | Spoofing | JELLYFIN_URL env var | mitigate | Scheme validation rejects non-http/https (SSRF-01) | closed |
| T-27-02 | Tampering | DNS response poisoning | accept | Boot-only validation per D-08 — operator controls DNS in self-hosted context | closed |
| T-27-03 | Repudiation | SSRF validation bypass | accept | Override is host-level env var, not API-accessible; no audit trail needed | closed |
| T-27-04 | Info disclosure | DNS query for JELLYFIN_URL hostname | accept | Only hostname leaks to DNS resolver; no credentials or paths in query | closed |
| T-27-05 | Denial of service | DNS failure blocks startup | accept | Fail-closed behavior per D-04 — app refuses to start without valid URL | closed |
| T-27-06 | Elevation of privilege | ALLOW_PRIVATE_JELLYFIN=1 bypass | mitigate | Requires host-level env var access; cannot be set via HTTP request | closed |
| T-27-07 | Elevation of privilege | Missing validate_jellyfin_url call in boot sequence | mitigate | Import and call placed after env var check, before Flask app creation | closed |
| T-27-08 | Denial of service | validate_jellyfin_url raises on valid public URL | mitigate | Tests verify public URLs (mock DNS → 93.184.216.34) pass without error | closed |
| T-27-09 | Tampering | ALLOW_PRIVATE_JELLYFIN=1 in test config | accept | Test-only override; production must set explicitly via env var | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-27-01 | T-27-02 | DNS rebinding risk accepted — boot-only validation per D-08. Self-hosted context where operator controls DNS; rebinding during boot-time window is extremely unlikely. | Phase 27 planning | 2026-04-27 |
| AR-27-02 | T-27-03 | No audit trail for ALLOW_PRIVATE_JELLYFIN override — operator sets env var at host level (not via API). Host-level access already implies full control. | Phase 27 planning | 2026-04-27 |
| AR-27-03 | T-27-04 | Only JELLYFIN_URL hostname is sent to DNS resolver — no credentials, paths, or sensitive data leak through DNS queries. | Phase 27 planning | 2026-04-27 |
| AR-27-04 | T-27-05 | DNS failure blocks startup (fail-closed per D-04). App refuses to start without resolvable hostname — this is the desired security behavior. | Phase 27 planning | 2026-04-27 |
| AR-27-05 | T-27-09 | ALLOW_PRIVATE_JELLYFIN=1 in tests/conftest.py is test-only override. Production must set explicitly via environment variable. Cannot be set via HTTP request. | Phase 27 planning | 2026-04-27 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-04-27 | 9 | 9 | 0 | gsd-security-auditor |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-04-27
