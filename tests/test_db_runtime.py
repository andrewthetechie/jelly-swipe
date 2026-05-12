"""Tests for the async database runtime primitives."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import jellyswipe.db
import jellyswipe.db_runtime as db_runtime
from jellyswipe.db_runtime import (
    build_async_database_url,
    build_async_sqlite_url,
    dispose_runtime,
    get_sessionmaker,
    initialize_runtime,
)
from jellyswipe.migrations import (
    build_sqlite_url,
    get_database_url,
    normalize_sync_database_url,
)


pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
async def reset_runtime(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DB_PATH", raising=False)
    await dispose_runtime()
    yield
    await dispose_runtime()


async def test_get_sessionmaker_raises_before_initialization():
    with pytest.raises(RuntimeError, match="Async database runtime is not initialized"):
        get_sessionmaker()


async def test_sync_database_url_resolution_stays_canonical(db_path, monkeypatch):
    expected = build_sqlite_url(db_path)

    assert normalize_sync_database_url(f"sqlite+aiosqlite:///{db_path}") == expected
    assert get_database_url(db_path) == expected

    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    assert get_database_url() == expected

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_PATH", db_path)
    assert get_database_url() == expected


async def test_async_database_url_helpers_derive_from_sync_target(db_path, monkeypatch):
    expected_sync = build_sqlite_url(db_path)
    expected_async = f"sqlite+aiosqlite:///{db_path}"

    assert build_async_database_url(expected_sync) == expected_async
    assert build_async_sqlite_url(db_path) == expected_async


async def test_initialize_runtime_creates_usable_sessionmaker(db_path):
    await initialize_runtime(build_sqlite_url(db_path))

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        assert isinstance(session, AsyncSession)
        result = await session.execute(text("SELECT 1"))
        assert result.scalar_one() == 1

        foreign_keys = await session.execute(text("PRAGMA foreign_keys"))
        assert foreign_keys.scalar_one() == 1

        synchronous = await session.execute(text("PRAGMA synchronous"))
        assert synchronous.scalar_one() == 1


async def test_cached_sessionmaker_creates_distinct_sessions(db_path):
    await initialize_runtime(build_sqlite_url(db_path))

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session_one, sessionmaker() as session_two:
        assert session_one is not session_two
        assert isinstance(session_one, AsyncSession)
        assert isinstance(session_two, AsyncSession)


async def test_dispose_runtime_clears_cached_state(db_path):
    await initialize_runtime(build_sqlite_url(db_path))

    assert db_runtime.RUNTIME_DATABASE_URL is not None
    assert db_runtime.RUNTIME_ENGINE is not None
    assert db_runtime.RUNTIME_SESSIONMAKER is not None

    await dispose_runtime()

    assert db_runtime.RUNTIME_DATABASE_URL is None
    assert db_runtime.RUNTIME_ENGINE is None
    assert db_runtime.RUNTIME_SESSIONMAKER is None

    with pytest.raises(RuntimeError, match="Async database runtime is not initialized"):
        get_sessionmaker()
