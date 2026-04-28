"""Tests for jellyswipe/auth.py module — token vault CRUD and @login_required decorator."""

import pytest
import re
import jellyswipe.db
import jellyswipe.auth
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_app(db_path, monkeypatch):
    """Create a Flask test app with auth routes and a temp database.

    Patches jellyswipe.db.DB_PATH to use a temp database, inits schema,
    and registers test routes that exercise auth functions within request context.
    """
    monkeypatch.setattr(jellyswipe.db, 'DB_PATH', db_path)
    jellyswipe.db.init_db()

    from flask import Flask, jsonify, g as flask_g

    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-secret-key'

    @app.route('/test-create-session', methods=['POST'])
    def create_session_route():
        """Test route that calls create_session within request context."""
        data = app.test_client().application.test_request_context().request.get_json(force=True) if False else None
        from flask import request as req
        body = req.get_json(force=True)
        sid = jellyswipe.auth.create_session(body['jf_token'], body['jf_user_id'])
        return jsonify({'session_id': sid})

    @app.route('/test-get-current-token', methods=['GET'])
    def get_token_route():
        """Test route that calls get_current_token within request context."""
        result = jellyswipe.auth.get_current_token()
        if result is None:
            return jsonify({'result': None})
        token, user_id = result
        return jsonify({'jf_token': token, 'jf_user_id': user_id})

    @app.route('/test-protected')
    @jellyswipe.auth.login_required
    def protected_route():
        """Test route decorated with @login_required."""
        return jsonify({'user_id': flask_g.user_id, 'jf_token': flask_g.jf_token})

    return app


@pytest.fixture
def client(auth_app):
    """Flask test client with session support."""
    return auth_app.test_client()


@pytest.fixture
def seed_vault(db_path, monkeypatch):
    """Seed a vault entry directly into user_tokens for testing.

    Returns the session_id that was inserted.
    """
    monkeypatch.setattr(jellyswipe.db, 'DB_PATH', db_path)

    def _seed(session_id='test-session-id', jf_token='test-jf-token', jf_user_id='test-jf-user-id'):
        from datetime import datetime, timezone
        created_at = datetime.now(timezone.utc).isoformat()
        with jellyswipe.db.get_db() as conn:
            conn.execute(
                'INSERT INTO user_tokens (session_id, jellyfin_token, jellyfin_user_id, created_at) '
                'VALUES (?, ?, ?, ?)',
                (session_id, jf_token, jf_user_id, created_at)
            )
        return session_id

    return _seed


# ---------------------------------------------------------------------------
# TestCreateSession
# ---------------------------------------------------------------------------

class TestCreateSession:
    """Tests for create_session() function."""

    def test_create_session_inserts_into_user_tokens(self, db_path, monkeypatch, client):
        """Verify INSERT into user_tokens with correct fields."""
        monkeypatch.setattr(jellyswipe.db, 'DB_PATH', db_path)

        resp = client.post('/test-create-session', json={
            'jf_token': 'my-jf-token',
            'jf_user_id': 'my-jf-user-id'
        })
        assert resp.status_code == 200
        data = resp.get_json()
        sid = data['session_id']

        # Verify the row exists in user_tokens
        with jellyswipe.db.get_db() as conn:
            row = conn.execute(
                'SELECT * FROM user_tokens WHERE session_id = ?', (sid,)
            ).fetchone()

        assert row is not None
        assert row['jellyfin_token'] == 'my-jf-token'
        assert row['jellyfin_user_id'] == 'my-jf-user-id'
        assert row['created_at'] is not None

    def test_create_session_sets_session_cookie(self, db_path, monkeypatch, client):
        """Verify session['session_id'] matches returned value."""
        monkeypatch.setattr(jellyswipe.db, 'DB_PATH', db_path)

        resp = client.post('/test-create-session', json={
            'jf_token': 'my-token',
            'jf_user_id': 'my-user'
        })
        data = resp.get_json()
        sid = data['session_id']

        # Verify session was set via session_transaction
        with client.session_transaction() as sess:
            assert sess.get('session_id') == sid

    def test_create_session_returns_session_id(self, db_path, monkeypatch, client):
        """Verify return value is a 64-char hex string."""
        monkeypatch.setattr(jellyswipe.db, 'DB_PATH', db_path)

        resp = client.post('/test-create-session', json={
            'jf_token': 'token',
            'jf_user_id': 'user'
        })
        data = resp.get_json()
        sid = data['session_id']

        assert len(sid) == 64
        assert re.match(r'^[0-9a-f]{64}$', sid), f"session_id is not 64-char hex: {sid}"

    def test_create_session_calls_cleanup(self, db_path, monkeypatch, client):
        """Mock cleanup_expired_tokens and verify it was called."""
        monkeypatch.setattr(jellyswipe.db, 'DB_PATH', db_path)

        with patch('jellyswipe.auth.cleanup_expired_tokens') as mock_cleanup:
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
        """Seed user_tokens, verify tuple return."""
        sid = seed_vault()

        # Set session cookie
        with client.session_transaction() as sess:
            sess['session_id'] = sid

        # Call get_current_token via test route
        resp = client.get('/test-get-current-token')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['jf_token'] == 'test-jf-token'
        assert data['jf_user_id'] == 'test-jf-user-id'

    def test_returns_none_when_no_session_id(self, client, db_path, monkeypatch):
        """No session set → None."""
        monkeypatch.setattr(jellyswipe.db, 'DB_PATH', db_path)

        resp = client.get('/test-get-current-token')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['result'] is None

    def test_returns_none_when_session_id_not_in_vault(self, client, db_path, monkeypatch):
        """session['session_id'] set but no matching row → None."""
        monkeypatch.setattr(jellyswipe.db, 'DB_PATH', db_path)

        with client.session_transaction() as sess:
            sess['session_id'] = 'nonexistent-session-id'

        resp = client.get('/test-get-current-token')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['result'] is None


# ---------------------------------------------------------------------------
# TestLoginRequired
# ---------------------------------------------------------------------------

class TestLoginRequired:
    """Tests for @login_required decorator."""

    def test_populates_g_user_id_and_jf_token_for_authenticated_request(self, client, seed_vault, db_path, monkeypatch):
        """Seed vault + set session, verify g fields populated and route handler called."""
        monkeypatch.setattr(jellyswipe.db, 'DB_PATH', db_path)
        sid = seed_vault('auth-sid', 'my-token', 'my-user')

        with client.session_transaction() as sess:
            sess['session_id'] = sid

        resp = client.get('/test-protected')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['user_id'] == 'my-user'
        assert data['jf_token'] == 'my-token'

    def test_returns_401_for_unauthenticated_request(self, client, db_path, monkeypatch):
        """No session → 401 with {'error': 'Authentication required'}."""
        monkeypatch.setattr(jellyswipe.db, 'DB_PATH', db_path)

        resp = client.get('/test-protected')
        assert resp.status_code == 401
        data = resp.get_json()
        assert data['error'] == 'Authentication required'

    def test_returns_401_when_session_id_not_in_vault(self, client, db_path, monkeypatch):
        """session set but vault empty → 401."""
        monkeypatch.setattr(jellyswipe.db, 'DB_PATH', db_path)

        with client.session_transaction() as sess:
            sess['session_id'] = 'nonexistent-session-id'

        resp = client.get('/test-protected')
        assert resp.status_code == 401
        data = resp.get_json()
        assert data['error'] == 'Authentication required'
