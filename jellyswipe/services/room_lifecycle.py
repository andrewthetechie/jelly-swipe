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
from jellyswipe.domain.deck import Deck
from jellyswipe.services.background_tasks import (
    BackgroundTaskRegistry,
    background_task_registry,
)
from jellyswipe.services.deck_pipeline import DeckProvider, EmptyDeckError, build_deck

__all__ = [
    "CreateRoomResult",
    "DeckProvider",
    "EmptyDeckError",
    "MutationResult",
    "QuitRoomResult",
    "RoomLifecycleService",
    "UniqueRoomCodeExhaustedError",
]


@dataclass(frozen=True)
class CreateRoomResult:
    pairing_code: str
    instance_id: str


@dataclass(frozen=True)
class QuitRoomResult:
    status: str


@dataclass(frozen=True)
class MutationResult:
    """Deck plus the event_id of the mutation event that was appended."""

    deck: list[dict[str, Any]]
    event_id: int


logger = logging.getLogger(__name__)


class UniqueRoomCodeExhaustedError(Exception):
    """Pairing-code allocation failed after bounded retries."""

    def __init__(self) -> None:
        super().__init__("Could not generate unique room code")


class RoomLifecycleService:
    """Create/join/quit/deck/genre/status and match-history reads for live rooms."""

    page_size = 20

    def __init__(
        self,
        registry: BackgroundTaskRegistry | None = None,
        sleep: Any = asyncio.sleep,
        grace_seconds: int = 60,
    ) -> None:
        self._registry = registry or background_task_registry
        self._sleep = sleep
        self._grace_seconds = grace_seconds

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

            room_deck = Deck.from_cards(deck).add_participant(user_id)
            instance_id = uuid4().hex
            await uow.rooms.create(
                pairing_code,
                deck=room_deck,
                ready=solo,  # ready defaults to True when solo=True
                current_genre="All",
                solo_mode=solo,
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
            )

        raise UniqueRoomCodeExhaustedError()

    async def join_room(
        self,
        code: str,
        user_id: str,
        uow: DatabaseUnitOfWork,
    ) -> bool:
        """Add ``user_id`` to the room and mark it ready for swiping.

        Returns ``True`` if the room exists and the user joined, ``False`` if
        the pairing code is unknown.
        """
        room = await uow.rooms.get_room(code)
        if room is None:
            return False

        # Add (or reset) the joining participant's cursor to 0, preserving others.
        updated_deck = room.deck.add_participant(user_id)

        await uow.rooms.set_ready(code, True)
        await uow.rooms.set_deck_position(code, updated_deck)

        # Append session_ready event
        instance = await uow.session_instances.get_by_pairing_code(code)
        if instance:
            await uow.session_events.append(
                instance.instance_id, "session_ready", json.dumps({})
            )

        return True

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
            # Schedule background cleanup through the visible task registry so it
            # is testable (injectable clock) and shutdown-aware (drained on exit).
            self._registry.schedule(self._cleanup_after_grace(instance.instance_id))

        await uow.rooms.delete(code)
        await uow.swipes.delete_room_swipes(code)
        await uow.matches.archive_active_for_room(code)
        return QuitRoomResult(status="session_ended")

    async def _cleanup_after_grace(self, instance_id: str) -> None:
        """Clean up session instance after the grace period."""
        await self._sleep(self._grace_seconds)
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
        return room.deck.page(user_id, page, page_size=self.page_size)

    async def set_genre(
        self,
        code: str,
        genre: str,
        provider: DeckProvider,
        uow: DatabaseUnitOfWork,
    ) -> MutationResult:
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
        # Append genre_changed event on success and return its event_id.
        # event_id stays 0 (never a real autoincrement id) when no session
        # instance exists — the frontend treats 0 as "nothing to suppress".
        instance = await uow.session_instances.get_by_pairing_code(code)
        event_id = 0
        if instance:
            event_id = await uow.session_events.append(
                instance.instance_id, "genre_changed", json.dumps({"genre": genre})
            )
        return MutationResult(deck=new_deck, event_id=event_id)

    async def set_watched_filter(
        self,
        code: str,
        hide_watched: bool,
        provider: DeckProvider,
        uow: DatabaseUnitOfWork,
    ) -> MutationResult:
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
        # Append hide_watched_changed event on success and return its event_id.
        # event_id stays 0 (never a real autoincrement id) when no session
        # instance exists — the frontend treats 0 as "nothing to suppress".
        instance = await uow.session_instances.get_by_pairing_code(code)
        event_id = 0
        if instance:
            event_id = await uow.session_events.append(
                instance.instance_id,
                "hide_watched_changed",
                json.dumps({"hide_watched": hide_watched}),
            )
        return MutationResult(deck=new_deck, event_id=event_id)

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
                "rating": r.rating,
                "duration": r.duration or "",
                "year": r.year if r.year else None,
            }
            for r in rows
        ]
