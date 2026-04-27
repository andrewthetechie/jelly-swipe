# Phase 28: Deployment Validation - Context

**Gathered:** 2026-04-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Validate the refactored application works correctly in Docker deployment with proper cookie security, proxy headers, and end-to-end flow. All 54+ existing tests must continue passing. New tests added for v2.0 features. No new requirements — this is validation of Phases 23-27.

**Requirements:** (validation phase — validates all 14 v2.0 requirements end-to-end)

**Depends on:** Phase 27 (all code changes complete)

</domain>

<decisions>
## Implementation Decisions

### Validation Scope
- **D-01:** Full E2E validation — Docker container builds and starts, ProxyFix headers correct, full auth → room → swipe → SSE match → deep link flow works.
- **D-02:** Verify session cookie security: HttpOnly flag, SameSite=Lax, Secure flag when behind HTTPS proxy.

### Test Compatibility
- **D-03:** All 54+ existing tests must continue passing after all v2.0 changes. Tests that rely on old route patterns must be updated to use new RESTful routes.
- **D-04:** New tests added for v2.0-specific features: auth vault, session cookie identity, RESTful routes, SSE-only match delivery, deep link generation.

### Docker Validation
- **D-05:** Verify multi-stage Docker build still works with new `auth.py` module
- **D-06:** Verify `uv sync --frozen` still resolves all dependencies (no new dependencies expected)
- **D-07:** Verify gunicorn + gevent workers start without errors

### the agent's Discretion
- Exact E2E test methodology (automated script vs manual checklist)
- How many new tests to add
- Whether to add a test for the TOCTOU race condition fix

</decisions>

<canonical_refs>
## Canonical References

### Phase requirements and research
- `.planning/ROADMAP.md` §Phase 28 — Success criteria
- `.planning/research/SUMMARY.md` — Docker considerations, ProxyFix notes
- `.planning/research/PITFALLS.md` — Cookie security behind reverse proxy, SESSION_COOKIE_SECURE

### Existing codebase
- `Dockerfile` — Multi-stage build that must work with new module structure
- `tests/` — Existing test suite that must pass
- `.github/workflows/` — CI workflows that must pass

### Prior phase decisions
- All prior phase CONTEXT.md files (23-27) — Validating their implementations

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tests/conftest.py` — Test fixtures with monkeypatching for clean imports
- `tests/test_routes_xss.py` — 6 XSS smoke tests (should pass unchanged)
- `.github/workflows/test.yml` — CI workflow running tests on push/PR

### Established Patterns
- Function-scoped fixtures for test isolation
- Mocked HTTP requests to prevent external API calls
- pytest-cov terminal output for coverage reporting

### Integration Points
- Dockerfile CMD must find `auth.py` module
- CI workflow must install any new dependencies (none expected)
- Test suite must cover new auth module routes

</code_context>

<specifics>
## Specific Ideas

- The Docker build is the primary validation gate — if it builds and starts, the basics work
- Existing XSS tests prove the CSP + safe DOM changes survived — they should continue passing
- The TOCTOU race fix (BEGIN IMMEDIATE) should have a dedicated test

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 28-deployment-validation*
*Context gathered: 2026-04-26*
