# Phase 37: Async Database Infrastructure - Research

**Researched:** 2026-05-05
**Domain:** FastAPI + SQLAlchemy asyncio + Alembic + SQLite runtime/test infrastructure
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

Copied verbatim from `.planning/phases/37-async-database-infrastructure/37-CONTEXT.md`. [VERIFIED: codebase grep]

### Locked Decisions
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

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MIG-04 | FastAPI startup runs a controlled migration path instead of ad hoc table creation. [VERIFIED: `.planning/REQUIREMENTS.md`] | Bootstrap wrapper runs Alembic before Uvicorn import; app lifespan stops calling sync schema/bootstrap helpers. [VERIFIED: codebase grep] [CITED: https://alembic.sqlalchemy.org/en/latest/api/commands.html] |
| ADB-01 | The database module exposes async SQLAlchemy engine and sessionmaker setup for the configured SQLite database path. [VERIFIED: `.planning/REQUIREMENTS.md`] | Use one process-wide `AsyncEngine` plus `async_sessionmaker`, targeting `sqlite+aiosqlite:///...`, with SQLite event hooks on `engine.sync_engine`. [CITED: https://docs.sqlalchemy.org/en/20/dialects/sqlite.html] [CITED: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html] |
| ADB-02 | FastAPI dependency injection provides request-scoped `AsyncSession` access through the existing dependency layer. [VERIFIED: `.planning/REQUIREMENTS.md`] | Keep `dependencies.py` as the DI seam, but yield a unit-of-work/repository-registry object and use `Depends(..., scope="function")` for deterministic teardown. [VERIFIED: codebase grep] [CITED: https://fastapi.tiangolo.com/reference/dependencies/] [CITED: https://fastapi.tiangolo.com/advanced/advanced-dependencies/] |
| ADB-04 | Async session lifecycle avoids shared global sessions and closes sessions cleanly after each request or unit of work. [VERIFIED: `.planning/REQUIREMENTS.md`] | `AsyncSession` must be per task/request, not shared globally; close via `async with` and dispose engine on shutdown. [CITED: https://docs.sqlalchemy.org/en/20/orm/session_basics.html] [CITED: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html] |
| VAL-01 | Tests create temporary databases through the Alembic upgrade path instead of `init_db()` table creation. [VERIFIED: `.planning/REQUIREMENTS.md`] | Existing fixtures already use `upgrade_to_head(build_sqlite_url(...))`; Phase 37 should extend that to async runtime fixtures and rewrite old sync-only dependency tests. [VERIFIED: codebase grep] |
</phase_requirements>

## Summary

Phase 37 should introduce one dedicated async runtime module, one bootstrap wrapper, and one DI-facing unit-of-work surface, then route startup and tests through those primitives immediately. The current code still boots through `prepare_runtime_database()` inside FastAPI lifespan, still exposes `sqlite3.Connection` via `get_db_dep()`, and still contains many direct sync DB callsites in `auth.py` and `routers/rooms.py`; that means this phase must focus on replacing the runtime seam without pretending the whole app is already async. [VERIFIED: codebase grep]

For SQLite, the standard path is `create_async_engine("sqlite+aiosqlite:///...")` plus `async_sessionmaker`, with per-connection setup attached to `engine.sync_engine` events. `AsyncSession` is explicitly not safe to share across concurrent tasks, so the correct boundary is "one session per request or unit of work", not a global singleton session. [CITED: https://docs.sqlalchemy.org/en/20/dialects/sqlite.html] [CITED: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html] [CITED: https://docs.sqlalchemy.org/en/20/orm/session_basics.html]

FastAPI now supports `Depends(scope="function")` for `yield` dependencies, which is the right fit for Phase 37's automatic commit-on-success and rollback-on-error rule. That matters here because the project already has a long-lived SSE route whose comments correctly note that request-scoped DB dependencies are a bad fit for stream lifetimes; Phase 37 should keep SSE on a separate path until the domain migration work in Phase 39. [CITED: https://fastapi.tiangolo.com/advanced/advanced-dependencies/] [CITED: https://fastapi.tiangolo.com/reference/dependencies/] [VERIFIED: codebase grep]

**Primary recommendation:** Build `DATABASE_URL`-driven async runtime primitives first, expose them via a unit-of-work dependency in `dependencies.py`, move Alembic execution into a pre-Uvicorn bootstrap wrapper, and keep SSE and most domain SQL conversion explicitly out of Phase 37. [VERIFIED: codebase grep] [CITED: https://alembic.sqlalchemy.org/en/latest/api/commands.html]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Pre-start migration runner | API / Backend | Database / Storage | The wrapper must run before the ASGI app serves traffic and must apply Alembic state to the target database. [VERIFIED: `.planning/phases/37-async-database-infrastructure/37-CONTEXT.md`] [CITED: https://alembic.sqlalchemy.org/en/latest/api/commands.html] |
| Async engine + session factory | API / Backend | Database / Storage | Engine/session lifecycle belongs to application runtime infrastructure, not to routers or models. [VERIFIED: `.planning/phases/37-async-database-infrastructure/37-CONTEXT.md`] [CITED: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html] |
| Request-scoped DB dependency / unit of work | API / Backend | -- | FastAPI DI owns request lifecycle and is already the project's seam for auth/provider/DB access. [VERIFIED: codebase grep] [CITED: https://fastapi.tiangolo.com/reference/dependencies/] |
| Runtime SQLite PRAGMAs + maintenance cleanup | API / Backend | Database / Storage | Current code treats WAL/synchronous/cleanup as runtime concerns after schema readiness, not migration logic. [VERIFIED: codebase grep] |
| Alembic-backed temp DB test setup | API / Backend | Database / Storage | Test fixtures must provision real database state through migrations, then exercise the same runtime/session primitives the app uses. [VERIFIED: codebase grep] |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy asyncio | `2.0.49` - published 2026-04-03. [VERIFIED: importlib.metadata + `uv.lock`] | `AsyncEngine`, `AsyncSession`, and `async_sessionmaker` for the app runtime. [CITED: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html] | Official SQLAlchemy async API is the project's chosen persistence stack and already matches Phase 36 models/Alembic work. [VERIFIED: `.planning/REQUIREMENTS.md`] [CITED: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html] |
| aiosqlite | `0.22.1` - published 2025-12-23. [VERIFIED: PyPI JSON] | SQLite async DBAPI driver behind `sqlite+aiosqlite:///...`. [CITED: https://docs.sqlalchemy.org/en/20/dialects/sqlite.html] | SQLAlchemy's SQLite async dialect is explicitly `aiosqlite`; Phase 37 cannot deliver ADB-01 without it. [CITED: https://docs.sqlalchemy.org/en/20/dialects/sqlite.html] [VERIFIED: importlib.metadata shows package missing] |
| Alembic | `1.18.4` - published 2026-02-10. [VERIFIED: importlib.metadata + PyPI JSON] | Programmatic `upgrade(head)` for bootstrap and tests. [CITED: https://alembic.sqlalchemy.org/en/latest/api/commands.html] | The repo already has `jellyswipe.migrations.upgrade_to_head()` and Phase 36 made Alembic the schema source of truth. [VERIFIED: codebase grep] |
| FastAPI | `0.136.1` - published 2026-04-23. [VERIFIED: importlib.metadata + `uv.lock`] | DI boundary, lifespan/shutdown integration, and request-scoped unit-of-work wiring. [CITED: https://fastapi.tiangolo.com/reference/dependencies/] | `Depends(scope="function")` plus `yield` teardown gives the cleanest commit/rollback boundary for this phase. [CITED: https://fastapi.tiangolo.com/advanced/advanced-dependencies/] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| AnyIO pytest plugin | `4.13.0` - published 2026-03-24. [VERIFIED: importlib.metadata + PyPI JSON] | Async unit/integration tests via `@pytest.mark.anyio`. [CITED: https://fastapi.tiangolo.com/advanced/async-tests/] | Use for tests that must `await` async session or runtime helpers directly. [VERIFIED: `pytest --markers` + `pytest --fixtures`] |
| HTTPX | `0.28.1` - published 2024-12-06. [VERIFIED: importlib.metadata + PyPI JSON] | `AsyncClient` + `ASGITransport` for async app tests. [CITED: https://fastapi.tiangolo.com/advanced/async-tests/] | Use only when test code itself is async; keep `TestClient` for ordinary sync route tests. [CITED: https://fastapi.tiangolo.com/advanced/async-tests/] |
| Uvicorn | `0.46.0` - published 2026-04-23. [VERIFIED: importlib.metadata + PyPI JSON] | ASGI server invoked after the bootstrap runner succeeds. [VERIFIED: codebase grep] | Use the existing runtime, but launch it from a wrapper instead of directly from Docker/README commands. [VERIFIED: codebase grep] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `@pytest.mark.anyio` | `pytest-asyncio` | The repo already has AnyIO installed and pytest exposes AnyIO markers/fixtures today, so adding `pytest-asyncio` is unnecessary unless the team strongly prefers its style. [VERIFIED: `pytest --markers` + `pytest --fixtures`] [CITED: https://fastapi.tiangolo.com/advanced/async-tests/] |
| Programmatic Alembic calls from Python | Shelling out to `alembic upgrade head` | The shell command works, but the repo already has a Python helper and Alembic officially supports `command.upgrade(Config, "head")`, which is easier to reuse in bootstrap and fixtures. [VERIFIED: codebase grep] [CITED: https://alembic.sqlalchemy.org/en/latest/api/commands.html] |
| Raw `AsyncSession` dependency | Unit-of-work / repository registry wrapper | Raw session injection is simpler, but it contradicts locked decision D-06 and makes later Phases 38-39 harder to structure cleanly. [VERIFIED: `.planning/phases/37-async-database-infrastructure/37-CONTEXT.md`] |

**Installation:**
```bash
uv add aiosqlite
```

**Version verification:**
- `fastapi==0.136.1` - 2026-04-23. [VERIFIED: importlib.metadata + `uv.lock`]
- `sqlalchemy==2.0.49` - 2026-04-03. [VERIFIED: importlib.metadata + `uv.lock`]
- `alembic==1.18.4` - 2026-02-10. [VERIFIED: importlib.metadata + PyPI JSON]
- `aiosqlite==0.22.1` - 2025-12-23. [VERIFIED: PyPI JSON]

## Architecture Patterns

### System Architecture Diagram

```text
process start
    |
    v
bootstrap runner (`python -m jellyswipe.bootstrap`) [recommended]
    |
    +--> resolve `DATABASE_URL`
    |
    +--> Alembic `upgrade head`
    |       |
    |       +--> failure -> exit non-zero, app never serves traffic
    |
    +--> initialize async runtime module
    |
    +--> start Uvicorn importing `jellyswipe:app`
                |
                v
        FastAPI request
                |
                +--> `dependencies.py` yields `DbUnitOfWork`
                |         |
                |         +--> `async_sessionmaker()` -> fresh `AsyncSession`
                |         +--> route/domain code uses repos via UoW
                |         +--> success -> commit
                |         +--> error -> rollback -> re-raise
                |
                +--> app shutdown -> `await engine.dispose()`

tests
    |
    +--> tmp db path
    +--> Alembic `upgrade head`
    +--> create async engine/session factory for that temp db
    +--> app / fixture uses same runtime primitives
```

### Recommended Project Structure
```text
jellyswipe/
├── bootstrap.py       # run migrations, init runtime, then start uvicorn
├── db_runtime.py      # async engine/sessionmaker + sqlite runtime hooks
├── db_uow.py          # unit-of-work / repository registry facade
├── migrations.py      # database URL resolution + Alembic helper
├── dependencies.py    # FastAPI Depends() wrappers over auth/provider/db UoW
└── __init__.py        # app factory and shutdown disposal only
tests/
├── conftest.py        # temp DB + runtime/app fixtures
└── test_dependencies.py
```

### Pattern 1: Dedicated Async Runtime Module
**What:** Keep engine creation, sessionmaker creation, and SQLite connection setup in one module that does not import the FastAPI app or model metadata graph. [VERIFIED: `.planning/phases/37-async-database-infrastructure/37-CONTEXT.md`] [CITED: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html]

**When to use:** Always; Phase 37's runtime should be process-wide infrastructure, not a helper recreated per request. [CITED: https://docs.sqlalchemy.org/en/20/core/connections.html] [CITED: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html]

**Example:**
```python
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

engine = create_async_engine(
    "sqlite+aiosqlite:///./data/jellyswipe.db",
    connect_args={"autocommit": False},
)
SessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

@event.listens_for(engine.sync_engine, "connect")
def on_connect(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()
```
Source: SQLAlchemy asyncio + SQLite docs. [CITED: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html] [CITED: https://docs.sqlalchemy.org/en/20/dialects/sqlite.html]

### Pattern 2: Function-Scoped Unit-of-Work Dependency
**What:** Yield a unit-of-work object from `dependencies.py`, commit after the route returns successfully, rollback on any exception, and close the session via `async with`. [VERIFIED: `.planning/phases/37-async-database-infrastructure/37-CONTEXT.md`] [CITED: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/] [CITED: https://fastapi.tiangolo.com/advanced/advanced-dependencies/]

**When to use:** For ordinary request/response routes in this phase; do not use it for long-lived SSE streams. [VERIFIED: codebase grep] [CITED: https://fastapi.tiangolo.com/advanced/advanced-dependencies/]

**Example:**
```python
from fastapi import Depends

async def get_db_uow():
    async with SessionFactory() as session:
        uow = DbUnitOfWork(session)
        try:
            yield uow
            await session.commit()
        except Exception:
            await session.rollback()
            raise

DbUowDep = Depends(get_db_uow, scope="function")
```
Source: pattern adapted from FastAPI `yield` dependency docs and SQLAlchemy async session factory docs. [CITED: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/] [CITED: https://fastapi.tiangolo.com/reference/dependencies/] [CITED: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html]

### Pattern 3: Alembic-Backed Temp Database Fixtures
**What:** Keep using temp file databases, run Alembic to head, then create the async runtime against that file for tests. [VERIFIED: codebase grep]

**When to use:** For all Phase 37 tests that need database state; do not reintroduce `init_db()` or ad hoc schema creation. [VERIFIED: `.planning/REQUIREMENTS.md`] [VERIFIED: codebase grep]

**Example:**
```python
from jellyswipe.migrations import build_sqlite_url, upgrade_to_head

db_url = build_sqlite_url(str(tmp_path / "test.db"))
upgrade_to_head(db_url)
engine = create_async_engine(db_url.replace("sqlite:///", "sqlite+aiosqlite:///"))
```
Source: current repo helper plus SQLAlchemy SQLite async URL format. [VERIFIED: codebase grep] [CITED: https://docs.sqlalchemy.org/en/20/dialects/sqlite.html]

### Anti-Patterns to Avoid
- **Running migrations inside FastAPI lifespan:** This violates D-03 and makes app import/startup behavior harder to reason about. [VERIFIED: `.planning/phases/37-async-database-infrastructure/37-CONTEXT.md`] [VERIFIED: codebase grep]
- **Global shared `AsyncSession`:** SQLAlchemy documents that `AsyncSession` is stateful and unsafe to share across concurrent tasks. [CITED: https://docs.sqlalchemy.org/en/20/orm/session_basics.html]
- **Using the request DB dependency inside SSE streams:** FastAPI's default request-scope teardown happens after the response is sent, and the repo already documents that request-scoped DB deps are a poor fit for 3600-second streams. [CITED: https://fastapi.tiangolo.com/advanced/advanced-dependencies/] [VERIFIED: codebase grep]
- **Pretending Phase 37 removes all sync DB access:** `auth.py` and most of `routers/rooms.py` still use sync helpers and are explicitly deferred to later phases. [VERIFIED: codebase grep] [VERIFIED: `.planning/ROADMAP.md`]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async session scoping | Custom global session registry | `async_sessionmaker` + per-request `async with` UoW | SQLAlchemy already defines the safe lifecycle pattern and warns against sharing one `AsyncSession` across concurrent tasks. [CITED: https://docs.sqlalchemy.org/en/20/orm/session_basics.html] [CITED: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html] |
| Schema/bootstrap execution | Manual `CREATE TABLE` or resurrected `init_db()` | Alembic `command.upgrade(..., "head")` via existing helper | Phase 36 made Alembic authoritative; manual schema creation would regress MIG-01/MIG-04. [VERIFIED: `.planning/REQUIREMENTS.md`] [VERIFIED: codebase grep] [CITED: https://alembic.sqlalchemy.org/en/latest/api/commands.html] |
| Async test event-loop glue | Homegrown loop runners | AnyIO plugin and/or FastAPI `TestClient` | The repo already has the AnyIO plugin active, and FastAPI documents the official async test path. [VERIFIED: `pytest --markers` + `pytest --fixtures`] [CITED: https://fastapi.tiangolo.com/advanced/async-tests/] |
| SQLite connection setup | Scattered PRAGMA calls in routes | SQLAlchemy connect events plus explicit post-migration runtime prep | Current runtime settings are infrastructure concerns, and SQLAlchemy documents connection event hooks for SQLite setup. [VERIFIED: codebase grep] [CITED: https://docs.sqlalchemy.org/en/20/dialects/sqlite.html] |

**Key insight:** Phase 37 should create reusable runtime primitives exactly once, then make startup/tests/dependencies consume them; it should not "half-convert" domain code by sprinkling ad hoc async helpers through routers. [VERIFIED: `.planning/phases/37-async-database-infrastructure/37-CONTEXT.md`] [VERIFIED: `.planning/ROADMAP.md`]

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | Existing `init_db()`-era databases have no required upgrade/stamp path because Phase 36 locked the milestone as effectively greenfield and said old DBs can be discarded. [VERIFIED: `.planning/phases/36-alembic-baseline-and-sqlalchemy-models/36-CONTEXT.md`] | Code edit only for new runtime/test paths; no production data migration is required in this phase. [VERIFIED: `.planning/phases/36-alembic-baseline-and-sqlalchemy-models/36-CONTEXT.md`] |
| Live service config | Docker still starts `uvicorn jellyswipe:app` directly, so no external bootstrap command exists yet. [VERIFIED: codebase grep] | Update container/runtime entrypoint to call the bootstrap wrapper instead of direct Uvicorn. [VERIFIED: codebase grep] |
| OS-registered state | None found in repo-scoped research. [VERIFIED: codebase grep] | None in this phase unless deployment scripts outside git are managing service commands. [ASSUMED] |
| Secrets/env vars | `DATABASE_URL` is locked as the new primary source, but current code still falls back through `DB_PATH` and app-level defaults. [VERIFIED: codebase grep] [VERIFIED: `.planning/phases/37-async-database-infrastructure/37-CONTEXT.md`] | Convert runtime bootstrap to prefer `DATABASE_URL` first, preserve minimal `DB_PATH` compatibility only where tests or legacy code still need it. [VERIFIED: codebase grep] |
| Build artifacts | `.venv` lacks `aiosqlite`; AnyIO plugin is present; no repo-local async runtime module exists yet. [VERIFIED: importlib.metadata] [VERIFIED: `pytest --markers` + `pytest --fixtures`] [VERIFIED: codebase grep] | Install `aiosqlite`, add runtime module(s), and rewrite dependency fixtures/tests to use them. [VERIFIED: importlib.metadata] |

## Common Pitfalls

### Pitfall 1: Commit/Rollback Happens Too Late
**What goes wrong:** The DB session stays open until after the response is sent because the dependency uses default request scope. [CITED: https://fastapi.tiangolo.com/advanced/advanced-dependencies/]
**Why it happens:** FastAPI's default for `yield` dependencies is request-scoped teardown, not function-scoped teardown. [CITED: https://fastapi.tiangolo.com/advanced/advanced-dependencies/] [CITED: https://fastapi.tiangolo.com/reference/dependencies/]
**How to avoid:** Bind the DB dependency with `Depends(..., scope="function")` for normal request/response routes. [CITED: https://fastapi.tiangolo.com/advanced/advanced-dependencies/]
**Warning signs:** A route returns successfully but the commit/rollback behavior is only observable after response completion, or streaming endpoints hold the DB resource far longer than intended. [CITED: https://fastapi.tiangolo.com/advanced/advanced-dependencies/] [VERIFIED: codebase grep]

### Pitfall 2: Async SQLite Driver Missing
**What goes wrong:** Runtime initialization fails or the engine URL is invalid because `sqlite+aiosqlite:///...` is configured without the `aiosqlite` package. [CITED: https://docs.sqlalchemy.org/en/20/dialects/sqlite.html]
**Why it happens:** The repo currently depends on SQLAlchemy and Alembic but does not have `aiosqlite` installed. [VERIFIED: importlib.metadata]
**How to avoid:** Add `aiosqlite` before implementing the runtime module and keep the URL scheme explicit in tests and app code. [VERIFIED: importlib.metadata] [CITED: https://docs.sqlalchemy.org/en/20/dialects/sqlite.html]
**Warning signs:** `ModuleNotFoundError: No module named 'aiosqlite'` or startup/tests still using `sqlite:///...` instead of `sqlite+aiosqlite:///...`. [VERIFIED: importlib.metadata] [CITED: https://docs.sqlalchemy.org/en/20/dialects/sqlite.html]

### Pitfall 3: Shared `AsyncSession` Across Tasks
**What goes wrong:** Cross-request state leakage, invalid concurrent use, or transaction-state corruption appears under load. [CITED: https://docs.sqlalchemy.org/en/20/orm/session_basics.html]
**Why it happens:** `AsyncSession` is mutable/stateful and SQLAlchemy says it is not safe to use one instance across concurrent asyncio tasks. [CITED: https://docs.sqlalchemy.org/en/20/orm/session_basics.html]
**How to avoid:** Create a fresh session from `async_sessionmaker` per request or per explicit unit of work. [CITED: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html]
**Warning signs:** Cached session singletons, task-local hacks, or dependencies that return the same session instance repeatedly. [CITED: https://docs.sqlalchemy.org/en/20/orm/session_basics.html] [ASSUMED]

### Pitfall 4: SSE Accidentally Pulled Onto the New Request Dependency
**What goes wrong:** The room stream holds one request DB session for the entire stream lifetime or closes it at the wrong moment. [VERIFIED: codebase grep] [CITED: https://fastapi.tiangolo.com/advanced/advanced-dependencies/]
**Why it happens:** The SSE route is long-lived and current code already documents that request-scoped DB dependencies do not fit a 3600-second stream. [VERIFIED: codebase grep]
**How to avoid:** Keep SSE on its current dedicated connection path in Phase 37 and revisit it during Phase 39's domain conversion. [VERIFIED: `.planning/ROADMAP.md`] [VERIFIED: codebase grep]
**Warning signs:** Attempts to replace the SSE route's local connection with the normal DB dependency during this phase. [VERIFIED: codebase grep]

### Pitfall 5: Bootstrap Wrapper Stops at Code but Not Deployment
**What goes wrong:** Local code supports a migration wrapper, but Docker/README/test launch paths still start Uvicorn directly, bypassing MIG-04. [VERIFIED: codebase grep]
**Why it happens:** The current Docker CMD and README commands still reference direct `uvicorn` or old `gunicorn` entrypoints. [VERIFIED: codebase grep]
**How to avoid:** Treat entrypoint updates as part of Phase 37 planning, not as follow-up cleanup. [VERIFIED: codebase grep]
**Warning signs:** `jellyswipe:app` remains the only documented production startup command after the phase lands. [VERIFIED: codebase grep]

## Code Examples

Verified patterns from official sources:

### Async Engine + Session Factory
```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

engine = create_async_engine("sqlite+aiosqlite:///filename")
SessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
```
Source: SQLAlchemy asyncio + SQLite docs. [CITED: https://docs.sqlalchemy.org/en/20/dialects/sqlite.html] [CITED: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html]

### FastAPI `yield` Dependency With Teardown
```python
async def get_db():
    db = DBSession()
    try:
        yield db
    finally:
        db.close()
```
Source: FastAPI dependency docs. [CITED: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/]

### Programmatic Alembic Upgrade
```python
from alembic.config import Config
from alembic import command

alembic_cfg = Config("/path/to/yourapp/alembic.ini")
command.upgrade(alembic_cfg, "head")
```
Source: Alembic command docs. [CITED: https://alembic.sqlalchemy.org/en/latest/api/commands.html]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| FastAPI `yield` dependencies always cleaned up after the full response lifecycle | FastAPI supports `Depends(scope="function")` to run dependency teardown immediately after the path operation returns. [CITED: https://fastapi.tiangolo.com/advanced/advanced-dependencies/] | Added in FastAPI `0.121.0`. [CITED: https://fastapi.tiangolo.com/advanced/advanced-dependencies/] | Phase 37 can commit/rollback deterministically for normal routes without waiting for response transmission. [CITED: https://fastapi.tiangolo.com/advanced/advanced-dependencies/] |
| Project startup used sync `prepare_runtime_database()` inside app lifespan | Milestone roadmap now requires a pre-Uvicorn Alembic migration path plus async runtime primitives. [VERIFIED: codebase grep] [VERIFIED: `.planning/ROADMAP.md`] | Milestone v2.1 / Phase 37 planning. [VERIFIED: `.planning/ROADMAP.md`] | Entry points, tests, and dependency wiring all need to pivot together; a partial change will leave startup inconsistent. [VERIFIED: codebase grep] |

**Deprecated/outdated:**
- `DBConn = Annotated[sqlite3.Connection, Depends(get_db_dep)]` as the primary runtime DB surface is outdated for this milestone and should be replaced in this phase. [VERIFIED: codebase grep] [VERIFIED: `.planning/phases/37-async-database-infrastructure/37-CONTEXT.md`]
- Direct `prepare_runtime_database()` from FastAPI lifespan is outdated as the schema/bootstrap path because MIG-04 requires a controlled migration runner. [VERIFIED: codebase grep] [VERIFIED: `.planning/REQUIREMENTS.md`]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | No repo-external service manager or deployment script is hiding an alternate startup command outside the checked-in Dockerfile/README. [ASSUMED] | Runtime State Inventory / Common Pitfalls | Planner could miss a non-git entrypoint that also needs the new bootstrap wrapper. |
| A2 | `asgi-lifespan` is not required for this phase if route-level async tests remain mostly `TestClient`-based and async tests focus on low-level runtime/session helpers. [ASSUMED] | Standard Stack / Validation Architecture | If the planner chooses full async HTTPX app tests with lifespan handling, one more test helper dependency may be needed. |

## Open Questions (RESOLVED)

1. **How much of auth cleanup belongs in Phase 37 versus Phase 38?**
   - What we know: Phase 37 locks runtime maintenance functions into the async path, while Phase 38 converts auth token CRUD semantics. [VERIFIED: `.planning/phases/37-async-database-infrastructure/37-CONTEXT.md`] [VERIFIED: `.planning/ROADMAP.md`]
   - Resolution: `cleanup_expired_auth_sessions()` moves in Phase 37 as runtime infrastructure, while `create_session()` / `get_current_token()` / `destroy_session()` remain on the legacy path until Phase 38 converts auth persistence end to end. [VERIFIED: `.planning/ROADMAP.md`] [VERIFIED: `.planning/phases/37-async-database-infrastructure/37-CONTEXT.md`]

2. **Which startup command becomes canonical for local dev and container runtime?**
   - What we know: Docker starts direct Uvicorn now, and the README still contains old direct app commands. [VERIFIED: codebase grep]
   - Resolution: adopt one Python module bootstrap entrypoint, `python -m jellyswipe.bootstrap`, and make Docker plus local startup documentation point to that wrapper so Alembic runs before the ASGI server starts. [VERIFIED: codebase grep] [ASSUMED]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | App/runtime/tests | Yes | `3.13.9`. [VERIFIED: `python3 --version`] | -- |
| `uv` | Dependency management / reproducible installs | Yes | `0.9.5`. [VERIFIED: `uv --version`] | `pip`, but the repo is already using `uv.lock`, so do not switch package managers in this phase. [VERIFIED: codebase grep] |
| pytest | Validation | Yes | `9.0.3`. [VERIFIED: importlib.metadata] | -- |
| AnyIO pytest plugin | Async tests | Yes | `4.13.0`; marker + fixtures are active. [VERIFIED: importlib.metadata] [VERIFIED: `pytest --markers` + `pytest --fixtures`] | Use existing `TestClient` tests if you do not need direct `await` calls. [CITED: https://fastapi.tiangolo.com/advanced/async-tests/] |
| aiosqlite | Async SQLite engine | No | Missing from `.venv`. [VERIFIED: importlib.metadata] | None - install required to satisfy ADB-01. [CITED: https://docs.sqlalchemy.org/en/20/dialects/sqlite.html] |
| HTTPX | Async app tests | Yes | `0.28.1`. [VERIFIED: importlib.metadata] | Keep sync `TestClient` tests if async client coverage is unnecessary. [CITED: https://fastapi.tiangolo.com/advanced/async-tests/] |
| `asgi-lifespan` | Full async HTTPX tests with lifespan handling | No | Missing from `.venv`. [VERIFIED: importlib.metadata] | Likely unnecessary if Phase 37 keeps most app-route tests on `TestClient`. [ASSUMED] |

**Missing dependencies with no fallback:**
- `aiosqlite` for the actual async SQLite engine. [VERIFIED: importlib.metadata]

**Missing dependencies with fallback:**
- `asgi-lifespan`; fallback is to keep app-route tests mostly sync via `TestClient` and reserve async tests for runtime helpers. [ASSUMED]

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest 9.0.3` with AnyIO plugin active. [VERIFIED: importlib.metadata] [VERIFIED: `pytest --markers`] |
| Config file | `pyproject.toml`. [VERIFIED: codebase grep] |
| Quick run command | `./.venv/bin/pytest tests/test_auth.py tests/test_dependencies.py -q` - passes today. [VERIFIED: command output] |
| Full suite command | `./.venv/bin/pytest` - existing project default. [VERIFIED: codebase grep] |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MIG-04 | Bootstrap runs Alembic before app serve path and fails fast on migration error. [VERIFIED: `.planning/REQUIREMENTS.md`] | integration | `./.venv/bin/pytest tests/test_bootstrap.py -q` | Planned in `37-02` Task `37-02-01` |
| ADB-01 | Async engine/sessionmaker resolves configured SQLite URL and can open a session. [VERIFIED: `.planning/REQUIREMENTS.md`] | unit | `./.venv/bin/pytest tests/test_db_runtime.py -q` | Planned in `37-01` Task `37-01-01` |
| ADB-02 | Dependency layer yields UoW/repo object and commits/rolls back correctly. [VERIFIED: `.planning/REQUIREMENTS.md`] | integration | `./.venv/bin/pytest tests/test_dependencies.py -q` | Yes - rewrite/extend existing file |
| ADB-04 | Session is not shared globally and closes cleanly after each request/unit of work. [VERIFIED: `.planning/REQUIREMENTS.md`] | unit/integration | `./.venv/bin/pytest tests/test_db_runtime.py tests/test_dependencies.py -q` | Planned across `37-01` runtime + dependency tasks |
| VAL-01 | Tests provision temp DBs through Alembic, not `init_db()`. [VERIFIED: `.planning/REQUIREMENTS.md`] | integration | `./.venv/bin/pytest tests/test_auth.py tests/test_dependencies.py -q` | Yes - fixtures already use Alembic, but dependency/runtime assertions are still sync-oriented |

### Sampling Rate
- **Per task commit:** `./.venv/bin/pytest tests/test_auth.py tests/test_dependencies.py -q`
- **Per wave merge:** `./.venv/bin/pytest tests/test_auth.py tests/test_dependencies.py tests/test_db.py -q`
- **Phase gate:** `./.venv/bin/pytest`

### Coverage Ownership (ASSIGNED)
- [ ] `tests/test_bootstrap.py` - created in Plan `37-02` Task `37-02-01` to prove bootstrap migration success/fail-fast behavior for MIG-04.
- [ ] `tests/test_db_runtime.py` - created in Plan `37-01` Task `37-01-01` to prove engine/session factory, shutdown disposal, and no-global-session lifecycle for ADB-01 and ADB-04.
- [ ] Rewrite `tests/test_dependencies.py` around async UoW behavior instead of `sqlite3.Connection`.
- [ ] Rewrite low-level callers in `tests/test_auth.py` that still assume sync-only DB helpers as the main verification surface.

## Security Domain

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Yes | Preserve existing `require_auth` boundary and do not change token semantics in this phase. [VERIFIED: codebase grep] [VERIFIED: `.planning/ROADMAP.md`] |
| V3 Session Management | Yes | Keep session-cookie + auth-vault lifecycle intact while moving only the DB infrastructure underneath it. [VERIFIED: codebase grep] [VERIFIED: `.planning/REQUIREMENTS.md`] |
| V4 Access Control | Yes | Continue routing protected endpoints through dependency-injected auth/user context rather than direct DB checks in routes. [VERIFIED: codebase grep] |
| V5 Input Validation | Yes | Use FastAPI request parsing plus SQLAlchemy bound parameters / ORM APIs; do not reintroduce string-built SQL during the migration. [VERIFIED: codebase grep] [ASSUMED] |
| V6 Cryptography | No new crypto in scope | Reuse existing framework/session signing primitives; do not hand-roll anything in this phase. [VERIFIED: codebase grep] [ASSUMED] |

### Known Threat Patterns for This Stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Shared session or transaction across concurrent requests | Tampering / Information Disclosure | One `AsyncSession` per request or unit of work; never store it globally. [CITED: https://docs.sqlalchemy.org/en/20/orm/session_basics.html] |
| Serving against an unmigrated schema | Tampering / Availability | Run Alembic before Uvicorn and fail fast on migration error. [VERIFIED: `.planning/phases/37-async-database-infrastructure/37-CONTEXT.md`] [CITED: https://alembic.sqlalchemy.org/en/latest/api/commands.html] |
| Stream endpoint holding open request DB resources | Denial of Service | Keep SSE on a separate short-transaction pattern and do not route it through the normal request UoW dependency in this phase. [VERIFIED: codebase grep] [CITED: https://fastapi.tiangolo.com/advanced/advanced-dependencies/] |
| SQL built outside ORM/bound-parameter paths during conversion | Tampering | Migrate infrastructure first, then convert domains through repository/UoW boundaries instead of sprinkling raw SQL across routes. [VERIFIED: `.planning/ROADMAP.md`] [ASSUMED] |

## Sources

### Primary (HIGH confidence)
- `.planning/phases/37-async-database-infrastructure/37-CONTEXT.md` - locked scope and implementation decisions. [VERIFIED: codebase grep]
- `.planning/phases/36-alembic-baseline-and-sqlalchemy-models/36-CONTEXT.md` - upstream migration/model decisions. [VERIFIED: codebase grep]
- `.planning/REQUIREMENTS.md` - Phase 37 requirement IDs and milestone scope. [VERIFIED: codebase grep]
- `.planning/ROADMAP.md` - phase dependencies and success criteria. [VERIFIED: codebase grep]
- `jellyswipe/__init__.py`, `jellyswipe/db.py`, `jellyswipe/dependencies.py`, `jellyswipe/auth.py`, `jellyswipe/migrations.py`, `jellyswipe/routers/rooms.py`, `tests/conftest.py`, `tests/test_auth.py`, `tests/test_dependencies.py`, `Dockerfile` - current implementation baseline. [VERIFIED: codebase grep]
- SQLAlchemy asyncio docs - `https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html`
- SQLAlchemy SQLite dialect docs - `https://docs.sqlalchemy.org/en/20/dialects/sqlite.html`
- SQLAlchemy session basics - `https://docs.sqlalchemy.org/en/20/orm/session_basics.html`
- FastAPI dependency reference - `https://fastapi.tiangolo.com/reference/dependencies/`
- FastAPI advanced dependencies - `https://fastapi.tiangolo.com/advanced/advanced-dependencies/`
- FastAPI dependencies with `yield` - `https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/`
- FastAPI async tests - `https://fastapi.tiangolo.com/advanced/async-tests/`
- Alembic commands/config docs - `https://alembic.sqlalchemy.org/en/latest/api/commands.html`, `https://alembic.sqlalchemy.org/en/latest/api/config.html`

### Secondary (MEDIUM confidence)
- PyPI JSON metadata for package version/date verification:
  - `https://pypi.org/pypi/aiosqlite/json`
  - `https://pypi.org/pypi/alembic/json`
  - `https://pypi.org/pypi/anyio/json`
  - `https://pypi.org/pypi/httpx/json`
  - `https://pypi.org/pypi/uvicorn/json`

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - core APIs, versions, and missing dependencies were verified from official docs, installed packages, and lockfile metadata. [VERIFIED: importlib.metadata] [VERIFIED: `uv.lock`] [CITED: official docs URLs above]
- Architecture: HIGH - user decisions are locked, and the current seams/startup/tests were verified directly in the repo. [VERIFIED: codebase grep]
- Pitfalls: HIGH - they are directly supported by official FastAPI/SQLAlchemy docs and by current SSE/dependency code comments. [CITED: official docs URLs above] [VERIFIED: codebase grep]

**Research date:** 2026-05-05
**Valid until:** 2026-06-04
