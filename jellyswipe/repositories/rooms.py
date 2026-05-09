"""Async room persistence."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from jellyswipe.models.room import Room
from jellyswipe.room_types import RoomRecord, RoomStatusSnapshot, StreamSnapshot


class RoomRepository:
    """Persistence access for rooms."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def pairing_code_exists(self, pairing_code: str) -> bool:
        stmt = select(func.count()).select_from(Room).where(Room.pairing_code == pairing_code)
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
            await self._session.scalars(select(Room).where(Room.pairing_code == pairing_code))
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

    async def set_deck_position(self, pairing_code: str, deck_position_json: str) -> int:
        result = await self._session.execute(
            update(Room).where(Room.pairing_code == pairing_code).values(deck_position=deck_position_json)
        )
        return result.rowcount or 0

    async def set_genre_and_deck(
        self, pairing_code: str, genre: str, movie_data_json: str, deck_position_json: str
    ) -> int:
        result = await self._session.execute(
            update(Room)
            .where(Room.pairing_code == pairing_code)
            .values(current_genre=genre, movie_data=movie_data_json, deck_position=deck_position_json)
        )
        return result.rowcount or 0

    async def set_last_match_data(self, pairing_code: str, last_match_data_json: str | None) -> int:
        result = await self._session.execute(
            update(Room).where(Room.pairing_code == pairing_code).values(last_match_data=last_match_data_json)
        )
        return result.rowcount or 0

    async def fetch_status(self, pairing_code: str) -> RoomStatusSnapshot | None:
        row = (
            await self._session.scalars(select(Room).where(Room.pairing_code == pairing_code))
        ).first()
        if row is None:
            return None
        last_match: dict[str, Any] | None = None
        raw = row.last_match_data
        if raw:
            try:
                parsed = json.loads(raw)
                last_match = parsed if isinstance(parsed, dict) else None
            except (json.JSONDecodeError, TypeError):
                last_match = None
        return RoomStatusSnapshot(
            ready=bool(row.ready),
            genre=row.current_genre,
            solo=bool(row.solo_mode),
            last_match=last_match,
            hide_watched=bool(row.hide_watched),
        )

    async def fetch_movie_data(self, pairing_code: str) -> str | None:
        return await self._session.scalar(
            select(Room.movie_data).where(Room.pairing_code == pairing_code)
        )

    async def fetch_stream_snapshot(self, pairing_code: str) -> StreamSnapshot | None:
        stmt = select(Room.ready, Room.current_genre, Room.solo_mode, Room.last_match_data, Room.hide_watched).where(
            Room.pairing_code == pairing_code
        )
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None
        ready_raw, genre, solo_raw, raw_last, hide_watched_raw = row[0], row[1], row[2], row[3], row[4]
        last_match: dict[str, Any] | None = None
        last_match_ts: str | float | int | None = None
        if raw_last:
            try:
                parsed = json.loads(raw_last)
                if isinstance(parsed, dict):
                    last_match = parsed
                    last_match_ts = parsed.get("ts")
            except (json.JSONDecodeError, TypeError):
                last_match = None
                last_match_ts = None
        return StreamSnapshot(
            ready=bool(ready_raw),
            genre=genre or "",
            solo=bool(solo_raw),
            last_match=last_match,
            last_match_ts=last_match_ts,
            hide_watched=bool(hide_watched_raw),
        )

    async def delete(self, pairing_code: str) -> int:
        result = await self._session.execute(delete(Room).where(Room.pairing_code == pairing_code))
        return result.rowcount or 0

    @staticmethod
    def _to_record(row: Room) -> RoomRecord:
        return RoomRecord(
            pairing_code=row.pairing_code,
            movie_data_json=row.movie_data,
            ready=bool(row.ready),
            current_genre=row.current_genre,
            solo_mode=bool(row.solo_mode),
            last_match_data_json=row.last_match_data,
            deck_position_json=row.deck_position,
            deck_order_json=row.deck_order,
            include_movies=bool(row.include_movies),
            include_tv_shows=bool(row.include_tv_shows),
            hide_watched=bool(row.hide_watched),
        )
