"""MatchFacts domain module.

A ``MatchFacts`` is the canonical match fact set (title, thumb, rating,
duration, year, media_type, deep_link) derived from a deck card or a stored
match row. It is the single owner of the defaulting rules for those fields and
the deep-link builder, so the swipe write path, the matches listing, and the
``match_found`` event can no longer drift apart.

Before this module existed, the fact set was derived three times: in the swipe
transaction (``_meta_from_card`` + ``_catalog_facts_from_card`` plus an inline
deep-link string in ``session_match_mutation``), in the matches listing
(``room_lifecycle``), and in the ``match_found`` event payload. All of that
now lives here, behind three projections each consumer uses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from jellyswipe.repositories.matches import MatchRecord

DEFAULT_MEDIA_TYPE = "movie"


def parse_rating(value: object) -> float | None:
    """Normalize a stored match rating to a float.

    The ``matches.rating`` column is ``TEXT`` and may hold legacy string
    values (e.g. ``"8.5"``), empty strings, ``None``, or unparseable values.
    Returns ``None`` for any value that cannot be read as a number so the
    repository exposes a canonical ``float | None`` to callers.
    """
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _deep_link(jellyfin_url: str | None, media_id: str) -> str:
    """Build the Jellyfin web deep link for ``media_id``.

    Returns ``""`` when no base URL is available.
    """
    return f"{jellyfin_url}/web/#/details?id={media_id}" if jellyfin_url else ""


@dataclass(frozen=True)
class MatchFacts:
    """Immutable canonical match fact set derived from a card or a stored row."""

    media_id: str
    title: str
    thumb: str
    media_type: str
    rating: float | None
    duration: str
    year: str
    deep_link: str

    @classmethod
    def from_card(
        cls, card: dict[str, Any], media_id: str, jellyfin_url: str | None
    ) -> MatchFacts:
        """Derive the fact set from a deck card (write path)."""
        year = card.get("year")
        return cls(
            media_id=media_id,
            title=card.get("title") or "",
            thumb=card.get("thumb") or "",
            media_type=card.get("media_type") or DEFAULT_MEDIA_TYPE,
            rating=parse_rating(card.get("rating")),
            duration=card.get("duration") or "",
            year=str(year) if year is not None else "",
            deep_link=_deep_link(jellyfin_url, media_id),
        )

    @classmethod
    def from_record(cls, record: MatchRecord) -> MatchFacts:
        """Derive the fact set from a stored match row (read path)."""
        return cls(
            media_id=record.movie_id,
            title=record.title,
            thumb=record.thumb,
            media_type=record.media_type or DEFAULT_MEDIA_TYPE,
            rating=parse_rating(record.rating),
            duration=record.duration or "",
            year=record.year or "",
            deep_link=record.deep_link or "",
        )

    def as_insert_row(self) -> dict[str, Any]:
        """Return the derived column values for a new ``matches`` row."""
        return {
            "title": self.title,
            "thumb": self.thumb,
            "deep_link": self.deep_link,
            "rating": self.rating,
            "duration": self.duration,
            "year": self.year,
            "media_type": self.media_type,
        }

    def as_event_payload(self) -> dict[str, Any]:
        """Return the eight-key ``match_found`` event payload (string shapes).

        ``year`` stays a string here, preserving the documented ``""``-when-
        absent sentinel.
        """
        return {
            "media_id": self.media_id,
            "title": self.title,
            "thumb": self.thumb,
            "media_type": self.media_type,
            "rating": self.rating,
            "duration": self.duration,
            "year": self.year,
            "deep_link": self.deep_link,
        }

    def as_response_row(self) -> dict[str, Any]:
        """Return the GET /matches row shape.

        ``year`` is converted explicitly from the stored string to ``int | None``
        instead of relying on Pydantic lax coercion.
        """
        return {
            "title": self.title,
            "thumb": self.thumb,
            "media_id": self.media_id,
            "media_type": self.media_type,
            "deep_link": self.deep_link,
            "rating": self.rating,
            "duration": self.duration,
            "year": self._year_int(),
        }

    def _year_int(self) -> int | None:
        try:
            return int(self.year) if self.year else None
        except (TypeError, ValueError):
            return None
