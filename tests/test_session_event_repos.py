"""Repository-level unit tests for session event persistence."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import jellyswipe.db
import jellyswipe.db_paths
import pytest
from sqlalchemy import text

from jellyswipe.db_runtime import (
    build_async_sqlite_url,
    dispose_runtime,
    get_sessionmaker,
    initialize_runtime,
)
from jellyswipe.db_uow import DatabaseUnitOfWork
from jellyswipe.migrations import build_sqlite_url, upgrade_to_head
from jellyswipe.repositories.session_events import append_sync


@pytest.fixture(autouse=True)
def reset_runtime(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DB_PATH", raising=False)
    monkeypatch.setattr(jellyswipe.db_paths.application_db_path, "path", None)
    yield


@pytest.fixture
async def runtime_sessionmaker(db_path, monkeypatch):
    sync_database_url = build_sqlite_url(db_path)
    runtime_database_url = build_async_sqlite_url(db_path)

    monkeypatch.setattr(jellyswipe.db_paths.application_db_path, "path", db_path)
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("DATABASE_URL", sync_database_url)

    upgrade_to_head(sync_database_url)
    await initialize_runtime(runtime_database_url)
    yield get_sessionmaker()
    await dispose_runtime()


@pytest.mark.anyio
class TestSessionEventRepository:
    async def test_append_and_read_after_returns_event(self, runtime_sessionmaker):
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.session_instances.create("inst-1", "1234")
            event_id = await uow.session_events.append(
                "inst-1", "test_event", json.dumps({"key": "value"})
            )
            await session.commit()

        assert event_id is not None
        assert event_id > 0

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            events = await uow.session_events.read_after("inst-1", after_event_id=0)

        assert len(events) == 1
        assert events[0].event_id == event_id
        assert events[0].event_type == "test_event"
        assert json.loads(events[0].payload_json) == {"key": "value"}

    async def test_read_after_multiple_events_returns_in_order(
        self, runtime_sessionmaker
    ):
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.session_instances.create("inst-2", "5678")
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            id1 = await uow.session_events.append(
                "inst-2", "event1", json.dumps({"n": 1})
            )
            id2 = await uow.session_events.append(
                "inst-2", "event2", json.dumps({"n": 2})
            )
            id3 = await uow.session_events.append(
                "inst-2", "event3", json.dumps({"n": 3})
            )
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            events = await uow.session_events.read_after("inst-2", after_event_id=0)

        assert len(events) == 3
        assert events[0].event_id == id1
        assert events[1].event_id == id2
        assert events[2].event_id == id3
        assert events[0].event_type == "event1"
        assert events[1].event_type == "event2"
        assert events[2].event_type == "event3"

    async def test_read_after_skips_events_up_to_after_event_id(
        self, runtime_sessionmaker
    ):
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.session_instances.create("inst-3", "9012")
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.session_events.append("inst-3", "event1", json.dumps({"n": 1}))
            await uow.session_events.append("inst-3", "event2", json.dumps({"n": 2}))
            await uow.session_events.append("inst-3", "event3", json.dumps({"n": 3}))
            await uow.session_events.append("inst-3", "event4", json.dumps({"n": 4}))
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            events = await uow.session_events.read_after("inst-3", after_event_id=2)

        assert len(events) == 2
        assert events[0].event_type == "event3"
        assert events[1].event_type == "event4"

    async def test_read_after_filters_by_instance_id(self, runtime_sessionmaker):
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.session_instances.create("inst-a", "1111")
            await uow.session_instances.create("inst-b", "2222")
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.session_events.append(
                "inst-a", "event_a", json.dumps({"src": "a"})
            )
            await uow.session_events.append(
                "inst-b", "event_b", json.dumps({"src": "b"})
            )
            await uow.session_events.append(
                "inst-a", "event_a2", json.dumps({"src": "a2"})
            )
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            events_a = await uow.session_events.read_after("inst-a", after_event_id=0)
            events_b = await uow.session_events.read_after("inst-b", after_event_id=0)

        assert len(events_a) == 2
        assert all(e.session_instance_id == "inst-a" for e in events_a)
        assert len(events_b) == 1
        assert events_b[0].session_instance_id == "inst-b"

    async def test_append_raw_sql_with_raw_connection(self, runtime_sessionmaker):
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.session_instances.create("inst-raw", "3333")
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            # Get the raw connection from the session
            conn = await session.connection()
            event_id = await uow.session_events.append_raw_sql(
                conn, "inst-raw", "raw_event", json.dumps({"raw": True})
            )
            await session.commit()

        assert event_id is not None
        assert event_id > 0

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            events = await uow.session_events.read_after("inst-raw", after_event_id=0)

        assert len(events) == 1
        assert events[0].event_type == "raw_event"
        assert json.loads(events[0].payload_json) == {"raw": True}

    async def test_append_sync_returns_positive_event_id(self, runtime_sessionmaker):
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.session_instances.create("inst-sync", "SYNC1")
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            event_id = await session.run_sync(
                lambda conn: append_sync(
                    conn, "inst-sync", "sync_event", json.dumps({"sync": True})
                )
            )
            await session.commit()

        assert event_id is not None
        assert event_id > 0

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            events = await uow.session_events.read_after("inst-sync", after_event_id=0)

        assert len(events) == 1
        assert events[0].event_type == "sync_event"
        assert json.loads(events[0].payload_json) == {"sync": True}

    async def test_append_sync_created_at_is_valid_iso8601(self, runtime_sessionmaker):
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.session_instances.create("inst-sync-iso", "SYNC2")
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await session.run_sync(
                lambda conn: append_sync(
                    conn, "inst-sync-iso", "iso_test", json.dumps({})
                )
            )
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            events = await uow.session_events.read_after(
                "inst-sync-iso", after_event_id=0
            )

        assert len(events) == 1
        # Verify created_at is a valid ISO 8601 string
        dt = datetime.fromisoformat(events[0].created_at)
        assert dt.tzinfo is not None

    async def test_append_sync_inside_begin_immediate_transaction(
        self, runtime_sessionmaker
    ):
        """Verify append_sync works inside a BEGIN IMMEDIATE transaction."""
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.session_instances.create("inst-sync-imm", "SYNC3")
            await session.commit()

        async with runtime_sessionmaker() as session:
            # Use run_sync to get a sync connection and execute BEGIN IMMEDIATE
            def _append_in_immediate(conn):
                conn.execute(text("BEGIN IMMEDIATE"))
                event_id = append_sync(
                    conn, "inst-sync-imm", "immediate_event", json.dumps({"imm": True})
                )
                conn.execute(text("COMMIT"))
                return event_id

            event_id = await session.run_sync(_append_in_immediate)

        assert event_id is not None
        assert event_id > 0

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            events = await uow.session_events.read_after(
                "inst-sync-imm", after_event_id=0
            )

        assert len(events) == 1
        assert events[0].event_type == "immediate_event"

    async def test_delete_for_instance_removes_all_events(self, runtime_sessionmaker):
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.session_instances.create("inst-del", "4444")
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.session_events.append("inst-del", "event1", json.dumps({}))
            await uow.session_events.append("inst-del", "event2", json.dumps({}))
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            count = await uow.session_events.delete_for_instance("inst-del")
            await session.commit()

        assert count == 2

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            events = await uow.session_events.read_after("inst-del", after_event_id=0)

        assert len(events) == 0


@pytest.mark.anyio
class TestSessionInstanceRepository:
    async def test_is_pairing_code_reserved_active_returns_true(
        self, runtime_sessionmaker
    ):
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.session_instances.create("inst-active", "5555")
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            reserved = await uow.session_instances.is_pairing_code_reserved("5555")

        assert reserved is True

    async def test_is_pairing_code_reserved_closing_returns_true(
        self, runtime_sessionmaker
    ):
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.session_instances.create("inst-closing", "6666")
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.session_instances.mark_closing("inst-closing")
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            reserved = await uow.session_instances.is_pairing_code_reserved("6666")

        assert reserved is True

    async def test_is_pairing_code_reserved_closed_returns_false(
        self, runtime_sessionmaker
    ):
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.session_instances.create("inst-closed", "7777")
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.session_instances.mark_closing("inst-closed")
            await uow.session_instances.mark_closed("inst-closed")
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            reserved = await uow.session_instances.is_pairing_code_reserved("7777")

        assert reserved is False

    async def test_is_pairing_code_reserved_nonexistent_returns_false(
        self, runtime_sessionmaker
    ):
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            reserved = await uow.session_instances.is_pairing_code_reserved("9999")

        assert reserved is False

    async def test_mark_closing_sets_status_and_closed_at(self, runtime_sessionmaker):
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.session_instances.create("inst-mark-closing", "8888")
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.session_instances.mark_closing("inst-mark-closing")
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            instance = await uow.session_instances.get_by_instance_id(
                "inst-mark-closing"
            )

        assert instance.status == "closing"
        assert instance.closed_at is not None
        assert datetime.fromisoformat(instance.closed_at) is not None

    async def test_mark_closed_sets_status(self, runtime_sessionmaker):
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.session_instances.create("inst-mark-closed", "0000")
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.session_instances.mark_closing("inst-mark-closed")
            await uow.session_instances.mark_closed("inst-mark-closed")
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            instance = await uow.session_instances.get_by_instance_id(
                "inst-mark-closed"
            )

        assert instance.status == "closed"

    async def test_cleanup_closed_before_deletes_old_closed_instances(
        self, runtime_sessionmaker
    ):
        import asyncio

        # Create and close the old instance
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.session_instances.create("inst-old", "1212")
            await uow.session_instances.mark_closing("inst-old")
            await uow.session_instances.mark_closed("inst-old")
            await session.commit()

        # Wait to ensure different created_at timestamps
        await asyncio.sleep(0.1)
        cutoff = datetime.now(timezone.utc).isoformat()
        await asyncio.sleep(0.1)

        # Create and close the new instance after cutoff
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.session_instances.create("inst-new", "3434")
            await uow.session_instances.mark_closing("inst-new")
            await uow.session_instances.mark_closed("inst-new")
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            deleted = await uow.session_instances.cleanup_closed_before(cutoff)
            await session.commit()

        assert deleted == 1

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            old_inst = await uow.session_instances.get_by_instance_id("inst-old")
            new_inst = await uow.session_instances.get_by_instance_id("inst-new")

        assert old_inst is None
        assert new_inst is not None


@pytest.mark.anyio
class TestMigration:
    async def test_migration_creates_tables_and_removes_last_match_data(
        self, db_path, monkeypatch
    ):
        sync_database_url = build_sqlite_url(db_path)
        runtime_database_url = build_async_sqlite_url(db_path)

        monkeypatch.setattr(jellyswipe.db_paths.application_db_path, "path", db_path)
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setenv("DATABASE_URL", sync_database_url)

        upgrade_to_head(sync_database_url)
        await initialize_runtime(runtime_database_url)
        sessionmaker = get_sessionmaker()

        try:
            async with sessionmaker() as session:
                result = await session.execute(
                    text(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='session_instances'"
                    )
                )
                assert result.scalar() is not None

                result = await session.execute(
                    text(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='session_events'"
                    )
                )
                assert result.scalar() is not None

                result = await session.execute(
                    text(
                        "SELECT name FROM sqlite_master WHERE type='index' AND name='ix_session_events_session_instance_id_event_id'"
                    )
                )
                assert result.scalar() is not None

                result = await session.execute(text("PRAGMA table_info(rooms)"))
                columns = [row[1] for row in result.all()]
                assert "last_match_data" not in columns
        finally:
            await dispose_runtime()
