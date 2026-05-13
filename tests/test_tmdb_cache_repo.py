"""Repository-level unit tests for TMDB cache persistence."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

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
class TestTmdbCacheRepository:
    async def test_put_then_get_returns_stored_record(self, runtime_sessionmaker):
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.tmdb_cache.put("movie-1", "trailer", json.dumps({"key": "value"}))
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            record = await uow.tmdb_cache.get("movie-1", "trailer")

        assert record is not None
        assert record.media_id == "movie-1"
        assert record.lookup_type == "trailer"
        assert json.loads(record.result_json) == {"key": "value"}

    async def test_get_with_fresh_entry_returns_record(self, runtime_sessionmaker):
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.tmdb_cache.put("movie-2", "trailer", json.dumps({"fresh": True}))
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            record = await uow.tmdb_cache.get("movie-2", "trailer", max_age_days=7)

        assert record is not None
        assert record.media_id == "movie-2"

    async def test_get_with_stale_entry_returns_none(self, runtime_sessionmaker):
        stale_time = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await session.execute(
                text(
                    "INSERT INTO tmdb_cache (media_id, lookup_type, result_json, fetched_at) "
                    "VALUES (:media_id, :lookup_type, :result_json, :fetched_at)"
                ),
                {
                    "media_id": "movie-3",
                    "lookup_type": "trailer",
                    "result_json": json.dumps({"stale": True}),
                    "fetched_at": stale_time,
                },
            )
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            record = await uow.tmdb_cache.get("movie-3", "trailer", max_age_days=7)

        assert record is None

    async def test_get_at_exact_max_age_boundary_returns_none(
        self, runtime_sessionmaker
    ):
        boundary_time = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await session.execute(
                text(
                    "INSERT INTO tmdb_cache (media_id, lookup_type, result_json, fetched_at) "
                    "VALUES (:media_id, :lookup_type, :result_json, :fetched_at)"
                ),
                {
                    "media_id": "movie-4",
                    "lookup_type": "trailer",
                    "result_json": json.dumps({"boundary": True}),
                    "fetched_at": boundary_time,
                },
            )
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            record = await uow.tmdb_cache.get("movie-4", "trailer", max_age_days=7)

        assert record is None

    async def test_get_for_missing_media_id_returns_none(self, runtime_sessionmaker):
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            record = await uow.tmdb_cache.get("nonexistent", "trailer")

        assert record is None

    async def test_get_filters_by_lookup_type(self, runtime_sessionmaker):
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.tmdb_cache.put(
                "movie-5", "trailer", json.dumps({"type": "trailer"})
            )
            await uow.tmdb_cache.put("movie-5", "cast", json.dumps({"type": "cast"}))
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            trailer_record = await uow.tmdb_cache.get("movie-5", "trailer")
            cast_record = await uow.tmdb_cache.get("movie-5", "cast")

        assert trailer_record is not None
        assert json.loads(trailer_record.result_json) == {"type": "trailer"}
        assert cast_record is not None
        assert json.loads(cast_record.result_json) == {"type": "cast"}

    async def test_put_upserts_overwrites_existing(self, runtime_sessionmaker):
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.tmdb_cache.put("movie-6", "trailer", json.dumps({"version": 1}))
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.tmdb_cache.put("movie-6", "trailer", json.dumps({"version": 2}))
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            record = await uow.tmdb_cache.get("movie-6", "trailer")

        assert record is not None
        assert json.loads(record.result_json) == {"version": 2}

    async def test_cleanup_stale_deletes_old_entries_returns_count(
        self, runtime_sessionmaker
    ):
        stale_time = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await session.execute(
                text(
                    "INSERT INTO tmdb_cache (media_id, lookup_type, result_json, fetched_at) "
                    "VALUES (:media_id, :lookup_type, :result_json, :fetched_at)"
                ),
                {
                    "media_id": "movie-old-1",
                    "lookup_type": "trailer",
                    "result_json": json.dumps({"old": True}),
                    "fetched_at": stale_time,
                },
            )
            await session.execute(
                text(
                    "INSERT INTO tmdb_cache (media_id, lookup_type, result_json, fetched_at) "
                    "VALUES (:media_id, :lookup_type, :result_json, :fetched_at)"
                ),
                {
                    "media_id": "movie-old-2",
                    "lookup_type": "cast",
                    "result_json": json.dumps({"old": True}),
                    "fetched_at": stale_time,
                },
            )
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            deleted = await uow.tmdb_cache.cleanup_stale(max_age_days=30)

        assert deleted == 2

    async def test_cleanup_stale_does_not_delete_fresh_entries(
        self, runtime_sessionmaker
    ):
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.tmdb_cache.put(
                "movie-fresh", "trailer", json.dumps({"fresh": True})
            )
            await session.commit()

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            deleted = await uow.tmdb_cache.cleanup_stale(max_age_days=30)

        assert deleted == 0

        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            record = await uow.tmdb_cache.get("movie-fresh", "trailer")

        assert record is not None

    async def test_cleanup_stale_with_no_stale_entries_returns_zero(
        self, runtime_sessionmaker
    ):
        async with runtime_sessionmaker() as session:
            uow = DatabaseUnitOfWork(session)
            deleted = await uow.tmdb_cache.cleanup_stale(max_age_days=30)

        assert deleted == 0
