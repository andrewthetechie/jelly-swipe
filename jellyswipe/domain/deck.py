"""Deck domain module.

A ``Deck`` is a room's ordered card list (``cards``) plus a per-participant
swipe cursor map (``cursors``). It is the single owner of deck JSON parsing,
cursor advance, page slicing, card lookup, and serialization for the
``movie_data`` / ``deck_position`` room columns.

Before this module existed, three separate ``json.loads`` parsers with
divergent error tolerance lived in ``deck_pipeline``, ``room_lifecycle``, and
``session_match_mutation``, each re-doing the ``id`` <-> ``media_id`` card
conversion. All of that now lives here, so the three consumers and the
repository seam share one contract.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

Card = dict[str, Any]

logger = logging.getLogger(__name__)


def _api_card(card: Card) -> dict[str, Any]:
    """Map one internal card to its public API shape (``id`` -> ``media_id``)."""
    item = {k: v for k, v in card.items() if k != "id"}
    item["media_id"] = card.get("id")
    item["media_type"] = card.get("media_type", "movie")
    return item


@dataclass(frozen=True)
class Deck:
    """Immutable room deck: an ordered card list plus per-user cursor map."""

    cards: tuple[Card, ...]
    cursors: dict[str, int]

    @classmethod
    def from_cards(
        cls, cards: list[Card] | tuple[Card, ...], cursors: dict[str, int] | None = None
    ) -> Deck:
        """Build a Deck from internal card dicts and an optional cursor map."""
        return cls(cards=tuple(cards), cursors=dict(cursors or {}))

    @classmethod
    def parse(cls, movie_data_json: str | None, deck_position_json: str | None) -> Deck:
        """Parse the two room JSON columns into a Deck, tolerating corruption.

        Any malformed input degrades to an empty deck / empty cursor map and is
        logged once at warning level — the caller never sees a raise, matching
        the legacy tolerant parsers each consumer used to own.
        """
        cards: list[Card] = []
        if movie_data_json:
            try:
                loaded = json.loads(movie_data_json)
                if isinstance(loaded, list):
                    cards = [c for c in loaded if isinstance(c, dict)]
            except (json.JSONDecodeError, TypeError):
                logger.warning("Unparseable deck movie_data JSON; treating as empty")

        cursors: dict[str, int] = {}
        if deck_position_json:
            try:
                loaded = json.loads(deck_position_json)
                if isinstance(loaded, dict):
                    for key, value in loaded.items():
                        try:
                            cursors[str(key)] = int(value)
                        except (TypeError, ValueError):
                            cursors[str(key)] = 0
            except (json.JSONDecodeError, TypeError):
                logger.warning("Unparseable deck position JSON; treating as empty")

        return cls(cards=tuple(cards), cursors=cursors)

    def cursor_for(self, user_id: str) -> int:
        """Return the swipe cursor for ``user_id`` (0 when absent)."""
        return self.cursors.get(user_id, 0)

    def advance_cursor(self, user_id: str) -> Deck:
        """Return a new Deck with ``user_id``'s cursor advanced by one."""
        return Deck(
            cards=self.cards,
            cursors={**self.cursors, user_id: self.cursor_for(user_id) + 1},
        )

    def add_participant(self, user_id: str) -> Deck:
        """Return a new Deck with ``user_id`` added at cursor 0, preserving others."""
        return Deck(cards=self.cards, cursors={**self.cursors, user_id: 0})

    def reset_cursors(self) -> Deck:
        """Return a new Deck with all cursors cleared (filter change)."""
        return Deck(cards=self.cards, cursors={})

    def api_cards(self) -> list[dict[str, Any]]:
        """Return the full deck in public API shape (``id`` -> ``media_id``)."""
        return [_api_card(card) for card in self.cards]

    def page(
        self, user_id: str, page: int, page_size: int = 20
    ) -> list[dict[str, Any]]:
        """Return the API-shape cards for ``user_id`` starting at its cursor.

        ``page`` is 1-indexed. The returned list is a ``page_size`` slice of the
        full API deck beginning at ``cursor + (page - 1) * page_size``.
        """
        start = self.cursor_for(user_id) + (page - 1) * page_size
        end = start + page_size
        return self.api_cards()[start:end]

    def card_by_id(self, media_id: str) -> Card | None:
        """Return the internal card for ``media_id``, or None if absent."""
        for card in self.cards:
            if str(card.get("id", "")) == str(media_id):
                return card
        return None

    def serialize(self) -> tuple[str, str]:
        """Return ``(movie_data_json, deck_position_json)`` for persistence."""
        return json.dumps(list(self.cards)), json.dumps(self.cursors)
