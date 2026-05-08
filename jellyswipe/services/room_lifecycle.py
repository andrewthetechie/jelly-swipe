"""Room lifecycle orchestration (non-swipe) on top of async repositories."""

from __future__ import annotations

import json
import secrets
from typing import Any, Protocol

from jellyswipe.db_uow import DatabaseUnitOfWork
from jellyswipe.room_types import MatchRecord


class UniqueRoomCodeExhaustedError(Exception):
    """Pairing-code allocation failed after bounded retries."""

    def __init__(self) -> None:
        super().__init__("Could not generate unique room code")


class DeckProvider(Protocol):
    def fetch_deck(self, media_types: list[str], genre_name: str | None = None) -> list[dict[str, Any]]: ...


class RoomLifecycleService:
    """Create/join/quit/deck/genre/status and match-history reads for live rooms."""

    page_size = 20

    @staticmethod
    def _cursor_from_deck_json(deck_position_json: str | None, user_id: str) -> int:
        if not deck_position_json:
            return 0
        try:
            positions = json.loads(deck_position_json)
        except (json.JSONDecodeError, TypeError):
            return 0
        if not isinstance(positions, dict):
            return 0
        raw = positions.get(user_id, 0)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _match_to_api_row(record: MatchRecord) -> dict[str, Any]:
        return {
            "title": record.title,
            "thumb": record.thumb,
            "media_id": record.movie_id,
            "media_type": "movie",
            "deep_link": record.deep_link,
            "rating": record.rating or "",
            "duration": record.duration or "",
            "year": record.year or "",
        }

    async def create_room(
        self,
        session_dict: dict[str, Any],
        user_id: str,
        provider: DeckProvider,
        uow: DatabaseUnitOfWork,
        include_movies: bool = True,
        include_tv_shows: bool = False,
        solo: bool = False,
    ) -> dict[str, str]:
        for _ in range(10):
            pairing_code = str(secrets.randbelow(9000) + 1000)
            exists = await uow.rooms.pairing_code_exists(pairing_code)
            if exists:
                continue
            # Build media_types list from boolean flags
            media_types = []
            if include_movies:
                media_types.append("movie")
            if include_tv_shows:
                media_types.append("tv_show")
            movie_list = provider.fetch_deck(media_types=media_types)
            deck_json = json.dumps({user_id: 0})
            await uow.rooms.create(
                pairing_code,
                movie_data_json=json.dumps(movie_list),
                ready=solo,  # ready defaults to True when solo=True
                current_genre="All",
                solo_mode=solo,
                deck_position_json=deck_json,
                include_movies=include_movies,
                include_tv_shows=include_tv_shows,
            )
            session_dict["active_room"] = pairing_code
            session_dict["solo_mode"] = solo
            return {"pairing_code": pairing_code}

        raise UniqueRoomCodeExhaustedError()

    async def create_solo_room(
        self,
        session_dict: dict[str, Any],
        user_id: str,
        provider: DeckProvider,
        uow: DatabaseUnitOfWork,
    ) -> dict[str, str]:
        for _ in range(10):
            pairing_code = str(secrets.randbelow(9000) + 1000)
            exists = await uow.rooms.pairing_code_exists(pairing_code)
            if exists:
                continue
            # Build media_types list from boolean flags - solo mode defaults to movies only
            media_types = ["movie"]
            movie_list = provider.fetch_deck(media_types=media_types)
            deck_json = json.dumps({user_id: 0})
            await uow.rooms.create(
                pairing_code,
                movie_data_json=json.dumps(movie_list),
                ready=True,
                current_genre="All",
                solo_mode=True,
                deck_position_json=deck_json,
            )
            session_dict["active_room"] = pairing_code
            session_dict["solo_mode"] = True
            return {"pairing_code": pairing_code}

        raise UniqueRoomCodeExhaustedError()

    async def join_room(
        self,
        code: str,
        session_dict: dict[str, Any],
        user_id: str,
        uow: DatabaseUnitOfWork,
    ) -> dict[str, str] | None:
        room = await uow.rooms.get_room(code)
        if room is None:
            return None

        positions: dict[str, Any] = {}
        if room.deck_position_json:
            try:
                loaded = json.loads(room.deck_position_json)
                if isinstance(loaded, dict):
                    positions = dict(loaded)
            except (json.JSONDecodeError, TypeError):
                positions = {}
        positions[user_id] = 0

        await uow.rooms.set_ready(code, True)
        await uow.rooms.set_deck_position(code, json.dumps(positions))

        session_dict["active_room"] = code
        session_dict["solo_mode"] = False
        return {"status": "success"}

    async def quit_room(
        self,
        code: str,
        session_dict: dict[str, Any],
        user_id: str,
        uow: DatabaseUnitOfWork,
    ) -> dict[str, str]:
        await uow.rooms.delete(code)
        await uow.swipes.delete_room_swipes(code)
        await uow.matches.archive_active_for_room(code)
        session_dict.pop("active_room", None)
        session_dict.pop("solo_mode", None)
        return {"status": "session_ended"}

    async def get_deck(
        self,
        code: str,
        user_id: str,
        page: int,
        uow: DatabaseUnitOfWork,
    ) -> list[dict[str, Any]]:
        room = await uow.rooms.get_room(code)
        if room is None:
            return []
        cursor_pos = self._cursor_from_deck_json(room.deck_position_json, user_id)
        try:
            movies = json.loads(room.movie_data_json)
        except (json.JSONDecodeError, TypeError):
            return []
        if not isinstance(movies, list):
            return []
        start = cursor_pos + (page - 1) * self.page_size
        end = start + self.page_size
        slice_ = movies[start:end]
        # Map id → media_id and add media_type for API response (exclude original id)
        result = []
        for m in (slice_ if isinstance(slice_, list) else []):
            item = {k: v for k, v in m.items() if k != "id"}
            item["media_id"] = m.get("id")
            item["media_type"] = m.get("media_type", "movie")
            result.append(item)
        return result

    async def set_genre(
        self,
        code: str,
        genre: str,
        provider: DeckProvider,
        uow: DatabaseUnitOfWork,
    ) -> list[dict[str, Any]]:
        # Get room to read media type configuration
        room = await uow.rooms.get_room(code)
        if room is None:
            return []

        # Build media_types list from room configuration
        media_types = []
        if room.include_movies:
            media_types.append("movie")
        if room.include_tv_shows:
            media_types.append("tv_show")

        new_list = provider.fetch_deck(media_types=media_types, genre_name=genre)
        await uow.rooms.set_genre_and_deck(
            code,
            genre,
            movie_data_json=json.dumps(new_list),
            deck_position_json=json.dumps({}),
        )
        return new_list

    async def get_status(self, code: str, uow: DatabaseUnitOfWork) -> dict[str, Any]:
        snapshot = await uow.rooms.fetch_status(code)
        if snapshot is None:
            return {"ready": False}
        return {
            "ready": snapshot.ready,
            "genre": snapshot.genre,
            "solo": snapshot.solo,
            "last_match": snapshot.last_match,
        }

    async def get_matches(
        self,
        active_room: str | None,
        user_id: str,
        view: str | None,
        uow: DatabaseUnitOfWork,
    ) -> list[dict[str, Any]]:
        if view == "history":
            rows = await uow.matches.list_history_for_user(user_id)
        elif active_room:
            rows = await uow.matches.list_active_for_user(active_room, user_id)
        else:
            rows = []
        return [self._match_to_api_row(r) for r in rows]
