# Phase 38: Auth Persistence Conversion - Pattern Map

**Mapped:** 2026-05-05
**Files analyzed:** 8
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `jellyswipe/auth_types.py` | type | shared-contract | `jellyswipe/dependencies.py` (`AuthUser` dataclass) | role-match |
| `jellyswipe/auth.py` | service | CRUD | `jellyswipe/auth.py` | exact |
| `jellyswipe/db_uow.py` | store | CRUD | `jellyswipe/db_uow.py` | exact |
| `jellyswipe/dependencies.py` | provider | request-response | `jellyswipe/dependencies.py` | exact |
| `jellyswipe/routers/auth.py` | route | request-response | `jellyswipe/routers/auth.py` | exact |
| `tests/test_auth.py` | test | CRUD | `tests/test_auth.py` | exact |
| `tests/test_dependencies.py` | test | request-response | `tests/test_dependencies.py` | exact |
| `tests/test_route_authorization.py` | test | request-response | `tests/test_route_authorization.py` | exact |

## Pattern Assignments

### `jellyswipe/auth_types.py` (type, shared-contract)

**Analog:** the lightweight dataclass contract in `jellyswipe/dependencies.py`

**Typed dataclass pattern** from `jellyswipe/dependencies.py` lines 25-29:
```python
@dataclass
class AuthUser:
    jf_token: str
    user_id: str
```

**Use for Phase 38:** keep `AuthRecord` as a minimal shared data contract with only persistence-facing scalar fields (`session_id`, `jf_token`, `user_id`, `created_at`). This file should stay dependency-light, define no service logic, and give both `jellyswipe/auth.py` and `jellyswipe/db_uow.py` a neutral import target.

---

### `jellyswipe/auth.py` (service, CRUD)

**Analog:** `jellyswipe/auth.py` with typed-record shape from `jellyswipe/dependencies.py`

**Imports pattern** from `jellyswipe/auth.py` lines 8-12:
```python
from typing import Optional, Tuple
import secrets
from datetime import datetime, timezone

from jellyswipe.db import get_db_closing, cleanup_expired_auth_sessions
```

**Typed dataclass shape to copy for the new auth record** from `jellyswipe/dependencies.py` lines 25-29:
```python
@dataclass
class AuthUser:
    jf_token: str
    user_id: str
```

**Core auth lifecycle pattern** from `jellyswipe/auth.py` lines 15-43 and 46-68:
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

    session_dict['session_id'] = session_id
    return session_id


def get_current_token(session_dict: dict) -> Optional[Tuple[str, str]]:
    sid = session_dict.get('session_id')
    if sid is None:
        return None

    with get_db_closing() as conn:
        row = conn.execute(
            'SELECT jellyfin_token, jellyfin_user_id FROM auth_sessions WHERE session_id = ?',
            (sid,)
        ).fetchone()

    if row is None:
        return None

    return (row['jellyfin_token'], row['jellyfin_user_id'])
```

**Destroy ordering baseline** from `jellyswipe/auth.py` lines 71-81:
```python
def destroy_session(session_dict: dict) -> None:
    sid = session_dict.get('session_id')
    if sid:
        with get_db_closing() as conn:
            conn.execute('DELETE FROM auth_sessions WHERE session_id = ?', (sid,))
        session_dict.pop('session_id', None)
```

**Service logging/error pattern to borrow for best-effort delete failures** from `jellyswipe/routers/auth.py` lines 17-18 and 34-49:
```python
_logger = logging.getLogger(__name__)


def log_exception(exc: Exception, request: Request, context: dict = None) -> None:
    log_data = {
        'request_id': getattr(request.state, 'request_id', 'unknown'),
        'route': request.url.path,
        'method': request.method,
        'exception_type': type(exc).__name__,
        'exception_message': str(exc),
        'stack_trace': traceback.format_exc(),
    }
    if context:
        log_data.update(context)
    _logger.error(
        "unhandled_exception",
        extra=log_data
    )
```

**Testing pattern** from `tests/test_auth.py` lines 95-155 and 214-259:
```python
class TestCreateSession:
    def test_create_session_inserts_into_auth_sessions(self, client, db_connection):
        resp = client.post('/test-create-session', json={
            'jf_token': 'my-jf-token',
            'jf_user_id': 'my-jf-user-id'
        })
        assert resp.status_code == 200
        sid = resp.json()['session_id']

        row = db_connection.execute(
            'SELECT * FROM auth_sessions WHERE session_id = ?', (sid,)
        ).fetchone()

        assert row is not None
        assert row['jellyfin_token'] == 'my-jf-token'
        assert row['jellyfin_user_id'] == 'my-jf-user-id'


class TestRequireAuth:
    def test_returns_401_when_session_id_not_in_vault(self, client, db_connection):
        resp = client.post('/test-create-session', json={
            'jf_token': 'token',
            'jf_user_id': 'user'
        })
        sid = resp.json()['session_id']

        db_connection.execute('DELETE FROM auth_sessions WHERE session_id = ?', (sid,))
        db_connection.commit()

        resp = client.get('/test-protected')
        assert resp.status_code == 401
        assert resp.json()['detail'] == 'Authentication required'
```

**Use for Phase 38:** keep `auth.py` as the thin domain service. Replace the sync DB calls with awaited repository calls, add a small typed auth record, keep session mutation in this module, and swallow only post-clear delete failures with logging.

---

### `jellyswipe/db_uow.py` (store, CRUD)

**Analog:** `jellyswipe/db_uow.py` with ORM table mapping from `jellyswipe/models/auth_session.py`

**Imports + session typing pattern** from `jellyswipe/db_uow.py` lines 5-9:
```python
from collections.abc import Callable
from typing import Any, TypeVar

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
```

**Repository class shape** from `jellyswipe/db_uow.py` lines 14-25:
```python
class AuthSessionRepository:
    """Repository for auth session maintenance queries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def delete_expired(self, cutoff_iso: str) -> int:
        result = await self._session.execute(
            text("DELETE FROM auth_sessions WHERE created_at < :cutoff_iso"),
            {"cutoff_iso": cutoff_iso},
        )
        return result.rowcount or 0
```

**Unit-of-work façade pattern** from `jellyswipe/db_uow.py` lines 44-60:
```python
class DatabaseUnitOfWork:
    """Typed async unit-of-work facade around one AsyncSession."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.auth_sessions = AuthSessionRepository(session)
        self.swipes = SwipeRepository(session)

    async def run_sync(self, fn: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
        """Run legacy sync work on the managed session connection.

        The sync callable may issue `BEGIN IMMEDIATE` or other SQLite statements,
        but it must not own the final COMMIT or ROLLBACK. The dependency boundary
        remains the single owner of transaction completion for this session.
        """

        return await self.session.run_sync(lambda sync_session: fn(sync_session, *args, **kwargs))
```

**ORM model import path and field names** from `jellyswipe/models/auth_session.py` lines 5-8 and 14-25:
```python
from sqlalchemy import Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jellyswipe.models.base import Base


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        Index("ix_auth_sessions_created_at", "created_at"),
    )

    session_id: Mapped[str] = mapped_column(Text, primary_key=True)
    jellyfin_token: Mapped[str] = mapped_column(Text, nullable=False)
    jellyfin_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
```

**Transaction ownership pattern** from `jellyswipe/dependencies.py` lines 44-54:
```python
async def get_db_uow():
    session = get_sessionmaker()()
    try:
        yield DatabaseUnitOfWork(session)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
```

**Testing pattern** from `tests/test_dependencies.py` lines 146-195:
```python
@pytest.mark.anyio
class TestGetDbUow:
    async def test_yields_uow_and_commits_on_success(self, runtime_sessionmaker, monkeypatch):
        session = runtime_sessionmaker()
        counts = _instrument_session(session)
        monkeypatch.setattr(deps, "get_sessionmaker", lambda: lambda: session)

        generator = get_db_uow()
        uow = await generator.__anext__()

        assert isinstance(uow, DatabaseUnitOfWork)

        await uow.run_sync(_begin_immediate_insert, "committed")

        with pytest.raises(StopAsyncIteration):
            await generator.__anext__()

        assert counts == {"commit": 1, "rollback": 0, "close": 1}
```

**Use for Phase 38:** extend `AuthSessionRepository` with more small async methods (`get_by_session_id`, insert, delete_by_session_id`) and keep all commit/rollback behavior outside the repository.

---

### `jellyswipe/dependencies.py` (provider, request-response)

**Analog:** `jellyswipe/dependencies.py`

**Imports + dependency surface pattern** from `jellyswipe/dependencies.py` lines 10-20:
```python
from dataclasses import dataclass
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Request

import threading

import jellyswipe.auth as auth
from jellyswipe.db_runtime import get_sessionmaker
from jellyswipe.db_uow import DatabaseUnitOfWork
```

**Auth guard contract** from `jellyswipe/dependencies.py` lines 25-41:
```python
@dataclass
class AuthUser:
    """Authenticated user data for FastAPI dependency injection."""
    jf_token: str
    user_id: str


def require_auth(request: Request) -> AuthUser:
    """FastAPI dependency that requires authentication."""
    result = auth.get_current_token(request.session)
    if result is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    jf_token, user_id = result
    return AuthUser(jf_token=jf_token, user_id=user_id)
```

**Request-scoped UoW dependency pattern** from `jellyswipe/dependencies.py` lines 44-57:
```python
async def get_db_uow():
    """Yield a request-scoped async unit of work."""
    session = get_sessionmaker()()
    try:
        yield DatabaseUnitOfWork(session)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


DBUoW = Annotated[DatabaseUnitOfWork, Depends(get_db_uow, scope="function")]
```

**Destroy-session dependency seam** from `jellyswipe/dependencies.py` lines 102-107:
```python
def destroy_session_dep(request: Request) -> None:
    """FastAPI dependency that destroys the current session.

    Calls auth.destroy_session(request.session).
    """
    auth.destroy_session(request.session)
```

**Testing pattern** from `tests/test_dependencies.py` lines 97-139 and 267-287:
```python
class TestRequireAuth:
    def test_returns_auth_user_for_valid_session(self, db_path, monkeypatch):
        monkeypatch.setattr(jellyswipe.db, "DB_PATH", db_path)
        upgrade_to_head(build_sqlite_url(db_path))

        sid = jellyswipe.auth.create_session("test-token", "test-user", {})

        request = MagicMock(spec=Request)
        request.session = {"session_id": sid}

        auth_user = require_auth(request)

        assert isinstance(auth_user, AuthUser)
        assert auth_user.jf_token == "test-token"
        assert auth_user.user_id == "test-user"


class TestDestroySessionDep:
    def test_calls_auth_destroy_session(self, db_path, monkeypatch):
        monkeypatch.setattr(jellyswipe.db, "DB_PATH", db_path)
        upgrade_to_head(build_sqlite_url(db_path))

        with patch("jellyswipe.auth.destroy_session") as mock_destroy:
            ...
            mock_destroy.assert_called_once()
```

**Use for Phase 38:** make `require_auth` async, keep the exact `401` body, clear stale `request.session` inside the dependency on invalid-session failures, and keep `get_db_uow()` as the only transaction owner.

---

### `jellyswipe/routers/auth.py` (route, request-response)

**Analog:** `jellyswipe/routers/auth.py` with async handler style from `jellyswipe/routers/rooms.py`

**Imports pattern** from `jellyswipe/routers/auth.py` lines 7-15:
```python
import logging
import traceback

from fastapi import APIRouter, Request, Depends, HTTPException
from jellyswipe import XSSSafeJSONResponse

from jellyswipe.dependencies import require_auth, AuthUser, get_provider, check_rate_limit
from jellyswipe.auth import create_session, destroy_session
from jellyswipe.config import TMDB_AUTH_HEADERS
```

**Shared error/logging pattern** from `jellyswipe/routers/auth.py` lines 23-49:
```python
def make_error_response(message: str, status_code: int, request: Request, extra_fields: dict = None) -> XSSSafeJSONResponse:
    """Create a standardized error response with request ID tracking."""
    if status_code >= 500:
        message = 'Internal server error'
    body = {'error': message}
    body['request_id'] = getattr(request.state, 'request_id', 'unknown')
    if extra_fields:
        body.update(extra_fields)
    return XSSSafeJSONResponse(content=body, status_code=status_code)


def log_exception(exc: Exception, request: Request, context: dict = None) -> None:
    """Log exception with request context."""
    log_data = {
        'request_id': getattr(request.state, 'request_id', 'unknown'),
        'route': request.url.path,
        'method': request.method,
        'exception_type': type(exc).__name__,
        'exception_message': str(exc),
        'stack_trace': traceback.format_exc(),
    }
    if context:
        log_data.update(context)
    _logger.error(
        "unhandled_exception",
        extra=log_data
    )
```

**Current login/delegate/logout route shape** from `jellyswipe/routers/auth.py` lines 59-95:
```python
@auth_router.post("/auth/jellyfin-use-server-identity")
def jellyfin_use_server_identity(request: Request):
    prov = get_provider()
    try:
        token = prov.server_access_token_for_delegate()
        uid = prov.server_primary_user_id_for_delegate()
    except RuntimeError:
        return make_error_response("Jellyfin delegate unavailable", 401, request)
    create_session(token, uid, request.session)
    return {"userId": uid}


@auth_router.post('/auth/jellyfin-login')
async def jellyfin_login(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    if not username or not password:
        return XSSSafeJSONResponse(content={"error": "Username and password are required"}, status_code=400)
    try:
        out = get_provider().authenticate_user_session(username, password)
        create_session(out["token"], out["user_id"], request.session)
        return {"userId": out["user_id"]}
    except Exception:
        return make_error_response("Jellyfin login failed", 401, request)


@auth_router.post('/auth/logout')
def logout(request: Request, user: AuthUser = Depends(require_auth)):
    destroy_session(request.session)
    return {'status': 'logged_out'}
```

**Async request-body parsing pattern** from `jellyswipe/routers/rooms.py` lines 390-404 and 427-441:
```python
@rooms_router.post('/room/{code}/undo')
async def undo_swipe(code: str, request: Request, user: AuthUser = Depends(require_auth)):
    try:
        data = await request.json()
    except Exception:
        data = {}
    mid = data.get('movie_id')
    if not mid:
        return JSONResponse(content={'error': 'movie_id required'}, status_code=400)
    ...


@rooms_router.post('/room/{code}/genre')
async def set_genre(code: str, request: Request, user: AuthUser = Depends(require_auth)):
    try:
        data = await request.json()
    except Exception:
        data = {}
    genre = data.get('genre')
    if not genre:
        return XSSSafeJSONResponse(content={'error': 'Genre required'}, status_code=400)
    ...
```

**Testing pattern** from `tests/test_route_authorization.py` lines 89-168 and 727-835:
```python
def test_login_creates_vault_entry(db_connection, client_real_auth):
    response = client_real_auth.post("/auth/jellyfin-login", json={
        "username": "testuser",
        "password": "testpass",
    })
    assert response.status_code == 200
    count = db_connection.execute("SELECT COUNT(*) FROM auth_sessions").fetchone()[0]
    assert count == 1


class TestLogout:
    def test_logout_clears_vault(self, db_connection, client_real_auth):
        _set_session(client_real_auth, db_connection, os.environ["FLASK_SECRET"], active_room="ROOM1", authenticated=True)
        resp = client_real_auth.post('/auth/logout')
        assert resp.status_code == 200
        assert resp.json()['status'] == 'logged_out'

        count = db_connection.execute("SELECT COUNT(*) FROM auth_sessions").fetchone()[0]
        assert count == 0

    def test_auth_lifecycle(self, db_connection, client_real_auth):
        resp = client_real_auth.post('/auth/jellyfin-use-server-identity')
        assert resp.status_code == 200

        resp = client_real_auth.get('/me')
        assert resp.status_code == 200

        resp = client_real_auth.post('/auth/logout')
        assert resp.status_code == 200

        resp = client_real_auth.get('/me')
        assert resp.status_code == 401
```

**Use for Phase 38:** keep all route URLs and response bodies stable, just swap the auth calls to awaited service methods and preserve the existing error-response helpers instead of introducing a new controller abstraction.

---

### `tests/test_auth.py` (test, CRUD)

**Analog:** `tests/test_auth.py`

**Minimal auth test app fixture** from `tests/test_auth.py` lines 31-64:
```python
@pytest.fixture
def auth_app(db_path, monkeypatch):
    _bootstrap_temp_db_runtime(db_path, monkeypatch)

    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret-key")

    @app.post("/test-create-session")
    async def create_session_route(request: Request):
        body = await request.json()
        sid = jellyswipe.auth.create_session(
            body["jf_token"], body["jf_user_id"], request.session
        )
        return {"session_id": sid}

    @app.get("/test-protected")
    def protected_route(auth: AuthUser = Depends(require_auth)):
        return {"user_id": auth.user_id, "jf_token": auth.jf_token}

    return app
```

**Seed helper pattern** from `tests/test_auth.py` lines 74-88:
```python
@pytest.fixture
def seed_vault(db_connection):
    def _seed(session_id="test-session-id", jf_token="test-jf-token", jf_user_id="test-jf-user-id"):
        from datetime import datetime, timezone

        created_at = datetime.now(timezone.utc).isoformat()
        db_connection.execute(
            "INSERT INTO auth_sessions (session_id, jellyfin_token, jellyfin_user_id, created_at) "
            "VALUES (?, ?, ?, ?)",
            (session_id, jf_token, jf_user_id, created_at),
        )
        db_connection.commit()
        return session_id
```

**Behavior assertion pattern** from `tests/test_auth.py` lines 98-155 and 242-259:
```python
def test_create_session_calls_cleanup(self, client):
    with patch('jellyswipe.auth.cleanup_expired_auth_sessions') as mock_cleanup:
        resp = client.post('/test-create-session', json={
            'jf_token': 'token',
            'jf_user_id': 'user'
        })
        assert resp.status_code == 200
        mock_cleanup.assert_called_once()


def test_returns_401_when_session_id_not_in_vault(self, client, db_connection):
    resp = client.post('/test-create-session', json={
        'jf_token': 'token',
        'jf_user_id': 'user'
    })
    sid = resp.json()['session_id']

    db_connection.execute('DELETE FROM auth_sessions WHERE session_id = ?', (sid,))
    db_connection.commit()

    resp = client.get('/test-protected')
    assert resp.status_code == 401
    assert resp.json()['detail'] == 'Authentication required'
```

**Use for Phase 38:** convert this file into service-focused coverage. Keep the tiny test app, but update it to await the new async auth functions and assert typed-record behavior, invalid-session clearing, cleanup-on-create, and best-effort delete swallowing.

---

### `tests/test_dependencies.py` (test, request-response)

**Analog:** `tests/test_dependencies.py`

**Async runtime fixture pattern** from `tests/test_dependencies.py` lines 37-53:
```python
@pytest.fixture
async def runtime_sessionmaker(db_path, monkeypatch):
    monkeypatch.setattr(jellyswipe.db, "DB_PATH", db_path)
    upgrade_to_head(build_sqlite_url(db_path))
    await dispose_runtime()
    await initialize_runtime(build_sqlite_url(db_path))

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await session.execute(
            text("CREATE TABLE bridge_rows (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        )
        await session.commit()

    yield sessionmaker
    await dispose_runtime()
```

**Async generator verification pattern** from `tests/test_dependencies.py` lines 55-76 and 146-195:
```python
def _instrument_session(session):
    counts = {"commit": 0, "rollback": 0, "close": 0}
    original_commit = session.commit
    original_rollback = session.rollback
    original_close = session.close
    ...
    return counts


@pytest.mark.anyio
class TestGetDbUow:
    async def test_rolls_back_on_error_after_begin_immediate_bridge(
        self, runtime_sessionmaker, monkeypatch
    ):
        session = runtime_sessionmaker()
        counts = _instrument_session(session)
        monkeypatch.setattr(deps, "get_sessionmaker", lambda: lambda: session)

        generator = get_db_uow()
        uow = await generator.__anext__()
        await uow.run_sync(_begin_immediate_insert, "rolled-back")

        with pytest.raises(RuntimeError, match="boom"):
            await generator.athrow(RuntimeError("boom"))

        assert counts == {"commit": 0, "rollback": 1, "close": 1}
```

**Current auth-contract assertions** from `tests/test_dependencies.py` lines 97-139:
```python
class TestRequireAuth:
    def test_raises_401_for_empty_session(self, db_path, monkeypatch):
        monkeypatch.setattr(jellyswipe.db, "DB_PATH", db_path)
        upgrade_to_head(build_sqlite_url(db_path))

        request = MagicMock(spec=Request)
        request.session = {}

        with pytest.raises(HTTPException) as exc_info:
            require_auth(request)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Authentication required"
```

**Use for Phase 38:** keep this file responsible for dependency contracts, not route behavior. Add async `require_auth` tests here for session clearing on stale vault lookups and preserve the `get_db_uow()` commit/rollback assertions unchanged.

---

### `tests/test_route_authorization.py` (test, request-response)

**Analog:** `tests/test_route_authorization.py`

**Real-auth session seeding pattern** from `tests/test_route_authorization.py` lines 17-35 and 221-230:
```python
def _set_session(client, db_connection, secret_key, *, active_room: str = "ROOM1", authenticated: bool = True):
    if authenticated:
        session_id = "test-session-" + secrets.token_hex(8)
        db_connection.execute(
            "INSERT INTO auth_sessions (session_id, jellyfin_token, jellyfin_user_id, created_at) VALUES (?, ?, ?, ?)",
            (session_id, "valid-token", "verified-user", datetime.now(timezone.utc).isoformat())
        )
        db_connection.commit()
        set_session_cookie(
            client,
            {"session_id": session_id, "active_room": active_room},
            secret_key
        )
    else:
        set_session_cookie(client, {"active_room": active_room}, secret_key)


def _setup_deck_session(client, db_connection, secret_key, *, user_id="verified-user", token="valid-token"):
    session_id = "test-session-" + secrets.token_hex(8)
    db_connection.execute(
        "INSERT INTO auth_sessions (session_id, jellyfin_token, jellyfin_user_id, created_at) VALUES (?, ?, ?, ?)",
        (session_id, token, user_id, datetime.now(timezone.utc).isoformat())
    )
    db_connection.commit()
    set_session_cookie(client, {"session_id": session_id}, secret_key)
    return session_id
```

**401 contract pattern** from `tests/test_route_authorization.py` lines 185-206:
```python
def test_unauthenticated_swipe_no_side_effects(db_connection, client_real_auth):
    _set_session(client_real_auth, db_connection, os.environ["FLASK_SECRET"], active_room="ROOM1", authenticated=False)
    _seed_room(db_connection, "ROOM1")
    before_swipes = db_connection.execute("SELECT COUNT(*) FROM swipes").fetchone()[0]
    response = client_real_auth.post("/room/ROOM1/swipe", json={"movie_id": "movie-1", "direction": "right"})
    after_swipes = db_connection.execute("SELECT COUNT(*) FROM swipes").fetchone()[0]
    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"
    assert after_swipes == before_swipes
```

**Auth route parity pattern** from `tests/test_route_authorization.py` lines 89-168:
```python
def test_login_creates_vault_entry(db_connection, client_real_auth):
    response = client_real_auth.post("/auth/jellyfin-login", json={
        "username": "testuser",
        "password": "testpass",
    })
    assert response.status_code == 200
    count = db_connection.execute("SELECT COUNT(*) FROM auth_sessions").fetchone()[0]
    assert count == 1


def test_delegate_creates_vault_entry(db_connection, client_real_auth):
    response = client_real_auth.post("/auth/jellyfin-use-server-identity")
    assert response.status_code == 200
    count = db_connection.execute("SELECT COUNT(*) FROM auth_sessions").fetchone()[0]
    assert count == 1
```

**Logout/lifecycle parity pattern** from `tests/test_route_authorization.py` lines 727-835:
```python
def test_logout_clears_session_cookie(self, db_connection, client_real_auth):
    _set_session(client_real_auth, db_connection, os.environ["FLASK_SECRET"], active_room="ROOM1", authenticated=True)
    resp1 = client_real_auth.get('/me')
    assert resp1.status_code == 200

    resp = client_real_auth.post('/auth/logout')
    assert resp.status_code == 200

    resp2 = client_real_auth.get('/me')
    assert resp2.status_code == 401


def test_auth_lifecycle(self, db_connection, client_real_auth):
    resp = client_real_auth.post('/auth/jellyfin-use-server-identity')
    assert resp.status_code == 200

    resp = client_real_auth.get('/me')
    assert resp.status_code == 200

    resp = client_real_auth.post('/auth/logout')
    assert resp.status_code == 200

    resp = client_real_auth.get('/me')
    assert resp.status_code == 401
```

**Use for Phase 38:** keep this file focused on externally visible parity. Add only route-level assertions for stale-session clearing and logout semantics; put detailed repository/service edge cases in `tests/test_auth.py` or `tests/test_dependencies.py`.

---

## Shared Patterns

### Request-Scoped Transaction Boundary
**Source:** `jellyswipe/dependencies.py` lines 44-57
**Apply to:** `jellyswipe/auth.py`, `jellyswipe/db_uow.py`, async auth callers
```python
async def get_db_uow():
    session = get_sessionmaker()()
    try:
        yield DatabaseUnitOfWork(session)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


DBUoW = Annotated[DatabaseUnitOfWork, Depends(get_db_uow, scope="function")]
```

### Auth Contract and 401 Shape
**Source:** `jellyswipe/dependencies.py` lines 25-41
**Apply to:** `require_auth`, protected auth routes, dependency tests, route auth parity tests
```python
@dataclass
class AuthUser:
    jf_token: str
    user_id: str


def require_auth(request: Request) -> AuthUser:
    result = auth.get_current_token(request.session)
    if result is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    jf_token, user_id = result
    return AuthUser(jf_token=jf_token, user_id=user_id)
```

### Session Cookie Injection for Real-Auth Tests
**Source:** `tests/conftest.py` lines 24-36 and 299-350
**Apply to:** `tests/test_route_authorization.py` and any route test that exercises real auth
```python
def set_session_cookie(client, data: dict, secret_key: str) -> None:
    signer = itsdangerous.TimestampSigner(str(secret_key))
    payload = b64encode(json.dumps(data).encode("utf-8"))
    signed = signer.sign(payload)
    client.cookies.set("session", signed.decode("utf-8"))


@pytest.fixture
def app_real_auth(db_path, monkeypatch):
    from jellyswipe import create_app
    from jellyswipe.dependencies import get_provider
    ...
    fast_app = create_app(test_config=test_config)
    fast_app.dependency_overrides[get_provider] = lambda: fake_provider
    ...


@pytest.fixture
def client_real_auth(app_real_auth):
    with TestClient(app_real_auth) as test_client:
        yield test_client
```

### Route Error Responses and Logging
**Source:** `jellyswipe/routers/auth.py` lines 23-49
**Apply to:** `jellyswipe/routers/auth.py`
```python
def make_error_response(message: str, status_code: int, request: Request, extra_fields: dict = None) -> XSSSafeJSONResponse:
    if status_code >= 500:
        message = 'Internal server error'
    body = {'error': message}
    body['request_id'] = getattr(request.state, 'request_id', 'unknown')
    if extra_fields:
        body.update(extra_fields)
    return XSSSafeJSONResponse(content=body, status_code=status_code)
```

### Async Request Body Parsing
**Source:** `jellyswipe/routers/auth.py` lines 72-88 and `jellyswipe/routers/rooms.py` lines 390-404
**Apply to:** async auth routes that parse request JSON
```python
try:
    data = await request.json()
except Exception:
    data = {}
```

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| None | — | — | Every planned Phase 38 file has an existing exact or role-match analog in the current repo. |

## Metadata

**Analog search scope:** `jellyswipe/`, `jellyswipe/models/`, `jellyswipe/routers/`, `tests/`, `.planning/phases/37-async-database-infrastructure/37-PATTERNS.md`
**Files scanned:** 49 Python source/test files via `rg` and targeted reads of 10 repo files plus the Phase 38 context/research artifacts
**Pattern extraction date:** 2026-05-05
