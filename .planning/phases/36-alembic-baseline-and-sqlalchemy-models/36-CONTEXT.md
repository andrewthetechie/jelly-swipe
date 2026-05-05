# Phase 36: Alembic Baseline and SQLAlchemy Models - Context

**Gathered:** 2026-05-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Make SQLAlchemy declarative metadata and Alembic migrations the source of truth for Jelly Swipe's database schema, replacing schema creation inside `init_db()` with a clean baseline for a greenfield persistence redesign. This phase defines the models, metadata import boundary, and baseline migration shape for rooms, swipes, matches, and user tokens. It does not introduce the async runtime/session path yet; that starts in Phase 37.

</domain>

<decisions>
## Implementation Decisions

### Schema Fidelity
- **D-01:** Phase 36 may tighten the schema where the current app behavior already depends on that structure; it is not limited to a byte-for-byte mirror of the ad hoc SQLite schema.
- **D-02:** Acceptable tightening in this phase includes indexes, foreign keys, and non-null constraints where they reflect behavior the app already relies on.
- **D-03:** SQLAlchemy models should include a full ORM relationship graph to support later repository work, while preserving existing product behavior.
- **D-04:** JSON-like fields such as `movie_data`, `deck_position`, `deck_order`, and `last_match_data` remain `TEXT` in this phase. Parsing and serialization stay outside the schema layer.

### Baseline Strategy
- **D-05:** The first Alembic migration should be a current-state baseline only.
- **D-06:** No upgrade or stamping path is needed for existing `init_db()`-era databases. Old databases can be discarded because this milestone is effectively greenfield.
- **D-07:** Phase 36 should rename obvious schema mistakes now rather than preserve awkward legacy names.
- **D-08:** Schema cleanup should be moderate: improve the relational model where it materially helps, but stay within this phase's scope and preserve product behavior.

### Model Boundaries
- **D-09:** Use a dedicated `jellyswipe.models` package rather than a single `models.py` or embedding schema objects in `db.py`.
- **D-10:** Alembic should import a pure metadata module that assembles `Base.metadata` without app startup side effects or package-import registration tricks.
- **D-11:** The model layer stays schema-only: columns, constraints, and relationships are allowed; query logic and application behavior are not.
- **D-12:** There is no translation layer for renamed tables or columns. Models and the baseline migration should use the cleaned-up names directly.

### Startup Side Effects
- **D-13:** Non-schema work currently inside `init_db()` must move into separate runtime functions. Alembic owns schema creation.
- **D-14:** SQLite PRAGMA setup such as `journal_mode=WAL` and `synchronous=NORMAL` remains runtime configuration, not migration logic.
- **D-15:** Orphan swipe cleanup and expired token cleanup remain explicit runtime maintenance functions invoked by startup or auth flows.
- **D-16:** Remove `init_db()` as a schema bootstrap concept in this phase. Introduce explicit primitives instead of a compatibility wrapper.

### the agent's Discretion
None. The user locked the main structural choices for this phase.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and Roadmap
- `.planning/PROJECT.md` — v2.1 milestone intent, greenfield persistence cleanup context, and active requirements summary
- `.planning/REQUIREMENTS.md` — Phase 36 requirements: `MIG-01`, `MIG-02`, `MIG-03`, `SCH-01`, `SCH-02`, `SCH-03`
- `.planning/ROADMAP.md` §Phase 36 — phase goal, dependencies, and success criteria
- `.planning/STATE.md` — current milestone state and accumulated decisions carried into this phase

### Current Database and Startup Sources
- `jellyswipe/db.py` — current ad hoc schema creation, in-place column patching, PRAGMA handling, and maintenance routines being replaced/split
- `jellyswipe/__init__.py` — app lifespan startup currently calling `init_db()`; key integration point for later phase boot changes
- `jellyswipe/dependencies.py` — current sync `DBConn` dependency and DB connection pattern that later async infrastructure must replace
- `jellyswipe/auth.py` — current token vault lifecycle and expired-token cleanup call pattern

### Current Schema Behavior
- `jellyswipe/routers/rooms.py` — current room, swipe, match, cursor, and last-match persistence semantics that the new schema must support
- `tests/test_db.py` — current schema assertions and old migration expectations; useful inventory of fields and constraints
- `tests/conftest.py` — current test bootstrap path built around `init_db()`, which later phases must replace with Alembic-driven setup

### Prior Phase Context
- `.planning/phases/35-test-suite-migration-and-full-validation/35-CONTEXT.md` — current test infrastructure and DB fixture expectations
- `.planning/phases/34-sse-route-migration/34-CONTEXT.md` — SSE behavior that depends on rooms and match persistence shape
- `.planning/phases/33-router-extraction-and-endpoint-parity/33-CONTEXT.md` — router structure and current room/auth persistence callsites

### External Specs
- No external specs or ADRs were referenced beyond the planning docs and current source files above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `jellyswipe/db.py`: the current single-file schema inventory is the fastest source for table/column/default discovery before replacing it with models and migrations.
- `jellyswipe/routers/rooms.py`: contains the real persistence behavior for rooms, swipes, matches, cursor JSON, solo mode, and match metadata.
- `jellyswipe/auth.py`: defines the token-vault lifecycle and cleanup trigger that the new schema must preserve.
- `tests/test_db.py`: captures the current table coverage, unique constraints, and maintenance expectations in executable form.

### Established Patterns
- Startup currently runs through FastAPI lifespan and calls `init_db()` directly from `jellyswipe/__init__.py`.
- Request-scoped DB access is still sync `sqlite3` via `DBConn`; async SQLAlchemy is explicitly deferred to Phase 37.
- Current code stores several structured payloads as JSON serialized into text columns rather than normalized child tables.
- Current tests assume a fresh SQLite file can be created quickly for each test via direct schema bootstrap.

### Integration Points
- Alembic needs a metadata import path that does not import the FastAPI app root or require Jellyfin/TMDB runtime configuration.
- A new `jellyswipe.models` package and pure metadata module will become the import boundary for both Alembic and later repository work.
- Removing schema creation from `init_db()` means later phases must rewire app startup and test database bootstrap to the Alembic upgrade path.
- Any renames or relational cleanup chosen here must still satisfy the current auth and room behaviors encoded in `auth.py` and `routers/rooms.py`.

</code_context>

<specifics>
## Specific Ideas

- Treat this as a greenfield persistence redesign, not a deployed-database migration problem.
- Use cleaned-up table and column names directly in the new models and baseline migration.
- Keep JSON-bearing columns as `TEXT` for now even if the surrounding relational structure becomes cleaner.
- Build the full relationship graph now so later repository/service work can attach to it without revisiting model topology.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 36-Alembic Baseline and SQLAlchemy Models*
*Context gathered: 2026-05-05*
