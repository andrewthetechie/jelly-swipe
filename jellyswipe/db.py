"""Synchronous SQLite runtime helpers for Jelly Swipe."""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import jellyswipe.db_runtime as db_runtime
from jellyswipe.db_paths import application_db_path
from jellyswipe.db_uow import DatabaseUnitOfWork


def configure_sqlite_connection(conn: sqlite3.Connection) -> sqlite3.Connection:
    """Apply runtime SQLite settings required by the current sync code paths."""
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


async def _initialize_maintenance_runtime(database_url: str | None = None) -> tuple[str, bool]:
    target_sync_url = database_url or _get_database_url()
    target_async_url = db_runtime.build_async_database_url(target_sync_url)
    runtime_already_initialized = (
        db_runtime.RUNTIME_ENGINE is not None
        and db_runtime.RUNTIME_DATABASE_URL == target_async_url
    )
    await db_runtime.initialize_runtime(target_sync_url)
    return target_sync_url, runtime_already_initialized


async def _configure_runtime_sqlite_pragmas() -> None:
    if db_runtime.RUNTIME_ENGINE is None:
        raise RuntimeError("Async runtime is not initialized")

    async with db_runtime.RUNTIME_ENGINE.begin() as conn:
        await conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        await conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        await conn.exec_driver_sql("PRAGMA synchronous=NORMAL")


async def _run_async_maintenance(
    operation: Callable[[DatabaseUnitOfWork], Awaitable[int]],
    database_url: str | None = None,
) -> int:
    _, runtime_already_initialized = await _initialize_maintenance_runtime(database_url)
    try:
        await _configure_runtime_sqlite_pragmas()
        async with db_runtime.get_sessionmaker()() as session:
            uow = DatabaseUnitOfWork(session)
            deleted = await operation(uow)
            await session.commit()
            return deleted
    finally:
        if not runtime_already_initialized:
            await db_runtime.dispose_runtime()


async def cleanup_orphan_swipes_async(database_url: str | None = None) -> int:
    """Delete orphan swipe rows through the async runtime path."""
    return await _run_async_maintenance(
        lambda uow: uow.swipes.delete_orphans(),
        database_url=database_url,
    )


async def cleanup_expired_auth_sessions_async(
    cutoff_iso: str | None = None,
    database_url: str | None = None,
) -> int:
    """Delete expired auth sessions through the async runtime path."""
    cutoff = cutoff_iso or (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    return await _run_async_maintenance(
        lambda uow: uow.auth_sessions.delete_expired(cutoff),
        database_url=database_url,
    )


async def prepare_runtime_database_async(database_url: str | None = None) -> None:
    """Run startup-safe database maintenance through the async runtime."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    _, runtime_already_initialized = await _initialize_maintenance_runtime(database_url)
    try:
        await _configure_runtime_sqlite_pragmas()
        async with db_runtime.get_sessionmaker()() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.swipes.delete_orphans()
            await uow.auth_sessions.delete_expired(cutoff)
            await session.commit()
    finally:
        if not runtime_already_initialized:
            await db_runtime.dispose_runtime()


def ensure_sqlite_wal_mode(db_path: str | None = None) -> None:
    """Compatibility wrapper that applies runtime SQLite pragmas off-request."""
    async def _apply() -> None:
        _, runtime_already_initialized = await _initialize_maintenance_runtime(
            _get_database_url(db_path or application_db_path.path)
        )
        try:
            await _configure_runtime_sqlite_pragmas()
        finally:
            if not runtime_already_initialized:
                await db_runtime.dispose_runtime()

    asyncio.run(_apply())


def get_db():
    """Get a configured runtime connection."""
    resolved = application_db_path.path
    if not resolved:
        raise RuntimeError("application_db_path is not configured")

    conn = sqlite3.connect(resolved, check_same_thread=False)
    return configure_sqlite_connection(conn)


@contextmanager
def get_db_closing():
    """Get a database connection that auto-closes on context exit."""
    conn = get_db()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def cleanup_orphan_swipes() -> None:
    """Compatibility wrapper for startup-safe orphan cleanup outside request loops."""
    asyncio.run(cleanup_orphan_swipes_async())


def cleanup_expired_auth_sessions() -> None:
    """Compatibility wrapper kept sync-safe for the current auth request path."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    with get_db_closing() as conn:
        conn.execute(
            "DELETE FROM auth_sessions WHERE created_at < ?",
            (cutoff,),
        )


def prepare_runtime_database() -> None:
    """Compatibility wrapper for startup-safe maintenance outside request loops."""
    asyncio.run(prepare_runtime_database_async())


def _get_database_url(db_path: str | None = None) -> str:
    from jellyswipe.migrations import get_database_url

    return get_database_url(db_path)
