"""Comprehensive SSE streaming tests for the /room/stream endpoint.

Tests cover SSE response format, state change events (ready, genre, solo, match),
room closure on missing room, stable state deduplication, and GeneratorExit handling.
Satisfies TEST-ROUTE-05.
"""

import asyncio
import json
import os
import secrets
import threading
import time
from datetime import datetime, timezone

import sqlite3

import pytest
from jellyswipe.db_paths import application_db_path
from tests.conftest import set_session_cookie


def _sqlite_conn_for_sse_tests():
    path = application_db_path.path
    assert path is not None
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


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
    """Seed a room row directly into SQLite for SSE tests (VAL-03: no jellyswipe.db.get_db)."""
    movie_data = json.dumps([])
    conn = _sqlite_conn_for_sse_tests()
    try:
        conn.execute(
            "INSERT INTO rooms (pairing_code, movie_data, ready, current_genre, solo_mode, last_match_data) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (room_code, movie_data, ready, current_genre, solo_mode, last_match_data),
        )
        conn.commit()
    finally:
        conn.close()


# Pre-generator time.time() call overhead in FastAPI TestClient context.
# During client.get(), the following call time.time() BEFORE the SSE generator runs:
# ~2 from httpx/starlette request timing, ~2 from cookie jar, ~1 from RequestIdMiddleware.
# All _make_time_mock thresholds must be >= this overhead + pre-loop setup (2 calls)
# to ensure deadline = real_start + 3600 (not real_start + 7300 which never expires).
_PRE_GENERATOR_OVERHEAD = 6


def _make_time_mock(iterations_before_timeout):
    """Create a time.time mock that advances past deadline after N calls.

    Returns a closure that returns real time for the first
    (iterations_before_timeout + _PRE_GENERATOR_OVERHEAD) calls, then returns
    real_time + 3700 (past the 3600s deadline) to exit the SSE polling loop.

    The overhead accounts for time.time() calls from httpx timing, cookies, and
    middleware that fire BEFORE the generator's deadline calculation.
    """
    # Add overhead so the deadline calculation runs BEFORE the mock triggers
    total_calls = iterations_before_timeout + _PRE_GENERATOR_OVERHEAD
    call_count = 0
    real_start = time.time()

    def _mock_time():
        nonlocal call_count
        call_count += 1
        if call_count > total_calls:
            return real_start + 3700
        return real_start
    return _mock_time


def _make_sse_sleep_mock(on_sleep_callback=None):
    """Create a selective asyncio.sleep mock for SSE generator testing.

    The SSE generator calls asyncio.sleep(delay) where delay is in [1.5, 2.0]
    (POLL=1.5 + random jitter 0–0.5). sse_starlette's _ping task uses exactly 15.0,
    and anyio/starlette internal checkpoints use 0 or 0.5.

    Strategy: intercept ONLY the generator's sleep range [1.4, 2.1] and yield control
    instantly (via asyncio.sleep(0)). This lets _ping run at its natural 15s interval,
    and task-group cancellation interrupts _ping after _stream_response completes.

    Passing through the _ping's 15s sleep means tests complete in at most one ping
    interval (15s) after the generator finishes — acceptable versus hanging indefinitely.

    Args:
        on_sleep_callback: Optional sync callable(delay) called when generator sleep is
                           intercepted. Sync only (called before yielding to event loop).
    """
    original_sleep = asyncio.sleep

    sleep_calls = []

    async def _selective_sleep(delay):
        if 1.4 <= delay <= 2.1:
            # Generator poll sleep in expected range — record and yield briefly
            sleep_calls.append(delay)
            if on_sleep_callback is not None:
                on_sleep_callback(delay)
            # Yield control without blocking, allowing task group to process cancellation
            await original_sleep(0)
        else:
            # _ping (15s), anyio checkpoints (0, 0.5) — keep real behavior
            await original_sleep(delay)

    return _selective_sleep, sleep_calls


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

    # Selective asyncio.sleep mock: skips SSE generator polls (>= 1.5s),
    # passes through internal anyio/sse_starlette sleeps (< 1.5s).
    mock_sleep, _ = _make_sse_sleep_mock()
    monkeypatch.setattr(asyncio, "sleep", mock_sleep)

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


def test_stream_room_not_found(client, monkeypatch):
    """Stream for nonexistent room sends closed event and stops."""
    _set_session_room(client, os.environ["FLASK_SECRET"], "FAKE")

    monkeypatch.setattr(time, "sleep", lambda _: None)
    monkeypatch.setattr(time, "time", _make_time_mock(3))

    response = client.get("/room/TEST1/stream")
    data = response.text

    assert 'data: {"closed": true}' in data

    events = [e for e in data.split("\n\n") if e.strip()]
    assert len(events) == 1


def test_stream_initial_state_events(client, monkeypatch):
    """Stream sends initial ready, solo, and genre events on first poll."""
    _seed_stream_room("TEST1", ready=0, current_genre="All", solo_mode=0)
    _set_session_room(client, os.environ["FLASK_SECRET"], "TEST1")

    # Force gevent sleep fallback path (gevent is available in test env)
    import jellyswipe
    monkeypatch.setattr(jellyswipe, "_gevent_sleep", None, raising=False)

    mock_sleep, _ = _make_sse_sleep_mock()
    monkeypatch.setattr(asyncio, "sleep", mock_sleep)

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

    mock_sleep, _ = _make_sse_sleep_mock()
    monkeypatch.setattr(asyncio, "sleep", mock_sleep)

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

    mock_sleep, _ = _make_sse_sleep_mock()
    monkeypatch.setattr(asyncio, "sleep", mock_sleep)

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

    # Use a sleep callback that updates DB on first generator poll sleep.
    # The SSE generator uses asyncio.sleep() — _make_sse_sleep_mock intercepts
    # those calls and invokes on_sleep_callback.
    sleep_call_count = 0

    def _on_sleep(delay):
        nonlocal sleep_call_count
        sleep_call_count += 1
        if sleep_call_count == 1:
            # After first poll (ready=0 sent), flip ready to 1
            conn = _sqlite_conn_for_sse_tests()
            try:
                conn.execute(
                    "UPDATE rooms SET ready = 1 WHERE pairing_code = ?",
                    ("TEST1",),
                )
                conn.commit()
            finally:
                conn.close()

    mock_sleep, _ = _make_sse_sleep_mock(on_sleep_callback=_on_sleep)
    monkeypatch.setattr(asyncio, "sleep", mock_sleep)
    # deadline + loop iterations (with state changes) then exit
    monkeypatch.setattr(time, "sleep", lambda _: None)
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

    mock_sleep, _ = _make_sse_sleep_mock()
    monkeypatch.setattr(asyncio, "sleep", mock_sleep)

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

    # Force gevent sleep fallback path so we can capture asyncio.sleep calls
    import jellyswipe
    monkeypatch.setattr(jellyswipe, "_gevent_sleep", None, raising=False)

    # Use _make_sse_sleep_mock to intercept SSE generator sleeps and capture durations
    mock_sleep, sleep_calls = _make_sse_sleep_mock()
    monkeypatch.setattr(asyncio, "sleep", mock_sleep)
    monkeypatch.setattr(time, "sleep", lambda _: None)
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

    mock_sleep, _ = _make_sse_sleep_mock()
    monkeypatch.setattr(asyncio, "sleep", mock_sleep)

    # Create time mock that advances past 15 seconds between polls to trigger heartbeat.
    # Thresholds account for _PRE_GENERATOR_OVERHEAD pre-generator calls PLUS:
    #   - _last_event_time init (1 call)
    #   - deadline calculation (1 call)
    #   - while time.time() < deadline (1 call)
    #   - inside first iteration: heartbeat check + event time (2 calls)
    # After first iteration: 16s gap triggers heartbeat; after second iteration: exit.
    call_count = 0
    real_start = time.time()
    # offset accounts for pre-generator overhead so deadline = real_start + 3600
    offset = _PRE_GENERATOR_OVERHEAD

    def _time_with_gap():
        nonlocal call_count
        call_count += 1
        if call_count <= offset + 5:
            # Pre-generator overhead + init + first iteration: real time
            return real_start
        elif call_count <= offset + 7:
            # Second iteration: advance 16 seconds to trigger heartbeat
            return real_start + 16
        else:
            # Past deadline: exit loop
            return real_start + 3700

    monkeypatch.setattr(time, "sleep", lambda _: None)
    monkeypatch.setattr(time, "time", _time_with_gap)

    response = client.get("/room/HB1/stream")
    data = response.text

    # SSE uses \r\n separators per spec (EventSourceResponse DEFAULT_SEPARATOR = "\r\n")
    assert ": ping" in data, f"Expected heartbeat ping in SSE stream, got: {repr(data)}"


def test_stream_no_heartbeat_when_data_sent(client, monkeypatch):
    """Heartbeat is NOT sent when data events are emitted within 15 seconds."""
    _seed_stream_room("NHB1", ready=0, current_genre="All")
    _set_session_room(client, os.environ["FLASK_SECRET"], "NHB1")

    # Force gevent sleep fallback path
    import jellyswipe
    monkeypatch.setattr(jellyswipe, "_gevent_sleep", None, raising=False)

    real_start = time.time()
    exit_after_idle_polls = [False]
    poll_sleeps = [0]

    def _after_poll_sleep(_delay):
        # End the stream only *between* full poll iterations so the next time.time()
        # call is the `while time.time() < deadline` check — not the `elif` that would
        # treat a fake +3700s jump as "idle for 15s" and emit a spurious ping.
        poll_sleeps[0] += 1
        if poll_sleeps[0] >= 40:
            exit_after_idle_polls[0] = True

    mock_sleep, _sleep_calls = _make_sse_sleep_mock(on_sleep_callback=_after_poll_sleep)
    monkeypatch.setattr(asyncio, "sleep", mock_sleep)

    def _time_frozen_then_exit_deadline():
        if exit_after_idle_polls[0]:
            return real_start + 3700
        return real_start

    monkeypatch.setattr(time, "sleep", lambda _: None)
    monkeypatch.setattr(time, "time", _time_frozen_then_exit_deadline)

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

    # Use a sleep callback that deletes the room on first generator poll sleep.
    sleep_count = 0

    def _on_sleep_delete(delay):
        nonlocal sleep_count
        sleep_count += 1
        if sleep_count == 1:
            # After first poll (initial state sent), delete the room
            conn = _sqlite_conn_for_sse_tests()
            try:
                conn.execute("DELETE FROM rooms WHERE pairing_code = ?", ("VANISH1",))
                conn.commit()
            finally:
                conn.close()

    mock_sleep, _ = _make_sse_sleep_mock(on_sleep_callback=_on_sleep_delete)
    monkeypatch.setattr(asyncio, "sleep", mock_sleep)
    monkeypatch.setattr(time, "sleep", lambda _: None)
    monkeypatch.setattr(time, "time", _make_time_mock(10))

    response = client.get("/room/VANISH1/stream")
    data = response.text

    assert '"closed": true' in data, f"Expected closed:true event in SSE stream, got: {repr(data)}"


# ---------------------------------------------------------------------------
# Section 6: Gap tests — disconnect detection, cleanup, CancelledError, auth
# ---------------------------------------------------------------------------


def test_stream_disconnect_breaks_loop_before_db_query(client, monkeypatch):
    """G1: is_disconnected() returning True breaks the poll loop before the next DB snapshot read.

    Strategy: seed a real room so the first poll succeeds and yields an event.
    Then mock is_disconnected to return True on the second call.
    Verify that the stream exits early — fetch_stream_snapshot call count confirms no
    additional query was issued after disconnect was detected.
    """
    from jellyswipe.repositories.rooms import RoomRepository

    _seed_stream_room("DISC1", ready=0, current_genre="All")
    _set_session_room(client, os.environ["FLASK_SECRET"], "DISC1")

    import jellyswipe
    monkeypatch.setattr(jellyswipe, "_gevent_sleep", None, raising=False)

    mock_sleep, sleep_calls = _make_sse_sleep_mock()
    monkeypatch.setattr(asyncio, "sleep", mock_sleep)
    monkeypatch.setattr(time, "sleep", lambda _: None)

    _orig_fetch = RoomRepository.fetch_stream_snapshot
    snapshot_calls = [0]

    async def counting_fetch(self, pairing_code):  # type: ignore[no-untyped-def]
        snapshot_calls[0] += 1
        return await _orig_fetch(self, pairing_code)

    monkeypatch.setattr(RoomRepository, "fetch_stream_snapshot", counting_fetch)

    # Patch is_disconnected on the Starlette Request class so all Request instances
    # use our fake. First call returns False (allow first poll), second returns True (break).
    from starlette.requests import Request as StarletteRequest

    is_disconnected_call_count = [0]

    async def fake_is_disconnected(self):
        is_disconnected_call_count[0] += 1
        # First call: not disconnected (let first poll happen)
        # Second call and beyond: disconnected (break loop before 2nd DB query)
        return is_disconnected_call_count[0] >= 2

    monkeypatch.setattr(StarletteRequest, "is_disconnected", fake_is_disconnected)

    # Use a safe deadline that won't time out before disconnect fires
    monkeypatch.setattr(time, "time", _make_time_mock(20))

    response = client.get("/room/DISC1/stream")
    data = response.text

    # The loop must have called is_disconnected at least once
    assert is_disconnected_call_count[0] >= 1, (
        f"is_disconnected was never called — disconnect detection not wired: calls={is_disconnected_call_count[0]}"
    )

    # After disconnect (2nd call returns True), the loop breaks BEFORE the next snapshot fetch.
    # So snapshot count must be exactly 1 (first poll) — not 2 or more.
    assert snapshot_calls[0] == 1, (
        f"Expected exactly 1 snapshot fetch (disconnect before 2nd query), got {snapshot_calls[0]}"
    )

    # The response is still a valid SSE stream (not an error)
    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("text/event-stream")


def test_stream_connection_closed_on_all_exit_paths(client, monkeypatch):
    """G2: each short-lived async session is closed after snapshot reads (context manager exit).

    Strategy: patch AsyncSession.close to count invocations. Consume a stream until
    deadline via time mock. Expect at least one close (one poll completed).
    """
    import sqlalchemy.ext.asyncio as sa_async

    _seed_stream_room("CLEANUP1", ready=0, current_genre="All")
    _set_session_room(client, os.environ["FLASK_SECRET"], "CLEANUP1")

    import jellyswipe
    monkeypatch.setattr(jellyswipe, "_gevent_sleep", None, raising=False)

    mock_sleep, _ = _make_sse_sleep_mock()
    monkeypatch.setattr(asyncio, "sleep", mock_sleep)
    monkeypatch.setattr(time, "sleep", lambda _: None)

    close_calls = [0]
    _orig_close = sa_async.AsyncSession.close

    async def counting_close(self):  # type: ignore[no-untyped-def]
        close_calls[0] += 1
        return await _orig_close(self)

    monkeypatch.setattr(sa_async.AsyncSession, "close", counting_close)

    # Time mock: exit after a few iterations (normal timeout exit path)
    monkeypatch.setattr(time, "time", _make_time_mock(8))

    response = client.get("/room/CLEANUP1/stream")
    _ = response.content  # consume fully

    assert close_calls[0] >= 1, (
        "Expected at least one AsyncSession.close from short-lived SSE poll sessions"
    )


def test_stream_cancelled_error_not_swallowed(monkeypatch):
    """G3: CancelledError raised inside the generate() loop must propagate out, not be swallowed.

    Strategy: unit test the generate() async generator directly by driving it with
    an async harness. Patch fetch_stream_snapshot so the snapshot read raises
    CancelledError on the first query. Verify CancelledError escapes the generator.
    """
    import asyncio
    from contextlib import asynccontextmanager

    import jellyswipe.routers.rooms as rooms_module
    from jellyswipe.repositories.rooms import RoomRepository
    from unittest.mock import AsyncMock, MagicMock, patch

    @asynccontextmanager
    async def _fake_async_session():
        yield MagicMock()

    class _FakeSessionMaker:
        def __call__(self):
            return _fake_async_session()

    monkeypatch.setattr(rooms_module, "get_sessionmaker", lambda: _FakeSessionMaker())

    # We need a Request object with is_disconnected returning False
    fake_request = MagicMock()
    fake_request.is_disconnected = AsyncMock(return_value=False)

    snapshot_calls = [0]

    async def raise_cancelled(self, pairing_code):  # type: ignore[no-untyped-def]
        snapshot_calls[0] += 1
        raise asyncio.CancelledError("simulated cancellation")

    # Extract the generate() inner function by calling room_stream
    from jellyswipe.dependencies import AuthUser
    fake_auth = AuthUser(jf_token="t", user_id="u")

    with patch.object(RoomRepository, "fetch_stream_snapshot", raise_cancelled):
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
            except (asyncio.CancelledError, Exception) as exc:
                if isinstance(exc, asyncio.CancelledError):
                    cancelled_error_propagated[0] = True
                else:
                    raise

        asyncio.run(drive_generator())

    assert cancelled_error_propagated[0], (
        "CancelledError was swallowed inside except Exception block — "
        "it must be re-raised so callers see cancellation semantics"
    )
    assert snapshot_calls[0] == 1, "Expected CancelledError to surface from first snapshot poll"


def test_room_stream_does_not_open_sqlite3_connection(client, monkeypatch):
    """Regression: SSE polling must stay off sync sqlite (get_db) in the router.

    aiosqlite opens sqlite under the hood for AsyncEngine — that is expected. This
    test blocks the legacy sync API so the stream path cannot regress to
    sqlite3.connect/get_db in application code.
    """
    _seed_stream_room("NO_SQLITE_ROUTE", ready=1, current_genre="All")
    _set_session_room(client, os.environ["FLASK_SECRET"], "NO_SQLITE_ROUTE")

    import jellyswipe.db as jelly_db

    def forbid_sync_get_db():
        pytest.fail("room_stream must not use jellyswipe.db.get_db() — use async SQLAlchemy sessions")

    monkeypatch.setattr(jelly_db, "get_db", forbid_sync_get_db, raising=False)

    import jellyswipe
    monkeypatch.setattr(jellyswipe, "_gevent_sleep", None, raising=False)

    mock_sleep, _ = _make_sse_sleep_mock()
    monkeypatch.setattr(asyncio, "sleep", mock_sleep)
    monkeypatch.setattr(time, "sleep", lambda _: None)
    monkeypatch.setattr(time, "time", _make_time_mock(4))

    response = client.get("/room/NO_SQLITE_ROUTE/stream")
    assert response.status_code == 200


def test_stream_unauthenticated_request_returns_401(client_real_auth):
    """G4: GET /room/{code}/stream without auth cookie must return HTTP 401.

    Uses client_real_auth (no dependency_overrides for require_auth).
    Sends request with no session cookie — real auth path must reject it.
    """
    # No set_session_cookie call — unauthenticated request
    response = client_real_auth.get("/room/AUTHTEST1/stream")

    assert response.status_code == 401, (
        f"Expected 401 for unauthenticated SSE request, got {response.status_code}: {response.text}"
    )
    body = response.json()
    assert "detail" in body, f"Expected 'detail' in 401 response body, got: {body}"
