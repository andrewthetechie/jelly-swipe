"""Tests for jellyswipe/auth.py module — token vault CRUD and require_auth dependency.

Uses FastAPI TestClient with minimal test app (no Flask).
"""

import asyncio
import pytest
import re
from unittest.mock import patch

import jellyswipe.db
import jellyswipe.auth
import jellyswipe.db_runtime
from fastapi import FastAPI, Depends, Request
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from jellyswipe.dependencies import (
    AuthUser,
    require_auth,
    check_rate_limit,
    destroy_session_dep,
)
from tests.conftest import _bootstrap_temp_db_runtime


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_app(db_path, monkeypatch):
    """Create a minimal FastAPI test app with session middleware and auth test routes."""
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

    @app.get("/test-get-current-token")
    def get_token_route(request: Request):
        result = jellyswipe.auth.get_current_token(request.session)
        if result is None:
            return {"result": None}
        token, user_id = result
        return {"jf_token": token, "jf_user_id": user_id}

    @app.get("/test-protected")
    def protected_route(auth: AuthUser = Depends(require_auth)):
        return {"user_id": auth.user_id, "jf_token": auth.jf_token}

    @app.post("/test-destroy-session")
    def destroy_route(request: Request):
        destroy_session_dep(request)
        return {"destroyed": True}

    return app


@pytest.fixture
def client(auth_app):
    """FastAPI TestClient for auth tests."""
    with TestClient(auth_app) as test_client:
        yield test_client


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

    return _seed


# ---------------------------------------------------------------------------
# TestCreateSession
# ---------------------------------------------------------------------------

class TestCreateSession:
    """Tests for create_session() function."""

    def test_create_session_inserts_into_auth_sessions(self, client, db_connection):
        """Verify INSERT into auth_sessions with correct fields."""
        resp = client.post('/test-create-session', json={
            'jf_token': 'my-jf-token',
            'jf_user_id': 'my-jf-user-id'
        })
        assert resp.status_code == 200
        data = resp.json()
        sid = data['session_id']

        # Verify the row exists in auth_sessions
        row = db_connection.execute(
            'SELECT * FROM auth_sessions WHERE session_id = ?', (sid,)
        ).fetchone()

        assert row is not None
        assert row['jellyfin_token'] == 'my-jf-token'
        assert row['jellyfin_user_id'] == 'my-jf-user-id'
        assert row['created_at'] is not None

    def test_create_session_sets_session_cookie(self, client):
        """Verify session['session_id'] matches returned value."""
        resp = client.post('/test-create-session', json={
            'jf_token': 'my-token',
            'jf_user_id': 'my-user'
        })
        data = resp.json()
        sid = data['session_id']

        # Verify session was set by checking we can access it
        resp = client.get('/test-get-current-token')
        assert resp.status_code == 200
        data = resp.json()
        assert data['jf_token'] == 'my-token'
        assert data['jf_user_id'] == 'my-user'

    def test_create_session_returns_session_id(self, client):
        """Verify return value is a 64-char hex string."""
        resp = client.post('/test-create-session', json={
            'jf_token': 'token',
            'jf_user_id': 'user'
        })
        data = resp.json()
        sid = data['session_id']

        assert len(sid) == 64
        assert re.match(r'^[0-9a-f]{64}$', sid), f"session_id is not 64-char hex: {sid}"

    def test_create_session_calls_cleanup(self, client):
        """Mock cleanup_expired_auth_sessions and verify it was called."""
        with patch('jellyswipe.auth.cleanup_expired_auth_sessions') as mock_cleanup:
            resp = client.post('/test-create-session', json={
                'jf_token': 'token',
                'jf_user_id': 'user'
            })
            assert resp.status_code == 200
            mock_cleanup.assert_called_once()


# ---------------------------------------------------------------------------
# TestGetCurrentToken
# ---------------------------------------------------------------------------

class TestGetCurrentToken:
    """Tests for get_current_token() function."""

    def test_returns_token_and_user_id_for_valid_session(self, client, seed_vault):
        """Seed auth_sessions, verify tuple return."""
        seed_vault()

        # Create session via POST
        client.post('/test-create-session', json={
            'jf_token': 'test-jf-token',
            'jf_user_id': 'test-jf-user-id'
        })

        # Call get_current_token via test route
        resp = client.get('/test-get-current-token')
        assert resp.status_code == 200
        data = resp.json()
        assert data['jf_token'] == 'test-jf-token'
        assert data['jf_user_id'] == 'test-jf-user-id'

    def test_returns_none_when_no_session_id(self, client):
        """No session set → None."""
        # Use a fresh client with no cookies
        with TestClient(client.app) as fresh_client:
            resp = fresh_client.get('/test-get-current-token')
            assert resp.status_code == 200
            data = resp.json()
            assert data['result'] is None

    def test_returns_none_when_session_id_not_in_vault(self, client, db_connection):
        """session['session_id'] set but no matching row → None."""
        # Create a session then delete the vault entry
        resp = client.post('/test-create-session', json={
            'jf_token': 'token',
            'jf_user_id': 'user'
        })
        sid = resp.json()['session_id']

        # Delete the vault entry
        db_connection.execute('DELETE FROM auth_sessions WHERE session_id = ?', (sid,))
        db_connection.commit()

        # Now get_current_token should return None
        resp = client.get('/test-get-current-token')
        assert resp.status_code == 200
        data = resp.json()
        assert data['result'] is None


# ---------------------------------------------------------------------------
# TestRequireAuth
# ---------------------------------------------------------------------------

class TestRequireAuth:
    """Tests for require_auth() dependency."""

    def test_returns_auth_user_for_valid_session(self, client, seed_vault):
        """Seed vault + set session, verify AuthUser returned with correct fields."""
        seed_vault('auth-sid', 'my-token', 'my-user')

        # Create session
        client.post('/test-create-session', json={
            'jf_token': 'my-token',
            'jf_user_id': 'my-user'
        })

        resp = client.get('/test-protected')
        assert resp.status_code == 200
        data = resp.json()
        assert data['user_id'] == 'my-user'
        assert data['jf_token'] == 'my-token'

    def test_returns_401_for_unauthenticated_request(self, client):
        """No session → 401 with {'detail': 'Authentication required'}."""
        # Use fresh client with no session
        with TestClient(client.app) as fresh_client:
            resp = fresh_client.get('/test-protected')
            assert resp.status_code == 401
            data = resp.json()
            assert data['detail'] == 'Authentication required'

    def test_returns_401_when_session_id_not_in_vault(self, client, db_connection):
        """session set but vault empty → 401."""
        # Create a session then delete the vault entry
        resp = client.post('/test-create-session', json={
            'jf_token': 'token',
            'jf_user_id': 'user'
        })
        sid = resp.json()['session_id']

        # Delete the vault entry
        db_connection.execute('DELETE FROM auth_sessions WHERE session_id = ?', (sid,))
        db_connection.commit()

        # Now protected route should return 401
        resp = client.get('/test-protected')
        assert resp.status_code == 401
        data = resp.json()
        assert data['detail'] == 'Authentication required'

    def test_shared_bootstrap_reinitializes_runtime_for_distinct_temp_dbs(self, tmp_path):
        """Shared temp DB bootstrap should rebind runtime cleanly across files."""
        first_db_path = str(tmp_path / "first.db")
        second_db_path = str(tmp_path / "second.db")
        first_patch = pytest.MonkeyPatch()
        second_patch = pytest.MonkeyPatch()

        try:
            first_bootstrap = _bootstrap_temp_db_runtime(first_db_path, first_patch)
            with jellyswipe.db.get_db_closing() as conn:
                conn.execute(
                    "INSERT INTO auth_sessions (session_id, jellyfin_token, jellyfin_user_id, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    ("sid-one", "token-one", "user-one", "2026-05-05T00:00:00+00:00"),
                )
            assert jellyswipe.db_runtime.RUNTIME_DATABASE_URL == first_bootstrap["runtime_database_url"]

            asyncio.run(jellyswipe.db_runtime.dispose_runtime())
            first_patch.undo()

            second_bootstrap = _bootstrap_temp_db_runtime(second_db_path, second_patch)
            assert jellyswipe.db_runtime.RUNTIME_DATABASE_URL == second_bootstrap["runtime_database_url"]
            assert second_bootstrap["runtime_database_url"] != first_bootstrap["runtime_database_url"]

            with jellyswipe.db.get_db_closing() as conn:
                row_count = conn.execute(
                    "SELECT COUNT(*) AS count FROM auth_sessions"
                ).fetchone()["count"]
            assert row_count == 0
        finally:
            asyncio.run(jellyswipe.db_runtime.dispose_runtime())
            second_patch.undo()
            first_patch.undo()


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
        monkeypatch.setattr(jellyswipe.db, "DB_PATH", db_path)
        import jellyswipe.dependencies as deps
        monkeypatch.setattr(deps, "_RATE_LIMITS", {"get-trailer": 5})

        app = FastAPI()
        app.add_middleware(SessionMiddleware, secret_key="test-secret-key")

        @app.get("/get-trailer/test")
        def rate_limited_route(_: None = Depends(check_rate_limit)):
            return {"ok": True}

        client = TestClient(app)

        # Exhaust a low limit so token-bucket refill cannot make the test flaky.
        for _ in range(5):
            client.get("/get-trailer/test")

        # 6th request should get 429
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


# ---------------------------------------------------------------------------
# TestDestroySessionDep
# ---------------------------------------------------------------------------

class TestDestroySessionDep:
    """Tests for destroy_session_dep() dependency."""

    def test_calls_auth_destroy_session(self, db_connection):
        """destroy_session_dep delegates to auth.destroy_session(request.session)."""
        with patch("jellyswipe.auth.destroy_session") as mock_destroy:
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
