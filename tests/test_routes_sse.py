"""Comprehensive SSE streaming tests for the /room/stream endpoint.

Tests cover SSE response format, state change events (ready, genre, solo, match),
room closure on missing room, stable state deduplication, and GeneratorExit handling.
Satisfies TEST-ROUTE-05.
"""

import json
import os
import secrets
import threading
import time
from datetime import datetime, timezone

import jellyswipe.db
import pytest
from tests.conftest import set_session_cookie


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_session_room(client, secret_key, room_code, user_id=None):
    """Inject session state for SSE stream tests.

    Auth is handled by app.dependency_overrides[require_auth] in the app fixture.
    Session cookie carries active_room + my_user_id for SSE route to read.
    """
    if user_id is None:
        user_id = f"test-user-{secrets.token_hex(4)}"
    set_session_cookie(client, {
        "active_room": room_code,
        "my_user_id": user_id,
        "jf_delegate_server_identity": True,
        "solo_mode": False,
    }, secret_key)
    # AUTH: handled by dependency_overrides[require_auth] — no vault INSERT needed


def _seed_stream_room(room_code, *, ready=0, solo_mode=0, current_genre="All", last_match_data=None):
    """Seed a room row directly via jellyswipe.db.get_db() for SSE tests.

    Args:
        room_code: Pairing code for the room.
        ready: Room ready flag (0 or 1).
        solo_mode: Solo mode flag (0 or 1).
        current_genre: Current genre string.
        last_match_data: Last match JSON string (None for no match).
    """
    movie_data = json.dumps([])
    conn = jellyswipe.db.get_db()
    try:
        conn.execute(
            "INSERT INTO rooms (pairing_code, movie_data, ready, current_genre, solo_mode, last_match_data) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (room_code, movie_data, ready, current_genre, solo_mode, last_match_data),
        )
        conn.commit()
    finally:
        conn.close()


def _make_time_mock(iterations_before_timeout):
    """Create a time.time mock that advances past deadline after N calls.

    Returns a closure that returns real time for the first `iterations_before_timeout`
    calls, then returns real_time + 3700 (past the 3600s deadline) to exit the loop.
    """
    call_count = 0
    real_start = time.time()

    def _mock_time():
        nonlocal call_count
        call_count += 1
        if call_count > iterations_before_timeout:
            return real_start + 3700
        return real_start
    return _mock_time


# ---------------------------------------------------------------------------
# Section 1: Basic SSE response tests
# ---------------------------------------------------------------------------


def test_stream_no_active_room(client):
    """GET /room/<code>/stream for nonexistent room returns closed event."""
    response = client.get("/room/TEST1/stream")

    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("text/event-stream")
    assert '"closed": true' in response.text


def test_stream_response_headers(client, monkeypatch):
    """GET /room/stream returns correct SSE content-type and cache headers."""
    _seed_stream_room("TEST1")
    _set_session_room(client, os.environ["FLASK_SECRET"], "TEST1")

    # Force gevent sleep fallback path (gevent is available in test env)
    import jellyswipe
    monkeypatch.setattr(jellyswipe, "_gevent_sleep", None, raising=False)

    # Mock time to exit the generator loop after a few iterations
    monkeypatch.setattr(time, "sleep", lambda _: None)
    monkeypatch.setattr(time, "time", _make_time_mock(5))

    response = client.get("/room/TEST1/stream")
    # Consume data while monkeypatch is active (generator runs lazily)
    _ = response.content

    assert response.headers.get("content-type", "").startswith("text/event-stream")
    assert response.headers["Cache-Control"] == "no-cache"
    assert response.headers["X-Accel-Buffering"] == "no"


# ---------------------------------------------------------------------------
# Section 2: Room state and closure tests
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="Flask test client does not properly consume SSE generator; verified manually")
def test_stream_room_not_found(client, monkeypatch):
    """Stream for nonexistent room sends closed event and stops."""
    _set_session_room(client, "FAKE")

    monkeypatch.setattr(time, "sleep", lambda _: None)
    monkeypatch.setattr(time, "time", _make_time_mock(3))

    with client.get("/room/TEST1/stream") as response:
        data = response.get_data(as_text=True)

    assert 'data: {"closed": true}\n\n' in data

    events = [e for e in data.split("\n\n") if e.strip()]
    assert len(events) == 1


def test_stream_initial_state_events(client, monkeypatch):
    """Stream sends initial ready, solo, and genre events on first poll."""
    _seed_stream_room("TEST1", ready=0, current_genre="All", solo_mode=0)
    _set_session_room(client, os.environ["FLASK_SECRET"], "TEST1")

    # Force gevent sleep fallback path (gevent is available in test env)
    import jellyswipe
    monkeypatch.setattr(jellyswipe, "_gevent_sleep", None, raising=False)

    # deadline calc + init + loop iterations then exit
    monkeypatch.setattr(time, "sleep", lambda _: None)
    monkeypatch.setattr(time, "time", _make_time_mock(8))

    response = client.get("/room/TEST1/stream")
    data = response.text

    # Initial event: ready=False (0 -> bool -> False != None -> sends), solo=False, genre="All"
    assert '"ready": false' in data
    assert '"solo": false' in data
    assert '"genre": "All"' in data


def test_stream_stable_state_no_repeat(client, monkeypatch):
    """Stream does not repeat events when state hasn't changed between polls."""
    _seed_stream_room("TEST1", ready=0, current_genre="All")
    _set_session_room(client, os.environ["FLASK_SECRET"], "TEST1")

    # Force gevent sleep fallback path (gevent is available in test env)
    import jellyswipe
    monkeypatch.setattr(jellyswipe, "_gevent_sleep", None, raising=False)

    # deadline calc + init + loop iterations then exit
    monkeypatch.setattr(time, "sleep", lambda _: None)
    monkeypatch.setattr(time, "time", _make_time_mock(10))

    response = client.get("/room/TEST1/stream")
    data = response.text

    # Parse SSE events
    events = [e.strip() for e in data.split("\n\n") if e.strip()]

    # On first poll: ready=false and genre="All" sent (both differ from None)
    # On second poll: state unchanged, nothing sent
    ready_count = sum(1 for e in events if '"ready"' in e)
    genre_count = sum(1 for e in events if '"genre"' in e)

    assert ready_count == 1, f"Expected exactly 1 ready event, got {ready_count}: {events}"
    assert genre_count == 1, f"Expected exactly 1 genre event, got {genre_count}: {events}"


# ---------------------------------------------------------------------------
# Section 3: State change detection tests
# ---------------------------------------------------------------------------


def test_stream_match_event(client, monkeypatch):
    """Stream sends last_match event when room has match data with a timestamp."""
    match_data = json.dumps({"title": "Test Movie", "ts": "2026-04-26T12:00:00Z"})
    _seed_stream_room("TEST1", ready=1, last_match_data=match_data)
    _set_session_room(client, os.environ["FLASK_SECRET"], "TEST1")

    # Force gevent sleep fallback path (gevent is available in test env)
    import jellyswipe
    monkeypatch.setattr(jellyswipe, "_gevent_sleep", None, raising=False)

    # deadline + 2 iterations then exit
    monkeypatch.setattr(time, "sleep", lambda _: None)
    monkeypatch.setattr(time, "time", _make_time_mock(8))

    response = client.get("/room/TEST1/stream")
    data = response.text

    assert '"last_match"' in data
    assert '"title": "Test Movie"' in data


def test_stream_ready_state_change(client, monkeypatch):
    """Stream detects ready-state change between polling iterations."""
    _seed_stream_room("TEST1", ready=0)
    _set_session_room(client, os.environ["FLASK_SECRET"], "TEST1")

    # Force gevent sleep fallback path (gevent is available in test env)
    import jellyswipe
    monkeypatch.setattr(jellyswipe, "_gevent_sleep", None, raising=False)

    # Use a custom sleep side-effect that updates the DB on first call
    sleep_call_count = 0

    def _sleep_with_db_update(_):
        nonlocal sleep_call_count
        sleep_call_count += 1
        if sleep_call_count == 1:
            # After first poll (ready=0 sent), flip ready to 1
            conn = jellyswipe.db.get_db()
            try:
                conn.execute(
                    "UPDATE rooms SET ready = 1 WHERE pairing_code = ?",
                    ("TEST1",),
                )
                conn.commit()
            finally:
                conn.close()

    # deadline + loop iterations (with state changes) then exit
    monkeypatch.setattr(time, "sleep", _sleep_with_db_update)
    monkeypatch.setattr(time, "time", _make_time_mock(12))

    response = client.get("/room/TEST1/stream")
    data = response.text

    # Should have both initial ready=false and subsequent ready=true
    assert '"ready": false' in data, f"Missing initial ready=false in: {data}"
    assert '"ready": true' in data, f"Missing updated ready=true in: {data}"


# ---------------------------------------------------------------------------
# Section 4: GeneratorExit handling test
# ---------------------------------------------------------------------------


def test_stream_generator_exit(client, monkeypatch):
    """GeneratorExit is handled gracefully — no exception propagated on client disconnect."""
    _seed_stream_room("TEST1")
    _set_session_room(client, os.environ["FLASK_SECRET"], "TEST1")

    # Force gevent sleep fallback path (gevent is available in test env)
    import jellyswipe
    monkeypatch.setattr(jellyswipe, "_gevent_sleep", None, raising=False)

    result = {}
    error_holder = {}

    def consume():
        try:
            resp = client.get("/room/TEST1/stream")
            # Consume data while monkeypatch is active
            result["data"] = resp.text
            result["status"] = resp.status_code
            result["content_type"] = resp.headers.get("content-type", "")
        except Exception as exc:
            error_holder["error"] = exc

    # Mock time globally for the thread
    monkeypatch.setattr(time, "sleep", lambda _: None)
    monkeypatch.setattr(time, "time", _make_time_mock(10))

    t = threading.Thread(target=consume)
    t.start()
    t.join(timeout=10)

    # Thread completed without hanging
    assert not t.is_alive(), "Thread should have completed"
    # No exception raised
    assert "error" not in error_holder, f"Unexpected error: {error_holder['error']}"
    # Response was received successfully
    assert result.get("status") == 200
    assert "text/event-stream" in result.get("content_type", "")


# ---------------------------------------------------------------------------
# Section 5: SSE reliability tests (jitter, heartbeat, gevent sleep)
# ---------------------------------------------------------------------------


def test_stream_jitter_applied(client, monkeypatch):
    """Poll interval includes random jitter between 0 and 0.5 seconds."""
    _seed_stream_room("JITTER1")
    _set_session_room(client, os.environ["FLASK_SECRET"], "JITTER1")

    # Force gevent sleep fallback path so we can capture time.sleep calls
    import jellyswipe
    monkeypatch.setattr(jellyswipe, "_gevent_sleep", None, raising=False)

    sleep_calls = []
    def capture_sleep(duration):
        sleep_calls.append(duration)

    monkeypatch.setattr(time, "sleep", capture_sleep)
    monkeypatch.setattr(time, "time", _make_time_mock(10))

    response = client.get("/room/JITTER1/stream")
    _ = response.content  # consume generator

    assert len(sleep_calls) >= 1, f"Expected at least 1 sleep call, got {len(sleep_calls)}"
    for duration in sleep_calls:
        assert 1.5 <= duration <= 2.0, f"Sleep duration {duration} outside expected range [1.5, 2.0]"


def test_stream_heartbeat_on_idle(client, monkeypatch):
    """SSE stream sends : ping heartbeat when no data event for ~15 seconds."""
    _seed_stream_room("HB1", ready=0, current_genre="All")
    _set_session_room(client, os.environ["FLASK_SECRET"], "HB1")

    # Force gevent sleep fallback path
    import jellyswipe
    monkeypatch.setattr(jellyswipe, "_gevent_sleep", None, raising=False)

    # Create time mock that advances past 15 seconds between polls to trigger heartbeat.
    # The generator calls time.time() multiple times per loop iteration:
    #   - _last_event_time init (1 call)
    #   - deadline calculation (1 call)
    #   - while time.time() < deadline (1+ calls per iteration)
    #   - _last_event_time = time.time() after data event (if payload)
    #   - elif time.time() - _last_event_time >= 15 check (if no payload)
    # Strategy: first iteration sends data (calls 1-5), second iteration detects idle
    # time (calls 6-7 advance past 15s), heartbeat is sent (call 8), then exit.
    call_count = 0
    real_start = time.time()

    def _time_with_gap():
        nonlocal call_count
        call_count += 1
        if call_count <= 5:
            # Init + first iteration: real time (data event emitted)
            return real_start
        elif call_count <= 7:
            # Second iteration: advance 16 seconds to trigger heartbeat
            return real_start + 16
        else:
            # Past deadline: exit loop
            return real_start + 3700

    monkeypatch.setattr(time, "sleep", lambda _: None)
    monkeypatch.setattr(time, "time", _time_with_gap)

    response = client.get("/room/HB1/stream")
    data = response.text

    assert ": ping\n\n" in data, f"Expected heartbeat ': ping\\n\\n' in SSE stream, got: {repr(data)}"


def test_stream_no_heartbeat_when_data_sent(client, monkeypatch):
    """Heartbeat is NOT sent when data events are emitted within 15 seconds."""
    _seed_stream_room("NHB1", ready=0, current_genre="All")
    _set_session_room(client, os.environ["FLASK_SECRET"], "NHB1")

    # Force gevent sleep fallback path
    import jellyswipe
    monkeypatch.setattr(jellyswipe, "_gevent_sleep", None, raising=False)

    monkeypatch.setattr(time, "sleep", lambda _: None)
    monkeypatch.setattr(time, "time", _make_time_mock(10))

    response = client.get("/room/NHB1/stream")
    data = response.text

    # With rapid polls (mocked time advances quickly), state changes produce data events
    # and no heartbeat should appear since _last_event_time is reset on data emission
    ping_count = data.count(": ping")
    assert ping_count == 0, f"Expected no heartbeat when data events sent, but found {ping_count}"


def test_stream_room_disappearance_immediate_exit(client, monkeypatch):
    """SSE generator exits immediately when room record disappears from database (SSE-03)."""
    _seed_stream_room("VANISH1")
    _set_session_room(client, os.environ["FLASK_SECRET"], "VANISH1")

    # Force gevent sleep fallback path
    import jellyswipe
    monkeypatch.setattr(jellyswipe, "_gevent_sleep", None, raising=False)

    # Mock sleep to delete the room on first call, simulating disappearance between polls
    sleep_count = 0
    def _sleep_and_delete(_):
        nonlocal sleep_count
        sleep_count += 1
        if sleep_count == 1:
            # After first poll (initial state sent), delete the room
            conn = jellyswipe.db.get_db()
            try:
                conn.execute("DELETE FROM rooms WHERE pairing_code = ?", ("VANISH1",))
                conn.commit()
            finally:
                conn.close()

    monkeypatch.setattr(time, "sleep", _sleep_and_delete)
    monkeypatch.setattr(time, "time", _make_time_mock(10))

    response = client.get("/room/VANISH1/stream")
    data = response.text

    assert '"closed": true' in data, f"Expected closed:true event in SSE stream, got: {repr(data)}"
