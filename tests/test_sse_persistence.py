"""Focused coverage for SSE stream snapshot persistence — Phase 39-04."""

from __future__ import annotations

import jellyswipe.db
import pytest

from jellyswipe.db_runtime import (
    build_async_sqlite_url,
    dispose_runtime,
    get_sessionmaker,
    initialize_runtime,
)
from jellyswipe.db_uow import DatabaseUnitOfWork
from jellyswipe.migrations import build_sqlite_url, upgrade_to_head
from jellyswipe.room_types import RoomStatusSnapshot


@pytest.fixture(autouse=True)
def reset_runtime(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DB_PATH", raising=False)
    yield


@pytest.fixture
async def runtime_sessionmaker(db_path, monkeypatch):
    sync_database_url = build_sqlite_url(db_path)
    runtime_database_url = build_async_sqlite_url(db_path)

    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("DATABASE_URL", sync_database_url)

    upgrade_to_head(sync_database_url)
    await initialize_runtime(runtime_database_url)
    yield get_sessionmaker()
    await dispose_runtime()


@pytest.mark.anyio
class TestStreamSnapshotRepo:
    async def test_fetch_status_missing_room(self, runtime_sessionmaker):
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            snap = await uow.rooms.fetch_status("NONE")
            assert snap is None

    async def test_fetch_status_preserves_ready_solo_hide_watched(
        self, runtime_sessionmaker
    ):
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.rooms.create(
                "4242",
                movie_data_json="[]",
                ready=True,
                current_genre="All",
                solo_mode=True,
                deck_position_json="{}",
            )
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            snap = await uow.rooms.fetch_status("4242")

        assert snap is not None
        assert isinstance(snap, RoomStatusSnapshot)
        assert snap.ready is True
        assert snap.solo is True
        assert snap.hide_watched is False
