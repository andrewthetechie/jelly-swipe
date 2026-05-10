"""SSE streaming tests for the event-driven /room/{code}/stream endpoint.

Tests cover:
- First attach (no cursor): session_bootstrap event
- Reconnect with valid cursor: missed events replayed
- Reconnect with stale cursor: session_reset sent
- Reconnect with wrong instance cursor: session_reset sent
- Session closed event: stream closes after session_closed
- SSE id field on every event
- Heartbeat ping after idle
- Disconnect detection
- CancelledError propagation
- Response headers
- GET /matches works independently
"""

import asyncio
import json
import os
import secrets
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock


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


def _seed_event(conn, instance_id, event_type, payload_json):
    """Seed a session event directly."""
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        "INSERT INTO session_events (session_instance_id, event_type, payload_json, created_at) "
        "VALUES (?, ?, ?, ?)",
        (instance_id, event_type, payload_json, now),
    )
    conn.commit()
    return cursor.lastrowid


def _sqlite_conn(app):
    """Get a direct sqlite3 connection to the app's database."""
    import sqlite3
    from jellyswipe.db_paths import application_db_path

    path = application_db_path.path
    assert path is not None
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


# ---------------------------------------------------------------------------
# Section 1: Basic SSE response tests
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


def _resolved_future():
    """Return an already-resolved Future for mocking notifier.subscribe."""
    f = asyncio.Future()
    f.set_result(None)
    return f


# ---------------------------------------------------------------------------
# Section 2: First attach (no cursor) — session_bootstrap
# ---------------------------------------------------------------------------


def test_stream_first_attach_sends_bootstrap(client, monkeypatch):
    """First attach (no Last-Event-ID, no after_event_id) sends session_bootstrap."""
    conn = _sqlite_conn(client)
    try:
        instance_id = _seed_room_and_instance(
            conn,
            "BOOT1",
            ready=1,
            current_genre="Action",
            solo_mode=1,
            hide_watched=1,
        )
    finally:
        conn.close()
    _set_session_room(client, os.environ["FLASK_SECRET"], "BOOT1")
    _setup_disconnect_after(client, monkeypatch, after_calls=2)

    monkeypatch.setattr(notifier, "subscribe", lambda code: _resolved_future())
    monkeypatch.setattr(time, "time", lambda: 1000000.0)

    response = client.get("/room/BOOT1/stream")
    data = response.text

    assert "session_bootstrap" in data
    assert (
        f'"instance_id": "{instance_id}"' in data
        or f'"instance_id":"{instance_id}"' in data
    )
    assert '"ready": true' in data
    assert '"genre": "Action"' in data
    assert '"solo": true' in data
    assert '"hide_watched": true' in data
    assert '"replay_boundary"' in data


def test_stream_first_attach_bootstrap_only_event_before_live(client, monkeypatch):
    """session_bootstrap is the only event before live events start."""
    conn = _sqlite_conn(client)
    try:
        _seed_room_and_instance(conn, "BOOT2")
    finally:
        conn.close()
    _set_session_room(client, os.environ["FLASK_SECRET"], "BOOT2")
    _setup_disconnect_after(client, monkeypatch, after_calls=2)

    monkeypatch.setattr(notifier, "subscribe", lambda code: _resolved_future())
    monkeypatch.setattr(time, "time", lambda: 1000000.0)

    response = client.get("/room/BOOT2/stream")
    data = response.text

    bootstrap_count = data.count("session_bootstrap")
    assert bootstrap_count == 1, f"Expected 1 bootstrap, got {bootstrap_count}: {data}"


def test_stream_first_attach_replay_boundary(client, monkeypatch):
    """First attach includes replay_boundary set to latest event_id."""
    conn = _sqlite_conn(client)
    try:
        instance_id = _seed_room_and_instance(conn, "BOOT3")
        _seed_event(conn, instance_id, "swipe", json.dumps({"media_id": "m1"}))
        _seed_event(conn, instance_id, "swipe", json.dumps({"media_id": "m2"}))
    finally:
        conn.close()
    _set_session_room(client, os.environ["FLASK_SECRET"], "BOOT3")
    _setup_disconnect_after(client, monkeypatch, after_calls=2)

    monkeypatch.setattr(notifier, "subscribe", lambda code: _resolved_future())
    monkeypatch.setattr(time, "time", lambda: 1000000.0)

    response = client.get("/room/BOOT3/stream")
    data = response.text

    assert '"replay_boundary": 2' in data or '"replay_boundary":2' in data


# ---------------------------------------------------------------------------
# Section 3: Reconnect with valid cursor — replay missed events
# ---------------------------------------------------------------------------


def test_stream_reconnect_replays_missed_events(client, monkeypatch):
    """Reconnect with valid cursor replays missed events in order."""
    conn = _sqlite_conn(client)
    try:
        instance_id = _seed_room_and_instance(conn, "REPLAY1")
        eid1 = _seed_event(
            conn,
            instance_id,
            "swipe",
            json.dumps({"media_id": "m1", "direction": "right"}),
        )
        eid2 = _seed_event(
            conn, instance_id, "match_found", json.dumps({"media_id": "m1"})
        )
    finally:
        conn.close()
    _set_session_room(client, os.environ["FLASK_SECRET"], "REPLAY1")
    _setup_disconnect_after(client, monkeypatch, after_calls=2)

    monkeypatch.setattr(notifier, "subscribe", lambda code: _resolved_future())
    monkeypatch.setattr(time, "time", lambda: 1000000.0)

    response = client.get(f"/room/REPLAY1/stream?after_event_id={eid1}")
    data = response.text

    assert "match_found" in data
    assert f'"event_id": {eid2}' in data or f'"event_id":{eid2}' in data
    assert '"event_type": "match_found"' in data or '"event_type":"match_found"' in data


def test_stream_reconnect_events_in_order(client, monkeypatch):
    """Replayed events are delivered in event_id order."""
    conn = _sqlite_conn(client)
    try:
        instance_id = _seed_room_and_instance(conn, "REPLAY2")
        eid1 = _seed_event(conn, instance_id, "swipe", json.dumps({"media_id": "m1"}))
        eid2 = _seed_event(conn, instance_id, "swipe", json.dumps({"media_id": "m2"}))
        eid3 = _seed_event(
            conn, instance_id, "match_found", json.dumps({"media_id": "m1"})
        )
    finally:
        conn.close()
    _set_session_room(client, os.environ["FLASK_SECRET"], "REPLAY2")
    _setup_disconnect_after(client, monkeypatch, after_calls=2)

    monkeypatch.setattr(notifier, "subscribe", lambda code: _resolved_future())
    monkeypatch.setattr(time, "time", lambda: 1000000.0)

    response = client.get(f"/room/REPLAY2/stream?after_event_id={eid1}")
    data = response.text

    pos_eid2 = data.find(f'"event_id": {eid2}')
    if pos_eid2 == -1:
        pos_eid2 = data.find(f'"event_id":{eid2}')
    pos_eid3 = data.find(f'"event_id": {eid3}')
    if pos_eid3 == -1:
        pos_eid3 = data.find(f'"event_id":{eid3}')
    assert pos_eid2 < pos_eid3, "Events should be in order"


# ---------------------------------------------------------------------------
# Section 4: Invalid cursor — stale
# ---------------------------------------------------------------------------


def test_stream_stale_cursor_sends_session_reset(client, monkeypatch):
    """Reconnect with stale cursor (no events after it) sends session_reset."""
    conn = _sqlite_conn(client)
    try:
        _seed_room_and_instance(conn, "STALE1")
    finally:
        conn.close()
    _set_session_room(client, os.environ["FLASK_SECRET"], "STALE1")

    monkeypatch.setattr(time, "time", lambda: 1000000.0)

    response = client.get("/room/STALE1/stream?after_event_id=999")
    data = response.text

    assert "session_reset" in data
    assert "stale_cursor" in data


# ---------------------------------------------------------------------------
# Section 5: Session closed event
# ---------------------------------------------------------------------------


def test_stream_session_closed_closes_stream(client, monkeypatch):
    """When session_closed event is replayed, stream closes after sending it."""
    conn = _sqlite_conn(client)
    try:
        instance_id = _seed_room_and_instance(conn, "CLOSE1")
        _seed_event(conn, instance_id, "swipe", json.dumps({"media_id": "m1"}))
        _seed_event(
            conn, instance_id, "session_closed", json.dumps({"reason": "user_quit"})
        )
    finally:
        conn.close()
    _set_session_room(client, os.environ["FLASK_SECRET"], "CLOSE1")

    monkeypatch.setattr(time, "time", lambda: 1000000.0)

    response = client.get("/room/CLOSE1/stream?after_event_id=0")
    data = response.text

    assert "session_closed" in data
    assert "session_bootstrap" not in data


def test_stream_two_matches_close_together(client, monkeypatch):
    """Two match_found events are delivered as distinct events with different event_ids."""
    conn = _sqlite_conn(client)
    try:
        instance_id = _seed_room_and_instance(conn, "MATCH2")
        eid1 = _seed_event(
            conn, instance_id, "match_found", json.dumps({"media_id": "m1"})
        )
        eid2 = _seed_event(
            conn, instance_id, "match_found", json.dumps({"media_id": "m2"})
        )
    finally:
        conn.close()
    _set_session_room(client, os.environ["FLASK_SECRET"], "MATCH2")
    _setup_disconnect_after(client, monkeypatch, after_calls=2)

    monkeypatch.setattr(notifier, "subscribe", lambda code: _resolved_future())
    monkeypatch.setattr(time, "time", lambda: 1000000.0)

    response = client.get("/room/MATCH2/stream?after_event_id=0")
    data = response.text

    assert data.count("match_found") >= 2
    assert f'"event_id": {eid1}' in data or f'"event_id":{eid1}' in data
    assert f'"event_id": {eid2}' in data or f'"event_id":{eid2}' in data


# ---------------------------------------------------------------------------
# Section 6: SSE id field
# ---------------------------------------------------------------------------


def test_stream_sse_id_field(client, monkeypatch):
    """Each event includes id: line with the event_id."""
    conn = _sqlite_conn(client)
    try:
        instance_id = _seed_room_and_instance(conn, "ID1")
        eid = _seed_event(conn, instance_id, "swipe", json.dumps({"media_id": "m1"}))
    finally:
        conn.close()
    _set_session_room(client, os.environ["FLASK_SECRET"], "ID1")
    _setup_disconnect_after(client, monkeypatch, after_calls=2)

    monkeypatch.setattr(notifier, "subscribe", lambda code: _resolved_future())
    monkeypatch.setattr(time, "time", lambda: 1000000.0)

    response = client.get("/room/ID1/stream?after_event_id=0")
    data = response.text

    assert f"id: {eid}" in data or f"id:{eid}" in data


# ---------------------------------------------------------------------------
# Section 7: Heartbeat
# ---------------------------------------------------------------------------


def test_stream_heartbeat_ping(client, monkeypatch):
    """After ~15s of no events, a : ping comment is sent."""
    conn = _sqlite_conn(client)
    try:
        _seed_room_and_instance(conn, "HB1")
    finally:
        conn.close()
    _set_session_room(client, os.environ["FLASK_SECRET"], "HB1")
    _setup_disconnect_after(client, monkeypatch, after_calls=4)

    time_counter = [0]

    def mock_time():
        time_counter[0] += 1
        if time_counter[0] <= 5:
            return 0.0
        return 16.0

    monkeypatch.setattr(time, "time", mock_time)

    # Mock wait_for to timeout immediately so the heartbeat check runs
    original_wait_for = asyncio.wait_for

    async def mock_wait_for(future, timeout):
        # Let the first call through (bootstrap phase), then timeout immediately
        if time_counter[0] > 5:
            raise asyncio.TimeoutError()
        return await original_wait_for(future, timeout=0.001)

    monkeypatch.setattr(asyncio, "wait_for", mock_wait_for)

    response = client.get("/room/HB1/stream")
    data = response.text

    assert ": ping" in data, f"Expected heartbeat ping in: {repr(data)}"


# ---------------------------------------------------------------------------
# Section 8: Disconnect detection
# ---------------------------------------------------------------------------


def test_stream_disconnect_exits_cleanly(client, monkeypatch):
    """If request.is_disconnected() returns True, generator exits cleanly."""
    conn = _sqlite_conn(client)
    try:
        _seed_room_and_instance(conn, "DISC1")
    finally:
        conn.close()
    _set_session_room(client, os.environ["FLASK_SECRET"], "DISC1")

    call_count = _setup_disconnect_after(client, monkeypatch, after_calls=2)
    monkeypatch.setattr(notifier, "subscribe", lambda code: _resolved_future())
    monkeypatch.setattr(time, "time", lambda: 1000000.0)

    response = client.get("/room/DISC1/stream")
    assert response.status_code == 200
    assert call_count[0] >= 1


# ---------------------------------------------------------------------------
# Section 9: CancelledError propagation
# ---------------------------------------------------------------------------


def test_stream_cancelled_error_not_swallowed(monkeypatch):
    """CancelledError raised inside the generator must propagate out."""
    import jellyswipe.routers.rooms as rooms_module
    from jellyswipe.dependencies import AuthUser

    fake_request = MagicMock()
    fake_request.is_disconnected = AsyncMock(return_value=False)
    fake_request.headers = {}
    fake_request.query_params = {}

    fake_auth = AuthUser(jf_token="t", user_id="u")

    # Custom async context manager that raises CancelledError on entry
    class _FailingSessionCM:
        async def __aenter__(self):
            raise asyncio.CancelledError("simulated cancellation")

        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(
        rooms_module, "get_sessionmaker", lambda: lambda: _FailingSessionCM()
    )

    result = rooms_module.room_stream(
        code="CANCEL1",
        request=fake_request,
        auth=fake_auth,
    )
    generator = result.body_iterator

    cancelled_error_propagated = [False]

    async def drive_generator():
        try:
            async for _ in generator:
                pass
        except asyncio.CancelledError:
            cancelled_error_propagated[0] = True

    asyncio.run(drive_generator())

    assert cancelled_error_propagated[0], (
        "CancelledError was swallowed — it must propagate"
    )


# ---------------------------------------------------------------------------
# Section 10: Room not found
# ---------------------------------------------------------------------------


def test_stream_room_not_found_no_instance(client, monkeypatch):
    """Stream for room with no instance sends session_reset and closes."""
    _set_session_room(client, os.environ["FLASK_SECRET"], "NOINSTANCE")

    monkeypatch.setattr(time, "time", lambda: 1000000.0)

    response = client.get("/room/NOINSTANCE/stream")
    data = response.text

    assert "session_reset" in data
    assert "instance_changed" in data


# ---------------------------------------------------------------------------
# Section 11: GET /matches works independently
# ---------------------------------------------------------------------------


def test_get_matches_works_independently(client, monkeypatch):
    """GET /matches continues to work independently of the stream."""
    conn = _sqlite_conn(client)
    try:
        _seed_room_and_instance(conn, "MATCHES1", ready=1)
    finally:
        conn.close()
    _set_session_room(client, os.environ["FLASK_SECRET"], "MATCHES1")

    response = client.get("/matches")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Section 12: Unauthenticated request
# ---------------------------------------------------------------------------


def test_stream_unauthenticated_request_returns_401(client_real_auth):
    """GET /room/{code}/stream without auth cookie must return HTTP 401."""
    response = client_real_auth.get("/room/AUTHTEST1/stream")

    assert response.status_code == 401, (
        f"Expected 401 for unauthenticated SSE request, got {response.status_code}: {response.text}"
    )
    body = response.json()
    assert "detail" in body, f"Expected 'detail' in 401 response body, got: {body}"
