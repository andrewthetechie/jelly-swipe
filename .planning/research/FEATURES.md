# Feature Research

**Domain:** FastAPI persistence migration: SQLite, Alembic, async SQLAlchemy
**Researched:** 2026-05-05
**Confidence:** HIGH

## Feature Landscape

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Declarative SQLAlchemy schema | Developers need one authoritative schema definition. | MEDIUM | Model all current tables: rooms, swipes, matches, user_tokens. |
| Alembic migration environment | Operators and tests need repeatable schema creation/upgrades. | MEDIUM | Configure async Alembic env and baseline current schema. |
| Async database dependency | FastAPI routes must not rely on synchronous sqlite connections. | MEDIUM | Export `AsyncSession` dependency from `dependencies.py`. |
| Async repositories/services | MVC organization needs database code outside route handlers. | HIGH | Move SQL into domain persistence modules rather than embedding query strings in routers. |
| Behavior parity tests | Migration should not change room, swipe, match, auth, or SSE behavior. | HIGH | Existing route tests are the safety net; add migration-specific tests. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Transactional swipe service | Keeps match race protection explicit while moving to async SQLAlchemy. | HIGH | Preserve SQLite `BEGIN IMMEDIATE` semantics or equivalent locking strategy. |
| SSE-friendly polling repository | Prevents stream code from owning raw DB connection lifecycle. | MEDIUM | Use short-lived async sessions inside the generator loop. |
| Test database migration fixture | Keeps all tests using the real migration path. | MEDIUM | Replace `init_db()` setup with Alembic upgrade for temp DBs. |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Big-bang route rewrite | Seems faster than staged conversion. | Raises risk across auth, rooms, SSE, and tests at once. | Convert by domain with compatibility wrappers only where needed. |
| SQLModel adoption | Reduces duplicate Pydantic/ORM definitions. | Explicitly rejected and adds instability risk. | SQLAlchemy ORM plus optional Pydantic later. |
| Keeping sync DB helpers indefinitely | Lowers migration effort. | Violates milestone requirement that DB interactions are async. | Temporary compatibility only inside a phase, removed before milestone completion. |

## Feature Dependencies

```text
Dependencies
  -> SQLAlchemy models
      -> Alembic env + baseline migration
          -> async engine/session dependency
              -> async auth persistence
              -> async room/match/swipe persistence
                  -> async SSE polling
                      -> full suite parity validation
```

## MVP Definition

### Launch With

- [ ] Alembic config and migrations can create/upgrade the full current SQLite schema.
- [ ] SQLAlchemy declarative models represent all current tables and constraints.
- [ ] FastAPI startup and pytest fixtures initialize DBs through Alembic, not ad hoc DDL.
- [ ] Auth, room, swipe, match, deck, genre, undo, quit, delete, and SSE paths use async DB access.
- [ ] Full existing test suite passes with migration-specific coverage.

### Add After Validation

- [ ] Pydantic v2 request/response schemas - deferred unless route contract typing becomes necessary.
- [ ] Environment variable rename from `FLASK_SECRET` - separate compatibility concern.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Alembic-managed schema | HIGH | MEDIUM | P1 |
| SQLAlchemy models | HIGH | MEDIUM | P1 |
| Async DB dependency | HIGH | MEDIUM | P1 |
| Auth persistence conversion | HIGH | MEDIUM | P1 |
| Room/swipe/match conversion | HIGH | HIGH | P1 |
| SSE polling conversion | HIGH | MEDIUM | P1 |
| Pydantic response models | MEDIUM | MEDIUM | P3 |

## Sources

- Local code: `jellyswipe/db.py`, `jellyswipe/dependencies.py`, `jellyswipe/auth.py`, `jellyswipe/routers/rooms.py`.
- SQLAlchemy asyncio docs: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- Alembic autogenerate docs: https://alembic.sqlalchemy.org/en/latest/autogenerate.html

---
*Feature research for: v2.1 Alembic + Async SQLAlchemy Persistence*
*Researched: 2026-05-05*
