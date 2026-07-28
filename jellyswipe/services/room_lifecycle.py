"""Room lifecycle orchestration (non-swipe) on top of async repositories."""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from jellyswipe.db_runtime import get_sessionmaker
from jellyswipe.db_uow import DatabaseUnitOfWork
from jellyswipe.services.deck_pipeline import DeckProvider, EmptyDeckError, build_deck

# Session keys shared with the rooms router: the service builds
# ``session_updates`` dicts with these keys; the router applies or pops them.
SESSION_ACTIVE_ROOM_KEY = "active_room"
SESSION_SOLO_MODE_KEY = "solo_mode"

# Re-export for backward compatibility
__all__ = [
    "SESSION_ACTIVE_ROOM_KEY",
    "SESSION_SOLO_MODE_KEY",
    "CreateRoomResult",
    "DeckProvider",
    "EmptyDeckError",
    "JoinRoomResult",
    "QuitRoomResult",
    "RoomLifecycleService",
    "UniqueRoomCodeExhaustedError",
]


@dataclass(frozen=True)
class CreateRoomResult:
    pairing_code: str
    instance_id: str
    session_updates: dict[str, str | bool]


@dataclass(frozen=True)
class JoinRoomResult:
    session_updates: dict[str, str | bool]


@dataclass(frozen=True)
class QuitRoomResult:
    status: str


logger = logging.getLogger(__name__)


class UniqueRoomCodeExhaustedError(Exception):
    """Pairing-code allocation failed after bounded retries."""

    def __init__(self) -> None:
        super().__init__("Could not generate unique room code")


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

    async def create_room(
        self,
        user_id: str,
        provider: DeckProvider,
        uow: DatabaseUnitOfWork,
        include_movies: bool = True,
        include_tv_shows: bool = False,
        solo: bool = False,
    ) -> CreateRoomResult:
        for _ in range(10):
            pairing_code = str(secrets.randbelow(9000) + 1000)
            exists = await uow.rooms.pairing_code_exists(pairing_code)
            reserved = await uow.session_instances.is_pairing_code_reserved(
                pairing_code
            )
            if exists or reserved:
                continue
            # Build media_types list from boolean flags
            media_types = []
            if include_movies:
                media_types.append("movie")
            if include_tv_shows:
                media_types.append("tv_show")
            deck = await build_deck(
                provider=provider,
                uow=uow,
                room_code=pairing_code,
                media_types=media_types,
                persist=False,
            )

            deck_json = json.dumps({user_id: 0})
            instance_id = uuid4().hex
            await uow.rooms.create(
                pairing_code,
                movie_data_json=json.dumps(deck),
                ready=solo,  # ready defaults to True when solo=True
                current_genre="All",
                solo_mode=solo,
                deck_position_json=deck_json,
                include_movies=include_movies,
                include_tv_shows=include_tv_shows,
            )
            await uow.session_instances.create(
                instance_id=instance_id, pairing_code=pairing_code
            )
            if solo:
                await uow.session_events.append(
                    instance_id, "session_ready", json.dumps({"solo": True})
                )
            return CreateRoomResult(
                pairing_code=pairing_code,
                instance_id=instance_id,
                session_updates={
                    SESSION_ACTIVE_ROOM_KEY: pairing_code,
                    SESSION_SOLO_MODE_KEY: solo,
                },
            )

        raise UniqueRoomCodeExhaustedError()

    async def join_room(
        self,
        code: str,
        user_id: str,
        uow: DatabaseUnitOfWork,
    ) -> JoinRoomResult | None:
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

        # Append session_ready event
        instance = await uow.session_instances.get_by_pairing_code(code)
        if instance:
            await uow.session_events.append(
                instance.instance_id, "session_ready", json.dumps({})
            )

        return JoinRoomResult(
            session_updates={
                SESSION_ACTIVE_ROOM_KEY: code,
                SESSION_SOLO_MODE_KEY: False,
            }
        )

    async def quit_room(
        self,
        code: str,
        user_id: str,
        uow: DatabaseUnitOfWork,
    ) -> QuitRoomResult:
        # Look up instance and append session_closed event
        instance = await uow.session_instances.get_by_pairing_code(code)
        if instance:
            await uow.session_events.append(
                instance.instance_id, "session_closed", json.dumps({})
            )
            await uow.session_instances.mark_closing(instance.instance_id)
            # Schedule background cleanup task
            asyncio.create_task(self._cleanup_after_grace(instance.instance_id))

        await uow.rooms.delete(code)
        await uow.swipes.delete_room_swipes(code)
        await uow.matches.archive_active_for_room(code)
        return QuitRoomResult(status="session_ended")

    async def _cleanup_after_grace(self, instance_id: str) -> None:
        """Clean up session instance after 60-second grace period."""
        await asyncio.sleep(60)
        async with get_sessionmaker()() as session:
            uow = DatabaseUnitOfWork(session)
            await uow.session_instances.mark_closed(instance_id)
            await uow.session_events.delete_for_instance(instance_id)
            await uow.session_instances.delete(instance_id)
            await session.commit()

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
        for m in slice_ if isinstance(slice_, list) else []:
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
        """Set genre filter and rebuild deck."""
        room = await uow.rooms.get_room(code)
        if room is None:
            raise EmptyDeckError("Room not found")

        media_types = []
        if room.include_movies:
            media_types.append("movie")
        if room.include_tv_shows:
            media_types.append("tv_show")

        new_deck = await build_deck(
            provider=provider,
            uow=uow,
            room_code=code,
            media_types=media_types,
            genre=genre,
            hide_watched=room.hide_watched,
            persist=True,
        )
        # Append genre_changed event on success
        instance = await uow.session_instances.get_by_pairing_code(code)
        if instance:
            await uow.session_events.append(
                instance.instance_id, "genre_changed", json.dumps({"genre": genre})
            )
        return new_deck

    async def set_watched_filter(
        self,
        code: str,
        hide_watched: bool,
        provider: DeckProvider,
        uow: DatabaseUnitOfWork,
    ) -> list[dict[str, Any]]:
        """Set watched filter and rebuild deck."""
        room = await uow.rooms.get_room(code)
        if room is None:
            raise EmptyDeckError("Room not found")

        media_types = []
        if room.include_movies:
            media_types.append("movie")
        if room.include_tv_shows:
            media_types.append("tv_show")

        new_deck = await build_deck(
            provider=provider,
            uow=uow,
            room_code=code,
            media_types=media_types,
            genre=room.current_genre,
            hide_watched=hide_watched,
            persist=True,
        )
        # Append hide_watched_changed event on success
        instance = await uow.session_instances.get_by_pairing_code(code)
        if instance:
            await uow.session_events.append(
                instance.instance_id,
                "hide_watched_changed",
                json.dumps({"hide_watched": hide_watched}),
            )
        return new_deck

    async def get_status(self, code: str, uow: DatabaseUnitOfWork) -> dict[str, Any]:
        snapshot = await uow.rooms.fetch_status(code)
        if snapshot is None:
            return {"ready": False}
        return {
            "ready": snapshot.ready,
            "genre": snapshot.genre,
            "solo": snapshot.solo,
            "hide_watched": snapshot.hide_watched,
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
        return [
            {
                "title": r.title,
                "thumb": r.thumb,
                "media_id": r.movie_id,
                "media_type": r.media_type or "movie",
                "deep_link": r.deep_link,
                "rating": r.rating or "",
                "duration": r.duration or "",
                "year": r.year if r.year else None,
            }
            for r in rows
        ]
