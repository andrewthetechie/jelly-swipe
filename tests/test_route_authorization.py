"""Route-level security regression tests for authorization hardening."""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import pytest


class FakeProvider:
    """Minimal provider stub for auth route tests."""

    def __init__(self, user_id: str = "verified-user", token: str = "valid-token"):
        self._user_id = user_id
        self._token = token
        self.favorites_added = []

    def server_primary_user_id_for_delegate(self) -> str:
        return self._user_id

    def server_access_token_for_delegate(self) -> str:
        return self._token

    def extract_media_browser_token(self, auth_header: str) -> str:
        marker = 'Token="'
        if marker in auth_header and auth_header.endswith('"'):
            return auth_header.split(marker, 1)[1][:-1]
        return ""

    def resolve_user_id_from_token(self, token: str) -> Optional[str]:
        if token == self._token:
            return self._user_id
        return None

    def authenticate_user_session(self, username: str, password: str) -> dict:
        return {"token": self._token, "user_id": self._user_id}

    def add_to_user_favorites(self, user_token: str, movie_id: str) -> None:
        self.favorites_added.append((user_token, movie_id))

    def resolve_item_for_tmdb(self, movie_id: str):
        from types import SimpleNamespace
        return SimpleNamespace(title=f"Movie-{movie_id}", year=2025)


@pytest.fixture
def app_module(db_connection, monkeypatch):
    import jellyswipe as app_module_obj

    fake_provider = FakeProvider()
    monkeypatch.setattr(app_module_obj, "_provider_singleton", fake_provider, raising=False)
    return app_module_obj


@pytest.fixture
def client(app_module):
    return app_module.app.test_client()


def _set_session(client, db_connection, *, active_room: str = "ROOM1", authenticated: bool = True):
    """Set up session with vault entry for authenticated testing."""
    if authenticated:
        import jellyswipe.db
        session_id = "test-session-" + secrets.token_hex(8)
        db_connection.execute(
            "INSERT INTO user_tokens (session_id, jellyfin_token, jellyfin_user_id, created_at) VALUES (?, ?, ?, ?)",
            (session_id, "valid-token", "verified-user", datetime.now(timezone.utc).isoformat())
        )
        db_connection.commit()
        with client.session_transaction() as sess:
            sess["session_id"] = session_id
            sess["active_room"] = active_room
    else:
        with client.session_transaction() as sess:
            sess["active_room"] = active_room


def _seed_room(conn, room_code: str = "ROOM1"):
    conn.execute(
        "INSERT INTO rooms (pairing_code, movie_data, ready, current_genre, solo_mode) VALUES (?, ?, ?, ?, ?)",
        (room_code, json.dumps([]), 1, "All", 0),
    )
    conn.commit()


def _prepare_route_state(conn, route: str, *, room_code: str, verified_user: str, session_user: str, movie_id: str = "movie-1"):
    _seed_room(conn, room_code)
    if route == "/matches":
        conn.execute(
            'INSERT INTO matches (room_code, movie_id, title, thumb, status, user_id) VALUES (?, ?, ?, ?, "active", ?)',
            (room_code, movie_id, "Movie", "thumb.jpg", verified_user),
        )
    elif route == "/matches/delete":
        conn.execute(
            'INSERT INTO matches (room_code, movie_id, title, thumb, status, user_id) VALUES (?, ?, ?, ?, "active", ?)',
            (room_code, movie_id, "Movie", "thumb.jpg", verified_user),
        )
    elif route == "/undo":
        conn.execute(
            "INSERT INTO swipes (room_code, movie_id, user_id, direction) VALUES (?, ?, ?, ?)",
            (room_code, movie_id, session_user, "right"),
        )
        conn.execute(
            'INSERT INTO matches (room_code, movie_id, title, thumb, status, user_id) VALUES (?, ?, ?, ?, "active", ?)',
            (room_code, movie_id, "Movie", "thumb.jpg", verified_user),
        )
    conn.commit()


def _send_request(client, method: str, path: str, payload: Optional[Dict[str, Any]], headers: Dict[str, str]):
    if method == "GET":
        return client.get(path, headers=headers)
    return client.post(path, json=payload or {}, headers=headers)


SPOOF_HEADERS = ("X-Provider-User-Id", "X-Jellyfin-User-Id", "X-Emby-UserId")
ROUTE_CASES: Tuple[Tuple[str, str, Optional[Dict[str, Any]]], ...] = (
    ("POST", "/room/swipe", {"movie_id": "movie-1", "title": "Movie", "thumb": "thumb.jpg", "direction": "right"}),
    ("GET", "/matches", None),
    ("POST", "/matches/delete", {"movie_id": "movie-1"}),
    ("POST", "/undo", {"movie_id": "movie-1"}),
    ("POST", "/watchlist/add", {"movie_id": "movie-1"}),
)


# --- Login/Delegate Route Tests ---


def test_login_returns_userId_no_authToken(db_connection, client):
    """Login endpoint stores token in vault and returns only userId."""
    response = client.post("/auth/jellyfin-login", json={
        "username": "testuser",
        "password": "testpass",
    })
    assert response.status_code == 200
    data = response.get_json()
    assert "userId" in data
    assert "authToken" not in data


def test_login_creates_vault_entry(db_connection, client):
    """Login creates a user_tokens row and sets session_id cookie."""
    response = client.post("/auth/jellyfin-login", json={
        "username": "testuser",
        "password": "testpass",
    })
    assert response.status_code == 200
    # Verify vault entry was created
    count = db_connection.execute("SELECT COUNT(*) FROM user_tokens").fetchone()[0]
    assert count == 1
    row = db_connection.execute("SELECT jellyfin_token, jellyfin_user_id FROM user_tokens").fetchone()
    assert row["jellyfin_token"] == "valid-token"
    assert row["jellyfin_user_id"] == "verified-user"


def test_login_sets_session_cookie(db_connection, client):
    """Login sets session_id in the session cookie."""
    with client.session_transaction() as sess:
        assert "session_id" not in sess
    response = client.post("/auth/jellyfin-login", json={
        "username": "testuser",
        "password": "testpass",
    })
    assert response.status_code == 200
    with client.session_transaction() as sess:
        assert "session_id" in sess
        assert len(sess["session_id"]) > 0


def test_login_missing_credentials_returns_400(db_connection, client):
    response = client.post("/auth/jellyfin-login", json={})
    assert response.status_code == 400


def test_delegate_returns_userId(db_connection, client):
    """Delegate endpoint stores server token in vault and returns only userId."""
    response = client.post("/auth/jellyfin-use-server-identity")
    assert response.status_code == 200
    data = response.get_json()
    assert "userId" in data
    assert data["userId"] == "verified-user"


def test_delegate_creates_vault_entry(db_connection, client):
    """Delegate creates a user_tokens row with server credentials."""
    response = client.post("/auth/jellyfin-use-server-identity")
    assert response.status_code == 200
    count = db_connection.execute("SELECT COUNT(*) FROM user_tokens").fetchone()[0]
    assert count == 1
    row = db_connection.execute("SELECT jellyfin_token, jellyfin_user_id FROM user_tokens").fetchone()
    assert row["jellyfin_token"] == "valid-token"
    assert row["jellyfin_user_id"] == "verified-user"


def test_delegate_no_session_flag(db_connection, client):
    """Delegate no longer sets jf_delegate_server_identity session flag."""
    response = client.post("/auth/jellyfin-use-server-identity")
    assert response.status_code == 200
    with client.session_transaction() as sess:
        assert "jf_delegate_server_identity" not in sess


def test_delegate_sets_session_cookie(db_connection, client):
    """Delegate sets session_id in the session cookie."""
    response = client.post("/auth/jellyfin-use-server-identity")
    assert response.status_code == 200
    with client.session_transaction() as sess:
        assert "session_id" in sess
        assert len(sess["session_id"]) > 0
