# Phase 38: Auth Persistence Conversion - Context

**Gathered:** 2026-05-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Convert Jelly Swipe's auth token-vault persistence to the async SQLAlchemy path established in Phase 37 and use auth as the first real repository/service conversion on top of that infrastructure. This phase covers session creation, current-session lookup, logout/destroy behavior, expired-token cleanup, and `require_auth` behavior. It does not convert room, swipe, match, or SSE persistence beyond what auth semantics already touch.

</domain>

<decisions>
## Implementation Decisions

### Auth Repository and Service Boundary
- **D-01:** Auth persistence should use a thin repository plus a thin auth service.
- **D-02:** The auth service owns `session_id` generation and `created_at` generation.
- **D-03:** Token lookup should return a small typed auth record rather than a tuple or ORM entity.
- **D-04:** `require_auth` and auth routes should call the auth service only; they should not talk to the repository directly.

### Session Lifecycle Semantics
- **D-05:** Phase 38 does not need to preserve the current 64-character hex `session_id` shape; any opaque session identifier is acceptable.
- **D-06:** Expired-token cleanup should run on every new session creation.
- **D-07:** Destroy/logout should clear cookie and session state immediately, while vault cleanup may be best-effort asynchronous.
- **D-08:** If a cookie contains a `session_id` but no vault row exists, auth should treat that as an invalid session error and clear the stale session state aggressively.

### Auth Dependency Behavior
- **D-09:** `require_auth` should continue returning a lightweight `AuthUser`-style object.
- **D-10:** `require_auth` itself should clear invalid or stale session state when auth fails due to missing or bad persisted session data.
- **D-11:** Auth should continue trusting the persisted auth record and should not revalidate against Jellyfin on each request.
- **D-12:** Auth failures should keep the exact current external contract: `401` with `{"detail": "Authentication required"}`.

### Cleanup and Invalid-Session Handling
- **D-13:** Token cleanup should live in the auth service.
- **D-14:** If best-effort destroy cleanup fails after local session state is cleared, the app should swallow and log the failure.
- **D-15:** Cleanup remains request-driven in this phase; no new background or scheduled cleanup path is required.
- **D-16:** Cleanup verification should lean on repository/service unit tests, with route tests kept lighter and focused on visible auth behavior.

### the agent's Discretion
None. The user locked the main auth-persistence and invalid-session choices for this phase.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and Roadmap
- `.planning/PROJECT.md` — v2.1 milestone intent and active persistence-migration context
- `.planning/REQUIREMENTS.md` — Phase 38 requirements: `MVC-01`, `PAR-01`
- `.planning/ROADMAP.md` §Phase 38 — phase goal, dependency on Phase 37, and success criteria
- `.planning/STATE.md` — current milestone state and current focus pointer

### Prior Phase Decisions
- `.planning/phases/37-async-database-infrastructure/37-CONTEXT.md` — mandatory upstream runtime decisions: `DATABASE_URL`, async unit-of-work/repository surface, bootstrap path, and async test bootstrap expectations
- `.planning/phases/36-alembic-baseline-and-sqlalchemy-models/36-CONTEXT.md` — schema and runtime cleanup decisions that Phase 38 builds on

### Current Auth Sources
- `jellyswipe/auth.py` — current session creation, token lookup, destroy, and cleanup behavior being converted
- `jellyswipe/dependencies.py` — current `require_auth` contract and current sync DB dependency surface
- `jellyswipe/routers/auth.py` — auth routes that currently call module-level auth helpers and define the route-level external contract

### Auth Tests and Behavior Fixtures
- `tests/test_auth.py` — low-level auth behavior tests that currently assume `init_db()` and sync DB helpers
- `tests/test_route_authorization.py` — route-level auth and authorization behavior that must keep passing through the async DB path
- `tests/conftest.py` — current session-cookie injection and app bootstrap fixtures used by auth and authorization tests

### External Specs
- No external specs or ADRs were referenced beyond the planning docs and current source files above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `jellyswipe/auth.py`: already isolates auth persistence concerns into `create_session`, `get_current_token`, and `destroy_session`, giving Phase 38 a contained conversion surface.
- `jellyswipe/dependencies.py`: already centralizes `require_auth`, making it the natural place to preserve the external auth contract while swapping persistence internals.
- `tests/conftest.py`: already centralizes cookie/session injection patterns that can keep driving route tests after the async auth conversion.
- `tests/test_route_authorization.py`: already exercises the real auth path with a seeded vault and is the main behavior guardrail for invalid-session semantics.

### Established Patterns
- Auth currently trusts the server-side token vault and does not call Jellyfin on every request.
- Session identity currently flows through Starlette session cookies, not bearer tokens or client-side token storage.
- Route-level auth failures currently rely on FastAPI `HTTPException(401, detail="Authentication required")`.
- Cleanup currently runs synchronously from auth code paths and low-level tests still seed or inspect DB state directly.

### Integration Points
- The Phase 37 async unit-of-work or repository surface must become the only DB path that auth and `require_auth` use.
- Auth routes in `jellyswipe/routers/auth.py` need to preserve response shapes while swapping from module-level sync helpers to the auth service.
- Invalid-session clearing must integrate with `request.session` handling inside `require_auth` without changing the external HTTP contract.
- Tests need to move from direct `init_db()` and sync helper assumptions toward the new async bootstrap and service/repository seams.

</code_context>

<specifics>
## Specific Ideas

- Let auth be the first domain to prove the repository/service pattern without making the service layer heavy.
- Keep the external auth surface intentionally boring: same `AuthUser` shape, same `401` message, same session-cookie mental model.
- Treat stale cookie-without-vault-row as an auth error worth clearing immediately, not as a silent anonymous fallback.
- Decouple user-visible logout success from storage cleanup success; local session clearing matters most to the user-facing contract.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 38-Auth Persistence Conversion*
*Context gathered: 2026-05-05*
