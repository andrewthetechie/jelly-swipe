"""Shared Pydantic v2 models for API responses."""

from typing import Optional

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Application-level error response."""

    error: str
    request_id: Optional[str] = None


class CardItem(BaseModel):
    """Card shape returned by deck and genre-change endpoints."""

    media_id: str
    title: str
    summary: str
    thumb: str
    year: int
    media_type: str
    rating: str
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
