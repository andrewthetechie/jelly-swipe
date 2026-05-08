"""Tests for jellyswipe/dependencies.py — FastAPI dependency injection layer."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

import jellyswipe.auth
import jellyswipe.db
import jellyswipe.dependencies as deps
from jellyswipe.auth_types import AuthRecord
from jellyswipe.db_runtime import dispose_runtime, get_sessionmaker, initialize_runtime
from jellyswipe.db_uow import DatabaseUnitOfWork
from jellyswipe.dependencies import (
    AuthUser,
    check_rate_limit,
    destroy_session_dep,
    get_db_uow,
    get_provider,
    require_auth,
)
from jellyswipe.migrations import build_sqlite_url, upgrade_to_head


@pytest.fixture(autouse=True)
def reset_runtime(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DB_PATH", raising=False)
    monkeypatch.setattr(jellyswipe.db_paths.application_db_path, "path", None)
    yield


@pytest.fixture
async def runtime_sessionmaker(db_path, monkeypatch):
    monkeypatch.setattr(jellyswipe.db_paths.application_db_path, "path", db_path)
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


def _instrument_session(session):
    counts = {"commit": 0, "rollback": 0, "close": 0}
    original_commit = session.commit
    original_rollback = session.rollback
    original_close = session.close

    async def commit():
        counts["commit"] += 1
        return await original_commit()

    async def rollback():
        counts["rollback"] += 1
        return await original_rollback()

    async def close():
        counts["close"] += 1
        return await original_close()

    session.commit = commit
    session.rollback = rollback
    session.close = close
    return counts


def _begin_immediate_insert(sync_session, value: str) -> None:
    connection = sync_session.connection()
    raw_connection = connection.connection.driver_connection
    raw_connection.isolation_level = None
    connection.exec_driver_sql("BEGIN IMMEDIATE")
    connection.exec_driver_sql(
        "INSERT INTO bridge_rows (value) VALUES (?)",
        (value,),
    )


# ---------------------------------------------------------------------------
# TestRequireAuth
# ---------------------------------------------------------------------------

@pytest.mark.anyio
class TestRequireAuth:
    """Tests for require_auth() dependency."""

    async def test_returns_auth_user_for_valid_session(self, runtime_sessionmaker):
        """Valid persisted session returns AuthUser from the auth service record."""
        record = AuthRecord(
            session_id="valid-session",
            jf_token="test-token",
            user_id="test-user",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        async with runtime_sessionmaker() as session:
            await DatabaseUnitOfWork(session).auth_sessions.insert(record)
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            request = MagicMock(spec=Request)
            request.session = {"session_id": record.session_id}
            auth_user = await require_auth(request, uow)

        assert isinstance(auth_user, AuthUser)
        assert auth_user.jf_token == "test-token"
        assert auth_user.user_id == "test-user"

    async def test_raises_401_for_empty_session(self, runtime_sessionmaker):
        """Empty session → raises HTTPException(401)."""
        request = MagicMock(spec=Request)
        request.session = {}

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            with pytest.raises(HTTPException) as exc_info:
                await require_auth(request, uow)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Authentication required"

    async def test_raises_401_and_clears_stale_session_when_session_id_not_in_vault(
        self, runtime_sessionmaker
    ):
        """Stale persisted session miss raises the same 401 and clears local state."""
        request = MagicMock(spec=Request)
        request.session = {
            "session_id": "nonexistent-session-id",
            "active_room": "ROOM1",
            "solo_mode": True,
        }

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            with pytest.raises(HTTPException) as exc_info:
                await require_auth(request, uow)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Authentication required"
        assert request.session == {}


# ---------------------------------------------------------------------------
# TestGetDbUow
# ---------------------------------------------------------------------------

@pytest.mark.anyio
class TestGetDbUow:
    """Tests for get_db_uow() dependency."""

    async def test_yields_uow_and_commits_on_success(self, runtime_sessionmaker, monkeypatch):
        """Successful downstream work commits once and closes the session."""
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

        async with runtime_sessionmaker() as verify_session:
            rows = (
                await verify_session.execute(text("SELECT value FROM bridge_rows ORDER BY id"))
            ).scalars().all()
        assert rows == ["committed"]

    async def test_rolls_back_on_error_after_begin_immediate_bridge(
        self, runtime_sessionmaker, monkeypatch
    ):
        """A downstream failure rolls back once after BEGIN IMMEDIATE bridge work."""
        session = runtime_sessionmaker()
        counts = _instrument_session(session)
        monkeypatch.setattr(deps, "get_sessionmaker", lambda: lambda: session)

        generator = get_db_uow()
        uow = await generator.__anext__()
        await uow.run_sync(_begin_immediate_insert, "rolled-back")

        with pytest.raises(RuntimeError, match="boom"):
            await generator.athrow(RuntimeError("boom"))

        assert counts == {"commit": 0, "rollback": 1, "close": 1}

        async with runtime_sessionmaker() as verify_session:
            rows = (
                await verify_session.execute(text("SELECT value FROM bridge_rows ORDER BY id"))
            ).scalars().all()
        assert rows == []


# ---------------------------------------------------------------------------
# TestCheckRateLimit
# ---------------------------------------------------------------------------

class TestCheckRateLimit:
    """Tests for check_rate_limit() dependency."""

    def setup_method(self):
        """Reset rate limiter state before each test."""
        from jellyswipe.rate_limiter import rate_limiter

        rate_limiter.reset()

    def teardown_method(self):
        """Reset rate limiter state after each test."""
        from jellyswipe.rate_limiter import rate_limiter

        rate_limiter.reset()

    def test_raises_429_when_limit_exceeded(self, db_path, monkeypatch):
        """Exceeding rate limit raises HTTPException(429)."""
        monkeypatch.setattr(jellyswipe.db_paths.application_db_path, "path", db_path)
        monkeypatch.setattr(deps, "_RATE_LIMITS", {"get-trailer": 5})

        app = FastAPI()
        app.add_middleware(SessionMiddleware, secret_key="test-secret-key")

        @app.get("/get-trailer/test")
        def rate_limited_route(_: None = Depends(check_rate_limit)):
            return {"ok": True}

        client = TestClient(app)

        for _ in range(5):
            client.get("/get-trailer/test")

        resp = client.get("/get-trailer/test")
        assert resp.status_code == 429
        assert resp.json()["detail"] == "Rate limit exceeded"

    def test_passes_through_unlisted_paths(self):
        """Paths not in _RATE_LIMITS pass through without error."""
        app = FastAPI()

        @app.get("/some-random-path")
        def route(_: None = Depends(check_rate_limit)):
            return {"ok": True}

        client = TestClient(app)
        resp = client.get("/some-random-path")
        assert resp.status_code == 200

    def test_passes_through_when_under_limit(self):
        """Under the limit → passes through without error."""
        app = FastAPI()

        @app.get("/get-trailer/test")
        def route(_: None = Depends(check_rate_limit)):
            return {"ok": True}

        client = TestClient(app)
        resp = client.get("/get-trailer/test")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# TestDestroySessionDep
# ---------------------------------------------------------------------------

class TestDestroySessionDep:
    """Tests for destroy_session_dep() dependency."""

    @pytest.mark.anyio
    async def test_calls_auth_destroy_session(self, runtime_sessionmaker):
        """destroy_session_dep awaits auth.destroy_session(request.session, uow)."""
        request = MagicMock(spec=Request)
        request.session = {"session_id": "destroy-session"}

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            with patch("jellyswipe.auth.destroy_session", new=AsyncMock()) as mock_destroy:
                await destroy_session_dep(request, uow)

        mock_destroy.assert_awaited_once_with(request.session, uow)


# ---------------------------------------------------------------------------
# TestGetProvider
# ---------------------------------------------------------------------------

class TestGetProvider:
    """Tests for get_provider() dependency."""

    def test_returns_jellyfin_library_provider_singleton(self):
        """get_provider returns the JellyfinLibraryProvider singleton."""
        import jellyswipe as app

        mock_provider = MagicMock()
        app._provider_singleton = mock_provider

        provider = get_provider()
        assert provider == mock_provider

    def test_returns_same_instance_on_multiple_calls(self):
        """Calling get_provider() multiple times returns the same instance."""
        import jellyswipe as app

        app._provider_singleton = None

        mock_instance = MagicMock()
        with patch(
            "jellyswipe.jellyfin_library.JellyfinLibraryProvider",
            return_value=mock_instance,
        ):
            provider1 = get_provider()
            provider2 = get_provider()

        assert provider1 is provider2
        assert provider1 is mock_instance
        assert app._provider_singleton is not None


# ---------------------------------------------------------------------------
# TestAuthUser
# ---------------------------------------------------------------------------

class TestAuthUser:
    """Tests for AuthUser dataclass."""

    def test_dataclass_fields_are_stable(self):
        auth_user = AuthUser(jf_token="token", user_id="user")
        assert auth_user.jf_token == "token"
        assert auth_user.user_id == "user"
