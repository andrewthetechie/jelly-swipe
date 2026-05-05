# Phase 37: Async Database Infrastructure - Context

**Gathered:** 2026-05-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Provide the async database runtime path that application bootstrap, FastAPI dependencies, and pytest fixtures can use after the schema baseline is in place. This phase introduces the primary runtime configuration, startup/bootstrap behavior, async engine and session lifecycle, and test database bootstrap path. It does not yet convert every persistence callsite in auth, rooms, swipes, matches, or SSE; later phases move those domains onto the infrastructure defined here.

</domain>

<decisions>
## Implementation Decisions

### Startup Migration Trigger
- **D-01:** On normal boot, the system should run `alembic upgrade head`.
- **D-02:** If migration fails, startup fails fast and the app does not serve requests.
- **D-03:** The migration call should live outside the FastAPI app process in a bootstrap wrapper that runs before Uvicorn starts. The app should assume the schema is ready.
- **D-04:** `DATABASE_URL` becomes the primary database configuration source in this phase.

### Async Engine and Session Lifecycle
- **D-05:** The async engine and `async_sessionmaker` should live in a dedicated runtime module separate from models, Alembic metadata, and the app factory.
- **D-06:** The FastAPI database dependency should expose a repository registry or unit-of-work style object rather than a raw `AsyncSession`.
- **D-07:** Commit on success and rollback on error should be handled automatically at the dependency boundary.
- **D-08:** The async engine should initialize during bootstrap and dispose during shutdown.

### Test Database Bootstrap Path
- **D-09:** Pytest fixtures should create fresh databases by running Alembic `upgrade head` against temporary databases.
- **D-10:** Low-level tests that still call `init_db()` directly should be rewritten in this phase around the new bootstrap/runtime primitives.
- **D-11:** Tests should prefer the same async session or repository path wherever practical instead of leaning on sync sqlite setup forever.
- **D-12:** Isolation and speed should be balanced; strict per-test fidelity matters, but not at any cost.

### Sync/Async Coexistence During the Transition
- **D-13:** Sync `sqlite3` access may remain only in route or domain areas that have not yet been converted in later phases; it should not remain the primary runtime path once async infrastructure exists.
- **D-14:** The existing sync `DBConn` / `get_db_dep()` dependency should be replaced immediately by the new async dependency surface.
- **D-15:** Runtime maintenance functions introduced in Phase 36 should move onto the async engine/session path in this phase.
- **D-16:** Temporary duplication should be minimized, even if that makes Phase 37 slightly broader than a narrow infrastructure-only slice.

### the agent's Discretion
None. The user locked the main runtime, bootstrap, and testing choices for this phase.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and Roadmap
- `.planning/PROJECT.md` — v2.1 milestone goal and current greenfield persistence direction
- `.planning/REQUIREMENTS.md` — Phase 37 requirements: `MIG-04`, `ADB-01`, `ADB-02`, `ADB-04`, `VAL-01`
- `.planning/ROADMAP.md` §Phase 37 — phase goal, dependency on Phase 36, and success criteria
- `.planning/STATE.md` — current milestone state and focus pointer

### Prior Phase Decisions
- `.planning/phases/36-alembic-baseline-and-sqlalchemy-models/36-CONTEXT.md` — mandatory upstream decisions about Alembic ownership, `DATABASE_URL` direction, greenfield cleanup, and removal of `init_db()` as schema bootstrap
- `.planning/phases/35-test-suite-migration-and-full-validation/35-CONTEXT.md` — current test fixture structure and `create_app(test_config=...)` assumptions
- `.planning/phases/34-sse-route-migration/34-CONTEXT.md` — SSE runtime behavior that later async persistence must preserve

### Current Runtime and DB Sources
- `jellyswipe/__init__.py` — current FastAPI lifespan and startup path calling `init_db()`
- `jellyswipe/db.py` — current sync DB helpers, PRAGMA behavior, maintenance functions, and `DB_PATH` handling being replaced/refactored
- `jellyswipe/dependencies.py` — current `DBConn` / `get_db_dep()` dependency surface that Phase 37 replaces
- `jellyswipe/auth.py` — current token-vault access and cleanup call pattern that must keep working through the transition

### Test Bootstrap Sources
- `tests/conftest.py` — current app fixtures, DB path injection, and direct `init_db()` bootstrap path
- `tests/test_auth.py` — low-level auth tests that currently create schema via `init_db()`
- `tests/test_dependencies.py` — dependency tests built around sync `get_db_dep()`

### External Specs
- No external specs or ADRs were referenced beyond the planning docs and current source files above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `jellyswipe/__init__.py`: already has a FastAPI lifespan hook and test-config DB override path, making it the current integration point for bootstrap replacement.
- `tests/conftest.py`: centralizes app and DB fixture setup, so Phase 37 can reroute most test bootstrap behavior from one place.
- `jellyswipe/auth.py`: token cleanup and vault access are already isolated enough to move behind async runtime primitives later.
- `jellyswipe/dependencies.py`: the current DI layer provides the seam where the sync `DBConn` path can be swapped for the async unit-of-work surface.

### Established Patterns
- The app currently assumes import-time environment configuration and startup-time schema creation.
- Tests currently patch `jellyswipe.db.DB_PATH` directly and call `init_db()` for both low-level and app-level setup.
- Session and provider overrides in tests are already centralized in FastAPI dependency overrides.
- The persistence layer is still split between direct `sqlite3` helpers and route-level context-manager usage.

### Integration Points
- A bootstrap wrapper outside Uvicorn will need to own `alembic upgrade head` and failure handling before the app process starts.
- The new async runtime module must connect `DATABASE_URL`, engine creation, sessionmaker setup, and shutdown disposal without importing the FastAPI app root into Alembic.
- FastAPI dependency injection must move from `DBConn` to an async unit-of-work or repository registry while leaving later domain conversion room in Phases 38 and 39.
- Pytest fixtures must switch from `init_db()` and raw DB path patching to Alembic-driven temp DB provisioning.

</code_context>

<specifics>
## Specific Ideas

- Treat `DATABASE_URL` as the canonical runtime setting now, even if compatibility shims briefly derive it from legacy local test inputs.
- Keep migration execution outside the app process so production startup semantics are explicit and failure is unambiguous.
- Use Alembic-driven temporary databases in tests rather than carrying forward ad hoc schema bootstrap.
- Push the async dependency surface into place now so later domain phases can focus on persistence conversion, not infrastructure invention.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 37-Async Database Infrastructure*
*Context gathered: 2026-05-05*
