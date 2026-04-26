# Phase 20: Security Regression Tests - Context

**Gathered:** 2026-04-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 20 adds automated route-level regression tests to prove authorization hardening remains enforced: spoofed identity headers are rejected, request-body `user_id` injection cannot bypass identity controls, and valid delegate/token identity flows still function on protected routes.

</domain>

<decisions>
## Implementation Decisions

### Route Test Harness Style
- **D-01:** Use Flask `test_client` route-level tests with monkeypatching of provider/session dependencies.
- **D-02:** Prioritize route contract assertions (`status`, payload, and data side effects) over helper-only unit assertions.

### Spoofed Header Coverage Matrix
- **D-03:** Test a full spoofed-header matrix (`X-Provider-User-Id`, `X-Jellyfin-User-Id`, `X-Emby-UserId`) across all protected routes in scope.
- **D-04:** Matrix scope includes `/room/swipe`, `/matches`, `/matches/delete`, `/undo`, and `/watchlist/add`.

### `/room/swipe` Body `user_id` Injection Assertions
- **D-05:** For unverified identity requests, assert strict `401` + unauthorized payload.
- **D-06:** Also assert no DB write side effects occur for injected `user_id` values (no cross-user swipe/match writes).

### Valid-Flow Regression Scenarios
- **D-07:** Cover both delegate and token happy paths across all protected routes.
- **D-08:** Valid-flow tests must prove Phase 18/19 hardening did not break legitimate access.

### Claude's Discretion
- Exact fixture decomposition and parametrization structure for keeping matrix tests maintainable.
- Whether to place all route-security tests in a dedicated file or extend existing module-level test files, as long as coverage intent is preserved.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone Scope and Security Requirements
- `.planning/ROADMAP.md` — Phase 20 goal, requirements, and success criteria.
- `.planning/REQUIREMENTS.md` — `VER-01`, `VER-02`, `VER-03` verification requirements.
- `.planning/PROJECT.md` — milestone objective and protected-route hardening context.

### Prior Locked Security Decisions
- `.planning/phases/18-verified-identity-resolution/18-CONTEXT.md` — trusted identity source and alias-header rejection rules.
- `.planning/phases/19-route-authorization-enforcement/19-CONTEXT.md` — strict `401` contract and request-body identity rejection policy.

### Route and Test Baselines
- `jellyswipe/__init__.py` — protected route authorization behavior under test.
- `tests/conftest.py` — existing test environment and fixture patterns.
- `tests/test_jellyfin_library.py` — existing pytest style and mocking conventions.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tests/conftest.py` already provides environment setup and DB fixtures suitable for isolated route tests.
- `jellyswipe/__init__.py` now exposes centralized `_provider_user_id_from_request()` route gating and uniform unauthorized responses.

### Established Patterns
- Current tests use pytest + monkeypatch fixtures and follow deterministic, isolated mocking patterns.
- Current suite includes broad provider unit coverage but lacks route-level security regression coverage for Phase 20 scope.

### Integration Points
- Route handlers in `jellyswipe/__init__.py`: `/room/swipe`, `/matches`, `/matches/delete`, `/undo`, `/watchlist/add`.
- DB assertions should verify side effects in `swipes` and `matches` tables for injection and authorized-path checks.

</code_context>

<specifics>
## Specific Ideas

- Build a matrix-driven test style to avoid repetitive per-route/per-header boilerplate.
- Ensure invalid identity tests and valid identity tests are paired so hardening regressions are detectable from both sides.
- Include explicit assertions for payload contract (`{"error":"Unauthorized"}`) and status (`401`).

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 20-security-regression-tests*
*Context gathered: 2026-04-25*
