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
    DeckPageResponse,
    JoinRoomResponse,
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
    "ErrorResponse",
    "CardItem",
    "MatchItem",
    "TrailerResponse",
    "CastMember",
    "CastResponse",
    "WatchlistAddRequest",
    "GenreListResponse",
    "LoginResponse",
    "LogoutResponse",
    "MeResponse",
    "ServerInfoResponse",
    "CreateRoomRequest",
    "CreateRoomResponse",
    "JoinRoomResponse",
    "RoomStatusResponse",
    "QuitRoomResponse",
    "SwipeRequest",
    "SwipeResponse",
    "UndoRequest",
    "UndoResponse",
    "SetGenreRequest",
    "SetWatchedFilterRequest",
    "DeckPageResponse",
]
