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


def _raw_connection(sync_session: Any) -> Any:
    """Return the underlying DBAPI connection for a sync connection.

    SQLAlchemy nests the driver connection several layers deep (sync session
    -> wrapped connection -> DBAPI connection). This helper collapses that
    chain for call sites that must talk to the driver connection directly
    (e.g. SQLite ``BEGIN IMMEDIATE`` and transaction-state checks).
    """
    return sync_session.connection().connection.driver_connection


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
        # Wake intent: room codes whose SSE subscribers should be woken after the
        # request boundary commits. Populated by routes/services via
        # ``wake_on_commit``; drained by the boundary after a successful commit.
        self._wake_codes: set[str] = set()
        # Set when the caller wants the request boundary to roll back instead of
        # committing (``abort``), e.g. an error-return route that wrote data.
        self._aborted: bool = False
        # True while a ``BEGIN IMMEDIATE`` transaction is open on this session; the
        # boundary owns the terminal COMMIT/ROLLBACK.
        self._immediate_active: bool = False

    def wake_on_commit(self, code: str) -> None:
        """Declare that subscribers for ``code`` should be woken after commit.

        Does not commit or notify. The request boundary commits, then wakes all
        declared codes. Call this after the DB writes for the request are done.
        """
        self._wake_codes.add(code)

    def abort(self) -> None:
        """Roll back this request's transaction at the boundary instead of committing.

        Use in an error-return route that already wrote data it does not want
        persisted. The boundary will roll back and skip notifying.
        """
        self._aborted = True

    @property
    def aborted(self) -> bool:
        """True if ``abort`` was called and the boundary must roll back."""
        return self._aborted

    def drain_wakes(self) -> set[str]:
        """Return and clear the set of room codes to wake after commit.

        Called by the request boundary after a successful commit.
        """
        wakes, self._wake_codes = self._wake_codes, set()
        return wakes

    def mark_transaction_completed(self) -> None:
        """Clear the ``BEGIN IMMEDIATE`` guard after the boundary commits/rolls back."""
        self._immediate_active = False

    async def run_sync(self, fn: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
        """Run legacy sync work on the managed session connection.

        The sync callable may issue `BEGIN IMMEDIATE` or other SQLite statements,
        but it must not own the final COMMIT or ROLLBACK. The dependency boundary
        remains the single owner of transaction completion for this session.
        """

        def _run(sync_session: Any) -> T:
            result = fn(sync_session, *args, **kwargs)
            if self._immediate_active:
                raw_conn = _raw_connection(sync_session)
                if not raw_conn.in_transaction:
                    raise RuntimeError(
                        "BEGIN IMMEDIATE transaction was committed/rolled back inside "
                        "run_sync(); transaction completion is owned by the request "
                        "boundary and cannot be issued by a sync callable"
                    )
            return result

        return await self.session.run_sync(_run)

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
            raw_conn = _raw_connection(sync_session)
            raw_conn.isolation_level = None
            conn.exec_driver_sql("BEGIN IMMEDIATE")

        await self.run_sync(_begin)
        self._immediate_active = True


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
