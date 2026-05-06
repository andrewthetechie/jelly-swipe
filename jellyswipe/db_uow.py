"""Async database unit-of-work and maintenance repositories."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

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


class SwipeRepository:
    """Repository for swipe maintenance queries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def delete_orphans(self) -> int:
        result = await self._session.execute(
            text(
                "DELETE FROM swipes "
                "WHERE room_code NOT IN (SELECT pairing_code FROM rooms)"
            )
        )
        return result.rowcount or 0


class DatabaseUnitOfWork:
    """Typed async unit-of-work facade around one AsyncSession."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.auth_sessions = AuthSessionRepository(session)
        self.swipes = SwipeRepository(session)

    async def run_sync(self, fn: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
        """Run legacy sync work on the managed session connection.

        The sync callable may issue `BEGIN IMMEDIATE` or other SQLite statements,
        but it must not own the final COMMIT or ROLLBACK. The dependency boundary
        remains the single owner of transaction completion for this session.
        """

        return await self.session.run_sync(lambda sync_session: fn(sync_session, *args, **kwargs))


__all__ = [
    "AuthSessionRepository",
    "DatabaseUnitOfWork",
    "SwipeRepository",
]
