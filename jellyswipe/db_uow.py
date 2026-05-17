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
