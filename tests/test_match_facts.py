"""Unit tests for the MatchFacts domain module (issue #417)."""

from __future__ import annotations

from dataclasses import dataclass

from jellyswipe.domain.match_facts import (
    DEFAULT_MEDIA_TYPE,
    MatchFacts,
    parse_rating,
)


@dataclass
class _Record:
    movie_id: str = "movie-1"
    title: str = "T"
    thumb: str = "thumb"
    media_type: str | None = "movie"
    rating: object = "8.5"
    duration: str | None = "2h"
    year: str | None = "2024"
    deep_link: str | None = "link"


def _card(**overrides) -> dict:
    card = {
        "id": "movie-1",
        "title": "T",
        "thumb": "thumb",
        "media_type": "movie",
        "rating": "8.5",
        "duration": "2h",
        "year": 2024,
    }
    card.update(overrides)
    return card


class TestFromCard:
    def test_full_card_produces_canonical_facts(self):
        facts = MatchFacts.from_card(_card(), media_id="movie-1", jellyfin_url="http://jf")
        assert facts.media_id == "movie-1"
        assert facts.title == "T"
        assert facts.thumb == "thumb"
        assert facts.media_type == "movie"
        assert facts.rating == 8.5
        assert facts.duration == "2h"
        assert facts.year == "2024"
        assert facts.deep_link == "http://jf/web/#/details?id=movie-1"

    def test_absent_media_type_defaults_to_movie(self):
        card = {k: v for k, v in _card().items() if k != "media_type"}
        facts = MatchFacts.from_card(card, media_id="m", jellyfin_url=None)
        assert facts.media_type == DEFAULT_MEDIA_TYPE

    def test_none_media_type_defaults_to_movie(self):
        facts = MatchFacts.from_card(_card(media_type=None), media_id="m", jellyfin_url=None)
        assert facts.media_type == DEFAULT_MEDIA_TYPE

    def test_empty_media_type_defaults_to_movie(self):
        facts = MatchFacts.from_card(_card(media_type=""), media_id="m", jellyfin_url=None)
        assert facts.media_type == DEFAULT_MEDIA_TYPE

    def test_missing_year_keeps_empty_sentinel(self):
        card = {k: v for k, v in _card().items() if k != "year"}
        facts = MatchFacts.from_card(card, media_id="m", jellyfin_url=None)
        assert facts.year == ""

    def test_none_year_keeps_empty_sentinel(self):
        facts = MatchFacts.from_card(_card(year=None), media_id="m", jellyfin_url=None)
        assert facts.year == ""

    def test_empty_duration_defaults_to_empty_string(self):
        facts = MatchFacts.from_card(_card(duration=""), media_id="m", jellyfin_url=None)
        assert facts.duration == ""

    def test_missing_duration_defaults_to_empty_string(self):
        card = {k: v for k, v in _card().items() if k != "duration"}
        facts = MatchFacts.from_card(card, media_id="m", jellyfin_url=None)
        assert facts.duration == ""

    def test_legacy_string_rating_normalized(self):
        facts = MatchFacts.from_card(_card(rating="8.5"), media_id="m", jellyfin_url=None)
        assert facts.rating == 8.5

    def test_unparseable_rating_returns_none(self):
        facts = MatchFacts.from_card(_card(rating="nope"), media_id="m", jellyfin_url=None)
        assert facts.rating is None

    def test_no_jellyfin_url_yields_empty_deep_link(self):
        facts = MatchFacts.from_card(_card(), media_id="m", jellyfin_url=None)
        assert facts.deep_link == ""


class TestFromRecord:
    def test_record_constructor_copies_canonical_facts(self):
        facts = MatchFacts.from_record(_Record())
        assert facts.media_id == "movie-1"
        assert facts.title == "T"
        assert facts.thumb == "thumb"
        assert facts.media_type == "movie"
        assert facts.rating == 8.5
        assert facts.duration == "2h"
        assert facts.year == "2024"
        assert facts.deep_link == "link"

    def test_falsy_stored_values_default(self):
        facts = MatchFacts.from_record(_Record(media_type="", duration="", year=None))
        assert facts.media_type == DEFAULT_MEDIA_TYPE
        assert facts.duration == ""
        assert facts.year == ""


class TestProjections:
    def test_insert_row_shape(self):
        facts = MatchFacts.from_card(_card(), media_id="movie-1", jellyfin_url="http://jf")
        assert facts.as_insert_row() == {
            "title": "T",
            "thumb": "thumb",
            "deep_link": "http://jf/web/#/details?id=movie-1",
            "rating": 8.5,
            "duration": "2h",
            "year": "2024",
            "media_type": "movie",
        }

    def test_event_payload_keeps_string_year(self):
        facts = MatchFacts.from_card(_card(), media_id="movie-1", jellyfin_url=None)
        payload = facts.as_event_payload()
        assert payload["year"] == "2024"
        assert payload["rating"] == 8.5

    def test_event_payload_keeps_empty_sentinel_for_missing_year(self):
        card = {k: v for k, v in _card().items() if k != "year"}
        facts = MatchFacts.from_card(card, media_id="m", jellyfin_url=None)
        assert facts.as_event_payload()["year"] == ""

    def test_response_row_converts_year_to_int(self):
        facts = MatchFacts.from_card(_card(), media_id="movie-1", jellyfin_url=None)
        row = facts.as_response_row()
        assert row["year"] == 2024

    def test_response_row_year_none_for_empty_sentinel(self):
        card = {k: v for k, v in _card().items() if k != "year"}
        facts = MatchFacts.from_card(card, media_id="m", jellyfin_url=None)
        assert facts.as_response_row()["year"] is None

    def test_response_row_unparseable_year_none(self):
        facts = MatchFacts.from_record(_Record(year="nope"))
        assert facts.as_response_row()["year"] is None

    def test_response_row_shape(self):
        facts = MatchFacts.from_card(_card(), media_id="movie-1", jellyfin_url="http://jf")
        assert facts.as_response_row() == {
            "title": "T",
            "thumb": "thumb",
            "media_id": "movie-1",
            "media_type": "movie",
            "deep_link": "http://jf/web/#/details?id=movie-1",
            "rating": 8.5,
            "duration": "2h",
            "year": 2024,
        }


class TestParseRating:
    def test_none_returns_none(self):
        assert parse_rating(None) is None

    def test_empty_string_returns_none(self):
        assert parse_rating("") is None

    def test_unparseable_returns_none(self):
        assert parse_rating("abc") is None

    def test_legacy_string_float(self):
        assert parse_rating("8.5") == 8.5
