# Project Research Summary

**Project:** Jelly Swipe
**Domain:** FastAPI persistence migration: SQLite, Alembic, async SQLAlchemy
**Researched:** 2026-05-05
**Confidence:** HIGH

## Executive Summary

Jelly Swipe currently has a synchronous `sqlite3` persistence layer: `init_db()` creates tables and performs ad hoc column checks, `dependencies.py` yields synchronous connections, auth helpers perform direct SQL, and the rooms router owns substantial transaction logic. v2.1 should replace this with an Alembic-managed schema and SQLAlchemy declarative models while preserving the existing room/session/match behavior.

The recommended approach is staged: introduce SQLAlchemy models and Alembic first, then add async engine/session infrastructure, then convert auth and room-related persistence behind MVC-friendly service/repository boundaries. The riskiest area is the swipe path because it currently depends on explicit SQLite transaction semantics to avoid match race regressions.

## Key Findings

### Recommended Stack

**Core technologies:**
- SQLAlchemy 2.0.x: declarative models, async engine, `AsyncSession`, `async_sessionmaker`.
- Alembic 1.18.x: migration environment, revision files, autogeneration against model metadata.
- aiosqlite 0.22.x: async SQLite driver for SQLAlchemy.

### Expected Features

**Must have:**
- Alembic config and migrations create/upgrade the current schema.
- SQLAlchemy declarative models cover rooms, swipes, matches, and user_tokens.
- FastAPI startup and tests run migrations instead of ad hoc DDL.
- App database operations use async SQLAlchemy APIs.
- Controllers stay thin; database behavior moves into MVC-aligned services/repositories.

**Defer:**
- SQLModel remains out of scope.
- Pydantic v2 request/response models remain separate unless needed for DB migration tests.
- `FLASK_SECRET` naming cleanup remains separate compatibility work.

### Architecture Approach

Use a side-effect-light model module for `Base.metadata`, an async database module for engine/sessionmaker/migration setup, repository/service modules for domain persistence, and a FastAPI dependency that yields request-scoped `AsyncSession` instances. Alembic should import only metadata, not the package root that creates the module-level app.

### Critical Pitfalls

1. **Shared AsyncSession** - avoid with `async_sessionmaker` and scoped sessions.
2. **Alembic import side effects** - avoid by isolating models from app startup.
3. **Lost swipe transaction semantics** - protect with explicit transaction design and race tests.
4. **Autogenerate over-trust** - review generated migration scripts manually.
5. **Tests bypass migrations** - make pytest fixtures use Alembic upgrade.

## Implications for Roadmap

### Phase 36: Alembic Baseline and SQLAlchemy Models

**Rationale:** Schema contract must exist before async repositories can depend on it.
**Delivers:** dependencies, model Base, table models, async Alembic env, baseline migration.
**Avoids:** import side effects and schema drift.

### Phase 37: Async Database Infrastructure

**Rationale:** Routes need a real async session dependency before conversion begins.
**Delivers:** async engine/sessionmaker, migration runner, FastAPI/test DB setup changes.
**Avoids:** shared session and sync DB lifecycle problems.

### Phase 38: Auth Persistence Conversion

**Rationale:** Auth is smaller than room/swipe logic and validates the repository pattern first.
**Delivers:** async token vault CRUD and `require_auth` integration.
**Uses:** AsyncSession dependency and user_tokens model.

### Phase 39: Room, Swipe, Match, and SSE Persistence Conversion

**Rationale:** Highest-risk domain should come after infrastructure and auth prove the pattern.
**Delivers:** async repositories/services for room lifecycle, deck cursor, swipes, matches, history, undo/delete, and SSE polling.
**Avoids:** match race regressions through explicit transaction tests.

### Phase 40: Full Migration Validation and Sync DB Removal

**Rationale:** The milestone is not complete until old `sqlite3` paths and ad hoc migrations are gone.
**Delivers:** full test suite parity, migration tests, no `sqlite3` app call sites, no table-creating `init_db()`.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Official SQLAlchemy and Alembic docs cover the required patterns. |
| Features | HIGH | Local code clearly shows all required persistence surfaces. |
| Architecture | HIGH | Existing FastAPI MVC/router split gives a clear destination. |
| Pitfalls | HIGH | Main risks are documented in official docs and visible in current code. |

**Overall confidence:** HIGH

## Sources

### Primary

- https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html - async engine/session APIs.
- https://docs.sqlalchemy.org/en/20/orm/session_basics.html#is-the-session-thread-safe-is-asyncsession-safe-to-share-in-concurrent-tasks - AsyncSession concurrency rule.
- https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html - declarative typed model patterns.
- https://alembic.sqlalchemy.org/en/latest/autogenerate.html - target metadata and autogenerate behavior.
- https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic - async Alembic env pattern.

### Local

- `jellyswipe/db.py` - current ad hoc schema and migrations.
- `jellyswipe/dependencies.py` - current sync DB dependency.
- `jellyswipe/auth.py` - token vault CRUD.
- `jellyswipe/routers/rooms.py` - room/swipe/match/SSE SQL and transaction logic.
- `tests/conftest.py`, `tests/test_db.py`, route tests - current DB setup and behavior coverage.

---
*Research completed: 2026-05-05*
*Ready for roadmap: yes*
