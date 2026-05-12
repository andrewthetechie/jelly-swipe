"""Unified Swipe Deck building pipeline.

Consolidates the 7-step deck building process (fetch, interleave, exclude swiped,
validate, persist, convert) into a single function.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol

from jellyswipe.db_uow import DatabaseUnitOfWork

logger = logging.getLogger(__name__)


class EmptyDeckError(Exception):
    """Deck build produced zero items — no state change occurred."""

    def __init__(self, reason: str = "No items matched the filter criteria") -> None:
        super().__init__(reason)


class DeckProvider(Protocol):
    def fetch_deck(
        self,
        media_types: list[str],
        genre_name: str | None = None,
        hide_watched: bool = False,
    ) -> list[dict[str, Any]]: ...


def _interleave(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply Balanced Interleaving (round-robin) to movies and TV shows."""
    movies = [m for m in items if m.get("media_type") == "movie"]
    tv_shows = [t for t in items if t.get("media_type") == "tv_show"]
    interleaved = []
    max_len = max(len(movies), len(tv_shows))
    for i in range(max_len):
        if i < len(movies):
            interleaved.append(movies[i])
        if i < len(tv_shows):
            interleaved.append(tv_shows[i])
    return interleaved


def _to_api_format(deck: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert internal card dicts (with 'id') to API format (with 'media_id')."""
    result = []
    for card in deck:
        api_item = {k: v for k, v in card.items() if k != "id"}
        api_item["media_id"] = card.get("id")
        result.append(api_item)
    return result


async def build_deck(
    provider: DeckProvider,
    uow: DatabaseUnitOfWork,
    room_code: str,
    media_types: list[str],
    genre: str | None = None,
    hide_watched: bool = False,
    persist: bool = True,
) -> list[dict]:
    """Unified Swipe Deck building pipeline.

    Steps:
    1. Fetch from provider via DeckProvider Protocol
    2. Apply Balanced Interleaving when both media types present
    3. Exclude swiped Media Candidate IDs
    4. Validate non-empty (raise EmptyDeckError)
    5. If persist=True: persist to room row, convert to API format
    6. Return deck

    Args:
        provider: DeckProvider implementation for fetching media items
        uow: DatabaseUnitOfWork for DB access
        room_code: Room pairing code
        media_types: List of media types to fetch (e.g., ["movie", "tv_show"])
        genre: Optional genre filter
        hide_watched: Whether to hide watched items
        persist: If True, persist deck to room row and return API format.
                 If False, return internal format without persisting.

    Returns:
        List of card dicts (API format if persist=True, internal format if persist=False)

    Raises:
        EmptyDeckError: If deck is empty after exclusion
    """
    # Step 1: Fetch from provider
    items = provider.fetch_deck(
        media_types=media_types,
        genre_name=genre,
        hide_watched=hide_watched,
    )

    # Step 2: Apply Balanced Interleaving when both media types present
    has_movies = "movie" in media_types
    has_tv = "tv_show" in media_types
    if has_movies and has_tv:
        items = _interleave(items)

    # Step 3: Exclude swiped Media Candidate IDs
    swiped_ids = await uow.swipes.list_swiped_media_ids(room_code)
    filtered_deck = [item for item in items if item.get("id") not in swiped_ids]

    # Step 4: Validate non-empty
    if not filtered_deck:
        logger.warning(
            "Empty deck for room %s: media_types=%s, genre=%s, hide_watched=%s, excluded %d swiped items",
            room_code,
            media_types,
            genre,
            hide_watched,
            len(swiped_ids),
        )
        raise EmptyDeckError("No items available. Try a different filter.")

    # Step 5 & 6: Persist (if requested) and return
    if persist:
        # Persist internal format to room row
        await uow.rooms.set_filters_and_deck(
            room_code,
            genre=genre or "All",
            hide_watched=hide_watched,
            movie_data_json=json.dumps(filtered_deck),
            deck_position_json=json.dumps({}),
        )
        # Return API format
        return _to_api_format(filtered_deck)

    # No-persist flow: return internal format
    return filtered_deck
