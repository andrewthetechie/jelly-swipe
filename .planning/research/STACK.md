# Stack Research

**Domain:** FastAPI persistence migration: SQLite, Alembic, async SQLAlchemy
**Researched:** 2026-05-05
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| SQLAlchemy | 2.0.x, current docs show 2.0.49 | Declarative ORM models, async engine, `AsyncSession`, typed mappings | Mature ORM with first-party asyncio support and Alembic integration. |
| Alembic | 1.18.x docs | Versioned schema migrations and autogenerate from SQLAlchemy metadata | First-party SQLAlchemy migration tool; supports async migration environments. |
| aiosqlite | 0.22.x | Async DBAPI driver for SQLite URLs such as `sqlite+aiosqlite:///...` | Required for SQLAlchemy asyncio with SQLite. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-asyncio or AnyIO pytest support | Current compatible release | Async DB tests | Needed when tests directly await async repository/session functions. |
| Pydantic v2 | Already deferred separately | Request/response validation | Do not couple to this milestone unless required for route contracts. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `alembic revision --autogenerate` | Generate migration candidates from ORM metadata | Always review generated scripts by hand before use. |
| `alembic upgrade head` | Apply migrations at startup/test setup | Replace `init_db()` schema DDL with a controlled migration runner. |
| `sqlalchemy.ext.asyncio.async_sessionmaker` | Produce request/unit-of-work sessions | One `AsyncSession` per request or operation; do not share across concurrent tasks. |

## Installation

```bash
uv add "sqlalchemy[asyncio]>=2.0,<3" "alembic>=1.18,<2" "aiosqlite>=0.22,<1"
uv add --dev pytest-asyncio
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| SQLAlchemy ORM | SQLAlchemy Core only | Use Core for narrow hot paths if ORM mapping adds no value. |
| Alembic | Handwritten `init_db()` DDL checks | Only acceptable for throwaway prototypes; this project has outgrown it. |
| aiosqlite | Raw sqlite3 with thread offload | Avoid unless a SQLAlchemy async driver cannot support a specific operation. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| SQLModel | User explicitly excluded it; it adds another abstraction over SQLAlchemy/Pydantic. | SQLAlchemy declarative models directly. |
| Shared global `AsyncSession` | SQLAlchemy documents `AsyncSession` as mutable/stateful and unsafe across concurrent tasks. | Request-scoped/sessionmaker-created sessions. |
| Autogenerate without review | Alembic generates candidate migrations, not guaranteed perfect migration intent. | Review and adjust every migration script. |
| `Base.metadata.create_all()` as production migration | It bypasses migration history and downgrade/upgrade intent. | Alembic revision scripts. |

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| SQLAlchemy 2.0.x | Python 3.13, Alembic 1.18.x | Use SQLAlchemy 2.0 style `Mapped` and `mapped_column`. |
| SQLAlchemy async SQLite | aiosqlite | DB URL must use the async dialect, not plain `sqlite:///`. |
| Alembic async env | SQLAlchemy async engine | Alembic runs migrations via `async_engine_from_config` and `connection.run_sync`. |

## Sources

- https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html - AsyncSession, async_sessionmaker, async engine patterns.
- https://docs.sqlalchemy.org/en/20/orm/session_basics.html#is-the-session-thread-safe-is-asyncsession-safe-to-share-in-concurrent-tasks - session concurrency rule.
- https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html - typed declarative mapping with `DeclarativeBase`, `Mapped`, and `mapped_column`.
- https://alembic.sqlalchemy.org/en/latest/autogenerate.html - autogenerate and `target_metadata`.
- https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic - async Alembic environment.

---
*Stack research for: v2.1 Alembic + Async SQLAlchemy Persistence*
*Researched: 2026-05-05*
