"""Shared Pydantic v2 models for API responses."""

from typing import Optional

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Application-level error response."""

    error: str
    request_id: Optional[str] = None


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
    year: Optional[int] = None
    media_type: str
    rating: Optional[float] = None
    duration: Optional[str] = None
    season_count: Optional[int] = None


class MatchItem(BaseModel):
    """Match row shape from matches endpoint."""

    title: Optional[str] = None
    thumb: Optional[str] = None
    media_id: Optional[str] = None
    media_type: Optional[str] = None
    deep_link: Optional[str] = None
    rating: Optional[str] = None
    duration: Optional[str] = None
    year: Optional[int] = None
