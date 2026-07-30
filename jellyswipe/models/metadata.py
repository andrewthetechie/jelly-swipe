"""Pure metadata assembly module for Alembic."""

from jellyswipe.models.auth_session import AuthSession
from jellyswipe.models.base import Base
from jellyswipe.models.match import Match
from jellyswipe.models.room import Room
from jellyswipe.models.session_event import SessionEvent, SessionInstance
from jellyswipe.models.swipe import Swipe
from jellyswipe.models.tmdb_cache import TmdbCache

target_metadata = Base.metadata

__all__ = [
    "AuthSession",
    "Base",
    "Match",
    "Room",
    "SessionEvent",
    "SessionInstance",
    "Swipe",
    "TmdbCache",
    "target_metadata",
]
