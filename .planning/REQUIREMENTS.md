# Requirements: Jelly Swipe v2.1

**Defined:** 2026-05-05
**Core Value:** Users can run a swipe session backed by Jellyfin, with library browsing, deck behavior, and match behavior preserved across framework changes.
**Milestone:** v2.1 Alembic + Async SQLAlchemy Persistence

## v2.1 Requirements

### Migrations

- [ ] **MIG-01**: The app can create a fresh SQLite database by running Alembic migrations to head.
- [ ] **MIG-02**: Alembic owns all schema changes that are currently embedded in `init_db()`, including rooms, swipes, matches, user_tokens, metadata columns, cursor fields, and constraints.
- [ ] **MIG-03**: Alembic autogenerate is configured against the SQLAlchemy declarative metadata without importing the FastAPI app root or requiring Jellyfin/TMDB runtime configuration.
- [ ] **MIG-04**: FastAPI startup runs a controlled migration path instead of ad hoc table creation.

### Schema

- [ ] **SCH-01**: SQLAlchemy declarative models represent every persisted table used by Jelly Swipe.
- [ ] **SCH-02**: Model definitions preserve current column names, defaults, nullable behavior, primary keys, and unique constraints needed by existing behavior.
- [ ] **SCH-03**: SQLModel is not introduced anywhere in the project.

### Async Database Access

- [ ] **ADB-01**: The database module exposes async SQLAlchemy engine and sessionmaker setup for the configured SQLite database path.
- [ ] **ADB-02**: FastAPI dependency injection provides request-scoped `AsyncSession` access through the existing dependency layer.
- [ ] **ADB-03**: Application database interactions use async SQLAlchemy APIs rather than direct `sqlite3` connections.
- [ ] **ADB-04**: Async session lifecycle avoids shared global sessions and closes sessions cleanly after each request or unit of work.

### MVC Persistence Boundaries

- [ ] **MVC-01**: Auth token vault reads, writes, cleanup, and destroy operations live behind async persistence functions instead of route/controller SQL.
- [ ] **MVC-02**: Room creation, join, quit, deck cursor, genre, and status persistence live behind async room persistence functions.
- [ ] **MVC-03**: Swipe, match creation, history, undo, and delete persistence live behind async swipe/match persistence functions.
- [ ] **MVC-04**: Route handlers remain controller-level code that delegates database behavior to dependency-injected services or repositories.

### Behavior Parity

- [ ] **PAR-01**: Existing auth/session behavior remains compatible, including `session_id` token vault lookup and 14-day token cleanup.
- [ ] **PAR-02**: Existing room lifecycle behavior remains compatible for multiplayer and solo rooms.
- [ ] **PAR-03**: Existing swipe behavior remains compatible, including deck cursor advancement, undo, right-swipe match detection, and match metadata.
- [ ] **PAR-04**: Swipe persistence preserves race protection equivalent to the current SQLite `BEGIN IMMEDIATE` behavior.
- [ ] **PAR-05**: SSE room stream behavior remains async and non-blocking while using async database access for polling.

### Validation

- [ ] **VAL-01**: Tests create temporary databases through the Alembic upgrade path instead of `init_db()` table creation.
- [ ] **VAL-02**: Migration tests prove an empty database reaches the current schema and an already-current database remains upgrade-safe.
- [ ] **VAL-03**: Existing DB, auth, room, route, SSE, and security tests pass after the migration.
- [ ] **VAL-04**: A final source scan finds no application-layer `sqlite3` database usage, no table-creating `init_db()` path, and no SQLModel dependency.

## Future Requirements

### API Contracts

- **API-01**: Pydantic v2 request/response models describe significant route payloads.

### Configuration

- **CFG-01**: Session secret configuration is renamed away from `FLASK_SECRET` while preserving backward compatibility.

## Out of Scope

| Feature | Reason |
|---------|--------|
| SQLModel | Explicitly rejected for this project as too unstable and immature. |
| Replacing SQLite with Postgres | v2.1 is a migration/access-layer cleanup, not a database backend change. |
| Pydantic route contract migration | Deferred from v2.0, but not required to deliver Alembic and async SQLAlchemy. |
| Jellyfin/TMDB behavior changes | Persistence migration must preserve product behavior. |
| WebSocket replacement for SSE | SSE remains sufficient and is not part of the persistence milestone. |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| MIG-01 | Phase 36 | Pending |
| MIG-02 | Phase 36 | Pending |
| MIG-03 | Phase 36 | Pending |
| MIG-04 | Phase 37 | Pending |
| SCH-01 | Phase 36 | Pending |
| SCH-02 | Phase 36 | Pending |
| SCH-03 | Phase 36 | Pending |
| ADB-01 | Phase 37 | Pending |
| ADB-02 | Phase 37 | Pending |
| ADB-03 | Phase 40 | Pending |
| ADB-04 | Phase 37 | Pending |
| MVC-01 | Phase 38 | Pending |
| MVC-02 | Phase 39 | Pending |
| MVC-03 | Phase 39 | Pending |
| MVC-04 | Phase 39 | Pending |
| PAR-01 | Phase 38 | Pending |
| PAR-02 | Phase 39 | Pending |
| PAR-03 | Phase 39 | Pending |
| PAR-04 | Phase 39 | Pending |
| PAR-05 | Phase 39 | Pending |
| VAL-01 | Phase 37 | Pending |
| VAL-02 | Phase 40 | Pending |
| VAL-03 | Phase 40 | Pending |
| VAL-04 | Phase 40 | Pending |

**Coverage:**
- v2.1 requirements: 24 total
- Mapped to phases: 24
- Unmapped: 0

---
*Requirements defined: 2026-05-05*
*Last updated: 2026-05-05 after roadmap traceability*
