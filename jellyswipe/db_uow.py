"""Async database unit-of-work and maintenance repositories."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from jellyswipe.repositories.auth_sessions import AuthSessionRepository
from jellyswipe.repositories.matches import MatchRepository
from jellyswipe.repositories.rooms import RoomRepository
from jellyswipe.repositories.session_events import (
    SessionEventRepository,
    SessionInstanceRepository,
)
from jellyswipe.repositories.swipes import SwipeRepository
from jellyswipe.repositories.tmdb_cache import TmdbCacheRepository

T = TypeVar("T")


class DatabaseUnitOfWork:
    """Typed async unit-of-work facade around one AsyncSession."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.auth_sessions = AuthSessionRepository(session)
        self.rooms = RoomRepository(session)
        self.swipes = SwipeRepository(session)
        self.matches = MatchRepository(session)
        self.session_instances = SessionInstanceRepository(session)
        self.session_events = SessionEventRepository(session)
        self.tmdb_cache = TmdbCacheRepository(session)

    async def run_sync(self, fn: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
        """Run legacy sync work on the managed session connection.

        The sync callable may issue `BEGIN IMMEDIATE` or other SQLite statements,
        but it must not own the final COMMIT or ROLLBACK. The dependency boundary
        remains the single owner of transaction completion for this session.
        """

        return await self.session.run_sync(
            lambda sync_session: fn(sync_session, *args, **kwargs)
        )

    async def begin_immediate(self) -> None:
        """Open a SQLite ``BEGIN IMMEDIATE`` write transaction on this session.

        This is the persistence-layer entry point for concurrency-critical
        write paths (e.g. the swipe transaction, see D-12/D-13). Subsequent
        repository calls on this UoW share the same connection and therefore
        run inside the immediate transaction. The caller must not issue the
        final COMMIT or ROLLBACK; the dependency boundary remains the single
        owner of transaction completion.
        """

        def _begin(sync_session: Any) -> None:
            conn = sync_session.connection()
            raw_conn = conn.connection.driver_connection
            raw_conn.isolation_level = None
            conn.exec_driver_sql("BEGIN IMMEDIATE")

        await self.run_sync(_begin)


__all__ = [
    "AuthSessionRepository",
    "DatabaseUnitOfWork",
    "MatchRepository",
    "RoomRepository",
    "SessionEventRepository",
    "SessionInstanceRepository",
    "SwipeRepository",
    "TmdbCacheRepository",
]
