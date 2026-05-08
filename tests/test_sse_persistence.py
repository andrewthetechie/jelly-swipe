"""Focused coverage for SSE stream snapshot persistence — Phase 39-04."""

from __future__ import annotations

import json

import jellyswipe.db
import pytest
from sqlalchemy import update

from jellyswipe.db_runtime import build_async_sqlite_url, dispose_runtime, get_sessionmaker, initialize_runtime
from jellyswipe.db_uow import DatabaseUnitOfWork
from jellyswipe.migrations import build_sqlite_url, upgrade_to_head
from jellyswipe.models.room import Room


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
class TestStreamSnapshotRepo:
    async def test_fetch_stream_snapshot_missing_room(self, runtime_sessionmaker):
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            snap = await uow.rooms.fetch_stream_snapshot("NONE")
            assert snap is None

    async def test_fetch_stream_snapshot_preserves_ready_solo_last_match_ts(self, runtime_sessionmaker):
        persisted_ts = 442
        lm = json.dumps({"type": "match", "movie_id": "m99", "title": "T", "thumb": "/", "ts": persisted_ts})
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
            await session.execute(
                update(Room).where(Room.pairing_code == "4242").values(last_match_data=lm),
            )
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            snap = await uow.rooms.fetch_stream_snapshot("4242")

        assert snap is not None
        assert snap.ready is True
        assert snap.solo is True
        assert snap.last_match == json.loads(lm)
        assert snap.last_match_ts == persisted_ts

