# Roadmap — Jelly Swipe

**Current State:** v2.1 planning complete
**Last Updated:** 2026-05-05

---

## Milestones

- Complete **v1.0-v1.7** — Phases 1-29 (all shipped; see `.planning/milestones/`)
- Complete **v2.0 Flask to FastAPI + MVC Refactor** — Phases 30-35 (shipped 2026-05-05; archived in [v2.0-ROADMAP.md](milestones/v2.0-ROADMAP.md))
- Active **v2.1 Alembic + Async SQLAlchemy Persistence** — Phases 36-40

## Phases

<details>
<summary>Complete v2.0 Flask to FastAPI + MVC Refactor (Phases 30-35) — SHIPPED 2026-05-05</summary>

- [x] Phase 30: Package and Deployment Infrastructure (1/1 plans) — completed 2026-05-02
- [x] Phase 31: FastAPI App Factory and Session Middleware (1/1 plans) — completed 2026-05-03
- [x] Phase 32: Auth Rewrite and Dependency Injection Layer (1/1 plans) — completed 2026-05-03
- [x] Phase 33: Router Extraction and Endpoint Parity (2/2 plans) — completed 2026-05-03
- [x] Phase 34: SSE Route Migration (2/2 plans) — completed 2026-05-03
- [x] Phase 35: Test Suite Migration and Full Validation (6/6 plans) — completed 2026-05-04

Full archive: [v2.0-ROADMAP.md](milestones/v2.0-ROADMAP.md)

</details>

### v2.1 Alembic + Async SQLAlchemy Persistence

- [x] **Phase 36: Alembic Baseline and SQLAlchemy Models** — Introduce SQLAlchemy declarative schema and Alembic migration baseline without app import side effects. (completed 2026-05-06)
- [ ] **Phase 37: Async Database Infrastructure** — Add async engine/sessionmaker, FastAPI DB dependency, migration runner, and Alembic-backed test setup.
- [ ] **Phase 38: Auth Persistence Conversion** — Convert token vault CRUD and auth dependency behavior to async SQLAlchemy behind persistence boundaries.
- [ ] **Phase 39: Room, Swipe, Match, and SSE Persistence Conversion** — Convert core room/session persistence to async SQLAlchemy while preserving transaction and stream behavior.
- [ ] **Phase 40: Full Migration Validation and Sync DB Removal** — Prove migration parity, remove old sync DB paths, and verify the full suite.

## Phase Details

### Phase 36: Alembic Baseline and SQLAlchemy Models

**Goal:** Make SQLAlchemy declarative metadata and Alembic migrations the source of truth for the current database schema.

**Requirements:** MIG-01, MIG-02, MIG-03, SCH-01, SCH-02, SCH-03

**Depends on:** v2.0 complete

**Success Criteria:**

1. SQLAlchemy declarative models cover rooms, swipes, matches, and user_tokens with current columns, defaults, and constraints.
2. Alembic `env.py` uses model `Base.metadata` for autogenerate without importing the FastAPI app root.
3. A baseline migration creates the current schema from an empty SQLite database.
4. SQLModel is absent from dependencies and source.

### Phase 37: Async Database Infrastructure

**Goal:** Provide the async database runtime path that app startup, routes, and tests can use.

**Requirements:** MIG-04, ADB-01, ADB-02, ADB-04, VAL-01

**Depends on:** Phase 36

**Plans:** 3 plans

Plans:
**Wave 1**
- [ ] 37-01-PLAN.md — Add the async engine/sessionmaker runtime and replace `DBConn` with a unit-of-work dependency seam.

**Wave 2** *(blocked on Wave 1 completion)*
- [ ] 37-02-PLAN.md — Move startup to a migration-first bootstrap wrapper and shift runtime maintenance onto the async path.

**Wave 3** *(blocked on Wave 2 completion)*
- [ ] 37-03-PLAN.md — Rewire pytest fixtures and low-level auth tests to the Alembic + async runtime bootstrap flow.

**Success Criteria:**

1. The database module configures an async SQLAlchemy engine and `async_sessionmaker` for the project SQLite DB path.
2. FastAPI dependencies expose request-scoped `AsyncSession` access and close sessions cleanly.
3. App startup runs Alembic upgrade head instead of ad hoc table creation.
4. Pytest fixtures initialize temporary databases through the same Alembic upgrade path.

### Phase 38: Auth Persistence Conversion

**Goal:** Convert session token vault persistence to async SQLAlchemy and establish the repository/service pattern on a lower-risk domain.

**Requirements:** MVC-01, PAR-01

**Depends on:** Phase 37

**Success Criteria:**

1. `create_session`, `get_current_token`, `destroy_session`, and token cleanup use async SQLAlchemy persistence.
2. Auth dependency behavior and existing session semantics remain compatible.
3. Token cleanup still deletes entries older than 14 days.
4. Auth and route authorization tests pass through the async DB path.

### Phase 39: Room, Swipe, Match, and SSE Persistence Conversion

**Goal:** Convert core room, swipe, match, deck cursor, and SSE persistence to async SQLAlchemy without behavior regressions.

**Requirements:** MVC-02, MVC-03, MVC-04, PAR-02, PAR-03, PAR-04, PAR-05

**Depends on:** Phase 38

**Success Criteria:**

1. Room creation, solo room creation, join, quit, genre, deck, status, undo, delete, and match history delegate persistence to async domain functions.
2. Swipe transaction behavior preserves race protection equivalent to the current SQLite `BEGIN IMMEDIATE` path.
3. SSE polling remains async/non-blocking and uses async DB access without holding one long-lived shared session.
4. Existing room, swipe, match, SSE, XSS, and error-handling tests pass.

### Phase 40: Full Migration Validation and Sync DB Removal

**Goal:** Close the milestone by proving parity and removing obsolete synchronous/ad hoc database code.

**Requirements:** ADB-03, VAL-02, VAL-03, VAL-04

**Depends on:** Phase 39

**Success Criteria:**

1. Migration tests prove empty-database upgrade to head and idempotent upgrade on an already-current database.
2. Full local test suite passes after the persistence migration.
3. Source scan confirms application DB access no longer uses `sqlite3`, `get_db_closing`, table-creating `init_db()`, or SQLModel.
4. Planning verification records requirement coverage and any intentionally deferred work.

## Traceability Summary

| Phase | Requirements | Count |
|-------|--------------|-------|
| 36 | MIG-01, MIG-02, MIG-03, SCH-01, SCH-02, SCH-03 | 6 |
| 37 | MIG-04, ADB-01, ADB-02, ADB-04, VAL-01 | 5 |
| 38 | MVC-01, PAR-01 | 2 |
| 39 | MVC-02, MVC-03, MVC-04, PAR-02, PAR-03, PAR-04, PAR-05 | 7 |
| 40 | ADB-03, VAL-02, VAL-03, VAL-04 | 4 |

**Coverage:** 24/24 v2.1 requirements mapped.

---

_For historical milestone details, see `.planning/milestones/`._
