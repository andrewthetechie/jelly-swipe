"""Comprehensive room lifecycle tests for RESTful room endpoints.

Tests cover POST /room, POST /room/<code>/join, POST /room/solo,
POST /room/<code>/quit, GET /room/<code>/status,
POST /room/<code>/swipe - including happy paths, edge cases, error conditions,
and the full swipe match logic (solo match, dual match, no match).
"""

import json
import secrets
from datetime import datetime, timezone

import jellyswipe.db
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_session(client, *, active_room=None, user_id="verified-user", authenticated=True, solo_mode=False):
    """Set up session with vault-based authentication for room route tests.

    When authenticated=True, creates a vault entry in user_tokens and sets
    session_id in the session cookie. When authenticated=False, only sets
    non-auth session variables (for testing 401 responses).
    """
    with client.session_transaction() as sess:
        if active_room is not None:
            sess["active_room"] = active_room
        sess["solo_mode"] = solo_mode

    if authenticated:
        session_id = "test-session-" + secrets.token_hex(8)
        conn = jellyswipe.db.get_db()
        conn.execute(
            "INSERT INTO user_tokens (session_id, jellyfin_token, jellyfin_user_id, created_at) VALUES (?, ?, ?, ?)",
            (session_id, "valid-token", user_id, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        conn.close()
        with client.session_transaction() as sess:
            sess["session_id"] = session_id


def _seed_room(db_path, room_code="TEST1", *, ready=0, solo_mode=0, movie_data=None, last_match_data=None):
    """Seed a room row directly into the database for testing."""
    if movie_data is None:
        movie_data = json.dumps([])
    conn = jellyswipe.db.get_db()
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


def test_room_create_returns_pairing_code(client):
    """POST /room returns 200 with a 4-digit pairing code."""
    _set_session(client, authenticated=True)
    response = _create_room_via_api(client)
    assert response.status_code == 200
    data = response.get_json()
    assert "pairing_code" in data
    code = data["pairing_code"]
    assert len(str(code)) == 4
    assert str(code).isdigit()


def test_room_create_sets_session(client):
    """POST /room sets active_room and solo_mode=False in session."""
    _set_session(client, authenticated=True)
    response = _create_room_via_api(client)
    assert response.status_code == 200
    code = response.get_json()["pairing_code"]

    with client.session_transaction() as sess:
        assert sess["active_room"] == code
        assert sess["solo_mode"] is False


def test_room_create_stores_room_in_db(client):
    """POST /room stores the room in the database with correct initial state."""
    _set_session(client, authenticated=True)
    response = _create_room_via_api(client)
    assert response.status_code == 200
    code = response.get_json()["pairing_code"]

    conn = jellyswipe.db.get_db()
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


def test_room_create_requires_auth(client):
    """POST /room without authentication returns 401."""
    response = client.post("/room")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Section 2: POST /room/<code>/join tests
# ---------------------------------------------------------------------------


def test_room_join_success(client):
    """POST /room/<code>/join with valid code returns 200 with status success."""
    _set_session(client, authenticated=True)
    _seed_room(None, "TEST1")
    response = client.post("/room/TEST1/join")
    assert response.status_code == 200
    assert response.get_json() == {"status": "success"}


def test_room_join_sets_session_and_ready(client):
    """POST /room/<code>/join sets session active_room and marks room ready in DB."""
    _set_session(client, authenticated=True)
    _seed_room(None, "TEST1")
    client.post("/room/TEST1/join")

    with client.session_transaction() as sess:
        assert sess["active_room"] == "TEST1"
        assert sess["solo_mode"] is False

    conn = jellyswipe.db.get_db()
    try:
        row = conn.execute(
            "SELECT ready FROM rooms WHERE pairing_code = ?", ("TEST1",)
        ).fetchone()
    finally:
        conn.close()
    assert row["ready"] == 1


def test_room_join_invalid_code_returns_404(client):
    """POST /room/<code>/join with non-existent code returns 404 with error."""
    _set_session(client, authenticated=True)
    response = client.post("/room/9999/join")
    assert response.status_code == 404
    data = response.get_json()
    assert "error" in data


# ---------------------------------------------------------------------------
# Section 3: POST /room/solo tests
# ---------------------------------------------------------------------------


def test_solo_room_creation(client):
    """POST /room/solo creates a solo room and returns pairing code."""
    _set_session(client, authenticated=True)
    response = client.post("/room/solo")
    assert response.status_code == 200
    data = response.get_json()
    assert "pairing_code" in data
    code = data["pairing_code"]
    assert len(str(code)) == 4
    assert str(code).isdigit()


def test_solo_room_db_state(client):
    """POST /room/solo stores solo_mode=1 and ready=1 in the database."""
    _set_session(client, authenticated=True)
    response = client.post("/room/solo")
    code = response.get_json()["pairing_code"]

    conn = jellyswipe.db.get_db()
    try:
        row = conn.execute(
            "SELECT solo_mode, ready FROM rooms WHERE pairing_code = ?", (code,)
        ).fetchone()
    finally:
        conn.close()
    assert row["solo_mode"] == 1
    assert row["ready"] == 1


def test_solo_room_requires_auth(client):
    """POST /room/solo without authentication returns 401."""
    response = client.post("/room/solo")
    assert response.status_code == 401


def test_solo_room_sets_session(client):
    """POST /room/solo sets solo_mode=True and active_room in session."""
    _set_session(client, authenticated=True)
    response = client.post("/room/solo")
    code = response.get_json()["pairing_code"]

    with client.session_transaction() as sess:
        assert sess["active_room"] == code
        assert sess["solo_mode"] is True


# ---------------------------------------------------------------------------
# Section 4: POST /room/<code>/quit tests
# ---------------------------------------------------------------------------


def test_quit_room_success(client):
    """POST /room/<code>/quit with existing room returns 200 with session_ended."""
    _set_session(client, active_room="TEST1", authenticated=True, solo_mode=True)
    _seed_room(None, "TEST1")
    response = client.post("/room/TEST1/quit")
    assert response.status_code == 200
    assert response.get_json() == {"status": "session_ended"}


def test_quit_room_deletes_from_db(client):
    """POST /room/<code>/quit deletes the room and its swipes from the database."""
    _set_session(client, active_room="TEST1", authenticated=True)
    _seed_room(None, "TEST1")

    conn = jellyswipe.db.get_db()
    try:
        conn.execute(
            "INSERT INTO swipes (room_code, movie_id, user_id, direction) VALUES (?, ?, ?, ?)",
            ("TEST1", "m1", "user-1", "left"),
        )
        conn.commit()
    finally:
        conn.close()

    client.post("/room/TEST1/quit")

    conn = jellyswipe.db.get_db()
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


def test_quit_room_archives_matches(client):
    """POST /room/<code>/quit archives active matches (status=archived, room_code=HISTORY)."""
    _set_session(client, active_room="TEST1", authenticated=True)
    _seed_room(None, "TEST1")

    conn = jellyswipe.db.get_db()
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

    conn = jellyswipe.db.get_db()
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


def test_quit_room_clears_session(client):
    """POST /room/<code>/quit clears active_room and solo_mode from the session."""
    _set_session(client, active_room="TEST1", authenticated=True, solo_mode=True)
    _seed_room(None, "TEST1")
    client.post("/room/TEST1/quit")

    with client.session_transaction() as sess:
        assert sess.get("active_room") is None
        assert sess.get("solo_mode") is None


def test_quit_nonexistent_room_still_succeeds(client):
    """POST /room/<code>/quit with nonexistent room code returns 200 (graceful no-op)."""
    _set_session(client, authenticated=True)
    response = client.post("/room/NONEXISTENT/quit")
    assert response.status_code == 200
    assert response.get_json() == {"status": "session_ended"}


# ---------------------------------------------------------------------------
# Section 5: GET /room/<code>/status tests
# ---------------------------------------------------------------------------


def test_room_status_active_room(client):
    """GET /room/<code>/status with existing room returns full room state."""
    _seed_room(None, "TEST1", ready=1, solo_mode=0)
    response = client.get("/room/TEST1/status")

    assert response.status_code == 200
    data = response.get_json()
    assert data["ready"] is True
    assert data["genre"] == "All"
    assert data["solo"] is False
    assert data["last_match"] is None


def test_room_status_with_last_match(client):
    """GET /room/<code>/status returns last_match data when room has a recent match."""
    match_data = json.dumps({"title": "Test Movie", "thumb": "test.jpg", "ts": 1234567890})
    _seed_room(None, "TEST1", ready=1, solo_mode=0, last_match_data=match_data)

    response = client.get("/room/TEST1/status")
    assert response.status_code == 200
    data = response.get_json()
    assert data["last_match"] is not None
    assert data["last_match"]["title"] == "Test Movie"
    assert data["last_match"]["thumb"] == "test.jpg"
    assert data["last_match"]["ts"] == 1234567890


def test_room_status_nonexistent_room(client):
    """GET /room/<code>/status for nonexistent room returns ready=False."""
    response = client.get("/room/NONEXISTENT/status")
    assert response.status_code == 200
    assert response.get_json() == {"ready": False}


def test_room_status_room_deleted_from_db(client):
    """GET /room/<code>/status for room deleted from DB returns ready=False."""
    _seed_room(None, "TEST1", ready=1)
    conn = jellyswipe.db.get_db()
    try:
        conn.execute("DELETE FROM rooms WHERE pairing_code = ?", ("TEST1",))
        conn.commit()
    finally:
        conn.close()
    response = client.get("/room/TEST1/status")
    assert response.status_code == 200
    assert response.get_json() == {"ready": False}


# ---------------------------------------------------------------------------
# Section 6: POST /room/<code>/swipe tests
# ---------------------------------------------------------------------------


def test_swipe_left_records_no_match(client):
    """POST /room/<code>/swipe with direction=left records swipe, returns accepted=True."""
    _set_session(client, active_room="TEST1", user_id="verified-user", authenticated=True)
    _seed_room(None, "TEST1", ready=1, solo_mode=1)

    response = client.post(
        "/room/TEST1/swipe",
        json={"movie_id": "m1", "direction": "left"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"accepted": True}

    conn = jellyswipe.db.get_db()
    try:
        row = conn.execute(
            "SELECT direction FROM swipes WHERE room_code = 'TEST1' AND movie_id = 'm1'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row["direction"] == "left"


def test_swipe_right_solo_match(client):
    """POST /room/<code>/swipe right in solo room creates match in DB."""
    _set_session(client, active_room="TEST1", user_id="verified-user", authenticated=True)
    _seed_room(None, "TEST1", ready=1, solo_mode=1)

    response = client.post(
        "/room/TEST1/swipe",
        json={"movie_id": "m1", "direction": "right"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"accepted": True}

    conn = jellyswipe.db.get_db()
    try:
        row = conn.execute(
            "SELECT * FROM matches WHERE room_code = 'TEST1' AND movie_id = 'm1'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None


def test_swipe_right_dual_match(client):
    """POST /room/<code>/swipe right in shared room matches when another user swiped right."""
    _seed_room(None, "TEST1", ready=1, solo_mode=0)
    _set_session(client, active_room="TEST1", user_id="verified-user", authenticated=True)

    conn = jellyswipe.db.get_db()
    try:
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
    data = response.get_json()
    assert data == {"accepted": True}

    conn = jellyswipe.db.get_db()
    try:
        rows = conn.execute(
            "SELECT user_id FROM matches WHERE room_code = 'TEST1' AND movie_id = 'm1'"
        ).fetchall()
    finally:
        conn.close()
    match_user_ids = [row["user_id"] for row in rows]
    assert "verified-user" in match_user_ids
    assert "user-2" in match_user_ids


def test_swipe_right_no_match_yet(client):
    """POST /room/<code>/swipe right in shared room with no prior swipe returns accepted=True."""
    _set_session(client, active_room="TEST1", user_id="verified-user", authenticated=True)
    _seed_room(None, "TEST1", ready=1, solo_mode=0)

    response = client.post(
        "/room/TEST1/swipe",
        json={"movie_id": "m1", "direction": "right"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"accepted": True}


def test_swipe_unauthorized_returns_401(client):
    """POST /room/<code>/swipe without authentication returns 401."""
    response = client.post(
        "/room/TEST1/swipe",
        json={"movie_id": "m1", "direction": "left"},
    )

    assert response.status_code == 401
    data = response.get_json()
    assert data["error"] == "Authentication required"


def test_swipe_right_updates_last_match_data(client):
    """POST /room/<code>/swipe dual match updates last_match_data in rooms table."""
    _seed_room(None, "TEST1", ready=1, solo_mode=0)
    _set_session(client, active_room="TEST1", user_id="verified-user", authenticated=True)

    conn = jellyswipe.db.get_db()
    try:
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

    conn = jellyswipe.db.get_db()
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