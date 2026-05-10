"""Async room persistence."""

from __future__ import annotations

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from jellyswipe.models.room import Room
from jellyswipe.room_types import RoomRecord, RoomStatusSnapshot


class RoomRepository:
    """Persistence access for rooms."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def pairing_code_exists(self, pairing_code: str) -> bool:
        stmt = (
            select(func.count())
            .select_from(Room)
            .where(Room.pairing_code == pairing_code)
        )
        count = await self._session.scalar(stmt)
        return (count or 0) > 0

    async def create(
        self,
        pairing_code: str,
        movie_data_json: str,
        ready: bool,
        current_genre: str,
        solo_mode: bool,
        deck_position_json: str,
        include_movies: bool = True,
        include_tv_shows: bool = False,
        hide_watched: bool = False,
    ) -> None:
        self._session.add(
            Room(
                pairing_code=pairing_code,
                movie_data=movie_data_json,
                ready=1 if ready else 0,
                current_genre=current_genre,
                solo_mode=1 if solo_mode else 0,
                deck_position=deck_position_json,
                include_movies=1 if include_movies else 0,
                include_tv_shows=1 if include_tv_shows else 0,
                hide_watched=1 if hide_watched else 0,
            )
        )

    async def get_room(self, pairing_code: str) -> RoomRecord | None:
        row = (
            await self._session.scalars(
                select(Room).where(Room.pairing_code == pairing_code)
            )
        ).first()
        if row is None:
            return None
        return self._to_record(row)

    async def set_ready(self, pairing_code: str, ready: bool) -> int:
        result = await self._session.execute(
            update(Room)
            .where(Room.pairing_code == pairing_code)
            .values(ready=1 if ready else 0)
        )
        return result.rowcount or 0

    async def set_deck_position(
        self, pairing_code: str, deck_position_json: str
    ) -> int:
        result = await self._session.execute(
            update(Room)
            .where(Room.pairing_code == pairing_code)
            .values(deck_position=deck_position_json)
        )
        return result.rowcount or 0

    async def set_genre_and_deck(
        self,
        pairing_code: str,
        genre: str,
        movie_data_json: str,
        deck_position_json: str,
    ) -> int:
        result = await self._session.execute(
            update(Room)
            .where(Room.pairing_code == pairing_code)
            .values(
                current_genre=genre,
                movie_data=movie_data_json,
                deck_position=deck_position_json,
            )
        )
        return result.rowcount or 0

    async def set_filters_and_deck(
        self,
        pairing_code: str,
        genre: str,
        hide_watched: bool,
        movie_data_json: str,
        deck_position_json: str,
    ) -> int:
        """Atomically update genre, hide_watched, deck, and cursor positions."""
        result = await self._session.execute(
            update(Room)
            .where(Room.pairing_code == pairing_code)
            .values(
                current_genre=genre,
                hide_watched=1 if hide_watched else 0,
                movie_data=movie_data_json,
                deck_position=deck_position_json,
            )
        )
        return result.rowcount or 0

    async def fetch_status(self, pairing_code: str) -> RoomStatusSnapshot | None:
        row = (
            await self._session.scalars(
                select(Room).where(Room.pairing_code == pairing_code)
            )
        ).first()
        if row is None:
            return None
        return RoomStatusSnapshot(
            ready=bool(row.ready),
            genre=row.current_genre,
            solo=bool(row.solo_mode),
            hide_watched=bool(row.hide_watched),
        )

    async def fetch_movie_data(self, pairing_code: str) -> str | None:
        return await self._session.scalar(
            select(Room.movie_data).where(Room.pairing_code == pairing_code)
        )

    async def delete(self, pairing_code: str) -> int:
        result = await self._session.execute(
            delete(Room).where(Room.pairing_code == pairing_code)
        )
        return result.rowcount or 0

    @staticmethod
    def _to_record(row: Room) -> RoomRecord:
        return RoomRecord(
            pairing_code=row.pairing_code,
            movie_data_json=row.movie_data,
            ready=bool(row.ready),
            current_genre=row.current_genre,
            solo_mode=bool(row.solo_mode),
            deck_position_json=row.deck_position,
            deck_order_json=row.deck_order,
            include_movies=bool(row.include_movies),
            include_tv_shows=bool(row.include_tv_shows),
            hide_watched=bool(row.hide_watched),
        )
