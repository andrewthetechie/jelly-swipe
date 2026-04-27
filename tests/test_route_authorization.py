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

    def fetch_deck(self, genre_name=None):
        """Return a list of 25 fake movie cards for deck testing."""
        return [
            {"id": f"movie-{i}", "title": f"Movie {i}", "summary": f"Summary {i}",
             "thumb": f"/proxy?path=jellyfin/movie-{i}/Primary",
             "rating": 7.0, "duration": "1h 30m", "year": 2024}
            for i in range(25)
        ]


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
    elif "/undo" in route:
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
    ("POST", "/room/ROOM1/swipe", {"movie_id": "movie-1", "direction": "right"}),
    ("GET", "/matches", None),
    ("POST", "/matches/delete", {"movie_id": "movie-1"}),
    ("POST", "/room/ROOM1/undo", {"movie_id": "movie-1"}),
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


# --- Mutation Route Authorization Tests ---


@pytest.mark.parametrize("method,path,payload", ROUTE_CASES)
@pytest.mark.parametrize("spoof_header", SPOOF_HEADERS)
def test_spoofed_headers_ignored_when_vault_authenticated(db_connection, client, method, path, payload, spoof_header):
    """Headers are ignored — vault identity is used regardless of what headers say."""
    _set_session(client, db_connection, active_room="ROOM1", authenticated=True)
    _prepare_route_state(db_connection, path, room_code="ROOM1",
                         verified_user="verified-user", session_user="verified-user")
    response = _send_request(client, method, path, payload, {spoof_header: "attacker-id"})
    assert response.status_code != 401  # spoofed headers don't cause 401 when vault is valid


def test_unauthenticated_swipe_no_side_effects(db_connection, client):
    """Without a vault entry, no side effects occur."""
    with client.session_transaction() as sess:
        sess["active_room"] = "ROOM1"
    _seed_room(db_connection, "ROOM1")
    before_swipes = db_connection.execute("SELECT COUNT(*) FROM swipes").fetchone()[0]
    response = client.post("/room/ROOM1/swipe", json={"movie_id": "movie-1", "direction": "right"})
    after_swipes = db_connection.execute("SELECT COUNT(*) FROM swipes").fetchone()[0]
    assert response.status_code == 401
    assert after_swipes == before_swipes


@pytest.mark.parametrize("method,path,payload", ROUTE_CASES)
def test_unauthenticated_returns_401(db_connection, client, method, path, payload):
    """No vault entry = 401 regardless of headers."""
    with client.session_transaction() as sess:
        sess["active_room"] = "ROOM1"
    _seed_room(db_connection, "ROOM1")
    response = _send_request(client, method, path, payload, {})
    assert response.status_code == 401
    assert response.get_json() == {"error": "Authentication required"}


@pytest.mark.parametrize("method,path,payload", ROUTE_CASES)
def test_authenticated_vault_identity_succeeds(db_connection, client, method, path, payload):
    _set_session(client, db_connection, active_room="ROOM1", authenticated=True)
    _prepare_route_state(db_connection, path, room_code="ROOM1",
                         verified_user="verified-user", session_user="verified-user")
    response = _send_request(client, method, path, payload, {})
    assert response.status_code != 401


# --- Deck Cursor Tracking Tests ---


def _setup_deck_session(client, db_connection, *, user_id="verified-user", token="valid-token"):
    """Set up an authenticated session and return the session_id."""
    import jellyswipe.db
    session_id = "test-session-" + secrets.token_hex(8)
    db_connection.execute(
        "INSERT INTO user_tokens (session_id, jellyfin_token, jellyfin_user_id, created_at) VALUES (?, ?, ?, ?)",
        (session_id, token, user_id, datetime.now(timezone.utc).isoformat())
    )
    db_connection.commit()
    with client.session_transaction() as sess:
        sess["session_id"] = session_id
    return session_id


def _create_room_with_auth(client):
    """Create a room and return the pairing code. Caller must set up auth first."""
    resp = client.post('/room')
    assert resp.status_code == 200
    return resp.json['pairing_code']


class TestDeckCursorTracking:
    """Tests for server-owned deck cursor tracking and pagination."""

    def test_deck_returns_cards_from_start(self, db_connection, client):
        """Create room, GET /room/{code}/deck returns non-empty card array."""
        _setup_deck_session(client, db_connection)
        code = _create_room_with_auth(client)

        resp = client.get(f'/room/{code}/deck')
        assert resp.status_code == 200
        cards = resp.get_json()
        assert isinstance(cards, list)
        assert len(cards) > 0

    def test_deck_paginated_20_cards(self, db_connection, client):
        """Deck endpoint returns at most 20 cards per page (25-card deck)."""
        _setup_deck_session(client, db_connection)
        code = _create_room_with_auth(client)

        resp = client.get(f'/room/{code}/deck')
        assert resp.status_code == 200
        cards = resp.get_json()
        assert len(cards) == 20  # 25 total, page 1 returns first 20

    def test_cursor_advances_on_swipe(self, db_connection, client):
        """After swiping, the next deck fetch starts from the next card."""
        _setup_deck_session(client, db_connection)
        code = _create_room_with_auth(client)

        # Get initial deck and note the first card
        resp = client.get(f'/room/{code}/deck')
        initial_cards = resp.get_json()
        first_card_id = initial_cards[0]['id']

        # Swipe on the first card
        resp = client.post(f'/room/{code}/swipe',
                           json={'movie_id': first_card_id, 'direction': 'left'})
        assert resp.status_code == 200

        # Get deck again — first card should be different (cursor advanced by 1)
        resp = client.get(f'/room/{code}/deck')
        new_cards = resp.get_json()
        assert new_cards[0]['id'] != first_card_id
        assert new_cards[0]['id'] == initial_cards[1]['id']

    def test_cursor_persists_across_requests(self, db_connection, client):
        """Cursor position persists across multiple requests."""
        _setup_deck_session(client, db_connection)
        code = _create_room_with_auth(client)

        # Swipe 3 times
        for i in range(3):
            resp = client.get(f'/room/{code}/deck')
            cards = resp.get_json()
            client.post(f'/room/{code}/swipe',
                        json={'movie_id': cards[0]['id'], 'direction': 'left'})

        # Fetch deck at position 3
        resp = client.get(f'/room/{code}/deck')
        cards_at_3 = resp.get_json()

        # Swipe 2 more times
        for i in range(2):
            resp = client.get(f'/room/{code}/deck')
            cards = resp.get_json()
            client.post(f'/room/{code}/swipe',
                        json={'movie_id': cards[0]['id'], 'direction': 'left'})

        # Fetch deck at position 5
        resp = client.get(f'/room/{code}/deck')
        cards_at_5 = resp.get_json()

        # Position 5 cards should be different from position 3 cards
        assert cards_at_5[0]['id'] != cards_at_3[0]['id']

    def test_genre_change_resets_cursor(self, db_connection, client):
        """Genre change resets cursor to position 0."""
        _setup_deck_session(client, db_connection)
        code = _create_room_with_auth(client)

        # Get the original first card
        resp = client.get(f'/room/{code}/deck')
        original_first = resp.get_json()[0]['id']

        # Swipe 2 times to advance cursor
        for i in range(2):
            resp = client.get(f'/room/{code}/deck')
            cards = resp.get_json()
            client.post(f'/room/{code}/swipe',
                        json={'movie_id': cards[0]['id'], 'direction': 'left'})

        # Verify cursor has advanced
        resp = client.get(f'/room/{code}/deck')
        assert resp.get_json()[0]['id'] != original_first

        # Change genre — resets cursor
        resp = client.post(f'/room/{code}/genre', json={'genre': 'Action'})
        assert resp.status_code == 200

        # Deck should start from position 0 again
        resp = client.get(f'/room/{code}/deck')
        cards = resp.get_json()
        assert cards[0]['id'] == original_first

    def test_join_initializes_cursor_at_zero(self, db_connection, client):
        """User B joining a room gets their own cursor starting at 0."""
        # User A creates room
        _setup_deck_session(client, db_connection, user_id="user-A", token="token-A")
        code = _create_room_with_auth(client)

        # Get original first card
        resp = client.get(f'/room/{code}/deck')
        original_first = resp.get_json()[0]['id']

        # User A swipes 3 times
        for i in range(3):
            resp = client.get(f'/room/{code}/deck')
            cards = resp.get_json()
            client.post(f'/room/{code}/swipe',
                        json={'movie_id': cards[0]['id'], 'direction': 'left'})

        # User B joins — set up separate session
        _setup_deck_session(client, db_connection, user_id="user-B", token="token-B")

        # User B joins the room
        resp = client.post(f'/room/{code}/join')
        assert resp.status_code == 200

        # User B gets deck starting from position 0 (their own cursor)
        resp = client.get(f'/room/{code}/deck')
        cards = resp.get_json()
        assert cards[0]['id'] == original_first

    def test_end_of_deck_returns_empty(self, db_connection, client):
        """After swiping all cards, deck endpoint returns empty array."""
        _setup_deck_session(client, db_connection)
        code = _create_room_with_auth(client)

        # Get the full deck to know how many cards (25 from FakeProvider)
        resp = client.get(f'/room/{code}/deck')
        first_page = resp.get_json()
        assert len(first_page) == 20

        # Swipe the first 20
        for card in first_page:
            client.post(f'/room/{code}/swipe',
                        json={'movie_id': card['id'], 'direction': 'left'})

        # Get remaining cards (page 1 at cursor=20)
        resp = client.get(f'/room/{code}/deck')
        remaining = resp.get_json()
        assert len(remaining) == 5  # 25 total - 20 swiped

        # Swipe the remaining 5
        for card in remaining:
            client.post(f'/room/{code}/swipe',
                        json={'movie_id': card['id'], 'direction': 'left'})

        # Now deck should be empty
        resp = client.get(f'/room/{code}/deck')
        assert resp.get_json() == []
