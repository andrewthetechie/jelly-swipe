# Phase 27: SSRF Protection - Context

**Gathered:** 2026-04-27
**Status:** Ready for planning
**Source:** ROADMAP Phase 27 specification + M04-REQUIREMENTS.md (SSRF-01 through SSRF-04) + Phase 25/26 infrastructure

<domain>
## Phase Boundary

Validate the `JELLYFIN_URL` environment variable at boot time to prevent Server-Side Request Forgery (SSRF) attacks. Reject non-http/https schemes, block private/loopback/metadata IP ranges (IPv4 and IPv6), resolve hostnames to IPs before validation, and provide an operator bypass via `ALLOW_PRIVATE_JELLYFIN=1` for self-hosted setups that legitimately use local addresses.

**In scope:**
- Boot-time URL scheme validation (http/https only)
- Hostname-to-IP resolution with private range rejection
- IPv4 private ranges: `127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.169.254`
- IPv6 private ranges: `::1`, `fc00::/7`, `fe80::/10`
- `ALLOW_PRIVATE_JELLYFIN=1` override for self-hosted operators
- Hard `RuntimeError` on validation failure (DNS failure, private IP, bad scheme)
- Integration into existing env-var validation block at boot
- Comprehensive unit tests for all SSRF scenarios

**Out of scope:**
- Runtime/per-request URL validation (validated once at boot only)
- DNS rebinding attack mitigation beyond boot-time validation
- Rate limiting (Phase 26, complete)
- Error handling infrastructure (Phase 25, complete)
- HTTP client changes (Phase 23, complete)
</domain>

<decisions>
## Implementation Decisions

### Module Structure
- **D-01:** SSRF validator lives in `jellyswipe/ssrf_validator.py` — separate module following `rate_limiter.py` pattern from Phase 26. Clean separation, independently testable, imported at boot by `__init__.py`.

### IP Range Coverage
- **D-02:** Validate both IPv4 and IPv6 private ranges:
  - **IPv4:** `127.0.0.0/8` (loopback), `10.0.0.0/8` (Class A private), `172.16.0.0/12` (Class B private), `192.168.0.0/16` (Class C private), `169.254.169.254` (cloud metadata service)
  - **IPv6:** `::1` (loopback), `fc00::/7` (unique local addresses), `fe80::/10` (link-local addresses)
- **D-03:** Use Python stdlib `ipaddress` module for all IP range checks — no new dependencies.

### DNS Resolution Failure
- **D-04:** Hard `RuntimeError` at boot if hostname cannot be resolved — app refuses to start. Matches existing boot-time validation pattern (missing env vars → `RuntimeError`).
- **D-05:** Error message includes the hostname and the resolver error for operator debugging.

### Validation Timing
- **D-06:** Validate once at boot in the existing env-var validation block (`__init__.py` lines 27-45), immediately after the `JELLYFIN_URL` presence check (line 33-34).
- **D-07:** `JELLYFIN_URL` is a module-level constant (line 171) — no runtime re-validation needed. Single validation point, single pass.

### DNS Rebinding Strategy
- **D-08:** Boot-only validation — accept rebinding risk. Hostname resolves at boot, IP validated, then Python's natural DNS handles subsequent requests. Rationale: self-hosted home-server app where operator controls DNS; rebinding during the boot-time window is extremely unlikely.

### Override Semantics
- **D-09:** `ALLOW_PRIVATE_JELLYFIN` uses exact `"1"` match: `os.getenv("ALLOW_PRIVATE_JELLYFIN") == "1"`. Unambiguous, matches requirement text exactly. Operators set `ALLOW_PRIVATE_JELLYFIN=1` to enable local Jellyfin connections (e.g., `http://192.168.1.100:8096`, `http://localhost:8096`).
- **D-10:** When override is active, all private/loopback ranges are allowed (both IPv4 and IPv6). No partial override.

### Dependencies
- **D-11:** Zero new pip dependencies — stdlib only (`ipaddress`, `socket`, `urllib.parse`). Follows Phase 25 and 26 "no new deps" pattern.

### the agent's Discretion
- Exact function signatures within `ssrf_validator.py` (e.g., `validate_jellyfin_url(url: str)` or split into `validate_scheme()` + `validate_host()`)
- Internal helper function structure
- Error message wording (as long as it includes hostname and error reason)
- Test file organization and naming (new `test_ssrf_validator.py` vs extending existing)
- Whether to use `socket.getaddrinfo()` or `socket.gethostbyname()` for resolution
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v1.6 Requirements
- `.planning/milestones/M04-REQUIREMENTS.md` — SSRF-01 through SSRF-04 requirements with success criteria
- `.planning/milestones/M04-CONTEXT.md` — Problem analysis including SSRF vulnerability details (section 6: No URL Validation)

### v1.6 Roadmap
- `.planning/ROADMAP.md` §Phase 27 — Phase boundary, success criteria, dependencies

### Phase 25 Infrastructure (MUST read — error handling patterns to follow)
- `jellyswipe/__init__.py` — `make_error_response()`, `get_request_id()`, boot-time env var validation block (lines 27-45), `RuntimeError` pattern
- `.planning/phases/25-error-handling-requestid/25-CONTEXT.md` — Error handling decisions (D-01 through D-06)

### Phase 26 Infrastructure (module pattern to follow)
- `jellyswipe/rate_limiter.py` — Example of standalone module imported by `__init__.py`
- `.planning/phases/26-rate-limiting/26-CONTEXT.md` — Module placement pattern (D-26: new features go in `jellyswipe/<module>.py`)

### Codebase Conventions
- `.planning/codebase/TESTING.md` — pytest patterns, mock conventions, fixture structure
- `tests/conftest.py` — Shared test fixtures and env var setup

### Integration Points
- `jellyswipe/__init__.py` line 33-34: Current JELLYFIN_URL presence check — SSRF validation inserts here
- `jellyswipe/__init__.py` line 171: `JELLYFIN_URL = os.getenv("JELLYFIN_URL", "").rstrip("/")` — validated value
- `jellyswipe/__init__.py` line 191: `JellyfinLibraryProvider(JELLYFIN_URL)` — consumer of validated URL
- `jellyswipe/jellyfin_library.py` line 43-44: `self._base = base_url.rstrip("/")` — stored URL used for all API calls
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Boot-time env var validation pattern** (`__init__.py` lines 27-45): `missing = []` loop → `raise RuntimeError(f"Missing env vars: {missing}")`. SSRF validation adds to this block or runs immediately after.
- **Module import pattern**: `from .rate_limiter import rate_limit` — same pattern for `from .ssrf_validator import validate_jellyfin_url`.
- **Test isolation**: All HTTP mocked in `conftest.py`; `monkeypatch` for env vars; Flask test client for route tests.
- **`make_error_response()`** from Phase 25: Not needed for boot-time validation (uses `RuntimeError`), but available if any runtime validation is added later.

### Established Patterns
- **Zero new dependencies**: Phases 25 and 26 both used stdlib only — `ipaddress`, `socket`, `urllib.parse` are all stdlib.
- **Test file naming**: `test_<module>.py` for new modules (e.g., `test_rate_limiter.py` → `test_ssrf_validator.py`).
- **IPv4/IPv6 handling**: Python `ipaddress` module handles both transparently — `ipaddress.ip_address()` parses either, `ipaddress.ip_network()` defines ranges.

### Integration Points
- **Validation insertion point**: After line 34 (`missing.append("JELLYFIN_URL")` check), before line 44 (`if missing: raise RuntimeError`). If JELLYFIN_URL is present, validate it for SSRF safety immediately.
- **`JellyfinLibraryProvider.__init__`** (`jellyfin_library.py:43-44`): Receives already-validated URL. No changes needed in provider code.
- **`/proxy` route** (`__init__.py:670`): Guard at line 675 (`if not JELLYFIN_URL: abort(503)`) — no changes needed, URL already validated at boot.
</code_context>

<specifics>
## Specific Ideas

- Most self-hosted Jellyfin instances run on LAN addresses (`192.168.x.x` or `10.x.x.x`) — the `ALLOW_PRIVATE_JELLYFIN=1` override is the expected default for most operators. The SSRF protection primarily guards against cloud metadata service access (`169.254.169.254`) and unintended exposure when the app runs in a cloud/VDI environment.
- The `169.254.169.254` metadata IP is the highest-priority block — it's the AWS/GCP/Azure instance metadata endpoint that can leak IAM credentials, instance IDs, and other secrets.
- Python's `ipaddress` module is the right tool: `ipaddress.ip_address(hostname_resolved_ip) in ipaddress.ip_network("127.0.0.0/8")` works for containment checks. IPv6 equivalent: `ipaddress.ip_network("::1/128")`, `ipaddress.ip_network("fc00::/7")`, `ipaddress.ip_network("fe80::/10")`.
- `socket.getaddrinfo()` is preferred over `socket.gethostbyname()` — returns both IPv4 and IPv6 addresses, handles dual-stack hosts correctly.
</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.
</deferred>

---

*Phase: 27-ssrf-protection*
*Context gathered: 2026-04-27*
