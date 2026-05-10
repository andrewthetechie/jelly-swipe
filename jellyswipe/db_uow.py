"""Async database unit-of-work and maintenance repositories."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from jellyswipe.auth_types import AuthRecord
from jellyswipe.models.auth_session import AuthSession
from jellyswipe.repositories.matches import MatchRepository
from jellyswipe.repositories.rooms import RoomRepository
from jellyswipe.repositories.session_events import (
    SessionEventRepository,
    SessionInstanceRepository,
)
from jellyswipe.repositories.swipes import SwipeRepository

T = TypeVar("T")


class AuthSessionRepository:
    """Repository for auth session maintenance queries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def delete_expired(self, cutoff_iso: str) -> int:
        result = await self._session.execute(
            text("DELETE FROM auth_sessions WHERE created_at < :cutoff_iso"),
            {"cutoff_iso": cutoff_iso},
        )
        return result.rowcount or 0

    async def get_by_session_id(self, session_id: str) -> AuthRecord | None:
        result = await self._session.execute(
            select(AuthSession).where(AuthSession.session_id == session_id)
        )
        record = result.scalar_one_or_none()
        if record is None:
            return None
        return AuthRecord(
            session_id=record.session_id,
            jf_token=record.jellyfin_token,
            user_id=record.jellyfin_user_id,
            created_at=record.created_at,
        )

    async def insert(self, record: AuthRecord) -> None:
        self._session.add(
            AuthSession(
                session_id=record.session_id,
                jellyfin_token=record.jf_token,
                jellyfin_user_id=record.user_id,
                created_at=record.created_at,
            )
        )

    async def delete_by_session_id(self, session_id: str) -> int:
        result = await self._session.execute(
            delete(AuthSession).where(AuthSession.session_id == session_id)
        )
        return result.rowcount or 0


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
]
