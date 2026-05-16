"""Async swipe persistence."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from jellyswipe.models.swipe import Swipe


@dataclass(slots=True)
class SwipeCounterparty:
    user_id: str
    session_id: str | None


class SwipeRepository:
    """Persistence access for swipes."""

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

    async def find_other_right_swipe(
        self,
        pairing_code: str,
        movie_id: str,
        user_id: str,
        session_id: str | None,
    ) -> SwipeCounterparty | None:
        stmt = (
            select(Swipe.user_id, Swipe.session_id)
            .where(
                Swipe.room_code == pairing_code,
                Swipe.movie_id == movie_id,
                Swipe.direction == "right",
            )
            .order_by(Swipe.user_id.asc())
            .limit(1)
        )
        if session_id:
            stmt = stmt.where(
                or_(Swipe.session_id.is_(None), Swipe.session_id != session_id)
            )
        else:
            stmt = stmt.where(Swipe.user_id != user_id)

        result = await self._session.execute(stmt)
        row = result.first()
        if row is None:
            return None
        return SwipeCounterparty(user_id=row.user_id, session_id=row.session_id)

    async def delete_room_swipes(self, pairing_code: str) -> int:
        result = await self._session.execute(
            delete(Swipe).where(Swipe.room_code == pairing_code)
        )
        return result.rowcount or 0

    async def delete_by_room_movie_session(
        self,
        pairing_code: str,
        movie_id: str,
        session_id: str | None,
    ) -> int:
        stmt = delete(Swipe).where(
            Swipe.room_code == pairing_code,
            Swipe.movie_id == movie_id,
        )
        if session_id is None:
            stmt = stmt.where(Swipe.session_id.is_(None))
        else:
            stmt = stmt.where(Swipe.session_id == session_id)
        result = await self._session.execute(stmt)
        return result.rowcount or 0

    async def list_swiped_media_ids(self, pairing_code: str) -> set[str]:
        result = await self._session.execute(
            select(Swipe.movie_id).where(Swipe.room_code == pairing_code)
        )
        return {row[0] for row in result.all()}
