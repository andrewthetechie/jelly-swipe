# Architecture Research

**Domain:** FastAPI persistence migration: SQLite, Alembic, async SQLAlchemy
**Researched:** 2026-05-05
**Confidence:** HIGH

## Recommended Architecture

```text
FastAPI app factory
  -> lifespan startup
      -> configure DB URL
      -> run Alembic upgrade head

Routers (controllers)
  -> dependencies.py
      -> require_auth
      -> Async DB session dependency
      -> provider/rate-limit dependencies
  -> domain services/repositories
      -> auth persistence
      -> room persistence
      -> swipe/match persistence
      -> SSE room-state polling
  -> SQLAlchemy models
      -> rooms
      -> swipes
      -> matches
      -> user_tokens
  -> Alembic versions
      -> baseline/current schema
      -> future schema deltas
```

## Component Responsibilities

| Component | Responsibility | Notes |
|-----------|----------------|-------|
| `jellyswipe/models.py` or `jellyswipe/models/` | SQLAlchemy declarative model definitions and shared `Base`. | Imported by Alembic `env.py` for `target_metadata`. |
| `jellyswipe/database.py` or refactored `db.py` | Async engine/sessionmaker setup, migration runner, DB URL handling. | Keep app startup and tests using the same path. |
| `jellyswipe/repositories/` | SQL query ownership for auth, rooms, swipes, matches. | Keeps controllers thin and preserves MVC/domain-router boundaries. |
| `jellyswipe/dependencies.py` | FastAPI `AsyncSession` dependency. | One session per request/unit of work. |
| `alembic/` | Migration environment and revision files. | Async env, metadata-based autogenerate, hand-reviewed revisions. |

## Architectural Patterns

### Pattern 1: Declarative Base As Schema Contract

**What:** Define typed SQLAlchemy ORM classes using `DeclarativeBase`, `Mapped`, and `mapped_column`.

**When to use:** All persisted app tables.

**Trade-offs:** Adds ORM model layer, but removes schema drift between ad hoc SQL and migrations.

### Pattern 2: Request-Scoped AsyncSession

**What:** `dependencies.py` yields an `AsyncSession` from `async_sessionmaker`.

**When to use:** Route handlers and repositories that do request-scoped work.

**Trade-offs:** Sessions are not concurrency-safe; SSE loops should open short-lived sessions per poll rather than holding one session for an hour.

### Pattern 3: Service/Repository Split For MVC

**What:** Route handlers parse request/session data and delegate persistence logic to async domain functions.

**When to use:** Current rooms router contains substantial SQL and transaction logic.

**Trade-offs:** More files, but easier tests and a clear boundary for DB behavior.

### Pattern 4: Alembic Startup Migration

**What:** App startup and test fixtures run `alembic upgrade head`; model metadata is not used for runtime `create_all`.

**When to use:** Production and tests.

**Trade-offs:** Slight startup/test overhead; avoids hidden schema drift.

## Data Flow

### Auth

```text
request.session["session_id"]
  -> require_auth()
  -> auth repository lookup in user_tokens
  -> AuthUser dependency result
```

### Swipe

```text
POST /room/{code}/swipe
  -> parse movie_id
  -> resolve Jellyfin metadata
  -> swipe service begins protected transaction
  -> insert swipe, advance cursor, maybe insert matches
  -> commit
```

### SSE

```text
EventSource generator loop
  -> check disconnect
  -> short-lived async DB query for room state
  -> emit only changed payload fields
  -> await non-blocking sleep
```

## Integration Points

| Boundary | Communication | Notes |
|----------|---------------|-------|
| FastAPI lifespan to database module | async startup call | Must run Alembic before serving requests. |
| Alembic env to app models | import `Base.metadata` | Avoid importing the FastAPI app instance or requiring runtime env vars unnecessarily. |
| Routers to repositories | async function calls | Keep SQL out of controllers. |
| Tests to DB setup | temp DB URL + Alembic upgrade | Test schema must match production schema creation. |

## Anti-Patterns

### Anti-Pattern 1: Importing App Factory From Alembic

**What people do:** `env.py` imports `jellyswipe` and triggers app startup/config validation.

**Why it is wrong:** This project currently creates a module-level app on import and reads env vars.

**Do this instead:** Import only lightweight model metadata from a module with no app startup side effects.

### Anti-Pattern 2: Holding One AsyncSession For SSE Lifetime

**What people do:** Open a session when the stream starts and reuse it until timeout.

**Why it is wrong:** It can hold transaction/connection state too long and is not needed for polling.

**Do this instead:** Open a short-lived session for each poll or each polling unit of work.

### Anti-Pattern 3: Mixing Raw sqlite3 And Async SQLAlchemy

**What people do:** Convert only some routes and leave direct sqlite calls in helpers.

**Why it is wrong:** Violates the milestone requirement and keeps two transaction models alive.

**Do this instead:** Track all `sqlite3`, `get_db_closing`, and direct `conn.execute` call sites to zero by milestone close.

## Sources

- SQLAlchemy asyncio docs: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- SQLAlchemy session concurrency docs: https://docs.sqlalchemy.org/en/20/orm/session_basics.html#is-the-session-thread-safe-is-asyncsession-safe-to-share-in-concurrent-tasks
- SQLAlchemy declarative table docs: https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html
- Alembic async cookbook: https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic

---
*Architecture research for: v2.1 Alembic + Async SQLAlchemy Persistence*
*Researched: 2026-05-05*
