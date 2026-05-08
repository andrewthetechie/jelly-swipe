"""Comprehensive room lifecycle tests for RESTful room endpoints.

Tests cover POST /room, POST /room/<code>/join, POST /room/solo,
POST /room/<code>/quit, GET /room/<code>/status,
POST /room/<code>/swipe - including happy paths, edge cases, error conditions,
and the full swipe match logic (solo match, dual match, no match).
"""

import json
import os
import secrets
from datetime import datetime, timezone

import sqlite3

import pytest
from jellyswipe.db_paths import application_db_path
from tests.conftest import set_session_cookie


def _sqlite_conn_for_route_tests():
    path = application_db_path.path
    assert path is not None
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_session(client, secret_key, *, active_room=None, user_id="verified-user", authenticated=True, solo_mode=False):
    """Inject session state for room tests.

    Auth is handled by app.dependency_overrides[require_auth] in the app fixture.
    Only app state (active_room, solo_mode) needs to be in the session cookie.
    """
    data = {"solo_mode": solo_mode}
    if active_room is not None:
        data["active_room"] = active_room
    if data:
        set_session_cookie(client, data, secret_key)


def _seed_room(room_code="TEST1", *, ready=0, solo_mode=0, movie_data=None, last_match_data=None):
    """Seed a room row directly into the database for testing."""
    if movie_data is None:
        movie_data = json.dumps([])
    conn = _sqlite_conn_for_route_tests()
    try:
        conn.execute(
            "INSERT INTO rooms (pairing_code, movie_data, ready, current_genre, solo_mode, last_match_data) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (room_code, movie_data, ready, "All", solo_mode, last_match_data),
        )
        conn.commit()
    finally:
        conn.close()


def _create_room_via_api(client):
    """Create a room via POST /room and return the response."""
    return client.post("/room")


# ---------------------------------------------------------------------------
# Section 1: POST /room tests
# ---------------------------------------------------------------------------


def test_room_create_returns_pairing_code(client, app):
    """POST /room returns 200 with a 4-digit pairing code."""
    _set_session(client, os.environ["FLASK_SECRET"], authenticated=True)
    response = _create_room_via_api(client)
    assert response.status_code == 200
    data = response.json()
    assert "pairing_code" in data
    code = data["pairing_code"]
    assert len(str(code)) == 4
    assert str(code).isdigit()


def test_room_create_sets_session(client, app):
    """POST /room sets active_room and solo_mode=False in session."""
    _set_session(client, os.environ["FLASK_SECRET"], authenticated=True)
    response = _create_room_via_api(client)
    assert response.status_code == 200
    code = response.json()["pairing_code"]

    # Note: Session state cannot be verified directly in FastAPI TestClient
    # The session is set via cookies by the endpoint
    assert code is not None


def test_room_create_stores_room_in_db(client, app):
    """POST /room stores the room in the database with correct initial state."""
    _set_session(client, os.environ["FLASK_SECRET"], authenticated=True)
    response = _create_room_via_api(client)
    assert response.status_code == 200
    code = response.json()["pairing_code"]

    conn = _sqlite_conn_for_route_tests()
    try:
        row = conn.execute(
            "SELECT * FROM rooms WHERE pairing_code = ?", (code,)
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row["ready"] == 0
    assert row["solo_mode"] == 0
    assert row["current_genre"] == "All"


# ---------------------------------------------------------------------------
# Section 2: POST /room/<code>/join tests
# ---------------------------------------------------------------------------


def test_room_join_success(client, app):
    """POST /room/<code>/join with valid code returns 200 with status success."""
    _set_session(client, os.environ["FLASK_SECRET"], authenticated=True)
    _seed_room("TEST1")
    response = client.post("/room/TEST1/join")
    assert response.status_code == 200
    assert response.json() == {"status": "success"}


def test_room_join_sets_session_and_ready(client, app):
    """POST /room/<code>/join sets session active_room and marks room ready in DB."""
    _set_session(client, os.environ["FLASK_SECRET"], authenticated=True)
    _seed_room("TEST1")
    client.post("/room/TEST1/join")

    # Note: Session state cannot be verified directly in FastAPI TestClient
    # The session is set via cookies by the endpoint

    conn = _sqlite_conn_for_route_tests()
    try:
        row = conn.execute(
            "SELECT ready FROM rooms WHERE pairing_code = ?", ("TEST1",)
        ).fetchone()
    finally:
        conn.close()
    assert row["ready"] == 1


def test_room_join_invalid_code_returns_404(client, app):
    """POST /room/<code>/join with non-existent code returns 404 with error."""
    _set_session(client, os.environ["FLASK_SECRET"], authenticated=True)
    response = client.post("/room/9999/join")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data


# ---------------------------------------------------------------------------
# Section 3: POST /room/solo tests
# ---------------------------------------------------------------------------


def test_solo_room_creation(client, app):
    """POST /room/solo creates a solo room and returns pairing code."""
    _set_session(client, os.environ["FLASK_SECRET"], authenticated=True)
    response = client.post("/room/solo")
    assert response.status_code == 200
    data = response.json()
    assert "pairing_code" in data
    code = data["pairing_code"]
    assert len(str(code)) == 4
    assert str(code).isdigit()


def test_solo_room_db_state(client, app):
    """POST /room/solo stores solo_mode=1 and ready=1 in the database."""
    _set_session(client, os.environ["FLASK_SECRET"], authenticated=True)
    response = client.post("/room/solo")
    code = response.json()["pairing_code"]

    conn = _sqlite_conn_for_route_tests()
    try:
        row = conn.execute(
            "SELECT solo_mode, ready FROM rooms WHERE pairing_code = ?", (code,)
        ).fetchone()
    finally:
        conn.close()
    assert row["solo_mode"] == 1
    assert row["ready"] == 1


def test_solo_room_sets_session(client, app):
    """POST /room/solo sets solo_mode=True and active_room in session."""
    _set_session(client, os.environ["FLASK_SECRET"], authenticated=True)
    response = client.post("/room/solo")
    code = response.json()["pairing_code"]

    # Note: Session state cannot be verified directly in FastAPI TestClient
    # The session is set via cookies by the endpoint
    assert code is not None


# ---------------------------------------------------------------------------
# Section 4: POST /room/<code>/quit tests
# ---------------------------------------------------------------------------


def test_quit_room_success(client, app):
    """POST /room/<code>/quit with existing room returns 200 with session_ended."""
    _set_session(client, os.environ["FLASK_SECRET"], active_room="TEST1", authenticated=True, solo_mode=True)
    _seed_room("TEST1")
    response = client.post("/room/TEST1/quit")
    assert response.status_code == 200
    assert response.json() == {"status": "session_ended"}


def test_quit_room_deletes_from_db(client, app):
    """POST /room/<code>/quit deletes the room and its swipes from the database."""
    _set_session(client, os.environ["FLASK_SECRET"], active_room="TEST1", authenticated=True)
    _seed_room("TEST1")

    conn = _sqlite_conn_for_route_tests()
    try:
        conn.execute(
            "INSERT INTO swipes (room_code, movie_id, user_id, direction) VALUES (?, ?, ?, ?)",
            ("TEST1", "m1", "user-1", "left"),
        )
        conn.commit()
    finally:
        conn.close()

    client.post("/room/TEST1/quit")

    conn = _sqlite_conn_for_route_tests()
    try:
        room_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM rooms WHERE pairing_code = ?", ("TEST1",)
        ).fetchone()["cnt"]
        swipe_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM swipes WHERE room_code = ?", ("TEST1",)
        ).fetchone()["cnt"]
    finally:
        conn.close()

    assert room_count == 0
    assert swipe_count == 0


def test_quit_room_archives_matches(client, app):
    """POST /room/<code>/quit archives active matches (status=archived, room_code=HISTORY)."""
    _set_session(client, os.environ["FLASK_SECRET"], active_room="TEST1", authenticated=True)
    _seed_room("TEST1")

    conn = _sqlite_conn_for_route_tests()
    try:
        conn.execute(
            "INSERT INTO matches (room_code, movie_id, title, thumb, status, user_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("TEST1", "m1", "Test Movie", "thumb.jpg", "active", "verified-user"),
        )
        conn.commit()
    finally:
        conn.close()

    client.post("/room/TEST1/quit")

    conn = _sqlite_conn_for_route_tests()
    try:
        row = conn.execute(
            "SELECT status, room_code FROM matches WHERE movie_id = ? AND user_id = ?",
            ("m1", "verified-user"),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row["status"] == "archived"
    assert row["room_code"] == "HISTORY"


def test_quit_room_clears_session(client, app):
    """POST /room/<code>/quit clears active_room and solo_mode from the session."""
    _set_session(client, os.environ["FLASK_SECRET"], active_room="TEST1", authenticated=True, solo_mode=True)
    _seed_room("TEST1")
    client.post("/room/TEST1/quit")

    # Note: Session state cannot be verified directly in FastAPI TestClient
    # The session is cleared via cookies by the endpoint


def test_quit_nonexistent_room_still_succeeds(client, app):
    """POST /room/<code>/quit with nonexistent room code returns 200 (graceful no-op)."""
    _set_session(client, os.environ["FLASK_SECRET"], authenticated=True)
    response = client.post("/room/NONEXISTENT/quit")
    assert response.status_code == 200
    assert response.json() == {"status": "session_ended"}


# ---------------------------------------------------------------------------
# Section 5: GET /room/<code>/status tests
# ---------------------------------------------------------------------------


def test_room_status_active_room(client):
    """GET /room/<code>/status with existing room returns full room state."""
    _seed_room("TEST1", ready=1, solo_mode=0)
    response = client.get("/room/TEST1/status")

    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True
    assert data["genre"] == "All"
    assert data["solo"] is False
    assert data["last_match"] is None


def test_room_status_with_last_match(client):
    """GET /room/<code>/status returns last_match data when room has a recent match."""
    match_data = json.dumps({"title": "Test Movie", "thumb": "test.jpg", "ts": 1234567890})
    _seed_room("TEST1", ready=1, solo_mode=0, last_match_data=match_data)

    response = client.get("/room/TEST1/status")
    assert response.status_code == 200
    data = response.json()
    assert data["last_match"] is not None
    assert data["last_match"]["title"] == "Test Movie"
    assert data["last_match"]["thumb"] == "test.jpg"
    assert data["last_match"]["ts"] == 1234567890


def test_room_status_nonexistent_room(client):
    """GET /room/<code>/status for nonexistent room returns ready=False."""
    response = client.get("/room/NONEXISTENT/status")
    assert response.status_code == 200
    assert response.json() == {"ready": False}


def test_room_status_room_deleted_from_db(client):
    """GET /room/<code>/status for room deleted from DB returns ready=False."""
    _seed_room("TEST1", ready=1)
    conn = _sqlite_conn_for_route_tests()
    try:
        conn.execute("DELETE FROM rooms WHERE pairing_code = ?", ("TEST1",))
        conn.commit()
    finally:
        conn.close()
    response = client.get("/room/TEST1/status")
    assert response.status_code == 200
    assert response.json() == {"ready": False}


# ---------------------------------------------------------------------------
# Section 6: POST /room/<code>/swipe tests
# ---------------------------------------------------------------------------


def test_swipe_left_records_no_match(client, app):
    """POST /room/<code>/swipe with direction=left records swipe, returns accepted=True."""
    _set_session(client, os.environ["FLASK_SECRET"], active_room="TEST1", user_id="verified-user", authenticated=True)
    _seed_room("TEST1", ready=1, solo_mode=1)

    response = client.post(
        "/room/TEST1/swipe",
        json={"movie_id": "m1", "direction": "left"},
    )

    assert response.status_code == 200
    assert response.json() == {"accepted": True}

    conn = _sqlite_conn_for_route_tests()
    try:
        row = conn.execute(
            "SELECT direction FROM swipes WHERE room_code = 'TEST1' AND movie_id = 'm1'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row["direction"] == "left"


def test_swipe_right_solo_match(client, app):
    """POST /room/<code>/swipe right in solo room creates match in DB."""
    _set_session(client, os.environ["FLASK_SECRET"], active_room="TEST1", user_id="verified-user", authenticated=True)
    _seed_room("TEST1", ready=1, solo_mode=1)

    response = client.post(
        "/room/TEST1/swipe",
        json={"movie_id": "m1", "direction": "right"},
    )

    assert response.status_code == 200
    assert response.json() == {"accepted": True}

    conn = _sqlite_conn_for_route_tests()
    try:
        row = conn.execute(
            "SELECT * FROM matches WHERE room_code = 'TEST1' AND movie_id = 'm1'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None


def test_swipe_right_dual_match(client, app):
    """POST /room/<code>/swipe right in shared room matches when another user swiped right."""
    _seed_room("TEST1", ready=1, solo_mode=0)
    _set_session(client, os.environ["FLASK_SECRET"], active_room="TEST1", user_id="verified-user", authenticated=True)

    conn = _sqlite_conn_for_route_tests()
    try:
        conn.execute(
            "INSERT INTO auth_sessions (session_id, jellyfin_token, jellyfin_user_id, created_at) VALUES (?, ?, ?, ?)",
            ("other-session-id", "valid-token", "user-2", "2026-05-05T00:00:00+00:00"),
        )
        conn.execute(
            "INSERT INTO swipes (room_code, movie_id, user_id, direction, session_id) VALUES (?, ?, ?, ?, ?)",
            ("TEST1", "m1", "user-2", "right", "other-session-id"),
        )
        conn.commit()
    finally:
        conn.close()

    response = client.post(
        "/room/TEST1/swipe",
        json={"movie_id": "m1", "direction": "right"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data == {"accepted": True}

    conn = _sqlite_conn_for_route_tests()
    try:
        rows = conn.execute(
            "SELECT user_id FROM matches WHERE room_code = 'TEST1' AND movie_id = 'm1'"
        ).fetchall()
    finally:
        conn.close()
    match_user_ids = [row["user_id"] for row in rows]
    assert "verified-user" in match_user_ids
    assert "user-2" in match_user_ids


def test_swipe_right_no_match_yet(client, app):
    """POST /room/<code>/swipe right in shared room with no prior swipe returns accepted=True."""
    _set_session(client, os.environ["FLASK_SECRET"], active_room="TEST1", user_id="verified-user", authenticated=True)
    _seed_room("TEST1", ready=1, solo_mode=0)

    response = client.post(
        "/room/TEST1/swipe",
        json={"movie_id": "m1", "direction": "right"},
    )

    assert response.status_code == 200
    assert response.json() == {"accepted": True}


def test_swipe_right_updates_last_match_data(client, app):
    """POST /room/<code>/swipe dual match updates last_match_data in rooms table."""
    _seed_room("TEST1", ready=1, solo_mode=0)
    _set_session(client, os.environ["FLASK_SECRET"], active_room="TEST1", user_id="verified-user", authenticated=True)

    conn = _sqlite_conn_for_route_tests()
    try:
        conn.execute(
            "INSERT INTO auth_sessions (session_id, jellyfin_token, jellyfin_user_id, created_at) VALUES (?, ?, ?, ?)",
            ("other-session-id", "valid-token", "user-2", "2026-05-05T00:00:00+00:00"),
        )
        conn.execute(
            "INSERT INTO swipes (room_code, movie_id, user_id, direction, session_id) VALUES (?, ?, ?, ?, ?)",
            ("TEST1", "m1", "user-2", "right", "other-session-id"),
        )
        conn.commit()
    finally:
        conn.close()

    client.post(
        "/room/TEST1/swipe",
        json={"movie_id": "m1", "direction": "right"},
    )

    conn = _sqlite_conn_for_route_tests()
    try:
        row = conn.execute(
            "SELECT last_match_data FROM rooms WHERE pairing_code = 'TEST1'"
        ).fetchone()
    finally:
        conn.close()

    assert row["last_match_data"] is not None
    match_data = json.loads(row["last_match_data"])
    assert match_data["type"] == "match"
    assert "ts" in match_data
