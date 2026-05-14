"""Pydantic v2 models for room lifecycle and swiping endpoints."""

from typing import Optional

from pydantic import BaseModel, Field, StrictBool, model_validator

from jellyswipe.schemas.common import CardItem, MatchItem


class CreateRoomRequest(BaseModel):
    """Request body for POST /room.

    All fields are JSON booleans — not strings. Sending ``"true"`` instead of
    ``true`` will result in a 422 validation error.
    """

    movies: StrictBool = Field(True, description="Include movies in the deck")
    tv_shows: StrictBool = Field(False, description="Include TV shows in the deck")
    solo: StrictBool = Field(False, description="Create a solo (single-player) room")

    @model_validator(mode="after")
    def at_least_one_media_type(self) -> "CreateRoomRequest":
        if not self.movies and not self.tv_shows:
            raise ValueError("At least one of movies or tv_shows must be true")
        return self


class CreateRoomResponse(BaseModel):
    """Response from POST /room."""

    pairing_code: str = Field(..., description="4-digit room pairing code")
    instance_id: str = Field(..., description="Unique session instance identifier")


class JoinRoomResponse(BaseModel):
    """Response from POST /room/{code}/join."""

    status: str = Field(..., description="Join status")


class RoomStatusResponse(BaseModel):
    """Response from GET /room/{code}/status."""

    ready: bool = Field(..., description="Whether the room is ready to start")
    genre: Optional[str] = Field(None, description="Current genre filter")
    solo: Optional[bool] = Field(None, description="Whether this is a solo room")
    hide_watched: Optional[bool] = Field(
        None, description="Whether watched items are hidden"
    )


class QuitRoomResponse(BaseModel):
    """Response from POST /room/{code}/quit."""

    status: str = Field(..., description="Quit status")


class SwipeRequest(BaseModel):
    """Request body for POST /room/{code}/swipe."""

    media_id: str = Field(..., description="Media ID to swipe on")
    direction: Optional[str] = Field(None, description="Swipe direction (left/right)")


class SwipeResponse(BaseModel):
    """Response from POST /room/{code}/swipe."""

    accepted: bool = Field(..., description="Whether the swipe was accepted")


class UndoRequest(BaseModel):
    """Request body for POST /room/{code}/undo."""

    media_id: str = Field(..., description="Media ID to undo the swipe for")


class UndoResponse(BaseModel):
    """Response from POST /room/{code}/undo."""

    status: str = Field(..., description="Undo status")


class SetGenreRequest(BaseModel):
    """Request body for POST /room/{code}/genre."""

    genre: str = Field(..., description="Genre name to filter by")


class SetWatchedFilterRequest(BaseModel):
    """Request body for POST /room/{code}/watched-filter."""

    hide_watched: StrictBool = Field(..., description="Whether to hide watched items")


class DeckPageResponse(BaseModel):
    """Response from GET /room/{code}/deck."""

    items: list["CardItem"] = Field(..., description="Page of cards from the deck")


class DeleteMatchRequest(BaseModel):
    """Request body for POST /matches/delete."""

    media_id: str = Field(..., description="Media ID of the match to delete")


class DeleteMatchResponse(BaseModel):
    """Response from POST /matches/delete."""

    status: str = Field(
        "deleted", description="Confirmation that the match was deleted"
    )


class MatchListResponse(BaseModel):
    """Response from GET /matches."""

    matches: list[MatchItem] = Field(..., description="List of matched items")
