"""Tests for jellyswipe/dependencies.py — FastAPI dependency injection layer."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

import jellyswipe.dependencies as deps
from jellyswipe.db_runtime import (
    build_async_sqlite_url,
    dispose_runtime,
    get_sessionmaker,
    initialize_runtime,
)
from jellyswipe.db_uow import DatabaseUnitOfWork
from jellyswipe.dependencies import (
    AuthUser,
    check_rate_limit,
    clear_room_session,
    clear_session,
    get_db_uow,
    get_provider,
    get_session_actor,
    mark_session_cookie_cleared,
    read_auth_session_id,
    require_auth,
    session_cookie_cleared,
    set_auth_session,
    set_room_session,
)
from jellyswipe.migrations import build_sqlite_url, upgrade_to_head
from jellyswipe.repositories.auth_sessions import AuthRecord
from jellyswipe.services.session_match_mutation import SessionActor


@pytest.fixture(autouse=True)
def reset_runtime(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DB_PATH", raising=False)
    yield


@pytest.fixture
async def runtime_sessionmaker(db_path, monkeypatch):
    upgrade_to_head(build_sqlite_url(db_path))
    await dispose_runtime()
    await initialize_runtime(build_async_sqlite_url(db_path))

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await session.execute(
            text(
                "CREATE TABLE bridge_rows (id INTEGER PRIMARY KEY, value TEXT NOT NULL)"
            )
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


class _DirtySessionWrapper:
    """Wraps a session to force dirty/new/deleted to truthy values."""

    def __init__(self, session):
        self._session = session
        self.dirty = True
        self.new = True
        self.deleted = True

    def __getattr__(self, name):
        return getattr(self._session, name)


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
            created_at=datetime.now(UTC).isoformat(),
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
    """Tests for get_db_uow() dependency — the single transaction boundary."""

    async def test_boundary_commits_on_success(self, runtime_sessionmaker, monkeypatch):
        """On success the boundary commits, persisting the request's writes."""
        session = runtime_sessionmaker()
        counts = _instrument_session(session)
        monkeypatch.setattr(deps, "get_sessionmaker", lambda: lambda: session)

        generator = get_db_uow()
        uow = await generator.__anext__()

        assert isinstance(uow, DatabaseUnitOfWork)

        await uow.run_sync(_begin_immediate_insert, "committed")

        with patch.object(deps._logger, "warning") as mock_warning:
            with pytest.raises(StopAsyncIteration):
                await generator.__anext__()
            mock_warning.assert_not_called()

        assert counts == {"commit": 1, "rollback": 0, "close": 1}

        # Data IS persisted
        async with runtime_sessionmaker() as verify_session:
            rows = (
                (
                    await verify_session.execute(
                        text("SELECT value FROM bridge_rows ORDER BY id")
                    )
                )
                .scalars()
                .all()
            )
        assert rows == ["committed"]

    async def test_rollback_on_error_preserved(self, runtime_sessionmaker, monkeypatch):
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
                (
                    await verify_session.execute(
                        text("SELECT value FROM bridge_rows ORDER BY id")
                    )
                )
                .scalars()
                .all()
            )
        assert rows == []

    async def test_boundary_abort_rolls_back(self, runtime_sessionmaker, monkeypatch):
        """abort() on a dirty session rolls back and does NOT persist."""
        session = runtime_sessionmaker()
        counts = _instrument_session(session)
        monkeypatch.setattr(deps, "get_sessionmaker", lambda: lambda: session)

        generator = get_db_uow()
        uow = await generator.__anext__()

        await uow.run_sync(_begin_immediate_insert, "aborted")
        uow.abort()

        with pytest.raises(StopAsyncIteration):
            await generator.__anext__()

        assert counts == {"commit": 0, "rollback": 1, "close": 1}

        async with runtime_sessionmaker() as verify_session:
            rows = (
                (
                    await verify_session.execute(
                        text("SELECT value FROM bridge_rows ORDER BY id")
                    )
                )
                .scalars()
                .all()
            )
        assert rows == []

    async def test_boundary_loud_fail_when_dirty_after_commit(
        self, runtime_sessionmaker, monkeypatch
    ):
        """Dirty state left after the boundary commit raises instead of warning."""
        session = runtime_sessionmaker()
        dirty_session = _DirtySessionWrapper(session)
        monkeypatch.setattr(deps, "get_sessionmaker", lambda: lambda: dirty_session)

        generator = get_db_uow()
        await generator.__anext__()

        # The commit runs, but the forced dirty state trips the loud-fail check.
        with pytest.raises(RuntimeError, match="still has dirty/new/deleted"):
            await generator.__anext__()

    async def test_clean_exit_commits_without_error(
        self, runtime_sessionmaker, monkeypatch
    ):
        """Clean session (no writes) exits via commit and close, no error."""
        session = runtime_sessionmaker()
        counts = _instrument_session(session)
        monkeypatch.setattr(deps, "get_sessionmaker", lambda: lambda: session)

        generator = get_db_uow()
        await generator.__anext__()

        with pytest.raises(StopAsyncIteration):
            await generator.__anext__()

        assert counts == {"commit": 1, "rollback": 0, "close": 1}


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
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setenv("DATABASE_URL", build_sqlite_url(db_path))
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
# TestGetProvider
# ---------------------------------------------------------------------------


class TestGetProvider:
    """Tests for get_provider() dependency."""

    @pytest.mark.anyio
    async def test_returns_jellyfin_library_provider_singleton(self):
        """get_provider returns the JellyfinLibrary (deck provider) singleton."""
        mock_provider = MagicMock()
        deps._provider_singleton = mock_provider
        deps._singletons_built = True

        # Create a mock config for the Depends parameter
        class MockConfig:
            jellyfin_url = "http://test"
            jellyfin_api_key = "test-key"
            jellyfin_device_id = "test-device"

        try:
            provider = await get_provider(config=MockConfig())
            assert provider == mock_provider
        finally:
            deps._provider_singleton = None
            deps._singletons_built = False

    @pytest.mark.anyio
    async def test_returns_same_instance_on_multiple_calls(self):
        """Calling get_provider() multiple times returns the same instance."""
        deps._provider_singleton = None
        deps._singletons_built = False

        mock_instance = MagicMock()
        with patch(
            "jellyswipe.jellyfin.library.JellyfinLibrary",
            return_value=mock_instance,
        ):

            class MockConfig:
                jellyfin_url = "http://test"
                jellyfin_api_key = "test-key"
                jellyfin_device_id = "test-device"

            try:
                provider1 = await get_provider(config=MockConfig())
                provider2 = await get_provider(config=MockConfig())
            finally:
                deps._provider_singleton = None
                deps._singletons_built = False

        assert provider1 is provider2
        assert provider1 is mock_instance


# ---------------------------------------------------------------------------
# TestAuthUser
# ---------------------------------------------------------------------------


class TestAuthUser:
    """Tests for AuthUser dataclass."""

    def test_dataclass_fields_are_stable(self):
        auth_user = AuthUser(jf_token="token", user_id="user")
        assert auth_user.jf_token == "token"
        assert auth_user.user_id == "user"


# ---------------------------------------------------------------------------
# TestSessionAdapter
# ---------------------------------------------------------------------------


class TestSessionHelpers:
    """Unit tests for the session adapter helper functions."""

    def _make_request(self, session=None):
        request = MagicMock(spec=Request)
        request.session = {} if session is None else session
        request.state = SimpleNamespace()
        return request

    def test_set_room_session_sets_both_keys(self):
        request = self._make_request()
        set_room_session(request, "AB12", True)
        assert request.session["active_room"] == "AB12"
        assert request.session["solo_mode"] is True

    def test_clear_room_session_pops_both_keys_only(self):
        request = self._make_request(
            {"active_room": "AB12", "solo_mode": True, "session_id": "s"}
        )
        clear_room_session(request)
        assert "active_room" not in request.session
        assert "solo_mode" not in request.session
        assert request.session["session_id"] == "s"

    def test_clear_room_session_is_idempotent_on_empty(self):
        request = self._make_request({})
        clear_room_session(request)  # must not raise
        assert request.session == {}

    def test_set_auth_session_and_read_auth_session_id_round_trip(self):
        request = self._make_request()
        set_auth_session(request, "sid-123")
        assert read_auth_session_id(request) == "sid-123"

    def test_read_auth_session_id_returns_none_when_absent(self):
        request = self._make_request({})
        assert read_auth_session_id(request) is None

    def test_clear_session_clears_everything(self):
        request = self._make_request({"session_id": "s", "active_room": "AB12"})
        clear_session(request)
        assert request.session == {}

    def test_mark_session_cookie_cleared_sets_flag(self):
        request = self._make_request()
        mark_session_cookie_cleared(request)
        assert request.state.clear_session_cookie is True

    def test_session_cookie_cleared_reads_flag(self):
        request = self._make_request()
        assert session_cookie_cleared(request) is False
        mark_session_cookie_cleared(request)
        assert session_cookie_cleared(request) is True

    def test_session_key_constants_match_wire_names(self):
        """The adapter's constants are the single source of truth."""
        assert deps.SESSION_ID_KEY == "session_id"
        assert deps.SESSION_ACTIVE_ROOM_KEY == "active_room"
        assert deps.SESSION_SOLO_MODE_KEY == "solo_mode"


class TestGetSessionActor:
    """Tests for get_session_actor() dependency."""

    @pytest.mark.anyio
    async def test_builds_actor_from_session_and_user(self):
        request = MagicMock(spec=Request)
        request.session = {"session_id": "sid", "active_room": "ROOM1"}
        user = AuthUser(jf_token="token", user_id="user-a")

        actor = await get_session_actor(request, user=user)

        assert isinstance(actor, SessionActor)
        assert actor.user_id == "user-a"
        assert actor.session_id == "sid"
        assert actor.active_room == "ROOM1"

    @pytest.mark.anyio
    async def test_actor_handles_missing_session_keys(self):
        request = MagicMock(spec=Request)
        request.session = {}
        user = AuthUser(jf_token="token", user_id="user-a")

        actor = await get_session_actor(request, user=user)

        assert actor.user_id == "user-a"
        assert actor.session_id is None
        assert actor.active_room is None

    def test_route_injects_actor_via_dependency_override(self):
        """A route declaring Depends(get_session_actor) accepts an injected actor.

        Demonstrates that swipe/undo/delete-style routes can be exercised by
        overriding the dependency without the full session-middleware stack.
        """
        app = FastAPI()
        injected = SessionActor(user_id="user-a", session_id="sid", active_room="ROOM1")

        app.dependency_overrides[get_session_actor] = lambda: injected

        @app.get("/actor")
        def route(actor: SessionActor = Depends(get_session_actor)):
            return {"user_id": actor.user_id, "active_room": actor.active_room}

        client = TestClient(app)
        resp = client.get("/actor")
        assert resp.status_code == 200
        assert resp.json() == {"user_id": "user-a", "active_room": "ROOM1"}

    def test_unauthenticated_get_session_actor_raises_401(self):
        """get_session_actor composes require_auth: no auth record -> 401."""
        app = FastAPI()
        app.add_middleware(SessionMiddleware, secret_key="test-secret-key")
        uow = MagicMock()
        uow.auth_sessions.get_by_session_id.return_value = None
        app.dependency_overrides[get_db_uow] = lambda: uow

        @app.get("/actor")
        def route(actor: SessionActor = Depends(get_session_actor)):
            return {"user_id": actor.user_id}

        client = TestClient(app)
        resp = client.get("/actor")
        assert resp.status_code == 401
