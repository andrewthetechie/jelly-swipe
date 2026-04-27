# Phase 23: Auth Route Tests - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-26
**Phase:** 23-auth-route-tests
**Areas discussed:** None (auto-resolved — clear-cut route testing phase)

---

## Skip Assessment

Phase 23 has well-defined success criteria from ROADMAP.md:
1. `/auth/provider` returns correct provider for MEDIA_PROVIDER env
2. `/auth/jellyfin-use-server-identity` handles valid and invalid tokens
3. `/auth/jellyfin-login` authenticates with valid credentials
4. Header-spoof tests verify EPIC-01 protection

All 3 auth routes are straightforward with clear success/error paths. The existing FakeProvider already has all necessary methods (`authenticate_user_session`, `server_access_token_for_delegate`, etc.). Test patterns from `test_route_authorization.py` apply directly.

**User choice:** No discussion needed
**Notes:** 3 endpoints, well-defined paths, existing test infrastructure from Phase 22 ready to use.

---

## the agent's Discretion

- Whether to use pytest classes or flat function naming
- Exact number of parametrized vs individual tests
- Whether to add helper functions for common assertions

## Deferred Ideas

None.
