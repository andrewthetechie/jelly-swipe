"""Tests for the pure TMDB module (lookup_trailer, lookup_cast).

Tests cover successful lookups, no-match scenarios, network failures,
and malformed responses. No DB or provider needed.
"""

from unittest.mock import patch, MagicMock

import requests

from jellyswipe.tmdb import lookup_trailer, lookup_cast


class TestLookupTrailer:
    """Tests for lookup_trailer function."""

    def test_successful_trailer_lookup(self):
        """Returns YouTube key when trailer is found."""
        search_response = MagicMock()
        search_response.json.return_value = {
            "results": [{"id": 12345, "title": "Test Movie"}]
        }

        videos_response = MagicMock()
        videos_response.json.return_value = {
            "results": [
                {"site": "YouTube", "type": "Trailer", "key": "abc123"},
                {"site": "YouTube", "type": "Teaser", "key": "xyz789"},
            ]
        }

        with patch("jellyswipe.tmdb.make_http_request") as mock_http:
            mock_http.side_effect = [search_response, videos_response]
            result = lookup_trailer("Test Movie", 2024, api_token="test-token")

        assert result == "abc123"
        assert mock_http.call_count == 2

    def test_no_search_results_returns_none(self):
        """Returns None when TMDB search has no results."""
        search_response = MagicMock()
        search_response.json.return_value = {"results": []}

        with patch("jellyswipe.tmdb.make_http_request") as mock_http:
            mock_http.return_value = search_response
            result = lookup_trailer("Nonexistent Movie", 2024, api_token="test-token")

        assert result is None

    def test_no_trailer_videos_returns_none(self):
        """Returns None when movie has no YouTube trailers."""
        search_response = MagicMock()
        search_response.json.return_value = {
            "results": [{"id": 12345, "title": "Test Movie"}]
        }

        videos_response = MagicMock()
        videos_response.json.return_value = {
            "results": [
                {"site": "Vimeo", "type": "Trailer", "key": "vimeo123"},
                {"site": "YouTube", "type": "Teaser", "key": "teaser123"},
            ]
        }

        with patch("jellyswipe.tmdb.make_http_request") as mock_http:
            mock_http.side_effect = [search_response, videos_response]
            result = lookup_trailer("Test Movie", 2024, api_token="test-token")

        assert result is None

    def test_network_failure_returns_none(self):
        """Returns None on network error."""
        with patch("jellyswipe.tmdb.make_http_request") as mock_http:
            mock_http.side_effect = requests.exceptions.ConnectionError(
                "Connection refused"
            )
            result = lookup_trailer("Test Movie", 2024, api_token="test-token")

        assert result is None

    def test_malformed_search_response_returns_none(self):
        """Returns None when search response is malformed."""
        search_response = MagicMock()
        search_response.json.return_value = {"unexpected": "format"}

        with patch("jellyswipe.tmdb.make_http_request") as mock_http:
            mock_http.return_value = search_response
            result = lookup_trailer("Test Movie", 2024, api_token="test-token")

        assert result is None

    def test_year_none_still_works(self):
        """Works when year is None."""
        search_response = MagicMock()
        search_response.json.return_value = {
            "results": [{"id": 12345, "title": "Test Movie"}]
        }

        videos_response = MagicMock()
        videos_response.json.return_value = {
            "results": [{"site": "YouTube", "type": "Trailer", "key": "key123"}]
        }

        with patch("jellyswipe.tmdb.make_http_request") as mock_http:
            mock_http.side_effect = [search_response, videos_response]
            result = lookup_trailer("Test Movie", None, api_token="test-token")

        assert result == "key123"


class TestLookupCast:
    """Tests for lookup_cast function."""

    def test_successful_cast_lookup(self):
        """Returns cast list when found."""
        search_response = MagicMock()
        search_response.json.return_value = {
            "results": [{"id": 12345, "title": "Test Movie"}]
        }

        credits_response = MagicMock()
        credits_response.json.return_value = {
            "cast": [
                {"name": "Actor 1", "character": "Role 1", "profile_path": "/img1.jpg"},
                {"name": "Actor 2", "character": "Role 2", "profile_path": None},
            ]
        }

        with patch("jellyswipe.tmdb.make_http_request") as mock_http:
            mock_http.side_effect = [search_response, credits_response]
            result = lookup_cast("Test Movie", 2024, api_token="test-token")

        assert len(result) == 2
        assert result[0]["name"] == "Actor 1"
        assert result[0]["character"] == "Role 1"
        assert result[0]["profile_path"] == "https://image.tmdb.org/t/p/w185/img1.jpg"
        assert result[1]["profile_path"] is None

    def test_no_search_results_returns_empty(self):
        """Returns [] when TMDB search has no results."""
        search_response = MagicMock()
        search_response.json.return_value = {"results": []}

        with patch("jellyswipe.tmdb.make_http_request") as mock_http:
            mock_http.return_value = search_response
            result = lookup_cast("Nonexistent Movie", 2024, api_token="test-token")

        assert result == []

    def test_network_failure_returns_empty(self):
        """Returns [] on network error."""
        with patch("jellyswipe.tmdb.make_http_request") as mock_http:
            mock_http.side_effect = requests.exceptions.Timeout("Request timed out")
            result = lookup_cast("Test Movie", 2024, api_token="test-token")

        assert result == []

    def test_limits_to_8_cast_members(self):
        """Returns at most 8 cast members."""
        search_response = MagicMock()
        search_response.json.return_value = {
            "results": [{"id": 12345, "title": "Test Movie"}]
        }

        credits_response = MagicMock()
        credits_response.json.return_value = {
            "cast": [
                {"name": f"Actor {i}", "character": f"Role {i}", "profile_path": None}
                for i in range(15)
            ]
        }

        with patch("jellyswipe.tmdb.make_http_request") as mock_http:
            mock_http.side_effect = [search_response, credits_response]
            result = lookup_cast("Test Movie", 2024, api_token="test-token")

        assert len(result) == 8

    def test_missing_character_defaults_to_empty_string(self):
        """Missing character field defaults to empty string."""
        search_response = MagicMock()
        search_response.json.return_value = {
            "results": [{"id": 12345, "title": "Test Movie"}]
        }

        credits_response = MagicMock()
        credits_response.json.return_value = {
            "cast": [{"name": "Actor 1", "profile_path": None}]
        }

        with patch("jellyswipe.tmdb.make_http_request") as mock_http:
            mock_http.side_effect = [search_response, credits_response]
            result = lookup_cast("Test Movie", 2024, api_token="test-token")

        assert result[0]["character"] == ""

    def test_empty_cast_list_returns_empty(self):
        """Returns [] when movie has no cast."""
        search_response = MagicMock()
        search_response.json.return_value = {
            "results": [{"id": 12345, "title": "Test Movie"}]
        }

        credits_response = MagicMock()
        credits_response.json.return_value = {"cast": []}

        with patch("jellyswipe.tmdb.make_http_request") as mock_http:
            mock_http.side_effect = [search_response, credits_response]
            result = lookup_cast("Test Movie", 2024, api_token="test-token")

        assert result == []
