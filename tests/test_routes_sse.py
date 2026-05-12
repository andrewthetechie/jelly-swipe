"""SSE streaming tests for the event-driven /room/{code}/stream endpoint.

After ORCH-023, this file tests only:
- SSE headers (Cache-Control, X-Accel-Buffering, Content-Type)
- Route wiring (instance not found → session_reset)
- Unauthenticated request returns 401

Generator-level behavior is tested in tests/test_session_event_stream.py.
"""

import asyncio
import json
import os
import secrets
import time
from datetime import datetime, timezone


from jellyswipe.notifier import notifier
from tests.conftest import set_session_cookie


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_session_room(client, secret_key, room_code, user_id=None):
    """Inject session state for SSE stream tests."""
    if user_id is None:
        user_id = f"test-user-{secrets.token_hex(4)}"
    set_session_cookie(
        client,
        {
            "active_room": room_code,
            "my_user_id": user_id,
            "jf_delegate_server_identity": True,
            "solo_mode": False,
        },
        secret_key,
    )


def _seed_room_and_instance(
    conn,
    room_code,
    *,
    ready=0,
    solo_mode=0,
    current_genre="All",
    instance_id=None,
    hide_watched=0,
    include_movies=1,
    include_tv_shows=0,
):
    """Seed a room row and session instance for SSE tests."""
    if instance_id is None:
        instance_id = f"inst-{secrets.token_hex(8)}"
    movie_data = json.dumps([])
    conn.execute(
        "INSERT INTO rooms (pairing_code, movie_data, ready, current_genre, solo_mode, "
        "hide_watched, include_movies, include_tv_shows, deck_position) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            room_code,
            movie_data,
            ready,
            current_genre,
            solo_mode,
            hide_watched,
            include_movies,
            include_tv_shows,
            "{}",
        ),
    )
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO session_instances (instance_id, pairing_code, status, created_at) "
        "VALUES (?, ?, ?, ?)",
        (instance_id, room_code, "active", now),
    )
    conn.commit()
    return instance_id


def _sqlite_conn(app):
    """Get a direct sqlite3 connection to the app's database."""
    import sqlite3
    import os

    path = os.environ["DB_PATH"]
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _setup_disconnect_after(client, monkeypatch, after_calls=2):
    """Mock is_disconnected to return True after N calls, so the stream loop exits."""
    from starlette.requests import Request as StarletteRequest

    call_count = [0]

    async def fake_is_disconnected(self):
        call_count[0] += 1
        return call_count[0] >= after_calls

    monkeypatch.setattr(StarletteRequest, "is_disconnected", fake_is_disconnected)
    return call_count


def _resolved_future():
    """Return an already-resolved Future for mocking notifier.subscribe."""
    f = asyncio.Future()
    f.set_result(None)
    return f


# ---------------------------------------------------------------------------
# SSE headers and route wiring
# ---------------------------------------------------------------------------


def test_stream_response_headers(client, monkeypatch):
    """GET /room/stream returns correct SSE content-type and cache headers."""
    conn = _sqlite_conn(client)
    try:
        _seed_room_and_instance(conn, "HDR1")
    finally:
        conn.close()
    _set_session_room(client, os.environ["FLASK_SECRET"], "HDR1")
    _setup_disconnect_after(client, monkeypatch, after_calls=2)

    # Mock notifier to resolve immediately
    monkeypatch.setattr(notifier, "subscribe", lambda code: _resolved_future())
    monkeypatch.setattr(time, "time", lambda: 1000000.0)

    response = client.get("/room/HDR1/stream")

    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("text/event-stream")
    assert response.headers["Cache-Control"] == "no-cache"
    assert response.headers["X-Accel-Buffering"] == "no"


def test_stream_room_not_found_no_instance(client, monkeypatch):
    """Stream for room with no instance sends session_reset and closes."""
    _set_session_room(client, os.environ["FLASK_SECRET"], "NOINSTANCE")

    monkeypatch.setattr(time, "time", lambda: 1000000.0)

    response = client.get("/room/NOINSTANCE/stream")
    data = response.text

    assert "session_reset" in data
    assert "instance_changed" in data


def test_stream_unauthenticated_request_returns_401(client_real_auth):
    """GET /room/{code}/stream without auth cookie must return HTTP 401."""
    response = client_real_auth.get("/room/AUTHTEST1/stream")

    assert response.status_code == 401, (
        f"Expected 401 for unauthenticated SSE request, got {response.status_code}: {response.text}"
    )
    body = response.json()
    assert "detail" in body, f"Expected 'detail' in 401 response body, got: {body}"
