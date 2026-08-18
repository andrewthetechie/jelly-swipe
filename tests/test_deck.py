"""Unit tests for the Deck domain module (issue #294)."""

from __future__ import annotations

import json

from jellyswipe.domain.deck import Deck


def _card(media_id: str, title: str = "T", media_type: str = "movie") -> dict:
    return {"id": media_id, "title": title, "media_type": media_type}


def _deck_with_n_cards(n: int) -> Deck:
    cards = [_card(str(i), title=f"Movie {i}") for i in range(n)]
    return Deck.from_cards(cards)


class TestParse:
    def test_parse_round_trip(self):
        cards = [_card("a"), _card("b")]
        deck = Deck.from_cards(cards, cursors={"user-1": 2})
        movie_json, pos_json = deck.serialize()
        parsed = Deck.parse(movie_json, pos_json)
        assert parsed.cards == tuple(cards)
        assert parsed.cursors == {"user-1": 2}

    def test_corrupt_movie_json_treats_as_empty(self):
        deck = Deck.parse("not json {[", '{"user-1": 0}')
        assert deck.cards == ()
        assert deck.cursors == {"user-1": 0}

    def test_non_list_movie_json_treats_as_empty(self):
        deck = Deck.parse('{"a": 1}', None)
        assert deck.cards == ()

    def test_corrupt_position_json_treats_as_empty(self):
        deck = Deck.parse("[]", "not json {[")
        assert deck.cards == ()
        assert deck.cursors == {}

    def test_non_dict_position_json_treats_as_empty(self):
        deck = Deck.parse("[]", "[1, 2, 3]")
        assert deck.cursors == {}

    def test_none_jsons_yield_empty_deck(self):
        deck = Deck.parse(None, None)
        assert deck.cards == ()
        assert deck.cursors == {}

    def test_string_int_cursor_coerced(self):
        deck = Deck.parse("[]", '{"user-1": "3"}')
        assert deck.cursors == {"user-1": 3}

    def test_non_numeric_cursor_coerced_to_zero(self):
        deck = Deck.parse("[]", '{"user-1": "abc"}')
        assert deck.cursors == {"user-1": 0}

    def test_non_dict_entries_filtered_from_cards(self):
        deck = Deck.parse('[{"id": "a"}, "garbage", 5]', None)
        assert deck.cards == ({"id": "a"},)


class TestCursor:
    def test_cursor_for_defaults_to_zero(self):
        deck = _deck_with_n_cards(5)
        assert deck.cursor_for("missing") == 0

    def test_advance_cursor_returns_new_deck(self):
        deck = _deck_with_n_cards(5).add_participant("u1")
        advanced = deck.advance_cursor("u1")
        assert advanced.cursor_for("u1") == 1
        # Original unaffected (immutable)
        assert deck.cursor_for("u1") == 0

    def test_add_participant_preserves_others(self):
        deck = _deck_with_n_cards(5).add_participant("u1")
        deck = deck.advance_cursor("u1").advance_cursor("u1")
        deck = deck.add_participant("u2")
        assert deck.cursor_for("u1") == 2
        assert deck.cursor_for("u2") == 0


class TestPage:
    def test_page_start_at_cursor(self):
        deck = Deck.from_cards(_deck_with_n_cards(45).cards, cursors={"u1": 5})
        page = deck.page("u1", 1)
        assert len(page) == 20
        assert page[0]["media_id"] == "5"
        assert page[-1]["media_id"] == "24"
        assert "id" not in page[0]
        assert page[0]["media_type"] == "movie"

    def test_second_page_offset(self):
        deck = Deck.from_cards(_deck_with_n_cards(45).cards, cursors={"u1": 5})
        page = deck.page("u1", 2)
        assert len(page) == 20
        assert page[0]["media_id"] == "25"

    def test_page_beyond_end_returns_empty(self):
        deck = Deck.from_cards(_deck_with_n_cards(3).cards, cursors={"u1": 2})
        assert deck.page("u1", 3) == []

    def test_default_page_size_is_20(self):
        deck = _deck_with_n_cards(5)
        assert deck.page("u1", 1) == deck.api_cards()
        assert len(deck.page("u1", 1, page_size=2)) == 2


class TestCardLookup:
    def test_card_by_id_returns_card(self):
        deck = Deck.from_cards([_card("abc")])
        assert deck.card_by_id("abc") == {
            "id": "abc",
            "title": "T",
            "media_type": "movie",
        }

    def test_card_by_id_numeric_id_string(self):
        deck = Deck.from_cards([_card("123")])
        assert deck.card_by_id("123")["id"] == "123"
        assert deck.card_by_id("123") is not None

    def test_card_by_id_missing_returns_none(self):
        assert _deck_with_n_cards(3).card_by_id("nope") is None

    def test_card_by_id_returns_raw_card(self):
        deck = Deck.from_cards([{"id": "x"}])
        assert deck.card_by_id("x") == {"id": "x"}

    def test_api_cards_media_type_defaults_to_movie(self):
        deck = Deck.from_cards([{"id": "x"}])
        assert deck.api_cards()[0]["media_type"] == "movie"


class TestSerialize:
    def test_serialize_round_trips(self):
        deck = _deck_with_n_cards(2)
        movie_json, pos_json = deck.serialize()
        assert json.loads(movie_json) == [
            {"id": "0", "title": "Movie 0", "media_type": "movie"},
            {"id": "1", "title": "Movie 1", "media_type": "movie"},
        ]
        assert json.loads(pos_json) == {}
