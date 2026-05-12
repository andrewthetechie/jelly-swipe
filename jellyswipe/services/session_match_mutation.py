"""Session Match Mutation — domain types and swipe transaction implementation.

This module defines the types and class for the Session Match Mutation
module. All types are immutable dataclasses. The ``apply_swipe`` method
implements the core concurrency-critical swipe transaction using
``BEGIN IMMEDIATE`` for SQLite serialization safety.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import text

from jellyswipe.repositories.session_events import append_sync
from jellyswipe.room_types import SwipeCounterparty

if TYPE_CHECKING:
    from jellyswipe.db_uow import DatabaseUnitOfWork


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


def _resolve_meta_from_deck(movie_data_json: str | None, media_id: str) -> dict:
    """Look up rating, duration, year, media_type from the Room's deck JSON."""
    try:
        items = json.loads(movie_data_json or "[]")
        for item in items:
            if str(item.get("id", "")) == str(media_id):
                rating = item.get("rating")
                duration = item.get("duration")
                year = item.get("year")
                media_type = item.get("media_type", "movie")
                return {
                    "rating": str(rating) if rating is not None else "",
                    "duration": duration or "",
                    "year": str(year) if year is not None else "",
                    "media_type": media_type,
                }
    except (json.JSONDecodeError, TypeError):
        pass
    return {"rating": "", "duration": "", "year": "", "media_type": "movie"}


def _insert_match(
    conn,
    code: str,
    media_id: str,
    user_id: str,
    catalog_facts: CatalogFacts,
    meta: dict,
    deep_link: str,
) -> None:
    """Insert a match row using INSERT OR IGNORE equivalent via SQLAlchemy."""
    conn.execute(
        text("""
            INSERT OR IGNORE INTO matches
                (room_code, movie_id, title, thumb, status, user_id, deep_link, rating, duration, year, media_type)
            VALUES
                (:room_code, :movie_id, :title, :thumb, :status, :user_id, :deep_link, :rating, :duration, :year, :media_type)
        """),
        {
            "room_code": code,
            "movie_id": media_id,
            "title": catalog_facts.title or "",
            "thumb": catalog_facts.thumb or "",
            "status": "active",
            "user_id": user_id,
            "deep_link": deep_link,
            "rating": meta["rating"],
            "duration": meta["duration"],
            "year": meta["year"],
            "media_type": meta["media_type"],
        },
    )


def _find_counterparty(
    conn,
    code: str,
    media_id: str,
    actor: SessionActor,
) -> SwipeCounterparty | None:
    """Find an existing right-swipe from another session/user."""
    if actor.session_id:
        row = (
            conn.execute(
                text("""
                SELECT user_id, session_id FROM swipes
                WHERE room_code = :code
                  AND movie_id = :media_id
                  AND direction = 'right'
                  AND (session_id IS NULL OR session_id != :session_id)
                LIMIT 1
            """),
                {
                    "code": code,
                    "media_id": media_id,
                    "session_id": actor.session_id,
                },
            )
            .mappings()
            .first()
        )
    else:
        row = (
            conn.execute(
                text("""
                SELECT user_id, session_id FROM swipes
                WHERE room_code = :code
                  AND movie_id = :media_id
                  AND direction = 'right'
                  AND user_id != :user_id
                LIMIT 1
            """),
                {
                    "code": code,
                    "media_id": media_id,
                    "user_id": actor.user_id,
                },
            )
            .mappings()
            .first()
        )

    if row is None:
        return None
    return SwipeCounterparty(user_id=row["user_id"], session_id=row["session_id"])


def _emit_match_event(
    conn,
    code: str,
    media_id: str,
    catalog_facts: CatalogFacts,
    meta: dict,
    deep_link: str,
) -> None:
    """Look up active instance and append a match_found event."""
    inst = (
        conn.execute(
            text("""
            SELECT instance_id FROM session_instances
            WHERE pairing_code = :code AND status = 'active'
            LIMIT 1
        """),
            {"code": code},
        )
        .mappings()
        .first()
    )

    if inst is None:
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
    append_sync(
        conn,
        instance_id=inst["instance_id"],
        event_type="match_found",
        payload_json=payload,
    )


def _sync_apply_swipe(
    sync_session,
    *,
    code: str,
    actor: SessionActor,
    media_id: str,
    direction: str | None,
    catalog_facts: CatalogFacts,
    jellyfin_url: str,
) -> ApplySwipeResult:
    """Internal sync function that runs inside uow.run_sync(...)."""
    conn = sync_session.connection()
    raw_conn = conn.connection.driver_connection
    raw_conn.isolation_level = None
    conn.exec_driver_sql("BEGIN IMMEDIATE")

    # 1. Room check
    room_row = (
        conn.execute(
            text(
                "SELECT pairing_code, movie_data, solo_mode, deck_position "
                "FROM rooms WHERE pairing_code = :code"
            ),
            {"code": code},
        )
        .mappings()
        .first()
    )
    if room_row is None:
        return SwipeRejected(reason="room_not_found")

    # 2. Insert swipe
    conn.execute(
        text(
            "INSERT INTO swipes (room_code, movie_id, user_id, direction, session_id) "
            "VALUES (:room_code, :movie_id, :user_id, :direction, :session_id)"
        ),
        {
            "room_code": code,
            "movie_id": media_id,
            "user_id": actor.user_id,
            "direction": direction or "left",
            "session_id": actor.session_id,
        },
    )

    # 3. Advance cursor
    positions = (
        json.loads(room_row["deck_position"]) if room_row["deck_position"] else {}
    )
    current_pos = int(positions.get(actor.user_id, 0))
    positions[actor.user_id] = current_pos + 1
    conn.execute(
        text(
            "UPDATE rooms SET deck_position = :deck_position WHERE pairing_code = :code"
        ),
        {"deck_position": json.dumps(positions), "code": code},
    )

    # 4. Match detection (only for right-swipe with title/thumb)
    if (
        direction != "right"
        or catalog_facts.title is None
        or catalog_facts.thumb is None
    ):
        return SwipeAccepted(match_created=False)

    # 5. Derive match metadata from room's movie_data
    meta = _resolve_meta_from_deck(room_row["movie_data"], media_id)
    deep_link = f"{jellyfin_url}/web/#/details?id={media_id}" if jellyfin_url else ""

    # 6. Solo mode: create match + event
    if room_row["solo_mode"]:
        _insert_match(
            conn, code, media_id, actor.user_id, catalog_facts, meta, deep_link
        )
        _emit_match_event(conn, code, media_id, catalog_facts, meta, deep_link)
        return SwipeAccepted(match_created=True)

    # 7. Hosted: check for counterparty right-swipe
    counterparty = _find_counterparty(conn, code, media_id, actor)

    if counterparty:
        _insert_match(
            conn, code, media_id, actor.user_id, catalog_facts, meta, deep_link
        )
        if counterparty.user_id != actor.user_id:
            _insert_match(
                conn,
                code,
                media_id,
                counterparty.user_id,
                catalog_facts,
                meta,
                deep_link,
            )
        _emit_match_event(conn, code, media_id, catalog_facts, meta, deep_link)
        return SwipeAccepted(match_created=True)

    return SwipeAccepted(match_created=False)


class SessionMatchMutation:
    """Typed methods for session-based match mutations."""

    async def apply_swipe(
        self,
        *,
        code: str,
        actor: SessionActor,
        media_id: str,
        direction: str | None,
        catalog_facts: CatalogFacts,
        uow: DatabaseUnitOfWork,
        jellyfin_url: str,
    ) -> ApplySwipeResult:
        return await uow.run_sync(
            _sync_apply_swipe,
            code=code,
            actor=actor,
            media_id=media_id,
            direction=direction,
            catalog_facts=catalog_facts,
            jellyfin_url=jellyfin_url,
        )

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
