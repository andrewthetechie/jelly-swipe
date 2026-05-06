"""Async database runtime primitives for Jelly Swipe."""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from jellyswipe.migrations import build_sqlite_url, get_database_url, normalize_sync_database_url

RUNTIME_DATABASE_URL: str | None = None
RUNTIME_ENGINE: AsyncEngine | None = None
RUNTIME_SESSIONMAKER: async_sessionmaker[AsyncSession] | None = None
RUNTIME_DATABASE_URL_OVERRIDE: str | None = None


def build_async_database_url(database_url: str) -> str:
    """Convert the canonical sync SQLite URL into the async runtime form."""
    normalized = normalize_sync_database_url(database_url)
    if not normalized.startswith("sqlite:///"):
        raise ValueError(
            "DATABASE_URL must use the canonical sync sqlite:/// form for Alembic/runtime resolution"
        )
    return normalized.replace("sqlite:///", "sqlite+aiosqlite:///", 1)


def build_async_sqlite_url(db_path: str) -> str:
    """Convenience wrapper that preserves the sync URL contract."""
    return build_async_database_url(build_sqlite_url(db_path))


def get_runtime_database_url(db_path: str | None = None) -> str:
    """Resolve the configured database target for the async runtime."""
    if db_path:
        return build_async_database_url(get_database_url(db_path))
    if RUNTIME_DATABASE_URL_OVERRIDE is not None:
        return RUNTIME_DATABASE_URL_OVERRIDE
    return build_async_database_url(get_database_url(db_path))


def set_runtime_database_url_override(database_url: str | None) -> None:
    """Store a runtime-only database override for tests and app factory wiring."""
    global RUNTIME_DATABASE_URL_OVERRIDE
    if database_url is None:
        RUNTIME_DATABASE_URL_OVERRIDE = None
        return
    RUNTIME_DATABASE_URL_OVERRIDE = build_async_database_url(database_url)


async def initialize_runtime(database_url: str | None = None) -> None:
    """Create the process-wide async engine and sessionmaker once."""
    global RUNTIME_DATABASE_URL, RUNTIME_ENGINE, RUNTIME_SESSIONMAKER

    target_url = (
        build_async_database_url(database_url)
        if database_url is not None
        else get_runtime_database_url()
    )
    if RUNTIME_ENGINE is not None:
        if RUNTIME_DATABASE_URL == target_url:
            return
        await dispose_runtime()

    engine = create_async_engine(target_url)

    @event.listens_for(engine.sync_engine, "connect")
    def _configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    RUNTIME_DATABASE_URL = target_url
    RUNTIME_ENGINE = engine
    RUNTIME_SESSIONMAKER = async_sessionmaker(engine, expire_on_commit=False)


async def dispose_runtime() -> None:
    """Dispose the cached engine and clear runtime globals."""
    global RUNTIME_DATABASE_URL, RUNTIME_ENGINE, RUNTIME_SESSIONMAKER

    if RUNTIME_ENGINE is not None:
        await RUNTIME_ENGINE.dispose()

    RUNTIME_DATABASE_URL = None
    RUNTIME_ENGINE = None
    RUNTIME_SESSIONMAKER = None


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return the initialized async sessionmaker."""
    if RUNTIME_SESSIONMAKER is None:
        raise RuntimeError(
            "Async database runtime is not initialized. Call initialize_runtime() before requesting sessions."
        )
    return RUNTIME_SESSIONMAKER


def session_factory() -> async_sessionmaker[AsyncSession]:
    """Compatibility alias for the initialized sessionmaker."""
    return get_sessionmaker()


__all__ = [
    "RUNTIME_DATABASE_URL",
    "RUNTIME_DATABASE_URL_OVERRIDE",
    "RUNTIME_ENGINE",
    "RUNTIME_SESSIONMAKER",
    "build_async_database_url",
    "build_async_sqlite_url",
    "dispose_runtime",
    "get_runtime_database_url",
    "get_sessionmaker",
    "initialize_runtime",
    "set_runtime_database_url_override",
    "session_factory",
]
