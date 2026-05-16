"""Auth session repository and shared auth data types."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from jellyswipe.models.auth_session import AuthSession


@dataclass(slots=True)
class AuthRecord:
    session_id: str
    jf_token: str
    user_id: str
    created_at: str


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
