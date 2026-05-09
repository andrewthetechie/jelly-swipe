"""Async match persistence."""

from __future__ import annotations

from sqlalchemy import delete, literal_column, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from jellyswipe.models.match import Match
from jellyswipe.room_types import MatchRecord


_ROWID_ORDER = literal_column("matches.rowid").label("match_order")


class MatchRepository:
    """Persistence access for matches."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active_for_user(
        self, pairing_code: str, user_id: str
    ) -> list[MatchRecord]:
        stmt = (
            select(Match, _ROWID_ORDER)
            .where(
                Match.room_code == pairing_code,
                Match.status == "active",
                Match.user_id == user_id,
            )
            .order_by(_ROWID_ORDER.desc())
        )
        result = await self._session.execute(stmt)
        return [self._match_tuple_to_record(match, mo) for match, mo in result.all()]

    async def list_history_for_user(self, user_id: str) -> list[MatchRecord]:
        stmt = (
            select(Match, _ROWID_ORDER)
            .where(Match.status == "archived", Match.user_id == user_id)
            .order_by(_ROWID_ORDER.desc())
        )
        result = await self._session.execute(stmt)
        return [self._match_tuple_to_record(match, mo) for match, mo in result.all()]

    async def archive_active_for_room(self, pairing_code: str) -> int:
        upd = (
            update(Match)
            .where(Match.room_code == pairing_code, Match.status == "active")
            .values(status="archived", room_code="HISTORY")
        )
        result = await self._session.execute(upd)
        return result.rowcount or 0

    async def delete_for_user(self, movie_id: str, user_id: str) -> int:
        result = await self._session.execute(
            delete(Match).where(Match.movie_id == movie_id, Match.user_id == user_id)
        )
        return result.rowcount or 0

    async def delete_active_for_room_movie_user(
        self,
        pairing_code: str,
        movie_id: str,
        user_id: str,
    ) -> int:
        result = await self._session.execute(
            delete(Match).where(
                Match.room_code == pairing_code,
                Match.movie_id == movie_id,
                Match.user_id == user_id,
                Match.status == "active",
            )
        )
        return result.rowcount or 0

    async def latest_active_for_room(self, pairing_code: str) -> MatchRecord | None:
        stmt = (
            select(Match, _ROWID_ORDER)
            .where(Match.room_code == pairing_code, Match.status == "active")
            .order_by(_ROWID_ORDER.desc())
            .limit(1)
        )
        row = (await self._session.execute(stmt)).first()
        if row is None:
            return None
        match, mo = row[0], row[1]
        return self._match_tuple_to_record(match, mo)

    @staticmethod
    def _match_tuple_to_record(match: Match, match_order_val: object) -> MatchRecord:
        mo: int | None
        try:
            mo = int(match_order_val) if match_order_val is not None else None
        except (TypeError, ValueError):
            mo = None
        return MatchRecord(
            room_code=match.room_code,
            movie_id=match.movie_id,
            title=match.title,
            thumb=match.thumb,
            status=match.status,
            user_id=match.user_id,
            deep_link=match.deep_link,
            rating=match.rating,
            duration=match.duration,
            year=match.year,
            media_type=match.media_type,
            match_order=mo,
        )
