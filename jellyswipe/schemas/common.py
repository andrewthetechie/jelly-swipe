"""Shared Pydantic v2 models for API responses."""

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Application-level error response."""

    error: str
    request_id: str | None = None


class CardItem(BaseModel):
    """Card shape returned by deck, genre-change, and watched-filter endpoints.

    ``rating`` is the raw Jellyfin community/critic rating (a float). TV-series
    cards omit ``rating`` and ``duration`` and instead carry ``season_count``.
    ``year`` may be ``null`` when Jellyfin lacks a production year.
    """

    media_id: str
    title: str
    summary: str
    thumb: str
    year: int | None = None
    media_type: str
    rating: float | None = None
    duration: str | None = None
    season_count: int | None = None


class MatchItem(BaseModel):
    """Match row shape from matches endpoint.

    ``rating`` mirrors ``CardItem.rating`` (a float) so the deck and matches
    endpoints expose a consistent ``rating`` type in the API contract. Legacy
    rows stored as text are normalized to a float when read.
    """

    title: str | None = None
    thumb: str | None = None
    media_id: str | None = None
    media_type: str | None = None
    deep_link: str | None = None
    rating: float | None = None
    duration: str | None = None
    year: int | None = None
