"""Session Match Mutation — domain types and stub class.

This module defines the types and class shell for the Session Match Mutation
module. All types are immutable dataclasses. The class methods are stubs that
raise ``NotImplementedError`` — implementations will be filled in by
subsequent tickets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

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


class SessionMatchMutation:
    """Typed stub methods for session-based match mutations."""

    async def apply_swipe(
        self,
        *,
        code: str,
        actor: SessionActor,
        media_id: str,
        direction: str | None,
        catalog_facts: CatalogFacts,
        uow: DatabaseUnitOfWork,
    ) -> ApplySwipeResult:
        raise NotImplementedError

    async def undo_swipe(
        self,
        *,
        code: str,
        actor: SessionActor,
        media_id: str,
        uow: DatabaseUnitOfWork,
    ) -> UndoSwipeResult:
        raise NotImplementedError

    async def delete_match(
        self,
        *,
        actor: SessionActor,
        media_id: str,
        uow: DatabaseUnitOfWork,
    ) -> DeleteMatchResult:
        raise NotImplementedError


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
