# Pitfalls Research

**Domain:** FastAPI persistence migration: SQLite, Alembic, async SQLAlchemy
**Researched:** 2026-05-05
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: AsyncSession Shared Across Tasks

**What goes wrong:** Concurrent requests or stream tasks mutate the same session/transaction state.

**Why it happens:** Developers treat `AsyncSession` like a stateless connection pool handle.

**How to avoid:** Use `async_sessionmaker`; create one session per request or unit of work.

**Warning signs:** Global `AsyncSession`, cached session on app state, or session passed into parallel tasks.

**Phase to address:** Async session infrastructure phase.

---

### Pitfall 2: Alembic Imports Trigger App Startup

**What goes wrong:** `alembic revision` or `alembic upgrade` fails because importing metadata also creates the FastAPI app, validates Jellyfin env vars, or runs startup side effects.

**Why it happens:** Current `jellyswipe/__init__.py` creates a module-level app on import.

**How to avoid:** Place SQLAlchemy models/Base in a side-effect-light module and import that from Alembic.

**Warning signs:** `env.py` imports `jellyswipe` package root or route modules.

**Phase to address:** Schema/model phase.

---

### Pitfall 3: Lost Swipe Transaction Semantics

**What goes wrong:** Concurrent right swipes stop producing exactly-once match behavior.

**Why it happens:** The current code relies on explicit SQLite `BEGIN IMMEDIATE`; a naive ORM rewrite may use weaker/default transaction behavior.

**How to avoid:** Design a swipe service transaction explicitly and add concurrent/race tests around match creation.

**Warning signs:** Transaction code disappears into independent repository calls; tests only cover single-client swipes.

**Phase to address:** Room/swipe persistence phase.

---

### Pitfall 4: Autogenerate Treated As Authoritative

**What goes wrong:** Migration scripts miss data cleanup, rename intent, indexes, defaults, or SQLite-specific constraints.

**Why it happens:** Alembic autogenerate compares metadata to database state and emits candidates, not business-safe scripts.

**How to avoid:** Review every generated revision, write tests for current DB upgrade, and document baseline decisions.

**Warning signs:** Migration generated and committed without manual edits or a test upgrade from an old schema.

**Phase to address:** Alembic baseline phase.

---

### Pitfall 5: Tests Bypass Migrations

**What goes wrong:** Runtime uses Alembic while tests still call `create_all()` or old `init_db()`, so migration breakage is invisible.

**Why it happens:** Test setup optimizes for speed and forgets production parity.

**How to avoid:** Test fixtures should create temp DBs by running Alembic upgrade head.

**Warning signs:** Tests pass after deleting migration files, or `init_db()` still creates tables.

**Phase to address:** Test migration phase.

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Compatibility wrapper around sync DB | Smaller phase diff | Hides remaining sync call sites | Only within a transitional phase, removed before close. |
| ORM models without repositories | Fewer files | SQL remains scattered through controllers | Never for rooms/swipes, maybe temporary for one simple auth call. |
| Alembic baseline without upgrade tests | Faster setup | Operators discover migration failures late | Never for milestone completion. |

## "Looks Done But Isn't" Checklist

- [ ] Alembic exists, but `init_db()` still creates tables.
- [ ] Models exist, but `env.py` does not use `Base.metadata` as `target_metadata`.
- [ ] Routes are `async def`, but DB work is still synchronous `sqlite3`.
- [ ] SSE route sleeps asynchronously, but polls with raw sqlite.
- [ ] Tests pass only because fixtures bypass migration scripts.
- [ ] SQLModel or Pydantic schema work sneaks into the milestone.

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Alembic import side effects | Phase 36 | `alembic upgrade head` runs without app startup side effects. |
| Autogenerate misuse | Phase 36 | Baseline migration reviewed and tested from empty DB. |
| Shared AsyncSession | Phase 37 | No global session; dependency yields scoped sessions. |
| Lost swipe transaction semantics | Phase 39 | Concurrent swipe/match tests pass. |
| Tests bypass migrations | Phase 40 | Test fixtures use Alembic upgrade path. |

## Sources

- SQLAlchemy session concurrency docs: https://docs.sqlalchemy.org/en/20/orm/session_basics.html#is-the-session-thread-safe-is-asyncsession-safe-to-share-in-concurrent-tasks
- Alembic autogenerate docs: https://alembic.sqlalchemy.org/en/latest/autogenerate.html
- Alembic async cookbook: https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic
- Local current implementation: `jellyswipe/db.py`, `jellyswipe/routers/rooms.py`, `tests/conftest.py`.

---
*Pitfalls research for: v2.1 Alembic + Async SQLAlchemy Persistence*
*Researched: 2026-05-05*
