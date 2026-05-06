"""Pure metadata assembly module for Alembic."""

from jellyswipe.models.auth_session import AuthSession
from jellyswipe.models.base import Base
from jellyswipe.models.match import Match
from jellyswipe.models.room import Room
from jellyswipe.models.swipe import Swipe

target_metadata = Base.metadata

__all__ = [
    "AuthSession",
    "Base",
    "Match",
    "Room",
    "Swipe",
    "target_metadata",
]
