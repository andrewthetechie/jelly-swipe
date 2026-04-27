"""Comprehensive room lifecycle tests for all 6 room endpoints.

Tests cover /room/create, /room/join, /room/go-solo, /room/quit, /room/status,
and /room/swipe — including happy paths, edge cases, error conditions, and the
full swipe match logic (solo match, dual match, no match).
"""

import json
import secrets

import jellyswipe.db
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_session(client, *, active_room=None, user_id=None, delegate=True, solo_mode=False):
    """Set up session with active room and identity for room route tests.

    Args:
        active_room: Room code to set (None = don't set).
        user_id: Session user ID (None = generate random).
        delegate: If True, set jf_delegate_server_identity in session.
        solo_mode: If True, set solo_mode flag in session.
    """
    with client.session_transaction() as sess:
        if active_room is not None:
            sess["active_room"] = active_room
        if user_id is None:
            user_id = f"test-user-{secrets.token_hex(4)}"
        sess["my_user_id"] = user_id
        if delegate:
            sess["jf_delegate_server_identity"] = True
        else:
            sess.pop("jf_delegate_server_identity", None)
        sess["solo_mode"] = solo_mode


def _seed_room(db_path, room_code="TEST1", *, ready=0, solo_mode=0, movie_data=None, last_match_data=None):
    """Seed a room row directly into the database for testing.

    Args:
        db_path: Database path (unused, kept for API consistency — DB_PATH already patched).
        room_code: Pairing code for the room.
        ready: Room ready flag (0 or 1).
        solo_mode: Solo mode flag (0 or 1).
        movie_data: Movie list JSON (None defaults to empty list).
        last_match_data: Last match JSON string (None for no match).
    """
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
    """Create a room via POST /room/create and return the response.

    Convenience wrapper for tests that need a room created through the API
    to test the real create flow.
    """
    return client.post("/room/create")


# ---------------------------------------------------------------------------
# Section 1: /room/create tests
# ---------------------------------------------------------------------------


def test_room_create_returns_pairing_code(client):
    """POST /room/create returns 200 with a 4-digit pairing code."""
    response = _create_room_via_api(client)
    assert response.status_code == 200
    data = response.get_json()
    assert "pairing_code" in data
    code = data["pairing_code"]
    assert len(str(code)) == 4
    assert str(code).isdigit()


def test_room_create_sets_session(client):
    """POST /room/create sets active_room, my_user_id (host_), and solo_mode=False in session."""
    response = _create_room_via_api(client)
    assert response.status_code == 200
    code = response.get_json()["pairing_code"]

    with client.session_transaction() as sess:
        assert sess["active_room"] == code
        assert sess["my_user_id"].startswith("host_")
        assert sess["solo_mode"] is False


def test_room_create_stores_room_in_db(client):
    """POST /room/create stores the room in the database with correct initial state."""
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


# ---------------------------------------------------------------------------
# Section 2: /room/join tests
# ---------------------------------------------------------------------------


def test_room_join_success(client):
    """POST /room/join with valid code returns 200 with status success."""
    _seed_room(None, "TEST1")
    response = client.post("/room/join", json={"code": "TEST1"})
    assert response.status_code == 200
    assert response.get_json() == {"status": "success"}


def test_room_join_sets_session_and_ready(client):
    """POST /room/join sets session (active_room, guest user_id) and marks room ready in DB."""
    _seed_room(None, "TEST1")
    client.post("/room/join", json={"code": "TEST1"})

    # Verify session
    with client.session_transaction() as sess:
        assert sess["active_room"] == "TEST1"
        assert sess["my_user_id"].startswith("guest_")
        assert sess["solo_mode"] is False

    # Verify DB — room should now be ready
    conn = jellyswipe.db.get_db()
    try:
        row = conn.execute(
            "SELECT ready FROM rooms WHERE pairing_code = ?", ("TEST1",)
        ).fetchone()
    finally:
        conn.close()
    assert row["ready"] == 1


def test_room_join_invalid_code_returns_404(client):
    """POST /room/join with non-existent code returns 404 with error."""
    response = client.post("/room/join", json={"code": "9999"})
    assert response.status_code == 404
    data = response.get_json()
    assert "error" in data


def test_room_join_missing_code_returns_404(client):
    """POST /room/join with empty body (code is None) returns 404."""
    response = client.post("/room/join", json={})
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Section 3: /room/go-solo tests
# ---------------------------------------------------------------------------


def test_go_solo_success(client):
    """POST /room/go-solo with active room returns 200 with status solo."""
    _set_session(client, active_room="TEST1")
    _seed_room(None, "TEST1")
    response = client.post("/room/go-solo")
    assert response.status_code == 200
    assert response.get_json() == {"status": "solo"}


def test_go_solo_updates_db(client):
    """POST /room/go-solo sets solo_mode=1 and ready=1 in the database."""
    _set_session(client, active_room="TEST1")
    _seed_room(None, "TEST1")
    client.post("/room/go-solo")

    conn = jellyswipe.db.get_db()
    try:
        row = conn.execute(
            "SELECT solo_mode, ready FROM rooms WHERE pairing_code = ?", ("TEST1",)
        ).fetchone()
    finally:
        conn.close()
    assert row["solo_mode"] == 1
    assert row["ready"] == 1


def test_go_solo_no_active_room_returns_400(client):
    """POST /room/go-solo without active room in session returns 400."""
    response = client.post("/room/go-solo")
    assert response.status_code == 400
    data = response.get_json()
    assert data.get("error") == "No active room"


def test_go_solo_sets_session_solo_mode(client):
    """POST /room/go-solo sets solo_mode=True in the session."""
    _set_session(client, active_room="TEST1")
    _seed_room(None, "TEST1")
    client.post("/room/go-solo")

    with client.session_transaction() as sess:
        assert sess["solo_mode"] is True


# ---------------------------------------------------------------------------
# Section 4: /room/quit tests
# ---------------------------------------------------------------------------


def test_quit_room_success(client):
    """POST /room/quit with active room returns 200 with session_ended."""
    _set_session(client, active_room="TEST1", solo_mode=True)
    _seed_room(None, "TEST1")
    response = client.post("/room/quit")
    assert response.status_code == 200
    assert response.get_json() == {"status": "session_ended"}


def test_quit_room_deletes_from_db(client):
    """POST /room/quit deletes the room and its swipes from the database."""
    _set_session(client, active_room="TEST1")
    _seed_room(None, "TEST1")

    # Seed a swipe to verify it gets cleaned up
    conn = jellyswipe.db.get_db()
    try:
        conn.execute(
            "INSERT INTO swipes (room_code, movie_id, user_id, direction) VALUES (?, ?, ?, ?)",
            ("TEST1", "m1", "user-1", "left"),
        )
        conn.commit()
    finally:
        conn.close()

    client.post("/room/quit")

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
    """POST /room/quit archives active matches (status=archived, room_code=HISTORY)."""
    _set_session(client, active_room="TEST1")
    _seed_room(None, "TEST1")

    # Seed an active match
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

    client.post("/room/quit")

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
    """POST /room/quit clears active_room and solo_mode from the session."""
    _set_session(client, active_room="TEST1", solo_mode=True)
    _seed_room(None, "TEST1")
    client.post("/room/quit")

    with client.session_transaction() as sess:
        assert sess.get("active_room") is None
        assert sess.get("solo_mode") is None


def test_quit_room_without_active_room_still_succeeds(client):
    """POST /room/quit without active room in session returns 200 (graceful no-op)."""
    response = client.post("/room/quit")
    assert response.status_code == 200
    assert response.get_json() == {"status": "session_ended"}


# ---------------------------------------------------------------------------
# Section 5: /room/status tests
# ---------------------------------------------------------------------------


def test_room_status_active_room(client):
    """GET /room/status with active room returns full room state."""
    _set_session(client, active_room="TEST1")
    _seed_room(None, "TEST1", ready=1, solo_mode=0)
    response = client.get("/room/status")

    assert response.status_code == 200
    data = response.get_json()
    assert data["ready"] is True
    assert data["genre"] == "All"
    assert data["solo"] is False
    assert data["last_match"] is None


def test_room_status_with_last_match(client):
    """GET /room/status returns last_match data when room has a recent match."""
    _set_session(client, active_room="TEST1")
    match_data = json.dumps({"title": "Test Movie", "thumb": "test.jpg", "ts": 1234567890})
    _seed_room(None, "TEST1", ready=1, solo_mode=0, last_match_data=match_data)

    response = client.get("/room/status")
    assert response.status_code == 200
    data = response.get_json()
    assert data["last_match"] is not None
    assert data["last_match"]["title"] == "Test Movie"
    assert data["last_match"]["thumb"] == "test.jpg"
    assert data["last_match"]["ts"] == 1234567890


def test_room_status_no_session(client):
    """GET /room/status without active room in session returns ready=False."""
    response = client.get("/room/status")
    assert response.status_code == 200
    assert response.get_json() == {"ready": False}


def test_room_status_room_deleted_from_db(client):
    """GET /room/status with active_room in session but room deleted from DB returns ready=False."""
    _set_session(client, active_room="TEST1")
    # Don't seed the room — simulates room was deleted
    response = client.get("/room/status")
    assert response.status_code == 200
    assert response.get_json() == {"ready": False}


# ---------------------------------------------------------------------------
# Section 6: /room/swipe tests
# ---------------------------------------------------------------------------


def test_swipe_left_records_no_match(client):
    """POST /room/swipe with direction=left records swipe but returns no match."""
    _set_session(client, active_room="TEST1", user_id="user-1", delegate=True)
    _seed_room(None, "TEST1", ready=1, solo_mode=1)

    response = client.post(
        "/room/swipe",
        json={"movie_id": "m1", "title": "Movie", "thumb": "t.jpg", "direction": "left"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"match": False}

    # Verify swipe recorded in DB
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
    """POST /room/swipe with direction=right in solo room creates immediate match."""
    _set_session(client, active_room="TEST1", user_id="user-1", delegate=True)
    _seed_room(None, "TEST1", ready=1, solo_mode=1)

    response = client.post(
        "/room/swipe",
        json={"movie_id": "m1", "title": "Solo Movie", "thumb": "solo.jpg", "direction": "right"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["match"] is True
    assert data["solo"] is True
    assert data["title"] == "Movie m1"
    assert data["thumb"] == "/proxy?path=jellyfin/m1/Primary"

    # Verify match exists in DB
    conn = jellyswipe.db.get_db()
    try:
        row = conn.execute(
            "SELECT * FROM matches WHERE room_code = 'TEST1' AND movie_id = 'm1'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None


def test_swipe_right_dual_match(client):
    """POST /room/swipe with direction=right in shared room matches when another user swiped right."""
    _seed_room(None, "TEST1", ready=1, solo_mode=0)
    _set_session(client, active_room="TEST1", user_id="user-1", delegate=True)

    # Seed another user's right swipe on the same movie
    conn = jellyswipe.db.get_db()
    try:
        conn.execute(
            "INSERT INTO swipes (room_code, movie_id, user_id, direction) VALUES (?, ?, ?, ?)",
            ("TEST1", "m1", "user-2", "right"),
        )
        conn.commit()
    finally:
        conn.close()

    response = client.post(
        "/room/swipe",
        json={"movie_id": "m1", "title": "Dual Movie", "thumb": "dual.jpg", "direction": "right"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["match"] is True
    # Solo key should not be present (or false) in dual mode
    assert data.get("solo") is not True

    # Verify TWO matches in DB (one for each user_id)
    conn = jellyswipe.db.get_db()
    try:
        rows = conn.execute(
            "SELECT user_id FROM matches WHERE room_code = 'TEST1' AND movie_id = 'm1'"
        ).fetchall()
    finally:
        conn.close()
    match_user_ids = [row["user_id"] for row in rows]
    assert len(match_user_ids) == 2
    assert "verified-user" in match_user_ids  # provider user_id for user-1
    assert "user-2" in match_user_ids  # the other session user


def test_swipe_right_no_match_yet(client):
    """POST /room/swipe with direction=right in shared room with no prior swipe returns no match."""
    _set_session(client, active_room="TEST1", user_id="user-1", delegate=True)
    _seed_room(None, "TEST1", ready=1, solo_mode=0)

    response = client.post(
        "/room/swipe",
        json={"movie_id": "m1", "title": "Movie", "thumb": "t.jpg", "direction": "right"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"match": False}


def test_swipe_no_active_room_returns_no_match(client):
    """POST /room/swipe without active_room returns match=False (not an error)."""
    _set_session(client, delegate=True)  # No active_room

    response = client.post(
        "/room/swipe",
        json={"movie_id": "m1", "title": "Movie", "thumb": "t.jpg", "direction": "left"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"match": False}


def test_swipe_unauthorized_returns_401(client):
    """POST /room/swipe without identity (no delegate, no token) returns 401."""
    _set_session(client, active_room="TEST1", delegate=False)

    response = client.post(
        "/room/swipe",
        json={"movie_id": "m1", "title": "Movie", "thumb": "t.jpg", "direction": "left"},
    )

    assert response.status_code == 401


def test_swipe_right_updates_last_match_data(client):
    """POST /room/swipe dual match updates last_match_data in rooms table."""
    _seed_room(None, "TEST1", ready=1, solo_mode=0)
    _set_session(client, active_room="TEST1", user_id="user-1", delegate=True)

    # Seed another user's right swipe to trigger dual match
    conn = jellyswipe.db.get_db()
    try:
        conn.execute(
            "INSERT INTO swipes (room_code, movie_id, user_id, direction) VALUES (?, ?, ?, ?)",
            ("TEST1", "m1", "user-2", "right"),
        )
        conn.commit()
    finally:
        conn.close()

    client.post(
        "/room/swipe",
        json={"movie_id": "m1", "title": "Match Movie", "thumb": "match.jpg", "direction": "right"},
    )

    # Verify last_match_data updated in rooms table
    conn = jellyswipe.db.get_db()
    try:
        row = conn.execute(
            "SELECT last_match_data FROM rooms WHERE pairing_code = 'TEST1'"
        ).fetchone()
    finally:
        conn.close()

    assert row["last_match_data"] is not None
    match_data = json.loads(row["last_match_data"])
    assert match_data["title"] == "Movie m1"
    assert match_data["thumb"] == "/proxy?path=jellyfin/m1/Primary"
    assert "ts" in match_data
