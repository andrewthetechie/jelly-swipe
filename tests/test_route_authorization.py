"""Route-level security regression tests for authorization hardening."""

from __future__ import annotations

import json
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
    app_module_obj._token_user_id_cache.clear()
    return app_module_obj


@pytest.fixture
def client(app_module):
    return app_module.app.test_client()


def _set_session(client, *, active_room: str = "ROOM1", session_user_id: str = "session-user", delegate: bool = False):
    with client.session_transaction() as sess:
        sess["active_room"] = active_room
        sess["my_user_id"] = session_user_id
        if delegate:
            sess["jf_delegate_server_identity"] = True
        else:
            sess.pop("jf_delegate_server_identity", None)


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


@pytest.mark.parametrize("method,path,payload", ROUTE_CASES)
@pytest.mark.parametrize("spoof_header", SPOOF_HEADERS)
def test_spoofed_alias_headers_rejected_with_401(db_connection, client, method, path, payload, spoof_header):
    _set_session(client, active_room="ROOM1", session_user_id="session-user")
    _seed_room(db_connection, "ROOM1")

    response = _send_request(client, method, path, payload, {spoof_header: "attacker-id"})

    assert response.status_code == 401
    assert response.get_json() == {"error": "Unauthorized"}


def test_room_swipe_body_user_id_injection_unauthorized_and_no_side_effects(db_connection, client):
    _set_session(client, active_room="ROOM1", session_user_id="session-user")
    _seed_room(db_connection, "ROOM1")

    before_swipes = db_connection.execute("SELECT COUNT(*) FROM swipes").fetchone()[0]
    before_matches = db_connection.execute("SELECT COUNT(*) FROM matches").fetchone()[0]

    response = client.post(
        "/room/swipe",
        json={
            "movie_id": "movie-1",
            "title": "Movie",
            "thumb": "thumb.jpg",
            "direction": "right",
            "user_id": "injected-user",
        },
    )

    after_swipes = db_connection.execute("SELECT COUNT(*) FROM swipes").fetchone()[0]
    after_matches = db_connection.execute("SELECT COUNT(*) FROM matches").fetchone()[0]

    assert response.status_code == 401
    assert response.get_json() == {"error": "Unauthorized"}
    assert after_swipes == before_swipes
    assert after_matches == before_matches


def test_room_swipe_ignores_body_user_id_when_token_is_valid(db_connection, client):
    _set_session(client, active_room="ROOM1", session_user_id="session-user")
    _seed_room(db_connection, "ROOM1")

    response = client.post(
        "/room/swipe",
        json={
            "movie_id": "movie-1",
            "title": "Movie",
            "thumb": "thumb.jpg",
            "direction": "right",
            "user_id": "injected-user",
        },
        headers={"Authorization": 'Token="valid-token"'},
    )

    injected_matches = db_connection.execute(
        "SELECT COUNT(*) FROM matches WHERE user_id = ?",
        ("injected-user",),
    ).fetchone()[0]

    assert response.status_code == 200
    assert injected_matches == 0


@pytest.mark.parametrize("method,path,payload", ROUTE_CASES)
def test_delegate_flow_valid_identity_succeeds(db_connection, client, method, path, payload):
    _set_session(client, active_room="ROOM1", session_user_id="session-user", delegate=True)
    _prepare_route_state(
        db_connection,
        path,
        room_code="ROOM1",
        verified_user="verified-user",
        session_user="session-user",
    )

    response = _send_request(client, method, path, payload, {})

    assert response.status_code != 401


@pytest.mark.parametrize("method,path,payload", ROUTE_CASES)
def test_token_flow_valid_identity_succeeds(db_connection, client, method, path, payload):
    _set_session(client, active_room="ROOM1", session_user_id="session-user", delegate=False)
    _prepare_route_state(
        db_connection,
        path,
        room_code="ROOM1",
        verified_user="verified-user",
        session_user="session-user",
    )

    response = _send_request(client, method, path, payload, {"Authorization": 'Token="valid-token"'})

    assert response.status_code != 401
