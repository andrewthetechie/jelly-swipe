"""Tests for the pure TMDB module (lookup_trailer, lookup_cast).

Tests cover successful lookups, no-match scenarios, network failures,
and malformed responses. No DB or provider needed.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest
import requests

from jellyswipe.tmdb import TmdbClient, lookup_cast, lookup_trailer


def _ok(payload):
    return httpx.Response(200, json=payload)


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


class TestTmdbClientTrailer:
    """Async TmdbClient.lookup_trailer over httpx.MockTransport."""

    @pytest.mark.anyio
    async def test_successful_trailer_lookup(self):
        """Returns the YouTube key and sends the bearer header on both calls."""
        calls = []

        def handler(request):
            calls.append(request.headers.get("Authorization"))
            if request.url.path == "/3/search/movie":
                return _ok({"results": [{"id": 12345, "title": "Test Movie"}]})
            if request.url.path == "/3/movie/12345/videos":
                return _ok(
                    {
                        "results": [
                            {"site": "YouTube", "type": "Trailer", "key": "abc123"},
                            {"site": "YouTube", "type": "Teaser", "key": "xyz789"},
                        ]
                    }
                )
            raise AssertionError(f"unexpected path {request.url.path}")

        client = TmdbClient("test-token", transport=httpx.MockTransport(handler))

        result = await client.lookup_trailer("Test Movie", 2024)

        assert result == "abc123"
        assert len(calls) == 2
        for auth in calls:
            assert auth == "Bearer test-token"
        assert client._http.timeout.connect == 5.0
        assert client._http.timeout.read == 15.0

    @pytest.mark.anyio
    async def test_no_search_results_returns_none(self):
        """Returns None when the search has no results."""
        def handler(request):
            return _ok({"results": []})

        client = TmdbClient("test-token", transport=httpx.MockTransport(handler))

        result = await client.lookup_trailer("Nonexistent Movie", 2024)

        assert result is None

    @pytest.mark.anyio
    async def test_no_youtube_trailer_returns_none(self):
        """Returns None when the movie has no YouTube trailers."""
        def handler(request):
            if request.url.path == "/3/search/movie":
                return _ok({"results": [{"id": 12345}]})
            if request.url.path == "/3/movie/12345/videos":
                return _ok(
                    {
                        "results": [
                            {"site": "Vimeo", "type": "Trailer", "key": "vimeo123"},
                            {"site": "YouTube", "type": "Teaser", "key": "teaser123"},
                        ]
                    }
                )
            raise AssertionError(f"unexpected path {request.url.path}")

        client = TmdbClient("test-token", transport=httpx.MockTransport(handler))

        result = await client.lookup_trailer("Test Movie", 2024)

        assert result is None

    @pytest.mark.anyio
    async def test_connect_error_returns_none(self):
        """Returns None (not raised) on httpx.ConnectError."""
        def handler(request):
            raise httpx.ConnectError("connection refused")

        client = TmdbClient("test-token", transport=httpx.MockTransport(handler))

        result = await client.lookup_trailer("Test Movie", 2024)

        assert result is None

    @pytest.mark.anyio
    async def test_read_timeout_returns_none(self):
        """Returns None (not raised) on httpx.ReadTimeout."""
        def handler(request):
            raise httpx.ReadTimeout("read timed out")

        client = TmdbClient("test-token", transport=httpx.MockTransport(handler))

        result = await client.lookup_trailer("Test Movie", 2024)

        assert result is None

    @pytest.mark.anyio
    async def test_malformed_response_returns_none(self):
        """Returns None when the response body is not valid JSON."""
        def handler(request):
            return httpx.Response(200, content=b"not json")

        client = TmdbClient("test-token", transport=httpx.MockTransport(handler))

        result = await client.lookup_trailer("Test Movie", 2024)

        assert result is None

    @pytest.mark.anyio
    async def test_year_none_still_works(self):
        """Works when year is None."""
        def handler(request):
            if request.url.path == "/3/search/movie":
                return _ok({"results": [{"id": 12345}]})
            if request.url.path == "/3/movie/12345/videos":
                return _ok(
                    {"results": [{"site": "YouTube", "type": "Trailer", "key": "key123"}]}
                )
            raise AssertionError(f"unexpected path {request.url.path}")

        client = TmdbClient("test-token", transport=httpx.MockTransport(handler))

        result = await client.lookup_trailer("Test Movie", None)

        assert result == "key123"


class TestTmdbClientCast:
    """Async TmdbClient.lookup_cast over httpx.MockTransport."""

    @pytest.mark.anyio
    async def test_successful_cast_lookup(self):
        """Returns cast with profile_path URL and None path, and bearer header."""
        calls = []

        def handler(request):
            calls.append(request.headers.get("Authorization"))
            if request.url.path == "/3/search/movie":
                return _ok({"results": [{"id": 12345}]})
            if request.url.path == "/3/movie/12345/credits":
                return _ok(
                    {
                        "cast": [
                            {"name": "Actor 1", "character": "Role 1", "profile_path": "/img1.jpg"},
                            {"name": "Actor 2", "character": "Role 2", "profile_path": None},
                        ]
                    }
                )
            raise AssertionError(f"unexpected path {request.url.path}")

        client = TmdbClient("test-token", transport=httpx.MockTransport(handler))

        result = await client.lookup_cast("Test Movie", 2024)

        assert len(result) == 2
        assert result[0]["name"] == "Actor 1"
        assert result[0]["character"] == "Role 1"
        assert result[0]["profile_path"] == "https://image.tmdb.org/t/p/w185/img1.jpg"
        assert result[1]["profile_path"] is None
        assert len(calls) == 2
        for auth in calls:
            assert auth == "Bearer test-token"

    @pytest.mark.anyio
    async def test_limits_to_8_cast_members(self):
        """Returns at most 8 cast members."""
        def handler(request):
            if request.url.path == "/3/search/movie":
                return _ok({"results": [{"id": 12345}]})
            if request.url.path == "/3/movie/12345/credits":
                return _ok(
                    {
                        "cast": [
                            {"name": f"Actor {i}", "character": f"Role {i}", "profile_path": None}
                            for i in range(15)
                        ]
                    }
                )
            raise AssertionError(f"unexpected path {request.url.path}")

        client = TmdbClient("test-token", transport=httpx.MockTransport(handler))

        result = await client.lookup_cast("Test Movie", 2024)

        assert len(result) == 8

    @pytest.mark.anyio
    async def test_missing_character_defaults_to_empty_string(self):
        """Missing character field defaults to empty string."""
        def handler(request):
            if request.url.path == "/3/search/movie":
                return _ok({"results": [{"id": 12345}]})
            if request.url.path == "/3/movie/12345/credits":
                return _ok({"cast": [{"name": "Actor 1", "profile_path": None}]})
            raise AssertionError(f"unexpected path {request.url.path}")

        client = TmdbClient("test-token", transport=httpx.MockTransport(handler))

        result = await client.lookup_cast("Test Movie", 2024)

        assert result[0]["character"] == ""

    @pytest.mark.anyio
    async def test_no_search_results_returns_empty(self):
        """Returns [] when the search has no results."""
        def handler(request):
            return _ok({"results": []})

        client = TmdbClient("test-token", transport=httpx.MockTransport(handler))

        result = await client.lookup_cast("Nonexistent Movie", 2024)

        assert result == []

    @pytest.mark.anyio
    async def test_empty_cast_list_returns_empty(self):
        """Returns [] when the movie has no cast."""
        def handler(request):
            if request.url.path == "/3/search/movie":
                return _ok({"results": [{"id": 12345}]})
            if request.url.path == "/3/movie/12345/credits":
                return _ok({"cast": []})
            raise AssertionError(f"unexpected path {request.url.path}")

        client = TmdbClient("test-token", transport=httpx.MockTransport(handler))

        result = await client.lookup_cast("Test Movie", 2024)

        assert result == []

    @pytest.mark.anyio
    async def test_read_timeout_returns_empty(self):
        """Returns [] (not raised) on httpx.ReadTimeout."""
        def handler(request):
            raise httpx.ReadTimeout("read timed out")

        client = TmdbClient("test-token", transport=httpx.MockTransport(handler))

        result = await client.lookup_cast("Test Movie", 2024)

        assert result == []
