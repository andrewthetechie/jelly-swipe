# Phase 37: Async Database Infrastructure - Pattern Map

**Mapped:** 2026-05-05
**Files analyzed:** 19
**Analogs found:** 19 / 19

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `jellyswipe/bootstrap.py` | service | batch | `jellyswipe/migrations.py` | partial |
| `jellyswipe/db_runtime.py` | service | CRUD | `jellyswipe/db.py` | role-match |
| `jellyswipe/db_uow.py` | service | CRUD | `jellyswipe/dependencies.py` | role-match |
| `jellyswipe/migrations.py` | utility | batch | `jellyswipe/migrations.py` | exact |
| `jellyswipe/dependencies.py` | provider | request-response | `jellyswipe/dependencies.py` | exact |
| `jellyswipe/routers/rooms.py` | router | request-response | `jellyswipe/routers/rooms.py` | exact |
| `jellyswipe/__init__.py` | provider | request-response | `jellyswipe/__init__.py` | exact |
| `jellyswipe/db.py` | utility | CRUD | `jellyswipe/db.py` | exact |
| `tests/conftest.py` | test | file-I/O | `tests/conftest.py` | exact |
| `tests/test_bootstrap.py` | test | batch | `tests/test_infrastructure.py` | role-match |
| `tests/test_db_runtime.py` | test | CRUD | `tests/test_db.py` | role-match |
| `tests/test_dependencies.py` | test | request-response | `tests/test_dependencies.py` | exact |
| `tests/test_auth.py` | test | request-response | `tests/test_auth.py` | exact |
| `tests/test_db.py` | test | CRUD | `tests/test_db.py` | exact |
| `tests/test_infrastructure.py` | test | batch | `tests/test_infrastructure.py` | exact |
| `Dockerfile` | config | batch | `Dockerfile` | exact |
| `README.md` | docs | batch | `README.md` | exact |
| `pyproject.toml` | config | batch | `pyproject.toml` | exact |
| `uv.lock` | config | batch | `uv.lock` | exact-generated |

## Pattern Assignments

### `jellyswipe/bootstrap.py` (service, batch)

**Analog:** `jellyswipe/migrations.py` with startup contract from `jellyswipe/__init__.py`

**Imports + bootstrap helper pattern** from `jellyswipe/migrations.py` lines 5-11:
```python
import os
from pathlib import Path

from alembic import command
from alembic.config import Config

import jellyswipe.db
```

**Programmatic migration pattern** from `jellyswipe/migrations.py` lines 36-43:
```python
def _alembic_config(database_url: str) -> Config:
    config = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def upgrade_to_head(database_url: str | None = None) -> None:
    command.upgrade(_alembic_config(database_url or get_database_url()), "head")
```

**ASGI handoff contract** from `jellyswipe/__init__.py` lines 182-193:
```python
def __getattr__(name: str):
    if name == "app":
        app = create_app()
        globals()["app"] = app
        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

**Container entrypoint contract** from `Dockerfile` line 37:
```dockerfile
CMD ["/app/.venv/bin/uvicorn", "jellyswipe:app", "--host", "0.0.0.0", "--port", "5005"]
```

**Use for Phase 37:** create the first explicit Python bootstrap runner here; there is no existing CLI module, so copy the Alembic call style from `migrations.py` and keep the app import lazy.

---

### `jellyswipe/db_runtime.py` (service, CRUD)

**Analog:** `jellyswipe/db.py`

**Imports + future-annotations pattern** from `jellyswipe/db.py` lines 3-8:
```python
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
```

**Connection setup pattern** from `jellyswipe/db.py` lines 13-18:
```python
def configure_sqlite_connection(conn: sqlite3.Connection) -> sqlite3.Connection:
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn
```

**Runtime prep sequencing** from `jellyswipe/db.py` lines 21-31 and 71-75:
```python
def ensure_sqlite_wal_mode(db_path: str | None = None) -> None:
    path = db_path or DB_PATH
    if not path:
        raise RuntimeError("DB_PATH is not configured")

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")


def prepare_runtime_database() -> None:
    ensure_sqlite_wal_mode()
    cleanup_orphan_swipes()
    cleanup_expired_auth_sessions()
```

**Use for Phase 37:** keep the module small and infrastructure-only. Port the helper shape and sequencing from `db.py`, but replace `sqlite3.Connection` with async engine/sessionmaker primitives.

---

### `jellyswipe/db_uow.py` (service, CRUD)

**Analog:** `jellyswipe/dependencies.py` with DB method shape from `jellyswipe/auth.py`

**Typed façade pattern** from `jellyswipe/dependencies.py` lines 25-53:
```python
@dataclass
class AuthUser:
    jf_token: str
    user_id: str


def get_db_dep():
    with get_db_closing() as conn:
        yield conn


DBConn = Annotated[sqlite3.Connection, Depends(get_db_dep)]
```

**Small focused DB method pattern** from `jellyswipe/auth.py` lines 15-43:
```python
def create_session(jf_token: str, jf_user_id: str, session_dict: dict) -> str:
    session_id = secrets.token_hex(32)
    created_at = datetime.now(timezone.utc).isoformat()

    cleanup_expired_auth_sessions()

    with get_db_closing() as conn:
        conn.execute(
            'INSERT INTO auth_sessions (session_id, jellyfin_token, jellyfin_user_id, created_at) '
            'VALUES (?, ?, ?, ?)',
            (session_id, jf_token, jf_user_id, created_at)
        )
```

**Use for Phase 37:** expose a narrow typed surface instead of a raw session. Keep methods small and explicit, mirroring current helper functions rather than introducing a large ORM-heavy abstraction.

---

### `jellyswipe/migrations.py` (utility, batch)

**Analog:** `jellyswipe/migrations.py`

**URL resolution precedence** from lines 14-33:
```python
def build_sqlite_url(db_path: str) -> str:
    path = Path(db_path).expanduser().resolve()
    return f"sqlite:///{path}"


def get_database_url(db_path: str | None = None) -> str:
    if db_path:
        return build_sqlite_url(db_path)

    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]

    if os.getenv("DB_PATH"):
        return build_sqlite_url(os.environ["DB_PATH"])
```

**Alembic config wrapper** from lines 36-43:
```python
def _alembic_config(database_url: str) -> Config:
    config = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def upgrade_to_head(database_url: str | None = None) -> None:
    command.upgrade(_alembic_config(database_url or get_database_url()), "head")
```

**Use for Phase 37:** preserve `DATABASE_URL`-first precedence and the programmatic Alembic wrapper; extend it for async runtime URL derivation rather than moving that logic into `__init__.py`.

---

### `jellyswipe/dependencies.py` (provider, request-response)

**Analog:** `jellyswipe/dependencies.py`

**Auth guard pattern** from lines 32-41:
```python
def require_auth(request: Request) -> AuthUser:
    result = auth.get_current_token(request.session)
    if result is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    jf_token, user_id = result
    return AuthUser(jf_token=jf_token, user_id=user_id)
```

**Dependency alias pattern** from lines 44-53:
```python
def get_db_dep():
    with get_db_closing() as conn:
        yield conn


DBConn = Annotated[sqlite3.Connection, Depends(get_db_dep)]
```

**Lazy singleton/provider pattern** from lines 106-145:
```python
def get_provider():
    try:
        import jellyswipe as _app
        import jellyswipe.config as _config
    except RuntimeError as exc:
        raise RuntimeError(
            "Cannot initialise JellyfinLibraryProvider: jellyswipe package "
            "failed to load. Ensure JELLYFIN_URL, JELLYFIN_API_KEY, and "
            "TMDB_ACCESS_TOKEN environment variables are set."
        ) from exc
```

**Use for Phase 37:** replace only the DB dependency surface. Keep `AuthUser`, `require_auth`, rate-limit helpers, export ordering, and lazy provider behavior stable.

---

### `jellyswipe/__init__.py` (provider, request-response)

**Analog:** `jellyswipe/__init__.py`

**Lifespan pattern** from lines 95-111:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    import jellyswipe.db
    if jellyswipe.db.DB_PATH is None:
        jellyswipe.db.DB_PATH = DB_PATH
    from .db import prepare_runtime_database
    prepare_runtime_database()
    _logger.info("jellyswipe_startup")
    yield
    global _provider_singleton
    _provider_singleton = None
```

**App factory + test override pattern** from lines 125-177:
```python
app = FastAPI(
    lifespan=lifespan,
    default_response_class=XSSSafeJSONResponse,
)

if test_config:
    if 'DB_PATH' in test_config:
        import jellyswipe.db
        jellyswipe.db.DB_PATH = test_config['DB_PATH']

app.mount('/static', StaticFiles(directory=os.path.join(_APP_ROOT, 'static')), name='static')
```

**Lazy app export pattern** from lines 182-193:
```python
def __getattr__(name: str):
    if name == "app":
        app = create_app()
        globals()["app"] = app
        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

**Use for Phase 37:** keep `create_app()` thin, preserve `test_config` overrides and shutdown cleanup, but remove migration/bootstrap responsibility from lifespan.

---

### `jellyswipe/db.py` (utility, CRUD)

**Analog:** `jellyswipe/db.py`

**Legacy helper shape** from lines 10-50:
```python
DB_PATH = None


def get_db():
    if not DB_PATH:
        raise RuntimeError("DB_PATH is not configured")

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return configure_sqlite_connection(conn)


@contextmanager
def get_db_closing():
    conn = get_db()
    try:
        with conn:
            yield conn
    finally:
        conn.close()
```

**Maintenance SQL pattern** from lines 53-75:
```python
def cleanup_orphan_swipes() -> None:
    with get_db_closing() as conn:
        conn.execute(
            "DELETE FROM swipes WHERE room_code NOT IN (SELECT pairing_code FROM rooms)"
        )


def cleanup_expired_auth_sessions() -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    with get_db_closing() as conn:
        conn.execute(
            "DELETE FROM auth_sessions WHERE created_at < ?",
            (cutoff,),
        )
```

**Use for Phase 37:** preserve this file as the legacy sync seam for still-unconverted routes. If you wrap new async primitives here, keep the public helper names stable until later phases remove sync callers.

---

### `tests/conftest.py` (test, file-I/O)

**Analog:** `tests/conftest.py`

**Environment bootstrap pattern** from lines 13-19 and 37-54:
```python
os.environ.setdefault("JELLYFIN_URL", "http://test.jellyfin.local")
os.environ.setdefault("JELLYFIN_API_KEY", "test-api-key")
os.environ.setdefault("TMDB_ACCESS_TOKEN", "test-tmdb-token")
os.environ.setdefault("FLASK_SECRET", "test-secret-key")
os.environ.setdefault("ALLOW_PRIVATE_JELLYFIN", "1")


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    mock_load_dotenv = patch('dotenv.load_dotenv', side_effect=lambda *args, **kwargs: None)
    mock_load_dotenv.start()
    yield
    mock_load_dotenv.stop()
```

**Temp DB provisioning pattern** from lines 116-146:
```python
@pytest.fixture
def db_connection(db_path, monkeypatch):
    import jellyswipe.db

    monkeypatch.setattr(jellyswipe.db, 'DB_PATH', db_path)
    upgrade_to_head(build_sqlite_url(db_path))

    conn = jellyswipe.db.get_db()
    try:
        yield conn
    finally:
        conn.close()
```

**App fixture override pattern** from lines 208-255 and 272-322:
```python
test_config = {
    "DB_PATH": db_file,
    "TESTING": True,
    "SECRET_KEY": os.environ["FLASK_SECRET"],
}
fast_app = create_app(test_config=test_config)

fast_app.dependency_overrides[require_auth] = lambda: AuthUser(
    jf_token="valid-token", user_id="verified-user"
)
fast_app.dependency_overrides[get_provider] = lambda: fake_provider

yield fast_app

fast_app.dependency_overrides.clear()
```

**Use for Phase 37:** centralize the Alembic-backed temp DB setup here first, then let route and dependency tests reuse it. Keep cleanup and `dependency_overrides.clear()` semantics unchanged.

---

### `tests/test_dependencies.py` (test, request-response)

**Analog:** `tests/test_dependencies.py`

**Request/session guard tests** from lines 31-81:
```python
request = MagicMock(spec=Request)
request.session = {'session_id': sid}

auth_user = require_auth(request)

assert isinstance(auth_user, AuthUser)
assert auth_user.jf_token == 'test-token'
assert auth_user.user_id == 'test-user'
```

**Yield dependency cleanup test** from lines 91-114:
```python
gen = get_db_dep()
conn = next(gen)
assert isinstance(conn, sqlite3.Connection)

row = conn.execute("SELECT 1").fetchone()
assert row[0] == 1

with pytest.raises(sqlite3.ProgrammingError):
    conn.execute("SELECT 1")
```

**Mini-app dependency behavior tests** from lines 141-158 and 199-212:
```python
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="test-secret-key")

@app.get("/get-trailer/test")
def rate_limited_route(_: None = Depends(check_rate_limit)):
    return {"ok": True}

client = TestClient(app)
```

**Use for Phase 37:** rewrite the DB dependency assertions around the new async UoW/dependency surface, but keep the direct unit-style request/session tests and the tiny FastAPI harness style.

---

### `tests/test_auth.py` (test, request-response)

**Analog:** `tests/test_auth.py`

**Minimal FastAPI auth harness** from lines 33-67:
```python
@pytest.fixture
def auth_app(db_path, monkeypatch):
    monkeypatch.setattr(jellyswipe.db, "DB_PATH", db_path)
    upgrade_to_head(build_sqlite_url(db_path))

    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret-key")

    @app.post("/test-create-session")
    async def create_session_route(request: Request):
        body = await request.json()
        sid = jellyswipe.auth.create_session(
            body["jf_token"], body["jf_user_id"], request.session
        )
        return {"session_id": sid}
```

**Seed helper pattern** from lines 76-91:
```python
def seed_vault(db_path, monkeypatch):
    monkeypatch.setattr(jellyswipe.db, "DB_PATH", db_path)

    def _seed(session_id="test-session-id", jf_token="test-jf-token", jf_user_id="test-jf-user-id"):
        from datetime import datetime, timezone
        created_at = datetime.now(timezone.utc).isoformat()
        with jellyswipe.db.get_db_closing() as conn:
            conn.execute(
                "INSERT INTO auth_sessions (session_id, jellyfin_token, jellyfin_user_id, created_at) "
                "VALUES (?, ?, ?, ?)",
                (session_id, jf_token, jf_user_id, created_at),
            )
```

**CRUD assertion style** from lines 101-123 and 159-170:
```python
with jellyswipe.db.get_db_closing() as conn:
    row = conn.execute(
        'SELECT * FROM auth_sessions WHERE session_id = ?', (sid,)
    ).fetchone()

assert row is not None
assert row['jellyfin_token'] == 'my-jf-token'
assert row['jellyfin_user_id'] == 'my-jf-user-id'

with patch('jellyswipe.auth.cleanup_expired_auth_sessions') as mock_cleanup:
    resp = client.post('/test-create-session', json={...})
    mock_cleanup.assert_called_once()
```

**Use for Phase 37:** keep auth tests focused on observable behavior, but route DB bootstrap through the shared Alembic/runtime fixtures instead of repeating raw `DB_PATH` patching everywhere.

---

### `tests/test_db.py` (test, CRUD)

**Analog:** `tests/test_db.py`

**Migration helper pattern** from lines 11-15:
```python
def _migrate(db_path: str) -> sqlite3.Connection:
    upgrade_to_head(build_sqlite_url(db_path))
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
```

**Idempotent migration assertion** from lines 125-135:
```python
upgrade_to_head(build_sqlite_url(db_path))
upgrade_to_head(build_sqlite_url(db_path))

conn = sqlite3.connect(db_path)
try:
    tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert "rooms" in tables
    assert "auth_sessions" in tables
finally:
    conn.close()
```

**Runtime export smoke test** from lines 138-143:
```python
assert hasattr(jellyswipe.db, "get_db")
assert hasattr(jellyswipe.db, "get_db_closing")
assert hasattr(jellyswipe.db, "prepare_runtime_database")
assert hasattr(jellyswipe.db, "cleanup_expired_auth_sessions")
```

**Use for Phase 37:** if `db.py` becomes a compatibility shim, keep these smoke assertions aligned with the public surface that still exists after the async split.

---

### `tests/test_infrastructure.py` (test, batch)

**Analog:** `tests/test_infrastructure.py`

**Raw-file dependency assertion pattern** from lines 57-90:
```python
content = pyproject_path.read_text()

required = ["fastapi", "uvicorn", "itsdangerous", "jinja2", "python-multipart"]
for pkg in required:
    assert pkg in content
```

**Raw-file Docker CMD assertion pattern** from lines 93-128:
```python
cmd_lines = [line for line in content.splitlines() if line.strip().startswith("CMD")]
assert len(cmd_lines) == 1
cmd_line = cmd_lines[0]

assert "uvicorn" in cmd_line
assert "5005" in cmd_line
assert "gunicorn" not in cmd_line.lower()
assert "gevent" not in cmd_line.lower()
```

**Use for Phase 37:** extend this file rather than creating a new smoke test. Update the expectations to cover `aiosqlite` and the bootstrap entrypoint.

---

### `Dockerfile` (config, batch)

**Analog:** `Dockerfile`

**Multi-stage layout pattern** from lines 1-19 and 21-37:
```dockerfile
FROM python:3.13-slim as builder
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project
COPY . .
RUN uv sync --frozen

FROM python:3.13-slim
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/jellyswipe /app/jellyswipe
RUN mkdir -p /app/data
EXPOSE 5005
CMD ["/app/.venv/bin/uvicorn", "jellyswipe:app", "--host", "0.0.0.0", "--port", "5005"]
```

**Use for Phase 37:** keep the two-stage build and only swap the final command to invoke the bootstrap wrapper instead of direct Uvicorn.

---

### `pyproject.toml` (config, batch)

**Analog:** `pyproject.toml`

**Dependency list pattern** from lines 5-20:
```toml
[project]
name = "jellyswipe"
version = "0.1.0"
requires-python = ">=3.13,<3.14"
dependencies = [
    "alembic>=1.18.4",
    "fastapi>=0.136.1",
    "itsdangerous>=2.2.0",
    "jinja2>=3.1.6",
    "python-dotenv>=1.2.2",
    "python-multipart>=0.0.18",
    "requests>=2.33.1",
    "sqlalchemy>=2.0.49",
    "sse-starlette>=3.4.1",
    "uvicorn[standard]>=0.46.0",
]
```

**Use for Phase 37:** add `aiosqlite` in this main dependency block next to `sqlalchemy`; do not move runtime deps into `dev`.

---

### `uv.lock` (config, batch)

**Analog:** generated from `pyproject.toml`

**Generation contract** from `README.md` lines 184-194:
```bash
uv add <package-name>
uv lock --upgrade
```

**Use for Phase 37:** treat `uv.lock` as generated output. Do not hand-edit patterns out of it; update `pyproject.toml`, then regenerate the lockfile.

---

## Shared Patterns

### `DATABASE_URL` Resolution and Alembic Execution
**Source:** `jellyswipe/migrations.py` lines 19-43  
**Apply to:** `jellyswipe/bootstrap.py`, `jellyswipe/db_runtime.py`, tests that provision temp DBs
```python
def get_database_url(db_path: str | None = None) -> str:
    if db_path:
        return build_sqlite_url(db_path)

    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]

    if os.getenv("DB_PATH"):
        return build_sqlite_url(os.environ["DB_PATH"])

def upgrade_to_head(database_url: str | None = None) -> None:
    command.upgrade(_alembic_config(database_url or get_database_url()), "head")
```

### Thin App Factory, Real Startup Work in Lifespan
**Source:** `jellyswipe/__init__.py` lines 95-111 and 125-177  
**Apply to:** `jellyswipe/__init__.py`, `jellyswipe/bootstrap.py`
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    _logger.info("jellyswipe_startup")
    yield
    global _provider_singleton
    _provider_singleton = None

app = FastAPI(
    lifespan=lifespan,
    default_response_class=XSSSafeJSONResponse,
)
```

### Typed Dependency Boundary
**Source:** `jellyswipe/dependencies.py` lines 25-53  
**Apply to:** `jellyswipe/db_uow.py`, `jellyswipe/dependencies.py`
```python
@dataclass
class AuthUser:
    jf_token: str
    user_id: str


DBConn = Annotated[sqlite3.Connection, Depends(get_db_dep)]
```

### Runtime Maintenance SQL Stays Small and Explicit
**Source:** `jellyswipe/db.py` lines 53-75  
**Apply to:** `jellyswipe/db_runtime.py`, compatibility helpers in `jellyswipe/db.py`
```python
def cleanup_orphan_swipes() -> None:
    with get_db_closing() as conn:
        conn.execute(
            "DELETE FROM swipes WHERE room_code NOT IN (SELECT pairing_code FROM rooms)"
        )


def cleanup_expired_auth_sessions() -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
```

### Alembic-Backed Test DB Fixtures
**Source:** `tests/conftest.py` lines 116-146 and 208-322  
**Apply to:** `tests/conftest.py`, `tests/test_dependencies.py`, `tests/test_auth.py`, `tests/test_db.py`
```python
monkeypatch.setattr(jellyswipe.db, 'DB_PATH', db_path)
upgrade_to_head(build_sqlite_url(db_path))

fast_app.dependency_overrides[get_provider] = lambda: fake_provider
yield fast_app
fast_app.dependency_overrides.clear()
```

### Request-Scoped DB Dependencies Must Not Be Reused for SSE
**Source:** `jellyswipe/routers/rooms.py` lines 413-418  
**Apply to:** `jellyswipe/dependencies.py`, planner notes for Phase 37 scope control
```python
# Per D-10, SQL-1: Direct connection scoped to stream lifetime.
# get_db_dep() is request-scoped and cannot serve a stream lasting up to 3600s.
import jellyswipe.db
conn = sqlite3.connect(jellyswipe.db.DB_PATH, check_same_thread=False)
```

### Existing Room Route Mutation Pattern
**Source:** `jellyswipe/routers/rooms.py` route handlers and swipe logic  
**Apply to:** `jellyswipe/routers/rooms.py`
- keep the route in place and change only the injected DB seam
- preserve the current `BEGIN IMMEDIATE` locking behavior as an implementation invariant
- prefer helper extraction inside the router module over introducing a second route layer

### Runtime Helper Tests Follow Direct Database Assertions
**Source:** `tests/test_db.py`  
**Apply to:** `tests/test_db_runtime.py`
- use temp database paths and direct helper calls
- assert concrete lifecycle behavior rather than route-level side effects
- keep the tests deterministic and small like the existing DB schema tests

### Bootstrap Orchestration Tests Follow Infrastructure Smoke Style
**Source:** `tests/test_infrastructure.py`  
**Apply to:** `tests/test_bootstrap.py`
- verify orchestration order through focused monkeypatch/stub assertions
- avoid starting a real server when a call-order test is sufficient
- keep command/entrypoint assertions lightweight and text-driven where possible

### Startup Docs Follow Existing Copy-Paste Command Style
**Source:** `README.md` local run section  
**Apply to:** `README.md`
- keep commands short and directly runnable
- update only the startup command path that changes under the new bootstrap contract
- preserve the existing uv and Docker guidance around it

## No Analog Found

None. The repo has usable partial analogs for every Phase 37 target, but `jellyswipe/bootstrap.py` will still be the first explicit Python startup wrapper and should be treated as a new composition of existing migration and app-factory patterns.

## Metadata

**Analog search scope:** `jellyswipe/`, `tests/`, `Dockerfile`, `pyproject.toml`, `uv.lock`, `README.md`, `docker-compose.yml`  
**Files scanned:** 16  
**Pattern extraction date:** 2026-05-05
