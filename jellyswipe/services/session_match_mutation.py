"""Session Match Mutation — domain types and swipe transaction implementation.

This module defines the types and class for the Session Match Mutation
module. All types are immutable dataclasses. The ``apply_swipe`` method
implements the core concurrency-critical swipe transaction using
``BEGIN IMMEDIATE`` for SQLite serialization safety. All persistence goes
through the repository layer exposed by ``DatabaseUnitOfWork`` — there is
no raw SQL in this module.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from jellyswipe.repositories.matches import parse_rating

if TYPE_CHECKING:
    from jellyswipe.db_uow import DatabaseUnitOfWork

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class SessionActor:
    """Replaces raw request.session dict plumbing."""

    user_id: str
    session_id: str | None
    active_room: str | None


@dataclass(slots=True, frozen=True)
class CatalogFacts:
    """Minimal external facts the module cannot derive from Session state."""

    title: str | None = None
    thumb: str | None = None


@dataclass(slots=True, frozen=True)
class SwipeAccepted:
    """Swipe was applied successfully."""

    match_created: bool


@dataclass(slots=True, frozen=True)
class SwipeRejected:
    """Swipe was rejected."""

    reason: str  # "room_not_found"


ApplySwipeResult = SwipeAccepted | SwipeRejected


@dataclass(slots=True, frozen=True)
class UndoChanged:
    """Swipe was found and removed."""

    match_removed: bool  # True if an active match was also removed


@dataclass(slots=True, frozen=True)
class UndoNoOp:
    """No matching swipe found to undo."""


UndoSwipeResult = UndoChanged | UndoNoOp


@dataclass(slots=True, frozen=True)
class DeleteChanged:
    """Match was found and deleted."""


@dataclass(slots=True, frozen=True)
class DeleteNoOp:
    """No matching match found to delete."""


DeleteMatchResult = DeleteChanged | DeleteNoOp


def _card_from_deck(movie_data_json: str | None, media_id: str) -> dict | None:
    """Return the Room deck card for ``media_id``, or None if absent."""
    try:
        items = json.loads(movie_data_json or "[]")
        for item in items:
            if str(item.get("id", "")) == str(media_id):
                return item
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _catalog_facts_from_card(card: dict | None, media_id: str) -> CatalogFacts:
    """Build CatalogFacts (title/thumb) from a deck card."""
    if card is None:
        return CatalogFacts(title=None, thumb=None)
    return CatalogFacts(title=card.get("title"), thumb=card.get("thumb"))


def _meta_from_card(card: dict | None) -> dict:
    """Derive rating/duration/year/media_type from a deck card."""
    if card is None:
        return {"rating": None, "duration": "", "year": "", "media_type": "movie"}
    duration = card.get("duration")
    year = card.get("year")
    media_type = card.get("media_type", "movie")
    return {
        "rating": parse_rating(card.get("rating")),
        "duration": duration or "",
        "year": str(year) if year is not None else "",
        "media_type": media_type,
    }


async def _insert_match_for_user(
    uow: DatabaseUnitOfWork,
    *,
    code: str,
    media_id: str,
    user_id: str,
    catalog_facts: CatalogFacts,
    meta: dict,
    deep_link: str,
) -> None:
    """Insert an active match row for one user (INSERT OR IGNORE semantics)."""
    await uow.matches.insert(
        room_code=code,
        movie_id=media_id,
        title=catalog_facts.title or "",
        thumb=catalog_facts.thumb or "",
        user_id=user_id,
        deep_link=deep_link,
        rating=meta["rating"],
        duration=meta["duration"],
        year=meta["year"],
        media_type=meta["media_type"],
    )


async def _emit_match_event(
    uow: DatabaseUnitOfWork,
    code: str,
    media_id: str,
    catalog_facts: CatalogFacts,
    meta: dict,
    deep_link: str,
) -> None:
    """Append a match_found event to the room's active session instance."""
    inst = await uow.session_instances.get_by_pairing_code(code)
    if inst is None or inst.status != "active":
        return

    payload = json.dumps(
        {
            "media_id": media_id,
            "title": catalog_facts.title,
            "thumb": catalog_facts.thumb,
            "media_type": meta.get("media_type", "movie"),
            "rating": meta["rating"],
            "duration": meta["duration"],
            "year": meta["year"],
            "deep_link": deep_link,
        }
    )
    await uow.session_events.append(
        instance_id=inst.instance_id,
        event_type="match_found",
        payload_json=payload,
    )


class SessionMatchMutation:
    """Typed methods for session-based match mutations."""

    async def apply_swipe(
        self,
        *,
        code: str,
        actor: SessionActor,
        media_id: str,
        direction: str | None,
        uow: DatabaseUnitOfWork,
        jellyfin_url: str,
    ) -> ApplySwipeResult:
        return await self.apply_swipe_transaction(
            uow=uow,
            code=code,
            actor=actor,
            media_id=media_id,
            direction=direction,
            jellyfin_url=jellyfin_url,
        )

    async def apply_swipe_transaction(
        self,
        *,
        uow: DatabaseUnitOfWork,
        code: str,
        actor: SessionActor,
        media_id: str,
        direction: str | None,
        jellyfin_url: str,
    ) -> ApplySwipeResult:
        """Apply one swipe atomically through the repository layer.

        Opens a ``BEGIN IMMEDIATE`` transaction for SQLite write serialization
        (see D-12/D-13), then performs room lookup, swipe insert, cursor
        advance, counterparty match detection, match insert, and event
        emission — all via the UoW's repositories on the same connection.
        Transaction completion stays with the route's dependency boundary.
        """
        await uow.begin_immediate()

        # 1. Room check
        room = await uow.rooms.get_room(code)
        if room is None:
            return SwipeRejected(reason="room_not_found")

        # 2. Insert swipe
        await uow.swipes.insert(
            room_code=code,
            movie_id=media_id,
            user_id=actor.user_id,
            direction=direction or "left",
            session_id=actor.session_id,
        )

        # 3. Advance cursor
        positions = (
            json.loads(room.deck_position_json) if room.deck_position_json else {}
        )
        current_pos = int(positions.get(actor.user_id, 0))
        positions[actor.user_id] = current_pos + 1
        await uow.rooms.set_deck_position(code, json.dumps(positions))

        # 4. Match detection (only for right-swipe with a card present in the deck)
        if direction != "right":
            return SwipeAccepted(match_created=False)

        card = _card_from_deck(room.movie_data_json, media_id)
        catalog_facts = _catalog_facts_from_card(card, media_id)
        if catalog_facts.title is None or catalog_facts.thumb is None:
            if card is None:
                logger.warning(
                    "right-swipe media_id=%s not in room %s deck; no match recorded",
                    media_id,
                    code,
                )
            return SwipeAccepted(match_created=False)

        # 5. Derive match metadata from room's movie_data
        meta = _meta_from_card(card)
        deep_link = (
            f"{jellyfin_url}/web/#/details?id={media_id}" if jellyfin_url else ""
        )

        # 6. Solo mode: create match + event
        if room.solo_mode:
            await _insert_match_for_user(
                uow,
                code=code,
                media_id=media_id,
                user_id=actor.user_id,
                catalog_facts=catalog_facts,
                meta=meta,
                deep_link=deep_link,
            )
            await _emit_match_event(uow, code, media_id, catalog_facts, meta, deep_link)
            return SwipeAccepted(match_created=True)

        # 7. Hosted: check for counterparty right-swipe
        counterparty = await uow.swipes.find_other_right_swipe(
            code, media_id, actor.user_id, actor.session_id
        )
        if counterparty is None:
            return SwipeAccepted(match_created=False)

        await _insert_match_for_user(
            uow,
            code=code,
            media_id=media_id,
            user_id=actor.user_id,
            catalog_facts=catalog_facts,
            meta=meta,
            deep_link=deep_link,
        )
        if counterparty.user_id != actor.user_id:
            await _insert_match_for_user(
                uow,
                code=code,
                media_id=media_id,
                user_id=counterparty.user_id,
                catalog_facts=catalog_facts,
                meta=meta,
                deep_link=deep_link,
            )
        await _emit_match_event(uow, code, media_id, catalog_facts, meta, deep_link)
        return SwipeAccepted(match_created=True)

    async def undo_swipe(
        self,
        *,
        code: str,
        actor: SessionActor,
        media_id: str,
        uow: DatabaseUnitOfWork,
    ) -> UndoSwipeResult:
        swipe_deleted = await uow.swipes.delete_by_room_movie_session(
            code, media_id, actor.session_id
        )
        if swipe_deleted == 0:
            return UndoNoOp()

        match_deleted = await uow.matches.delete_active_for_room_movie_user(
            code, media_id, actor.user_id
        )
        return UndoChanged(match_removed=match_deleted > 0)

    async def delete_match(
        self,
        *,
        actor: SessionActor,
        media_id: str,
        uow: DatabaseUnitOfWork,
    ) -> DeleteMatchResult:
        deleted = await uow.matches.delete_for_user(media_id, actor.user_id)
        if deleted == 0:
            return DeleteNoOp()
        return DeleteChanged()


__all__ = [
    "ApplySwipeResult",
    "CatalogFacts",
    "DeleteChanged",
    "DeleteMatchResult",
    "DeleteNoOp",
    "SessionActor",
    "SessionMatchMutation",
    "SwipeAccepted",
    "SwipeRejected",
    "UndoChanged",
    "UndoNoOp",
    "UndoSwipeResult",
]
