# Phase 35: Test Suite Migration and Full Validation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-03
**Phase:** 35-test-suite-migration-and-full-validation
**Areas discussed:** Auth injection strategy, Session state injection, create_app SECRET_KEY

---

## Auth Injection Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| (a) dependency_overrides everywhere | All tests bypass require_auth; no real auth code path | |
| (b) session cookie crafting everywhere | All tests craft itsdangerous-signed cookies; real auth path | |
| (c) mixed | dependency_overrides by default; test_routes_auth + test_route_authorization use real auth | ✓ |

**User's choice:** 1c — mixed
**Notes:** Most tests get the override for simplicity; auth-specific test files opt out via a separate fixture variant.

---

## Session State Injection (active_room, solo_mode, my_user_id)

| Option | Description | Selected |
|--------|-------------|----------|
| (a) endpoint-driven setup | Call actual endpoints (join, solo) to set session state; integration-y | |
| (b) cookie crafting | itsdangerous helper to inject session dict as signed cookie; surgical | |
| (c) Let Claude decide | Pick whatever fits cleanest with auth choice | ✓ |

**User's choice:** 2c — deferred to Claude
**Notes:** Claude resolved to cookie crafting (2b) — natural complement to the mixed auth approach since most tests bypass real auth anyway; direct cookie injection stays unit-test-y and matches the "only API surface changes" intent of TST-01.

---

## create_app SECRET_KEY Injection

| Option | Description | Selected |
|--------|-------------|----------|
| (a) env is sufficient | FLASK_SECRET already set in conftest env; no factory change | |
| (b) make it injectable | create_app() accepts SECRET_KEY from test_config; fully hermetic | ✓ |

**User's choice:** 3b — make SECRET_KEY injectable
**Notes:** Ensures the signing key used by set_session_cookie() and the running app are guaranteed to match in tests.

---

## Claude's Discretion

- Session state injection approach: resolved to cookie crafting (from 2c user deferral)
- Exact Starlette `itsdangerous` signer variant: planner must verify before implementing
- `raise_server_exceptions=False` flag: planner applies surgically to error-handling test files

## Deferred Ideas

None — discussion stayed within phase scope.
