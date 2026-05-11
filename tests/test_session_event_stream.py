"""Tests for session_event_stream generator with injectable dependencies.

Tests the generator directly with fake dependencies:
- Fake notifier: subscribe returns a Future, notify resolves it on demand
- Fake is_disconnected: returns True after N calls
- Real in-memory DB via runtime_sessionmaker
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from jellyswipe.db_runtime import (
    build_async_sqlite_url,
    dispose_runtime,
    get_sessionmaker,
    initialize_runtime,
)
from jellyswipe.migrations import build_sqlite_url, upgrade_to_head
from jellyswipe.services.session_event_stream import session_event_stream

import jellyswipe.db_paths as db_paths_mod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_runtime(monkeypatch):
    """Reset runtime state before each test."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DB_PATH", raising=False)
    monkeypatch.setattr(db_paths_mod.application_db_path, "path", None)
    yield


@pytest.fixture
async def runtime_sessionmaker(db_path, monkeypatch):
    """Provide an async sessionmaker backed by a temp SQLite DB."""
    sync_database_url = build_sqlite_url(db_path)
    runtime_database_url = build_async_sqlite_url(db_path)

    monkeypatch.setattr(db_paths_mod.application_db_path, "path", db_path)
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("DATABASE_URL", sync_database_url)

    upgrade_to_head(sync_database_url)
    await initialize_runtime(runtime_database_url)
    yield get_sessionmaker()
    await dispose_runtime()


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
    """Seed a room row and session instance for tests."""
    import secrets

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


def _sqlite_conn(db_path):
    """Get a direct sqlite3 connection."""
    import sqlite3

    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


class FakeNotifier:
    """Fake notifier that lets tests control when subscribe futures resolve."""

    def __init__(self):
        self._subscribers: dict[str, set[asyncio.Future]] = {}

    def subscribe(self, room_code: str) -> asyncio.Future:
        future: asyncio.Future = asyncio.Future()
        if room_code not in self._subscribers:
            self._subscribers[room_code] = set()
        self._subscribers[room_code].add(future)
        return future

    def notify(self, room_code: str) -> None:
        """Resolve all subscribers for a room."""
        if room_code not in self._subscribers:
            return
        futures = self._subscribers.pop(room_code)
        for future in futures:
            if not future.done():
                future.set_result(None)

    def unsubscribe(self, room_code: str, future: asyncio.Future) -> None:
        if room_code not in self._subscribers:
            return
        self._subscribers[room_code].discard(future)
        if not future.done():
            future.cancel()
        if not self._subscribers[room_code]:
            del self._subscribers[room_code]


def _make_disconnected_after(after_calls: int):
    """Return an is_disconnected callable that returns True after N calls."""
    call_count = [0]

    async def is_disconnected():
        call_count[0] += 1
        return call_count[0] >= after_calls

    return is_disconnected, call_count


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
class TestSessionEventStream:
    """Test the session_event_stream generator directly."""

    async def test_first_attach_no_cursor_yields_bootstrap(
        self, runtime_sessionmaker, db_path
    ):
        """First attach (no cursor) yields session_bootstrap with correct fields."""
        conn = _sqlite_conn(db_path)
        instance_id = _seed_room_and_instance(
            conn, "BOOT1", ready=1, current_genre="Action", solo_mode=1, hide_watched=1
        )
        conn.close()

        notifier = FakeNotifier()
        is_disconnected, _ = _make_disconnected_after(1)

        gen = session_event_stream(
            code="BOOT1",
            instance_id=instance_id,
            room=MagicMock(
                ready=True, current_genre="Action", solo_mode=True, hide_watched=True
            ),
            cursor=None,
            sessionmaker_factory=runtime_sessionmaker,
            notifier=notifier,
            is_disconnected=is_disconnected,
        )

        events = []
        async for event in gen:
            events.append(event)

        assert len(events) >= 1
        data = json.loads(events[0]["data"])
        assert data["event_type"] == "session_bootstrap"
        assert data["instance_id"] == instance_id
        assert data["ready"] is True
        assert data["genre"] == "Action"
        assert data["solo"] is True
        assert data["hide_watched"] is True
        assert "replay_boundary" in data

    async def test_first_attach_replay_boundary_is_latest_event_id(
        self, runtime_sessionmaker, db_path
    ):
        """First attach with existing events: replay_boundary is the latest event_id."""
        conn = _sqlite_conn(db_path)
        instance_id = _seed_room_and_instance(conn, "BOOT2")
        _seed_event(conn, instance_id, "swipe", json.dumps({"media_id": "m1"}))
        eid2 = _seed_event(conn, instance_id, "swipe", json.dumps({"media_id": "m2"}))
        conn.close()

        notifier = FakeNotifier()
        is_disconnected, _ = _make_disconnected_after(1)

        gen = session_event_stream(
            code="BOOT2",
            instance_id=instance_id,
            room=MagicMock(
                ready=False, current_genre="All", solo_mode=False, hide_watched=False
            ),
            cursor=None,
            sessionmaker_factory=runtime_sessionmaker,
            notifier=notifier,
            is_disconnected=is_disconnected,
        )

        events = []
        async for event in gen:
            events.append(event)

        data = json.loads(events[0]["data"])
        assert data["replay_boundary"] == eid2

    async def test_reconnect_valid_cursor_replays_missed_events(
        self, runtime_sessionmaker, db_path
    ):
        """Reconnect with valid cursor: missed events replayed in order."""
        conn = _sqlite_conn(db_path)
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
        conn.close()

        notifier = FakeNotifier()
        is_disconnected, _ = _make_disconnected_after(1)

        gen = session_event_stream(
            code="REPLAY1",
            instance_id=instance_id,
            room=None,
            cursor=eid1,
            sessionmaker_factory=runtime_sessionmaker,
            notifier=notifier,
            is_disconnected=is_disconnected,
        )

        events = []
        async for event in gen:
            events.append(event)

        assert len(events) >= 1
        data = json.loads(events[0]["data"])
        assert data["event_type"] == "match_found"
        assert data["event_id"] == eid2

    async def test_reconnect_events_in_order(self, runtime_sessionmaker, db_path):
        """Replayed events are delivered in event_id order."""
        conn = _sqlite_conn(db_path)
        instance_id = _seed_room_and_instance(conn, "REPLAY2")
        eid1 = _seed_event(conn, instance_id, "swipe", json.dumps({"media_id": "m1"}))
        eid2 = _seed_event(conn, instance_id, "swipe", json.dumps({"media_id": "m2"}))
        eid3 = _seed_event(
            conn, instance_id, "match_found", json.dumps({"media_id": "m1"})
        )
        conn.close()

        notifier = FakeNotifier()
        is_disconnected, _ = _make_disconnected_after(1)

        gen = session_event_stream(
            code="REPLAY2",
            instance_id=instance_id,
            room=None,
            cursor=eid1,
            sessionmaker_factory=runtime_sessionmaker,
            notifier=notifier,
            is_disconnected=is_disconnected,
        )

        events = []
        async for event in gen:
            events.append(event)

        assert len(events) == 2
        assert json.loads(events[0]["data"])["event_id"] == eid2
        assert json.loads(events[1]["data"])["event_id"] == eid3

    async def test_reconnect_stale_cursor_yields_session_reset(
        self, runtime_sessionmaker, db_path
    ):
        """Reconnect with stale cursor: yields session_reset with reason=stale_cursor."""
        conn = _sqlite_conn(db_path)
        instance_id = _seed_room_and_instance(conn, "STALE1")
        conn.close()

        notifier = FakeNotifier()
        is_disconnected, _ = _make_disconnected_after(1)

        gen = session_event_stream(
            code="STALE1",
            instance_id=instance_id,
            room=None,
            cursor=999,
            sessionmaker_factory=runtime_sessionmaker,
            notifier=notifier,
            is_disconnected=is_disconnected,
        )

        events = []
        async for event in gen:
            events.append(event)

        assert len(events) == 1
        data = json.loads(events[0]["data"])
        assert data["event_type"] == "session_reset"
        assert data["reason"] == "stale_cursor"

    async def test_session_closed_during_replay_stops_generator(
        self, runtime_sessionmaker, db_path
    ):
        """session_closed event during replay: generator stops after yielding session_closed."""
        conn = _sqlite_conn(db_path)
        instance_id = _seed_room_and_instance(conn, "CLOSE1")
        _seed_event(conn, instance_id, "swipe", json.dumps({"media_id": "m1"}))
        _seed_event(
            conn, instance_id, "session_closed", json.dumps({"reason": "user_quit"})
        )
        conn.close()

        notifier = FakeNotifier()
        is_disconnected, _ = _make_disconnected_after(1)

        gen = session_event_stream(
            code="CLOSE1",
            instance_id=instance_id,
            room=None,
            cursor=0,
            sessionmaker_factory=runtime_sessionmaker,
            notifier=notifier,
            is_disconnected=is_disconnected,
        )

        events = []
        async for event in gen:
            events.append(event)

        # Should have swipe + session_closed, then stop
        event_types = [json.loads(e["data"])["event_type"] for e in events]
        assert "session_closed" in event_types
        # No bootstrap since cursor was provided
        assert not any("session_bootstrap" in e.get("data", "") for e in events)

    async def test_disconnect_detected_exits_cleanly(
        self, runtime_sessionmaker, db_path
    ):
        """Disconnect detected: is_disconnected returns True -> generator exits cleanly."""
        conn = _sqlite_conn(db_path)
        instance_id = _seed_room_and_instance(conn, "DISC1")
        conn.close()

        notifier = FakeNotifier()
        is_disconnected, call_count = _make_disconnected_after(1)

        gen = session_event_stream(
            code="DISC1",
            instance_id=instance_id,
            room=None,
            cursor=None,
            sessionmaker_factory=runtime_sessionmaker,
            notifier=notifier,
            is_disconnected=is_disconnected,
        )

        events = []
        async for event in gen:
            events.append(event)

        # Should get bootstrap then exit on disconnect
        assert len(events) >= 1
        assert "session_bootstrap" in events[0]["data"]
        assert call_count[0] >= 1

    async def test_first_attach_no_room_yields_defaults(
        self, runtime_sessionmaker, db_path
    ):
        """First attach with no room object yields default values."""
        conn = _sqlite_conn(db_path)
        instance_id = _seed_room_and_instance(conn, "NOROOM1")
        conn.close()

        notifier = FakeNotifier()
        is_disconnected, _ = _make_disconnected_after(1)

        gen = session_event_stream(
            code="NOROOM1",
            instance_id=instance_id,
            room=None,
            cursor=None,
            sessionmaker_factory=runtime_sessionmaker,
            notifier=notifier,
            is_disconnected=is_disconnected,
        )

        events = []
        async for event in gen:
            events.append(event)

        data = json.loads(events[0]["data"])
        assert data["ready"] is False
        assert data["genre"] == "All"
        assert data["solo"] is False
        assert data["hide_watched"] is False
