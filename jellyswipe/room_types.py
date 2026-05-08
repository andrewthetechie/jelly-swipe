"""Shared non-ORM contracts for room, swipe, and match persistence (Phase 39)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RoomRecord:
    pairing_code: str
    movie_data_json: str
    ready: bool
    current_genre: str
    solo_mode: bool
    last_match_data_json: str | None
    deck_position_json: str | None
    deck_order_json: str | None
    include_movies: bool
    include_tv_shows: bool


@dataclass(slots=True)
class RoomStatusSnapshot:
    ready: bool
    genre: str
    solo: bool
    last_match: dict | None


@dataclass(slots=True)
class StreamSnapshot:
    ready: bool
    genre: str
    solo: bool
    last_match: dict | None
    last_match_ts: str | float | int | None


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
    match_order: int | None


@dataclass(slots=True)
class SwipeCounterparty:
    user_id: str
    session_id: str | None
