# Phase 36: Alembic Baseline and SQLAlchemy Models - Pattern Map

**Mapped:** 2026-05-05
**Files analyzed:** 12
**Analogs found:** 12 / 12

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `pyproject.toml` | dependency config | build/runtime | self | exact |
| `jellyswipe/models/base.py` | schema foundation | metadata | `jellyswipe/dependencies.py` module minimalism | role-match |
| `jellyswipe/models/room.py` | schema model | room persistence | `jellyswipe/routers/rooms.py` query inventory | role-match |
| `jellyswipe/models/swipe.py` | schema model | swipe persistence | `jellyswipe/routers/rooms.py` swipe SQL | role-match |
| `jellyswipe/models/match.py` | schema model | match persistence | `jellyswipe/routers/rooms.py` match SQL | role-match |
| `jellyswipe/models/auth_session.py` | schema model | auth persistence | `jellyswipe/auth.py` vault SQL | exact domain |
| `jellyswipe/models/metadata.py` | metadata assembly | alembic import | `jellyswipe/__init__.py` thin assembly pattern | role-match |
| `alembic/env.py` | migration runtime | metadata -> DDL | `jellyswipe/__init__.py` config/bootstrap wiring | role-match |
| `alembic/versions/*_baseline.py` | migration revision | DDL | `jellyswipe/db.py:init_db()` schema inventory | exact source |
| `jellyswipe/migrations.py` | bootstrap helper | schema bootstrap | `jellyswipe/db.py` utility function style | role-match |
| `jellyswipe/db.py` | sync runtime helpers | connection lifecycle | self | exact |
| `tests/conftest.py` / `tests/test_db.py` | test bootstrap and verification | migration bootstrap | current temp-DB fixture pattern | exact |

---

## Package and Module Patterns

### Thin package assembly

**Analog:** `jellyswipe/routers/` inclusion pattern in [`jellyswipe/__init__.py`](/Users/aherrington/.superset/worktrees/jelly-swipe/aherrington/alembic/jellyswipe/__init__.py:162)

Pattern to reuse:

- leaf modules own one concern,
- package root re-exports convenience symbols,
- a dedicated assembly module can exist when import hygiene matters.

Apply that to models:

```python
# jellyswipe/models/metadata.py
from jellyswipe.models.base import Base
from jellyswipe.models.room import Room
from jellyswipe.models.swipe import Swipe
from jellyswipe.models.match import Match
from jellyswipe.models.auth_session import AuthSession

target_metadata = Base.metadata
```

This keeps Alembic away from package-root side effects while still making model registration explicit.

### Schema-only modules

**Analog:** `jellyswipe/dependencies.py` keeps transport/runtime contracts small and explicit.

Pattern to reuse:

- no hidden initialization,
- no query logic embedded in the type definition module,
- exports stay obvious.

Apply that to model files:

- `room.py` contains the `Room` class only,
- `swipe.py` contains `Swipe`,
- `match.py` contains `Match`,
- `auth_session.py` contains `AuthSession`.

---

## Table Modeling Patterns

### Use current raw SQL as the authoritative behavior map

**Primary analog:** [`jellyswipe/db.py`](/Users/aherrington/.superset/worktrees/jelly-swipe/aherrington/alembic/jellyswipe/db.py:33)

The baseline revision should be derived from the actual DDL and patch logic already in `init_db()`:

```python
conn.execute('CREATE TABLE IF NOT EXISTS rooms (pairing_code TEXT PRIMARY KEY, movie_data TEXT, ready INTEGER, current_genre TEXT, solo_mode INTEGER DEFAULT 0)')
conn.execute('CREATE TABLE IF NOT EXISTS swipes (room_code TEXT, movie_id TEXT, user_id TEXT, direction TEXT, session_id TEXT)')
conn.execute('''CREATE TABLE IF NOT EXISTS matches (
    room_code TEXT, movie_id TEXT, title TEXT, thumb TEXT,
    status TEXT DEFAULT "active", user_id TEXT,
    UNIQUE(room_code, movie_id, user_id)
)''')
conn.execute('''CREATE TABLE IF NOT EXISTS user_tokens (
    session_id TEXT PRIMARY KEY,
    jellyfin_token TEXT,
    jellyfin_user_id TEXT,
    created_at TEXT
)''')
```

That code is the source material for the first revision; the migration should not try to infer a different product model.

### Query-driven indexes

**Primary analog:** [`jellyswipe/routers/rooms.py`](/Users/aherrington/.superset/worktrees/jelly-swipe/aherrington/alembic/jellyswipe/routers/rooms.py:220)

Existing SQL reveals which composite lookups matter:

```python
conn.execute(
    'SELECT user_id, session_id FROM swipes WHERE room_code = ? AND movie_id = ? AND direction = "right" AND (session_id IS NULL OR session_id != ?)',
    (code, mid, _session_id)
).fetchone()

conn.execute(
    'SELECT title, thumb, movie_id, deep_link, rating, duration, year FROM matches WHERE room_code = ? AND status = "active" AND user_id = ?',
    (code, user.user_id)
).fetchall()
```

Patterns to preserve:

- composite swipe index around `room_code`, `movie_id`, `direction`,
- match lookup index around `status`, `user_id`,
- keep the current `UNIQUE(room_code, movie_id, user_id)` behavior.

### Explicit exception to FK tightening

**Primary analog:** [`jellyswipe/routers/rooms.py`](/Users/aherrington/.superset/worktrees/jelly-swipe/aherrington/alembic/jellyswipe/routers/rooms.py:311)

Current archival behavior:

```python
conn.execute(
    'UPDATE matches SET status = "archived", room_code = "HISTORY" WHERE room_code = ? AND status = "active"',
    (code,)
)
```

Pattern conclusion:

- `swipes.room_code` can be a real FK,
- `matches.room_code` cannot be a real FK while `"HISTORY"` remains the archive sentinel.

The ORM relationship can still exist, but the DB constraint must not.

---

## Runtime Helper Patterns

### Keep connection helpers small and sync

**Analog:** [`jellyswipe/db.py:get_db()`](/Users/aherrington/.superset/worktrees/jelly-swipe/aherrington/alembic/jellyswipe/db.py:11)

Current style:

```python
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn
```

Phase 36 should preserve that utility style, but move schema bootstrap out of it. Good follow-on shape:

```python
def configure_sqlite_connection(conn: sqlite3.Connection) -> None:
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
```

and a separate one-time helper for `journal_mode=WAL`.

### Separate migration bootstrap from runtime connection use

**Analog:** the existing split between `create_app()` and route modules.

Pattern to reuse:

- `jellyswipe/migrations.py` owns Alembic command invocation,
- `jellyswipe/db.py` owns runtime connection configuration and maintenance,
- `jellyswipe/__init__.py` stops mixing those responsibilities.

---

## Test Bootstrap Patterns

### Temp database fixture shape should stay the same

**Analog:** [`tests/conftest.py`](/Users/aherrington/.superset/worktrees/jelly-swipe/aherrington/alembic/tests/conftest.py:89)

Current pattern:

```python
@pytest.fixture
def db_path(tmp_path):
    db_file = tmp_path / "test.db"
    yield str(db_file)
```

Keep this pattern. Only the bootstrap action changes:

- before: `jellyswipe.db.init_db()`
- after: `upgrade_to_head(sqlite_url_for(db_path))`

### DB tests currently prove schema by direct PRAGMA inspection

**Analog:** [`tests/test_db.py`](/Users/aherrington/.superset/worktrees/jelly-swipe/aherrington/alembic/tests/test_db.py:60)

Pattern to preserve:

- use `PRAGMA table_info(...)`,
- use `PRAGMA index_list(...)`,
- use simple inserts/selects for behavioral verification.

Those tests should be retargeted from "init_db created this" to "Alembic baseline created this".

---

## Planned Write Set

### Plan 01 candidate files

- `pyproject.toml`
- `jellyswipe/models/__init__.py`
- `jellyswipe/models/base.py`
- `jellyswipe/models/room.py`
- `jellyswipe/models/swipe.py`
- `jellyswipe/models/match.py`
- `jellyswipe/models/auth_session.py`
- `jellyswipe/models/metadata.py`

### Plan 02 candidate files

- `alembic.ini`
- `alembic/env.py`
- `alembic/script.py.mako`
- `alembic/versions/*_baseline.py`
- `jellyswipe/migrations.py`

### Plan 03 candidate files

- `jellyswipe/db.py`
- `jellyswipe/__init__.py`
- `jellyswipe/auth.py`
- `tests/conftest.py`
- `tests/test_db.py`
- `tests/test_auth.py`
- `tests/test_dependencies.py`
- `tests/test_route_authorization.py`
- `tests/test_error_handling.py`

---

## Pattern Conclusions

1. The current repo already favors thin modules and explicit assembly points; the models package should follow that pattern.
2. `init_db()` is the exact schema inventory for the baseline migration; do not re-invent the table set.
3. Runtime helpers should stay sync and utilitarian in Phase 36.
4. Test fixtures already have the right temp-file shape; only the bootstrap mechanism needs to change.
5. The only safe DB-level foreign keys today are on `swipes`, not on `matches`.
