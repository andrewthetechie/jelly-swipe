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

    def server_info(self) -> dict:
        return {"machineIdentifier": "test-server-id", "name": "TestServer"}


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


# --- SSE Match Delivery Tests ---


def _seed_room_with_movies(conn, room_code="ROOM1", solo_mode=0):
    """Seed a room with movie data containing enriched metadata."""
    movies = [
        {"id": "movie-1", "title": "Test Movie", "summary": "A test movie",
         "thumb": "/proxy?path=jellyfin/movie-1/Primary",
         "rating": 8.5, "duration": "2h 15m", "year": 2024},
        {"id": "movie-2", "title": "Other Movie", "summary": "Another test",
         "thumb": "/proxy?path=jellyfin/movie-2/Primary",
         "rating": 6.0, "duration": "1h 45m", "year": 2023},
    ]
    conn.execute(
        "INSERT INTO rooms (pairing_code, movie_data, ready, current_genre, solo_mode) VALUES (?, ?, ?, ?, ?)",
        (room_code, json.dumps(movies), 1, "All", solo_mode),
    )
    conn.execute(
        "UPDATE rooms SET deck_position = ? WHERE pairing_code = ?",
        (json.dumps({"verified-user": 0}), room_code),
    )
    conn.commit()


class TestSSEMatchDelivery:
    """Tests for SSE-only match delivery, enriched metadata, deep links, and transaction safety."""

    def test_swipe_returns_accepted_only(self, db_connection, client):
        """POST /room/{code}/swipe returns {accepted: true} only — no match payload."""
        _set_session(client, db_connection, active_room="ROOM1", authenticated=True)
        _seed_room_with_movies(db_connection)

        resp = client.post('/room/ROOM1/swipe',
                           json={'movie_id': 'movie-1', 'direction': 'right'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data == {'accepted': True}
        assert 'match' not in data
        assert 'title' not in data
        assert 'thumb' not in data

    def test_swipe_no_match_returns_accepted(self, db_connection, client):
        """Left-swipe also returns {accepted: true}."""
        _set_session(client, db_connection, active_room="ROOM1", authenticated=True)
        _seed_room_with_movies(db_connection)

        resp = client.post('/room/ROOM1/swipe',
                           json={'movie_id': 'movie-1', 'direction': 'left'})
        assert resp.status_code == 200
        assert resp.get_json() == {'accepted': True}

    def test_match_created_with_deep_link(self, db_connection, client):
        """Two users right-swiping the same movie creates match with deep link."""
        _set_session(client, db_connection, active_room="ROOM1", authenticated=True)
        _seed_room_with_movies(db_connection)

        # First user swipes right
        client.post('/room/ROOM1/swipe',
                    json={'movie_id': 'movie-1', 'direction': 'right'})

        # Set up second user session
        _setup_deck_session(client, db_connection, user_id="user-B", token="token-B")
        with client.session_transaction() as sess:
            sess["active_room"] = "ROOM1"

        # Second user swipes right
        client.post('/room/ROOM1/swipe',
                    json={'movie_id': 'movie-1', 'direction': 'right'})

        # Verify match has deep link
        row = db_connection.execute(
            "SELECT deep_link FROM matches WHERE room_code = ? AND movie_id = ?",
            ("ROOM1", "movie-1"),
        ).fetchone()
        assert row is not None
        assert row["deep_link"] is not None
        assert "/web/#/details?id=movie-1" in row["deep_link"]

    def test_match_created_with_enriched_metadata(self, db_connection, client):
        """Solo match stores rating, duration, year from movie_data."""
        _set_session(client, db_connection, active_room="ROOM1", authenticated=True)
        _seed_room_with_movies(db_connection, solo_mode=1)

        resp = client.post('/room/ROOM1/swipe',
                           json={'movie_id': 'movie-1', 'direction': 'right'})
        assert resp.status_code == 200

        row = db_connection.execute(
            "SELECT rating, duration, year FROM matches WHERE room_code = ? AND movie_id = ?",
            ("ROOM1", "movie-1"),
        ).fetchone()
        assert row is not None
        assert row["rating"] == "8.5"
        assert row["duration"] == "2h 15m"
        assert row["year"] == "2024"

    def test_get_matches_returns_enriched_fields(self, db_connection, client):
        """GET /matches includes deep_link, rating, duration, year."""
        _set_session(client, db_connection, active_room="ROOM1", authenticated=True)
        _seed_room_with_movies(db_connection, solo_mode=1)

        client.post('/room/ROOM1/swipe',
                    json={'movie_id': 'movie-1', 'direction': 'right'})

        resp = client.get('/matches')
        assert resp.status_code == 200
        matches = resp.get_json()
        assert len(matches) == 1
        m = matches[0]
        assert "deep_link" in m
        assert m["deep_link"] is not None
        assert "rating" in m
        assert m["rating"] == "8.5"
        assert "duration" in m
        assert m["duration"] == "2h 15m"
        assert "year" in m
        assert m["year"] == "2024"

    def test_last_match_data_includes_enriched_payload(self, db_connection, client):
        """After a match, rooms.last_match_data contains full enriched JSON."""
        _set_session(client, db_connection, active_room="ROOM1", authenticated=True)
        _seed_room_with_movies(db_connection, solo_mode=1)

        client.post('/room/ROOM1/swipe',
                    json={'movie_id': 'movie-1', 'direction': 'right'})

        row = db_connection.execute(
            "SELECT last_match_data FROM rooms WHERE pairing_code = ?",
            ("ROOM1",),
        ).fetchone()
        assert row["last_match_data"] is not None
        data = json.loads(row["last_match_data"])
        assert data["type"] == "match"
        assert data["title"] == "Movie-movie-1"
        assert data["movie_id"] == "movie-1"
        assert data["rating"] == "8.5"
        assert data["duration"] == "2h 15m"
        assert data["year"] == "2024"
        assert "/web/#/details?id=movie-1" in data["deep_link"]
        assert "ts" in data

    def test_concurrent_right_swipes_one_match_per_user(self, db_connection, client):
        """Two users right-swiping same movie produces exactly 1 match row per user."""
        _set_session(client, db_connection, active_room="ROOM1", authenticated=True)
        _seed_room_with_movies(db_connection)

        # First user swipes right
        client.post('/room/ROOM1/swipe',
                    json={'movie_id': 'movie-1', 'direction': 'right'})

        # Second user
        _setup_deck_session(client, db_connection, user_id="user-B", token="token-B")
        with client.session_transaction() as sess:
            sess["active_room"] = "ROOM1"

        # Second user swipes right
        client.post('/room/ROOM1/swipe',
                    json={'movie_id': 'movie-1', 'direction': 'right'})

        # Exactly 2 match rows: one per user (INSERT OR IGNORE prevents duplicates)
        count = db_connection.execute(
            "SELECT COUNT(*) FROM matches WHERE room_code = ? AND movie_id = ?",
            ("ROOM1", "movie-1"),
        ).fetchone()[0]
        assert count == 2

        # Each user has exactly one match
        user_a = db_connection.execute(
            "SELECT COUNT(*) FROM matches WHERE room_code = ? AND movie_id = ? AND user_id = ?",
            ("ROOM1", "movie-1", "verified-user"),
        ).fetchone()[0]
        assert user_a == 1

        user_b = db_connection.execute(
            "SELECT COUNT(*) FROM matches WHERE room_code = ? AND movie_id = ? AND user_id = ?",
            ("ROOM1", "movie-1", "user-B"),
        ).fetchone()[0]
        assert user_b == 1


# --- GET /me Endpoint Tests ---


class TestGetMe:
    """Tests for GET /me identity endpoint (API-03)."""

    def test_get_me_returns_user_info(self, db_connection, client):
        """Authenticated GET /me returns userId, displayName, serverName, serverId."""
        _set_session(client, db_connection, authenticated=True)

        resp = client.get('/me')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['userId'] == 'verified-user'
        assert data['displayName'] == 'verified-user'
        assert data['serverName'] == 'TestServer'
        assert data['serverId'] == 'test-server-id'

    def test_get_me_requires_auth(self, db_connection, client):
        """Unauthenticated GET /me returns 401."""
        resp = client.get('/me')
        assert resp.status_code == 401
        assert resp.get_json() == {'error': 'Authentication required'}


# --- Solo Room Endpoint Tests ---


class TestSoloRoom:
    """Tests for POST /room/solo endpoint (API-04)."""

    def test_solo_room_creation(self, db_connection, client):
        """POST /room/solo creates solo room with ready=1 and solo_mode=1."""
        _setup_deck_session(client, db_connection)

        resp = client.post('/room/solo')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'pairing_code' in data
        code = data['pairing_code']
        assert len(code) == 4

        # Verify room state in DB
        row = db_connection.execute(
            "SELECT ready, solo_mode FROM rooms WHERE pairing_code = ?",
            (code,),
        ).fetchone()
        assert row['ready'] == 1
        assert row['solo_mode'] == 1

    def test_solo_room_deck_cursor_initialized(self, db_connection, client):
        """Solo room initializes deck cursor for creator at position 0."""
        _setup_deck_session(client, db_connection)

        resp = client.post('/room/solo')
        code = resp.get_json()['pairing_code']

        row = db_connection.execute(
            "SELECT deck_position FROM rooms WHERE pairing_code = ?",
            (code,),
        ).fetchone()
        positions = json.loads(row['deck_position'])
        assert 'verified-user' in positions
        assert positions['verified-user'] == 0

    def test_solo_room_sets_session(self, db_connection, client):
        """POST /room/solo sets session active_room and solo_mode=True."""
        _setup_deck_session(client, db_connection)

        resp = client.post('/room/solo')
        code = resp.get_json()['pairing_code']

        with client.session_transaction() as sess:
            assert sess['active_room'] == code
            assert sess['solo_mode'] is True

    def test_solo_room_requires_auth(self, db_connection, client):
        """Unauthenticated POST /room/solo returns 401."""
        resp = client.post('/room/solo')
        assert resp.status_code == 401
        assert resp.get_json() == {'error': 'Authentication required'}


# --- Logout Endpoint Tests ---


class TestLogout:
    """Tests for POST /auth/logout endpoint (CLNT-01)."""

    def test_logout_clears_vault(self, db_connection, client):
        """POST /auth/logout removes session_id from user_tokens vault."""
        _set_session(client, db_connection, active_room="ROOM1", authenticated=True)
        # Verify vault entry exists before logout
        count = db_connection.execute("SELECT COUNT(*) FROM user_tokens").fetchone()[0]
        assert count >= 1

        resp = client.post('/auth/logout')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'logged_out'

        # Verify vault entry was removed
        count = db_connection.execute("SELECT COUNT(*) FROM user_tokens").fetchone()[0]
        assert count == 0

    def test_logout_clears_session_cookie(self, db_connection, client):
        """POST /auth/logout clears session_id from session cookie."""
        _set_session(client, db_connection, active_room="ROOM1", authenticated=True)
        # Verify session is set
        with client.session_transaction() as sess:
            assert sess.get('session_id') is not None

        resp = client.post('/auth/logout')
        assert resp.status_code == 200

        # Verify session_id is cleared
        with client.session_transaction() as sess:
            assert sess.get('session_id') is None

    def test_logout_requires_auth(self, db_connection, client):
        """POST /auth/logout without authentication returns 401."""
        resp = client.post('/auth/logout')
        assert resp.status_code == 401
        assert resp.get_json() == {'error': 'Authentication required'}


# --- GET /me activeRoom Tests ---


class TestGetMeActiveRoom:
    """Tests for GET /me activeRoom field."""

    def test_me_includes_active_room_null(self, db_connection, client):
        """GET /me returns activeRoom as null when no room active."""
        _set_session(client, db_connection, active_room="ROOM1", authenticated=True)
        # Remove active_room from session
        with client.session_transaction() as sess:
            sess.pop('active_room', None)

        resp = client.get('/me')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'activeRoom' in data
        assert data['activeRoom'] is None

    def test_me_includes_active_room_code(self, db_connection, client):
        """GET /me returns activeRoom with room code when room active."""
        _set_session(client, db_connection, active_room="ROOM1", authenticated=True)

        resp = client.get('/me')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'activeRoom' in data
        assert data['activeRoom'] == 'ROOM1'


# --- Go-Solo Route Removal Test ---


class TestGoSoloRemoved:
    """Tests that /room/<code>/go-solo route has been removed."""

    def test_go_solo_returns_404(self, db_connection, client):
        """POST /room/<code>/go-solo returns 404 (route removed)."""
        _set_session(client, db_connection, active_room="ROOM1", authenticated=True)
        _seed_room(db_connection, "ROOM1")

        resp = client.post('/room/ROOM1/go-solo')
        assert resp.status_code == 404


# --- Phase 27 Compliance Tests ---


class TestPhase27Compliance:
    """Integration verification tests for Phase 27 (CLNT-01 and CLNT-02 compliance)."""

    def test_auth_lifecycle(self, db_connection, client):
        """Full auth lifecycle: delegate login -> GET /me (200) -> logout -> GET /me (401)."""
        # Step 1: Login via delegate
        resp = client.post('/auth/jellyfin-use-server-identity')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'userId' in data

        # Step 2: GET /me returns 200 with user info
        resp = client.get('/me')
        assert resp.status_code == 200
        me_data = resp.get_json()
        assert me_data['userId'] == 'verified-user'

        # Step 3: POST /auth/logout clears session
        resp = client.post('/auth/logout')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'logged_out'

        # Step 4: GET /me now returns 401
        resp = client.get('/me')
        assert resp.status_code == 401

    def test_swipe_no_match_in_response(self, db_connection, client):
        """Swipe returns {accepted: true} only — no match field (CLNT-02)."""
        _set_session(client, db_connection, active_room="ROOM1", authenticated=True)
        _seed_room_with_movies(db_connection)

        resp = client.post('/room/ROOM1/swipe',
                           json={'movie_id': 'movie-1', 'direction': 'right'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data == {'accepted': True}
        assert 'match' not in data
        assert 'title' not in data
        assert 'thumb' not in data
        assert 'solo' not in data

    def test_sse_match_has_enriched_fields(self, db_connection, client):
        """Two-player match via /room/{code}/status has deep_link, rating, duration, year."""
        _set_session(client, db_connection, active_room="ROOM1", authenticated=True)
        _seed_room_with_movies(db_connection)

        # First user swipes right
        client.post('/room/ROOM1/swipe',
                     json={'movie_id': 'movie-1', 'direction': 'right'})

        # Second user
        _setup_deck_session(client, db_connection, user_id="user-B", token="token-B")
        with client.session_transaction() as sess:
            sess["active_room"] = "ROOM1"

        # Second user swipes right — creates match
        client.post('/room/ROOM1/swipe',
                     json={'movie_id': 'movie-1', 'direction': 'right'})

        # Check room status for enriched match data
        resp = client.get('/room/ROOM1/status')
        assert resp.status_code == 200
        status = resp.get_json()
        assert status['last_match'] is not None
        match = status['last_match']
        assert match['type'] == 'match'
        assert 'title' in match
        assert 'thumb' in match
        assert 'movie_id' in match
        assert 'deep_link' in match
        assert '/web/#/details?id=movie-1' in match['deep_link']
        assert match['rating'] == '8.5'
        assert match['duration'] == '2h 15m'
        assert match['year'] == '2024'
        assert 'ts' in match

    def test_solo_endpoint_not_go_solo(self, db_connection, client):
        """POST /room/solo creates solo room (200), POST /room/{code}/go-solo returns 404."""
        _setup_deck_session(client, db_connection)

        # POST /room/solo works
        resp = client.post('/room/solo')
        assert resp.status_code == 200
        code = resp.get_json()['pairing_code']

        # Old route returns 404
        resp = client.post(f'/room/{code}/go-solo')
        assert resp.status_code == 404

    def test_me_returns_active_room(self, db_connection, client):
        """GET /me tracks activeRoom: null -> code -> null after quit."""
        _setup_deck_session(client, db_connection)

        # Before room: activeRoom is null
        resp = client.get('/me')
        assert resp.status_code == 200
        assert resp.get_json()['activeRoom'] is None

        # Create room: activeRoom becomes pairing code
        resp = client.post('/room')
        assert resp.status_code == 200
        code = resp.get_json()['pairing_code']

        resp = client.get('/me')
        assert resp.status_code == 200
        assert resp.get_json()['activeRoom'] == code

        # Quit room: activeRoom becomes null
        resp = client.post(f'/room/{code}/quit')
        assert resp.status_code == 200

        resp = client.get('/me')
        assert resp.status_code == 200
        assert resp.get_json()['activeRoom'] is None
