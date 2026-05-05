"""Tests for jellyswipe/dependencies.py — FastAPI dependency injection layer."""

import pytest
import sqlite3
from unittest.mock import patch, MagicMock
from fastapi import Depends, HTTPException, Request
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

import jellyswipe.db
import jellyswipe.auth
from jellyswipe.dependencies import (
    AuthUser,
    require_auth,
    get_db_dep,
    DBConn,
    check_rate_limit,
    destroy_session_dep,
    get_provider,
)


# ---------------------------------------------------------------------------
# TestRequireAuth
# ---------------------------------------------------------------------------

class TestRequireAuth:
    """Tests for require_auth() dependency."""

    def test_returns_auth_user_for_valid_session(self, db_path, monkeypatch):
        """Valid session in vault → returns AuthUser with correct fields."""
        monkeypatch.setattr(jellyswipe.db, 'DB_PATH', db_path)
        jellyswipe.db.init_db()

        # Create a session in vault
        sid = jellyswipe.auth.create_session('test-token', 'test-user', {})

        # Build mock request with session
        request = MagicMock(spec=Request)
        request.session = {'session_id': sid}

        # Call require_auth
        auth_user = require_auth(request)

        # Verify AuthUser structure
        assert isinstance(auth_user, AuthUser)
        assert auth_user.jf_token == 'test-token'
        assert auth_user.user_id == 'test-user'

    def test_raises_401_for_empty_session(self, db_path, monkeypatch):
        """Empty session → raises HTTPException(401)."""
        monkeypatch.setattr(jellyswipe.db, 'DB_PATH', db_path)
        jellyswipe.db.init_db()

        # Mock request with empty session
        request = MagicMock(spec=Request)
        request.session = {}

        # Should raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            require_auth(request)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Authentication required"

    def test_raises_401_when_session_id_not_in_vault(self, db_path, monkeypatch):
        """session with invalid session_id → raises HTTPException(401)."""
        monkeypatch.setattr(jellyswipe.db, 'DB_PATH', db_path)
        jellyswipe.db.init_db()

        # Mock request with nonexistent session_id
        request = MagicMock(spec=Request)
        request.session = {'session_id': 'nonexistent-session-id'}

        # Should raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            require_auth(request)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Authentication required"


# ---------------------------------------------------------------------------
# TestGetDbDep
# ---------------------------------------------------------------------------

class TestGetDbDep:
    """Tests for get_db_dep() dependency."""

    def test_yields_connection_and_closes(self, db_path, monkeypatch):
        """get_db_dep yields a sqlite3.Connection that is closed after context exits."""
        monkeypatch.setattr(jellyswipe.db, 'DB_PATH', db_path)
        jellyswipe.db.init_db()

        # Create generator
        gen = get_db_dep()
        conn = next(gen)
        assert isinstance(conn, sqlite3.Connection)

        # Connection should be usable
        row = conn.execute("SELECT 1").fetchone()
        assert row[0] == 1

        # Exhaust the generator (trigger cleanup)
        try:
            next(gen)
        except StopIteration:
            pass

        # After cleanup, connection should be closed
        # sqlite3 raises ProgrammingError when using closed connection
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")


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
        monkeypatch.setattr(jellyswipe.db, 'DB_PATH', db_path)
        # Use a low limit to avoid token-bucket refill during the request loop
        import jellyswipe.dependencies as deps
        monkeypatch.setattr(deps, '_RATE_LIMITS', {'get-trailer': 5})

        from fastapi import FastAPI
        app = FastAPI()
        app.add_middleware(SessionMiddleware, secret_key="test-secret-key")

        @app.get("/get-trailer/test")
        def rate_limited_route(_: None = Depends(check_rate_limit)):
            return {"ok": True}

        client = TestClient(app)

        # Exhaust the rate limit (5 requests allowed)
        for _ in range(5):
            client.get("/get-trailer/test")

        # 6th request should get 429
        resp = client.get("/get-trailer/test")
        assert resp.status_code == 429
        assert resp.json()["detail"] == "Rate limit exceeded"

    def test_passes_through_unlisted_paths(self):
        """Paths not in _RATE_LIMITS pass through without error."""
        from fastapi import FastAPI
        app = FastAPI()

        @app.get("/some-random-path")
        def route(_: None = Depends(check_rate_limit)):
            return {"ok": True}

        client = TestClient(app)
        resp = client.get("/some-random-path")
        assert resp.status_code == 200

    def test_passes_through_when_under_limit(self):
        """Under the limit → passes through without error."""
        from fastapi import FastAPI
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

    def test_calls_auth_destroy_session(self, db_path, monkeypatch):
        """destroy_session_dep delegates to auth.destroy_session(request.session)."""
        monkeypatch.setattr(jellyswipe.db, 'DB_PATH', db_path)
        jellyswipe.db.init_db()

        with patch("jellyswipe.auth.destroy_session") as mock_destroy:
            from fastapi import FastAPI
            app = FastAPI()
            app.add_middleware(SessionMiddleware, secret_key="test-secret-key")

            @app.post("/test-destroy-session")
            def destroy_route(request: Request):
                destroy_session_dep(request)
                return {"destroyed": True}

            client = TestClient(app)
            resp = client.post("/test-destroy-session")
            assert resp.status_code == 200
            mock_destroy.assert_called_once()


# ---------------------------------------------------------------------------
# TestGetProvider
# ---------------------------------------------------------------------------

class TestGetProvider:
    """Tests for get_provider() dependency."""

    def test_returns_jellyfin_library_provider_singleton(self, monkeypatch):
        """get_provider returns the JellyfinLibraryProvider singleton."""
        # Set a mock singleton in jellyswipe module
        import jellyswipe as app
        from unittest.mock import MagicMock

        mock_provider = MagicMock()
        app._provider_singleton = mock_provider

        provider = get_provider()
        assert provider == mock_provider

    def test_returns_same_instance_on_multiple_calls(self, monkeypatch):
        """Calling get_provider() multiple times returns the same instance (singleton)."""
        import jellyswipe as app

        # Reset singleton so the lazy-init path runs
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

    def test_auth_user_dataclass_structure(self):
        """AuthUser is a dataclass with jf_token and user_id fields."""
        auth_user = AuthUser(jf_token="my-token", user_id="my-user")

        assert auth_user.jf_token == "my-token"
        assert auth_user.user_id == "my-user"
        assert hasattr(auth_user, '__dataclass_fields__')
