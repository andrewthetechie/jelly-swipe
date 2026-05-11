"""Unit tests for the pure TMDB lookup module.

Tests cover lookup_trailer and lookup_cast with mocked HTTP calls.
"""

from unittest.mock import Mock

from jellyswipe.tmdb import lookup_trailer, lookup_cast


class TestLookupTrailer:
    """Test suite for lookup_trailer function."""

    def _make_mock_response(self, json_data):
        """Helper to create a mock response object."""
        mock = Mock()
        mock.json.return_value = json_data
        return mock

    def test_successful_lookup_returns_youtube_key(self, mocker):
        """Search returns results, videos returns YouTube trailer → returns key."""
        mock_search = self._make_mock_response(
            {
                "results": [
                    {"id": 12345, "title": "Test Movie", "release_date": "2024-01-01"}
                ]
            }
        )
        mock_videos = self._make_mock_response(
            {
                "results": [
                    {"site": "YouTube", "type": "Trailer", "key": "abc123"},
                    {"site": "YouTube", "type": "Teaser", "key": "xyz789"},
                ]
            }
        )

        mocker.patch(
            "jellyswipe.tmdb.make_http_request",
            side_effect=[mock_search, mock_videos],
        )

        result = lookup_trailer("Test Movie", 2024)
        assert result == "abc123"

    def test_no_tmdb_match_returns_none(self, mocker):
        """Search returns empty results → returns None."""
        mock_search = self._make_mock_response({"results": []})
        mocker.patch("jellyswipe.tmdb.make_http_request", return_value=mock_search)

        result = lookup_trailer("Nonexistent Movie", 2024)
        assert result is None

    def test_no_trailer_found_returns_none(self, mocker):
        """Search returns results, videos returns non-YouTube entries → returns None."""
        mock_search = self._make_mock_response({"results": [{"id": 12345}]})
        mock_videos = self._make_mock_response(
            {
                "results": [
                    {"site": "Vimeo", "type": "Trailer", "key": "vimeo123"},
                    {"site": "YouTube", "type": "Behind the Scenes", "key": "bts456"},
                ]
            }
        )

        mocker.patch(
            "jellyswipe.tmdb.make_http_request",
            side_effect=[mock_search, mock_videos],
        )

        result = lookup_trailer("Test Movie", 2024)
        assert result is None

    def test_network_failure_on_search_returns_none(self, mocker):
        """Search raises exception → returns None."""
        mocker.patch(
            "jellyswipe.tmdb.make_http_request",
            side_effect=Exception("Connection refused"),
        )

        result = lookup_trailer("Test Movie", 2024)
        assert result is None

    def test_network_failure_on_videos_returns_none(self, mocker):
        """Search succeeds, videos raises → returns None."""
        mock_search = self._make_mock_response({"results": [{"id": 12345}]})

        mocker.patch(
            "jellyswipe.tmdb.make_http_request",
            side_effect=[mock_search, Exception("Timeout")],
        )

        result = lookup_trailer("Test Movie", 2024)
        assert result is None

    def test_malformed_response_returns_none(self, mocker):
        """Search returns results without id key → returns None."""
        mock_search = self._make_mock_response(
            {
                "results": [{"title": "Test Movie"}]  # missing "id"
            }
        )
        mocker.patch("jellyswipe.tmdb.make_http_request", return_value=mock_search)

        result = lookup_trailer("Test Movie", 2024)
        assert result is None

    def test_malformed_videos_response_returns_none(self, mocker):
        """Videos response missing results key → returns None."""
        mock_search = self._make_mock_response({"results": [{"id": 12345}]})
        mock_videos = self._make_mock_response({})  # no "results" key

        mocker.patch(
            "jellyswipe.tmdb.make_http_request",
            side_effect=[mock_search, mock_videos],
        )

        result = lookup_trailer("Test Movie", 2024)
        assert result is None


class TestLookupCast:
    """Test suite for lookup_cast function."""

    def _make_mock_response(self, json_data):
        """Helper to create a mock response object."""
        mock = Mock()
        mock.json.return_value = json_data
        return mock

    def test_successful_lookup_returns_cast_list(self, mocker):
        """Search + credits return data → returns list of cast dicts."""
        cast_members = [
            {
                "name": f"Actor {i}",
                "character": f"Character {i}",
                "profile_path": f"/img{i}.jpg",
            }
            for i in range(10)
        ]
        mock_search = self._make_mock_response({"results": [{"id": 12345}]})
        mock_credits = self._make_mock_response({"cast": cast_members})

        mocker.patch(
            "jellyswipe.tmdb.make_http_request",
            side_effect=[mock_search, mock_credits],
        )

        result = lookup_cast("Test Movie", 2024)
        assert len(result) == 8  # capped at 8
        assert result[0] == {
            "name": "Actor 0",
            "character": "Character 0",
            "profile_path": "https://image.tmdb.org/t/p/w185/img0.jpg",
        }

    def test_fewer_than_8_cast_members_returns_all(self, mocker):
        """Returns all available when fewer than 8."""
        cast_members = [
            {"name": "Actor 1", "character": "Lead", "profile_path": "/lead.jpg"},
            {
                "name": "Actor 2",
                "character": "Supporting",
                "profile_path": "/support.jpg",
            },
        ]
        mock_search = self._make_mock_response({"results": [{"id": 12345}]})
        mock_credits = self._make_mock_response({"cast": cast_members})

        mocker.patch(
            "jellyswipe.tmdb.make_http_request",
            side_effect=[mock_search, mock_credits],
        )

        result = lookup_cast("Test Movie", 2024)
        assert len(result) == 2

    def test_no_tmdb_match_returns_empty_list(self, mocker):
        """Search returns empty results → returns []."""
        mock_search = self._make_mock_response({"results": []})
        mocker.patch("jellyswipe.tmdb.make_http_request", return_value=mock_search)

        result = lookup_cast("Nonexistent Movie", 2024)
        assert result == []

    def test_network_failure_returns_empty_list(self, mocker):
        """Search raises exception → returns []."""
        mocker.patch(
            "jellyswipe.tmdb.make_http_request",
            side_effect=Exception("Connection refused"),
        )

        result = lookup_cast("Test Movie", 2024)
        assert result == []

    def test_network_failure_on_credits_returns_empty_list(self, mocker):
        """Search succeeds, credits raises → returns []."""
        mock_search = self._make_mock_response({"results": [{"id": 12345}]})
        mocker.patch(
            "jellyswipe.tmdb.make_http_request",
            side_effect=[mock_search, Exception("Timeout")],
        )

        result = lookup_cast("Test Movie", 2024)
        assert result == []

    def test_malformed_response_returns_empty_list(self, mocker):
        """Credits response missing cast key → returns []."""
        mock_search = self._make_mock_response({"results": [{"id": 12345}]})
        mock_credits = self._make_mock_response({})  # no "cast" key

        mocker.patch(
            "jellyswipe.tmdb.make_http_request",
            side_effect=[mock_search, mock_credits],
        )

        result = lookup_cast("Test Movie", 2024)
        assert result == []

    def test_cast_member_without_profile_path_has_none(self, mocker):
        """Cast member without profile_path → profile_path is None in result."""
        cast_members = [
            {"name": "Actor 1", "character": "Lead"},  # no profile_path
            {"name": "Actor 2", "character": "Supporting", "profile_path": None},
        ]
        mock_search = self._make_mock_response({"results": [{"id": 12345}]})
        mock_credits = self._make_mock_response({"cast": cast_members})

        mocker.patch(
            "jellyswipe.tmdb.make_http_request",
            side_effect=[mock_search, mock_credits],
        )

        result = lookup_cast("Test Movie", 2024)
        assert len(result) == 2
        assert result[0]["profile_path"] is None
        assert result[1]["profile_path"] is None

    def test_cast_member_dict_shape(self, mocker):
        """Verify cast member dict has correct shape: name, character, profile_path."""
        mock_search = self._make_mock_response({"results": [{"id": 12345}]})
        mock_credits = self._make_mock_response(
            {
                "cast": [
                    {
                        "name": "Test Actor",
                        "character": "Test Role",
                        "profile_path": "/test.jpg",
                    }
                ]
            }
        )

        mocker.patch(
            "jellyswipe.tmdb.make_http_request",
            side_effect=[mock_search, mock_credits],
        )

        result = lookup_cast("Test Movie", 2024)
        assert len(result) == 1
        member = result[0]
        assert set(member.keys()) == {"name", "character", "profile_path"}
        assert member["name"] == "Test Actor"
        assert member["character"] == "Test Role"
        assert member["profile_path"] == "https://image.tmdb.org/t/p/w185/test.jpg"
