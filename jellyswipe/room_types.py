"""Shared non-ORM contracts for room, swipe, and match persistence (Phase 39)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SessionInstanceRecord:
    instance_id: str
    pairing_code: str
    status: str
    created_at: str
    closed_at: str | None


@dataclass(slots=True)
class SessionEventRecord:
    event_id: int
    session_instance_id: str
    event_type: str
    payload_json: str
    created_at: str


@dataclass(slots=True)
class RoomRecord:
    pairing_code: str
    movie_data_json: str
    ready: bool
    current_genre: str
    solo_mode: bool
    deck_position_json: str | None
    deck_order_json: str | None
    include_movies: bool
    include_tv_shows: bool
    hide_watched: bool


@dataclass(slots=True)
class RoomStatusSnapshot:
    ready: bool
    genre: str
    solo: bool
    hide_watched: bool


@dataclass(slots=True)
class MatchRecord:
    room_code: str
    movie_id: str
    title: str
    thumb: str
    status: str
    user_id: str
    deep_link: str | None
    rating: str | None
    duration: str | None
    year: str | None
    media_type: str | None
    match_order: int | None


@dataclass(slots=True)
class SwipeCounterparty:
    user_id: str
    session_id: str | None


@dataclass(slots=True)
class TmdbCacheRecord:
    media_id: str
    lookup_type: str
    result_json: str
    fetched_at: str
