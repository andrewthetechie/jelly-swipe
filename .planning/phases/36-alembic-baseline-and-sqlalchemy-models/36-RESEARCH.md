# Phase 36: Alembic Baseline and SQLAlchemy Models - Research

**Researched:** 2026-05-05
**Domain:** SQLAlchemy declarative models, Alembic baseline migration, SQLite runtime/schema boundary
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01 / D-02:** The baseline is allowed to tighten the schema where current behavior already depends on it. Low-risk tightening includes indexes, foreign keys, and non-null constraints.
- **D-03:** The model layer should include a full ORM relationship graph for later repository work.
- **D-04:** JSON-bearing fields such as `movie_data`, `deck_position`, `deck_order`, and `last_match_data` remain `TEXT`.
- **D-05 / D-06:** The first Alembic revision is a current-state baseline only. No legacy upgrade or stamp path is required.
- **D-07 / D-08:** This is greenfield enough for moderate schema cleanup, including bounded renames where they materially improve the model.
- **D-09 / D-10 / D-11:** Use a dedicated `jellyswipe.models` package and a pure metadata import module. Keep models schema-only.
- **D-12:** No legacy translation layer. Any renamed schema objects become the new database truth.
- **D-13 / D-14 / D-15 / D-16:** Alembic owns schema creation. Runtime PRAGMAs and maintenance stay outside migrations. `init_db()` should stop being the schema bootstrap path in this phase.

### Inferred Boundaries

The codebase still has broad raw-SQL usage in `auth.py`, `dependencies.py`, `routers/rooms.py`, and several tests. Because of that blast radius, "rename obvious mistakes now" should be applied narrowly in Phase 36. The only rename that is clearly beneficial and still bounded is `user_tokens` -> `auth_sessions`. Renaming `rooms.pairing_code` or the room-facing columns now would force wide SQL churn before Phase 39 and is too aggressive for the phase boundary.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MIG-01 | Fresh SQLite DB reaches current schema through Alembic | Baseline revision plus migration test should prove `upgrade head` from empty file |
| MIG-02 | Alembic owns schema currently embedded in `init_db()` | All table DDL and column additions in `db.py` can move into one baseline revision |
| MIG-03 | Alembic autogenerate uses declarative metadata without importing app root | `jellyswipe.models.metadata` can export `target_metadata` without touching `jellyswipe.__init__` |
| SCH-01 | Declarative models represent every persisted table | Four persisted tables exist today: `rooms`, `swipes`, `matches`, and token vault storage |
| SCH-02 | Models preserve behaviorally relevant shape | Current code/query inventory defines which names, defaults, nullability, and uniqueness matter |
| SCH-03 | SQLModel is absent | `pyproject.toml` currently has no SQLAlchemy/Alembic or SQLModel dependency; Phase 36 should add SQLAlchemy/Alembic only |

</phase_requirements>

---

## Summary

Phase 36 is a clean split between schema truth and runtime behavior. Today `jellyswipe/db.py` does three unrelated jobs:

1. creates/patches schema,
2. configures SQLite runtime PRAGMAs, and
3. runs maintenance cleanup.

That mix is the thing Phase 36 needs to remove.

The codebase is still sync-`sqlite3` and raw-SQL driven, so the safest execution shape is:

1. add SQLAlchemy + Alembic,
2. define schema-only declarative models in a dedicated `jellyswipe.models` package,
3. generate a hand-authored baseline migration that represents the new source of truth,
4. move DB creation to an explicit Alembic bootstrap helper,
5. leave runtime PRAGMAs and maintenance in `db.py`,
6. keep the existing sync route/auth code working against the new schema until Phases 37-39 convert persistence access.

The main design pressure is bounded cleanup. Current raw SQL is too widespread to rename the room schema aggressively in Phase 36. The research recommendation is:

- keep `rooms`, `swipes`, and `matches` table/column names stable for now,
- rename `user_tokens` to `auth_sessions`,
- add foreign keys only where current behavior can actually support them,
- let ORM relationships be richer than the DB constraint graph where history behavior prevents a strict FK.

---

## Current Schema Inventory

Source of truth today is `jellyswipe/db.py:init_db()`.

### Current tables

1. `rooms`
   - `pairing_code TEXT PRIMARY KEY`
   - `movie_data TEXT`
   - `ready INTEGER`
   - `current_genre TEXT`
   - `solo_mode INTEGER DEFAULT 0`
   - `last_match_data TEXT`
   - `deck_position TEXT`
   - `deck_order TEXT`

2. `swipes`
   - `room_code TEXT`
   - `movie_id TEXT`
   - `user_id TEXT`
   - `direction TEXT`
   - `session_id TEXT`

3. `matches`
   - `room_code TEXT`
   - `movie_id TEXT`
   - `title TEXT`
   - `thumb TEXT`
   - `status TEXT DEFAULT "active"`
   - `user_id TEXT`
   - `deep_link TEXT`
   - `rating TEXT`
   - `duration TEXT`
   - `year TEXT`
   - `UNIQUE(room_code, movie_id, user_id)`

4. `user_tokens`
   - `session_id TEXT PRIMARY KEY`
   - `jellyfin_token TEXT`
   - `jellyfin_user_id TEXT`
   - `created_at TEXT`

### Embedded migration logic in `init_db()`

`init_db()` currently:

- creates all four tables,
- checks `PRAGMA table_info(...)` for prior missing columns,
- `ALTER TABLE` adds room/match/swipe columns piecemeal,
- deletes orphan swipes,
- calls token cleanup.

Every one of those schema mutations belongs in Alembic instead.

---

## Query and Constraint Inventory

### `rooms`

Observed usage:

- lookup by `pairing_code` in create/join/status/deck/SSE flows,
- update `deck_position`, `movie_data`, `ready`, `current_genre`, `last_match_data`,
- room deletion drives swipe cleanup and match archival.

Recommended shape:

- keep table name `rooms`,
- keep `pairing_code` in Phase 36 to avoid broad raw-SQL churn,
- tighten with:
  - `ready INTEGER NOT NULL DEFAULT 0`
  - `current_genre TEXT NOT NULL DEFAULT 'All'`
  - `solo_mode INTEGER NOT NULL DEFAULT 0`
  - `movie_data TEXT NOT NULL DEFAULT '[]'`
- keep `last_match_data`, `deck_position`, and `deck_order` as nullable `TEXT`.

Reason for `movie_data DEFAULT '[]'`: current tests and helper code create minimal room rows; this preserves that workflow without weakening runtime expectations.

### `swipes`

Observed usage:

- insert in `/room/{code}/swipe`,
- match detection lookup by `(room_code, movie_id, direction, session_id/user_id)`,
- undo deletes by `(room_code, movie_id, session_id)`,
- orphan cleanup currently deletes rows whose room no longer exists.

Recommended shape:

- `room_code TEXT NOT NULL`
- `movie_id TEXT NOT NULL`
- `user_id TEXT NOT NULL`
- `direction TEXT NOT NULL`
- `session_id TEXT NULL`
- add FK `room_code -> rooms.pairing_code ON DELETE CASCADE`
- add FK `session_id -> auth_sessions.session_id ON DELETE SET NULL`
- add index on `(room_code, movie_id, direction)`
- add index on `(room_code, movie_id, session_id)`

Important runtime implication: SQLite only enforces foreign keys when `PRAGMA foreign_keys=ON` is set per connection. Phase 36 runtime helpers must add that PRAGMA alongside WAL and `synchronous=NORMAL`.

### `matches`

Observed usage:

- active matches queried by `(room_code, status, user_id)`,
- history queried by `(status, user_id)` with `room_code='HISTORY'`,
- inserted with `INSERT OR IGNORE` under unique `(room_code, movie_id, user_id)`,
- archived by rewriting `room_code` to sentinel `"HISTORY"`.

Recommended shape:

- keep table name and current columns,
- tighten:
  - `room_code TEXT NOT NULL`
  - `movie_id TEXT NOT NULL`
  - `title TEXT NOT NULL`
  - `thumb TEXT NOT NULL`
  - `status TEXT NOT NULL DEFAULT 'active'`
  - `user_id TEXT NOT NULL`
- keep metadata columns nullable/blank-text compatible,
- preserve `UNIQUE(room_code, movie_id, user_id)`,
- add index on `(status, user_id)`.

Critical constraint finding: **do not add a DB foreign key from `matches.room_code` to `rooms.pairing_code` in Phase 36.** Current behavior archives matches by setting `room_code='HISTORY'`, which would violate that FK. The ORM can still expose a room relationship with an explicit join condition later, but the database constraint must stay absent unless the history model changes.

### `auth_sessions` (rename from `user_tokens`)

Observed usage:

- auth session creation inserts session row,
- `require_auth` and logout look up/delete by `session_id`,
- cleanup deletes rows older than 14 days.

Recommended shape:

- rename table `user_tokens` -> `auth_sessions`,
- keep columns:
  - `session_id TEXT PRIMARY KEY`
  - `jellyfin_token TEXT NOT NULL`
  - `jellyfin_user_id TEXT NOT NULL`
  - `created_at TEXT NOT NULL`
- add index on `created_at`.

This rename is the best bounded cleanup in the current phase: the table stores authenticated browser sessions, not "users" and not generic "tokens".

---

## Recommended Model Package

Use a dedicated package:

```text
jellyswipe/models/
  __init__.py
  base.py
  room.py
  swipe.py
  match.py
  auth_session.py
  metadata.py
```

### Recommended responsibilities

- `base.py`
  - `class Base(DeclarativeBase)`
- `room.py`, `swipe.py`, `match.py`, `auth_session.py`
  - schema-only ORM classes
  - columns, table args, relationships only
- `metadata.py`
  - imports all model modules
  - exports `target_metadata = Base.metadata`
  - contains no runtime setup and no app imports
- `__init__.py`
  - convenience exports for the model classes only

This satisfies D-09 through D-11 and gives Alembic a side-effect-free import path.

---

## Relationship Graph Recommendation

Even where the DB constraint graph is limited, the ORM graph can still be complete.

Recommended relationships:

- `Room.swipes -> list[Swipe]`
- `Room.matches -> list[Match]` with explicit `primaryjoin`
- `Swipe.room -> Room`
- `Swipe.auth_session -> AuthSession | None`
- `AuthSession.swipes -> list[Swipe]`
- `Match.room -> Room | None` with explicit `primaryjoin` and `viewonly=True` or no hard FK backing

The key distinction:

- `swipes.room_code` is safe for a real FK,
- `matches.room_code` is **not** safe for a real FK because of the `"HISTORY"` sentinel,
- but a relationship is still useful for repository code that deals with active matches.

---

## Alembic Architecture

### Required files

- `alembic.ini`
- `alembic/env.py`
- `alembic/script.py.mako` (default template is fine)
- `alembic/versions/<revision>_baseline.py`

### `env.py` recommendation

`env.py` should:

- import `target_metadata` from `jellyswipe.models.metadata`,
- derive DB URL without importing `jellyswipe.__init__`,
- support offline and online migration modes,
- set SQLite batch mode options if needed for future alters,
- avoid any provider/auth/config side effects.

### DB URL helper

Because Phase 37 will later introduce `DATABASE_URL` as the primary runtime input, Phase 36 should not hardcode future async behavior into Alembic. A small helper module such as `jellyswipe/migrations.py` can provide:

- `get_database_url(db_path: str | None = None) -> str`
- `upgrade_to_head(database_url: str) -> None`

For Phase 36 that helper can still derive a SQLite URL from `DB_PATH` or an explicit path, without importing the app root.

---

## Runtime Split Recommendation

`jellyswipe/db.py` should stop owning schema creation. Keep it as the sync runtime utility module for the pre-async phases.

Recommended post-Phase-36 responsibilities for `db.py`:

- `get_db()` / `get_db_closing()` for current sync code paths,
- `configure_sqlite_connection(conn)`:
  - `PRAGMA foreign_keys=ON`
  - `PRAGMA synchronous=NORMAL`
- one-time DB file setup helper for WAL:
  - `PRAGMA journal_mode=WAL`
- `cleanup_orphan_swipes()`
- `cleanup_expired_auth_sessions()` (or keep legacy function name temporarily if the code transition is staged inside the phase)

Recommended removals:

- table creation DDL,
- `PRAGMA table_info` migration logic,
- `ALTER TABLE` patching,
- `init_db()` as the canonical bootstrap path.

### App startup implication

Phase 36 should leave the app expecting a migrated database. That means:

- tests and any explicit bootstrap path should run Alembic first,
- app startup should only do runtime setup/cleanup against an existing schema,
- automatic "create tables on import/startup" behavior should disappear.

That sets up Phase 37 cleanly, where the bootstrap wrapper can run Alembic before Uvicorn.

---

## Affected Tests

High-confidence files that will need direct updates in execution:

- `tests/conftest.py`
  - stop using `init_db()` for schema bootstrap
  - add Alembic/bootstrap helper for temp DBs
- `tests/test_db.py`
  - stop asserting `init_db()` DDL behavior
  - assert migration-created schema and runtime helper behavior instead
- `tests/test_auth.py`
- `tests/test_dependencies.py`
- `tests/test_route_authorization.py`
- `tests/test_error_handling.py`

Those tests reference the token vault table directly or rely on `init_db()`.

---

## Risks and Landmines

1. **`matches.room_code` cannot take a strict FK today**
   - `quit_room()` rewrites active matches to `room_code='HISTORY'`.

2. **SQLite FKs require runtime PRAGMA**
   - adding FKs in Alembic is not enough; each sync connection must enable `foreign_keys=ON`.

3. **Removing `init_db()` breaks test fixtures immediately**
   - `tests/conftest.py`, `tests/test_auth.py`, and `tests/test_dependencies.py` currently call it directly.

4. **Schema rename scope must stay bounded**
   - renaming `pairing_code` now would force wide raw-SQL churn across routes and tests before the async repository phases.

5. **Autogenerate import path must stay clean**
   - importing `jellyswipe.__init__` would trigger env validation and provider wiring; Alembic must avoid that completely.

---

## Recommended Execution Order

1. Add SQLAlchemy/Alembic dependencies and model package.
2. Hand-author the baseline migration and Alembic environment.
3. Replace `init_db()` bootstrap usage with explicit migration + runtime helpers.
4. Update DB/auth/dependency tests and fixtures to use Alembic-created temp DBs.

That order keeps the repo bootable through the transition.

---

## Validation Architecture

Recommended verification split for Phase 36:

- **Quick loop**
  - `uv run pytest tests/test_db.py tests/test_auth.py tests/test_dependencies.py -q --no-cov`
- **Focused migration checks**
  - `uv run pytest tests/test_db.py -q --no-cov`
- **Source scan**
  - `rg -n "SQLModel|sqlmodel" jellyswipe tests pyproject.toml`
- **Full suite before phase close**
  - `uv run pytest`

Manual checks should be minimal. The key phase risk is schema/bootstrap correctness, so most confidence should come from migration-driven temp DB tests rather than app-level manual probing.

---

## Recommendation

Proceed with three serial plans:

1. **Model foundation** — add SQLAlchemy/Alembic deps and the `jellyswipe.models` package.
2. **Baseline migration** — create Alembic env and a hand-authored baseline revision, including the bounded rename to `auth_sessions`.
3. **Runtime/bootstrap split** — remove `init_db()` as schema bootstrap, add explicit runtime helpers, and convert DB-facing tests/fixtures to Alembic bootstrapping.

This is the smallest shape that satisfies the user’s locked decisions without bleeding deep async repository work into Phase 36.
