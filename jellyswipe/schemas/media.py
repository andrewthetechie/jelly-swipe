"""Pydantic v2 models for media enrichment endpoints."""

from typing import Optional

from pydantic import BaseModel, Field, RootModel


class TrailerResponse(BaseModel):
    """Trailer YouTube key for a movie."""

    youtube_key: str = Field(description="YouTube video key for embedding the trailer")


class CastMember(BaseModel):
    """A single cast member returned by TMDB."""

    name: str = Field(description="Actor's name")
    character: str = Field(description="Character name in the movie")
    profile_path: Optional[str] = Field(
        None, description="URL to profile image, or null if unavailable"
    )


class CastResponse(BaseModel):
    """Cast list for a movie."""

    cast: list[CastMember] = Field(description="List of cast members")


class WatchlistAddRequest(BaseModel):
    """Request body for POST /watchlist/add."""

    media_id: str = Field(
        description="Jellyfin media ID to add to the user's watchlist"
    )


class WatchlistAddResponse(BaseModel):
    """Successful response from POST /watchlist/add."""

    status: str = Field(description="Always 'success' on a successful add")


class GenreListResponse(RootModel[list[str]]):
    """JSON array of genre names available in the Jellyfin library."""
