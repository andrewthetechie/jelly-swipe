"""Shared Pydantic v2 models for API documentation and responses."""

from jellyswipe.schemas.auth import (
    LoginResponse,
    LogoutResponse,
    MeResponse,
    ServerInfoResponse,
)
from jellyswipe.schemas.common import CardItem, ErrorResponse, MatchItem
from jellyswipe.schemas.media import (
    CastMember,
    CastResponse,
    GenreListResponse,
    TrailerResponse,
    WatchlistAddRequest,
)
from jellyswipe.schemas.rooms import (
    CreateRoomRequest,
    CreateRoomResponse,
    JoinRoomResponse,
    MutationChangeResponse,
    QuitRoomResponse,
    RoomStatusResponse,
    SetGenreRequest,
    SetWatchedFilterRequest,
    SwipeRequest,
    SwipeResponse,
    UndoRequest,
    UndoResponse,
)

__all__ = [
    "CardItem",
    "CastMember",
    "CastResponse",
    "CreateRoomRequest",
    "CreateRoomResponse",
    "ErrorResponse",
    "GenreListResponse",
    "JoinRoomResponse",
    "LoginResponse",
    "LogoutResponse",
    "MatchItem",
    "MeResponse",
    "MutationChangeResponse",
    "QuitRoomResponse",
    "RoomStatusResponse",
    "ServerInfoResponse",
    "SetGenreRequest",
    "SetWatchedFilterRequest",
    "SwipeRequest",
    "SwipeResponse",
    "TrailerResponse",
    "UndoRequest",
    "UndoResponse",
    "WatchlistAddRequest",
]
