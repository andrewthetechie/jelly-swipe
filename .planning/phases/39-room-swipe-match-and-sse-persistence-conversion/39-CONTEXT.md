# Phase 39: Room, Swipe, Match, and SSE Persistence Conversion - Context

**Gathered:** 2026-05-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Convert Jelly Swipe's core room lifecycle, swipe persistence, match persistence, deck cursor updates, and SSE-backed room status streaming onto the async SQLAlchemy persistence path established in Phases 37 and 38. This phase preserves the existing HTTP and SSE behavior contracts while moving room creation, solo rooms, join, quit, genre, deck, status, undo, delete, match history, and room streaming off the remaining ad hoc `sqlite3` helpers.

</domain>

<decisions>
## Implementation Decisions

### Room Identity and Lifecycle
- **D-01:** Persisted room, swipe, and match flows keep using the current browser/session identity as the participant key everywhere in this phase.
- **D-02:** If local session state points at a missing or stale room, the app should clear `active_room` and related local room state immediately.
- **D-03:** Solo rooms use the same persistence and service path as multiplayer rooms, controlled by `solo_mode` rather than a separate solo-only stack.
- **D-04:** Room teardown is immediate hard cleanup when a room is closed or emptied; no reconnect or recovery retention is required in Phase 39.

### Swipe and Match Transaction Semantics
- **D-05:** A swipe remains one atomic mutation covering swipe write, deck cursor advance, match detection, and `last_match` update.
- **D-06:** Room swipe mutations must preserve serialized race protection equivalent to the current SQLite `BEGIN IMMEDIATE` behavior.
- **D-07:** Undo and delete behavior must recompute visible match and history state immediately for the affected room or user view.
- **D-08:** Persisted match history plus the room-level `last_match` sentinel remains the source of truth for fast room-status and SSE parity.

### SSE Stream Behavior
- **D-09:** SSE connect should keep sending the latest room snapshot immediately when one is available.
- **D-10:** SSE fanout must only reflect committed room or swipe state; no pre-commit event emission.
- **D-11:** Disconnected or missed clients do not get a replay buffer in this phase; reconnects resubscribe and refresh from current room state.
- **D-12:** Phase 39 keeps the current app-local broadcaster and polling semantics rather than introducing a persistence-backed event bus or outbox.

### Service and Repository Slicing
- **D-13:** Repositories should be split by aggregate concern: rooms, swipes, and matches, with transaction coordination staying in the service layer.
- **D-14:** Service structure should use one room-lifecycle orchestration service plus a dedicated swipe/match mutation service.
- **D-15:** Router migration should happen in vertical slices while keeping endpoint shapes, response bodies, and visible semantics unchanged throughout the conversion.
- **D-16:** Parity coverage should keep the current route-level behavior tests and add focused service and repository tests underneath them.

### the agent's Discretion
None. The user locked the main persistence, transaction, stream, and slicing choices for this phase.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and Roadmap
- `.planning/PROJECT.md` — current milestone intent and remaining persistence-migration scope
- `.planning/REQUIREMENTS.md` — Phase 39 requirements: `MVC-02`, `MVC-03`, `MVC-04`, `PAR-02`, `PAR-03`, `PAR-04`, `PAR-05`
- `.planning/ROADMAP.md` §Phase 39 — phase goal, dependency on Phase 38, and success criteria
- `.planning/STATE.md` — current focus pointer and current milestone state

### Prior Phase Decisions
- `.planning/phases/36-alembic-baseline-and-sqlalchemy-models/36-CONTEXT.md` — upstream schema and migration decisions that define the room, swipe, and match table baseline
- `.planning/phases/37-async-database-infrastructure/37-CONTEXT.md` — async runtime, unit-of-work, and transaction-boundary decisions this phase must build on
- `.planning/phases/38-auth-persistence-conversion/38-CONTEXT.md` — carried-forward auth/session decisions, especially stale-room cleanup via session state and service/repository seams

### Current Room and SSE Runtime
- `jellyswipe/routers/rooms.py` — current room endpoints, swipe transaction bridge, room status contract, and SSE polling behavior being converted
- `jellyswipe/dependencies.py` — request-scoped async unit-of-work dependency and auth dependency contract used by the room routes
- `jellyswipe/db_uow.py` — existing async unit-of-work facade and the current `run_sync()` bridge that preserves `BEGIN IMMEDIATE`
- `jellyswipe/auth.py` — current stale-room cleanup helper and current session-state semantics that Phase 39 must preserve around `active_room`
- `jellyswipe/db.py` — remaining legacy sync DB helpers still used by room and SSE code paths

### Persistence Models
- `jellyswipe/models/room.py` — room storage fields including `solo_mode`, `last_match_data`, `deck_position`, and relationships
- `jellyswipe/models/swipe.py` — swipe schema, participant/session columns, and existing indexes relevant to match lookup and undo behavior
- `jellyswipe/models/match.py` — match schema, uniqueness rules, and archived-vs-active storage behavior

### Behavior and Parity Tests
- `tests/conftest.py` — temp DB runtime bootstrap, provider overrides, and route-test fixture setup for async persistence
- `tests/test_routes_room.py` — current room lifecycle, swipe, undo, delete, status, and match-history behavior that must stay stable
- `tests/test_routes_sse.py` — SSE snapshot, closed-room, heartbeat, disconnect, and cleanup behavior that must keep passing
- `tests/test_route_authorization.py` — real-auth route coverage that protects session-backed room compatibility edges
- `tests/test_dependencies.py` — async unit-of-work and `require_auth` dependency behavior that constrains the route migration seam

### External Specs
- No external specs or ADRs were referenced beyond the planning docs and current source/test files above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `jellyswipe/db_uow.py`: `DatabaseUnitOfWork.run_sync()` already provides the bridge needed for legacy transactional logic that still relies on low-level SQLite statements like `BEGIN IMMEDIATE`.
- `jellyswipe/auth.py`: `resolve_active_room()` already codifies eager stale-room cleanup semantics that align with this phase's room-lifecycle decision.
- `jellyswipe/models/room.py`, `jellyswipe/models/swipe.py`, and `jellyswipe/models/match.py`: the core tables and relationships already exist from earlier migration phases, so Phase 39 is primarily a behavior-preserving domain conversion.
- `tests/conftest.py`: the async runtime bootstrap and app fixtures already support route tests and lower-level async repository/service tests against migrated tables.
- `tests/test_routes_room.py` and `tests/test_routes_sse.py`: the project already has broad route-level parity coverage for room lifecycle, swipe semantics, and stream behavior.

### Established Patterns
- Route handlers currently mutate `request.session` directly for `active_room`, `solo_mode`, and room/session compatibility, so the migration must preserve those side effects exactly.
- Swipe behavior currently uses one serialized mutation path that writes the swipe, advances deck position, detects matches, and updates `last_match_data` in one transaction.
- Solo and multiplayer behavior currently share most route logic and differ mainly by `solo_mode` and match-detection semantics.
- SSE currently uses app-local polling plus snapshot-diff emission, with no replay buffer and with explicit closed-room signaling.
- The async request dependency owns commit or rollback for ordinary route work, while the long-lived SSE stream intentionally avoids holding one shared request session open for up to an hour.

### Integration Points
- Room create, solo create, join, quit, genre, deck, status, undo, delete, and match-history endpoints in `jellyswipe/routers/rooms.py` need to move from `get_db_closing()` calls to repository/service orchestration on the async persistence stack.
- The swipe endpoint already receives `DBUoW`; its transaction bridge is the immediate seam for extracting a dedicated swipe/match mutation service.
- Room session compatibility must stay aligned with `require_auth()` and `resolve_active_room()` so stale room state clears eagerly without changing the auth contract.
- SSE planning must respect the current isolation rule: async/non-blocking polling without one long-lived shared request-scoped `AsyncSession`.
- Tests should be extended downward with service/repository coverage, but route tests remain the contract gate for behavior parity.

</code_context>

<specifics>
## Specific Ideas

- Keep the external room API intentionally boring during the migration: same routes, same response shapes, same SSE semantics.
- Treat the current browser session identity as the durable participant key for now rather than introducing a new participant model mid-migration.
- Preserve the current "room disappears, client sees closed/eager cleanup" behavior instead of layering in reconnect recovery.
- Keep match notification fast-path semantics via persisted match history plus `last_match_data`; planners should not convert this phase into a new eventing architecture.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 39-Room, Swipe, Match, and SSE Persistence Conversion*
*Context gathered: 2026-05-06*
