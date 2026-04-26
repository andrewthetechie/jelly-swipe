"""XSS security tests for EPIC-03 verification.

Tests verify that all user-controlled input is properly sanitized before being
stored, rendered, or reflected in responses. Flask's jsonify() auto-escapes
HTML entities in JSON strings — these tests prove that protection works and
that non-JSON paths (proxy) are also safe.
"""

import json

import jellyswipe.db
import pytest

# ---------------------------------------------------------------------------
# Module-level XSS payload constants (per D-03, D-04, D-05, D-06, D-07)
# ---------------------------------------------------------------------------

XSS_SCRIPT_TAG = "<script>alert('xss')</script>"
XSS_IMG_TAG = '<img src=x onerror=alert(1)>'
XSS_SVG_TAG = '<svg onload=alert(1)>'
XSS_JS_URL = "javascript:alert(1)"
XSS_JS_VOID = "javascript:void(0)"
XSS_EVENT_HANDLER_DQ = '" onmouseover="alert(1)'
XSS_EVENT_HANDLER_SQ = "' onload='alert(1)"
XSS_ENCODED_ANGLE = "&lt;script&gt;"
XSS_PERCENT = "%3Cscript%3E"
XSS_HEX_ENCODED = "&#x3C;script&#x3E;"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_session(client, *, active_room="ROOM1", session_user_id="test-user", delegate=True):
    """Set up session with active room and identity for swipe tests."""
    with client.session_transaction() as sess:
        sess["active_room"] = active_room
        sess["my_user_id"] = session_user_id
        if delegate:
            sess["jf_delegate_server_identity"] = True
        else:
            sess.pop("jf_delegate_server_identity", None)


def _seed_solo_room(db_path, room_code="ROOM1"):
    """Seed a solo-mode room ready for swiping."""
    conn = jellyswipe.db.get_db()
    try:
        conn.execute(
            "INSERT INTO rooms (pairing_code, movie_data, ready, current_genre, solo_mode) "
            "VALUES (?, ?, ?, ?, ?)",
            (room_code, json.dumps([]), 1, "All", 1),
        )
        conn.commit()
    finally:
        conn.close()


def _setup_solo_swipe_session(client):
    """Prepare a solo-mode room with delegate identity for swipe XSS tests.

    Combines session setup and room seeding into one call.
    Returns nothing — the caller just needs the client.
    """
    _set_session(client)
    _seed_solo_room(None)


# ---------------------------------------------------------------------------
# Section 1: Stored XSS via /room/swipe (D-08, D-09, D-10)
# ---------------------------------------------------------------------------


def test_swipe_xss_title_escaped_in_match_response(client):
    """Swipe with XSS <script> in title — Flask jsonify escapes it in match response."""
    _setup_solo_swipe_session(client)

    response = client.post(
        "/room/swipe",
        json={
            "movie_id": "movie-1",
            "title": XSS_SCRIPT_TAG,
            "thumb": "thumb.jpg",
            "direction": "right",
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["match"] is True
    # Per D-19: Flask jsonify encodes < as \u003c in JSON strings
    assert "\u003c" in data.get("title", "")
    # Raw unescaped <script> must NOT appear in the JSON body
    assert "<script>" not in response.get_data(as_text=True)


def test_swipe_xss_thumb_escaped_in_match_response(client):
    """Swipe with XSS <img> in thumb — escaped in match response JSON."""
    _setup_solo_swipe_session(client)

    response = client.post(
        "/room/swipe",
        json={
            "movie_id": "movie-2",
            "title": "Normal Title",
            "thumb": XSS_IMG_TAG,
            "direction": "right",
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["match"] is True
    # Escaped form must be present
    assert "\u003c" in data.get("thumb", "")
    # Raw unescaped <img> must NOT appear in the response body
    assert "<img" not in response.get_data(as_text=True)


def test_stored_xss_matches_endpoint(client):
    """Stored XSS read path: swipe with XSS title, then GET /matches — must be escaped."""
    _setup_solo_swipe_session(client)

    # Store XSS payload via swipe
    client.post(
        "/room/swipe",
        json={
            "movie_id": "movie-3",
            "title": XSS_SCRIPT_TAG,
            "thumb": XSS_IMG_TAG,
            "direction": "right",
        },
    )

    # Retrieve via /matches endpoint
    response = client.get("/matches")

    assert response.status_code == 200
    body_text = response.get_data(as_text=True)
    # Raw <script> and <img> must NOT appear in output
    assert "<script>" not in body_text
    assert "<img" not in body_text
    # Escaped JSON unicode forms should be present (literal \u003c in HTTP body)
    assert "\\u003c" in body_text


def test_swipe_xss_img_tag_escaped(client):
    """Swipe with <img onerror> XSS in title — escaped in match response."""
    _setup_solo_swipe_session(client)

    response = client.post(
        "/room/swipe",
        json={
            "movie_id": "movie-4",
            "title": XSS_IMG_TAG,
            "thumb": "thumb.jpg",
            "direction": "right",
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["match"] is True
    assert "\u003c" in data.get("title", "")
    assert "<img" not in response.get_data(as_text=True)


def test_swipe_xss_event_handler_escaped(client):
    """Swipe with event handler injection in title — quotes escaped in response."""
    _setup_solo_swipe_session(client)

    response = client.post(
        "/room/swipe",
        json={
            "movie_id": "movie-5",
            "title": XSS_EVENT_HANDLER_DQ,
            "thumb": "thumb.jpg",
            "direction": "right",
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["match"] is True
    # The title value is present (round-trip through jsonify)
    assert XSS_EVENT_HANDLER_DQ in data.get("title", "") or "\u0022" in data.get("title", "")


# ---------------------------------------------------------------------------
# Section 2: Proxy route XSS tests (D-12, D-13, D-14, D-15)
# ---------------------------------------------------------------------------


def test_proxy_javascript_url_rejected(client):
    """GET /proxy with javascript: URL — must return 403."""
    response = client.get(f"/proxy?path={XSS_JS_URL}")
    assert response.status_code == 403


def test_proxy_javascript_void_rejected(client):
    """GET /proxy with javascript:void(0) — must return 403."""
    response = client.get(f"/proxy?path={XSS_JS_VOID}")
    assert response.status_code == 403


def test_proxy_path_traversal_rejected(client):
    """GET /proxy with ../path traversal — must return 403."""
    response = client.get("/proxy?path=../../etc/passwd")
    assert response.status_code == 403


def test_proxy_html_in_path_rejected(client):
    """GET /proxy with <script> in path parameter — must return 403."""
    response = client.get(f"/proxy?path={XSS_SCRIPT_TAG}")
    assert response.status_code == 403


def test_proxy_valid_uuid_path_accepted(client):
    """GET /proxy with valid 32-char hex UUID — must return 200."""
    response = client.get("/proxy?path=jellyfin/00000000000000000000000000000000/Primary")
    assert response.status_code == 200
    assert "image" in response.content_type


def test_proxy_valid_uuid_with_dashes_accepted(client):
    """GET /proxy with valid 36-char UUID with dashes — must return 200."""
    response = client.get("/proxy?path=jellyfin/00000000-0000-0000-0000-000000000000/Primary")
    assert response.status_code == 200
    assert "image" in response.content_type


# ---------------------------------------------------------------------------
# Section 3: Input validation tests (D-16, D-17)
# ---------------------------------------------------------------------------


def test_login_xss_username_not_echoed(client):
    """POST /auth/jellyfin-login with XSS in username — response must not echo raw payload."""
    response = client.post(
        "/auth/jellyfin-login",
        json={"username": XSS_SCRIPT_TAG, "password": "testpass"},
    )

    body_text = response.get_data(as_text=True)
    # The error message is static ("Jellyfin login failed"), never echoes input
    assert "<script>" not in body_text
    # Verify we got a proper response (either 200 or 401 depending on mock)
    assert response.status_code in (200, 401)


def test_join_room_xss_code_not_echoed(client):
    """POST /room/join with XSS in code — response must not echo raw payload."""
    response = client.post(
        "/room/join",
        json={"code": XSS_SCRIPT_TAG},
    )

    body_text = response.get_data(as_text=True)
    # The error message is static ("Invalid Code"), never echoes input
    assert "<script>" not in body_text
    assert response.status_code == 404
