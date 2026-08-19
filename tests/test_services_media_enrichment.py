"""Tests for the MediaEnrichmentService named lookups.

Covers fetch_trailer / fetch_cast cache-aside logic: cache hit/miss,
empty/sentinel handling, storage policy, and error handling. Tests target
the named methods (not a parameterized callback interface) and assert both
the returned payload and the stored ``result_json`` so that storage policy
is covered directly.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jellyswipe.services.media_enrichment import MediaEnrichmentService

# Patch targets for the TMDB lookup functions owned by the service module.
_TRAILER = "jellyswipe.services.media_enrichment.lookup_trailer"
_CAST = "jellyswipe.services.media_enrichment.lookup_cast"


@pytest.mark.anyio
class MediaEnrichmentTestBase:
    """Shared mock helpers for the enrichment service tests."""

    def _make_uow(self, cached=None):
        """Build a mock DatabaseUnitOfWork with optional cached result."""
        uow = MagicMock()
        uow.tmdb_cache = AsyncMock()
        uow.tmdb_cache.get = AsyncMock(return_value=cached)
        uow.tmdb_cache.put = AsyncMock()
        uow.session = AsyncMock()
        return uow

    def _make_provider(self, title="Test Movie", year=2024):
        """Build a mock provider that resolves items."""
        provider = MagicMock()
        provider.resolve_item_for_tmdb = AsyncMock(
            return_value=SimpleNamespace(title=title, year=year)
        )
        return provider

    def _make_request(self):
        """Build a mock FastAPI Request."""
        request = MagicMock()
        request.state.request_id = "test-request-id"
        return request

    def _make_cache_record(self, result_json):
        """Build a mock TmdbCacheRecord."""
        record = MagicMock()
        record.result_json = json.dumps(result_json)
        return record


@pytest.mark.anyio
class TestFetchTrailer(MediaEnrichmentTestBase):
    """Unit tests for MediaEnrichmentService.fetch_trailer()."""

    async def test_cache_hit_returns_cached_dict_without_lookup(self):
        """Cache hit returns the wrapped dict directly, no TMDB lookup."""
        service = MediaEnrichmentService()
        uow = self._make_uow(
            cached=self._make_cache_record({"youtube_key": "cached-key"})
        )
        provider = self._make_provider()
        request = self._make_request()

        with patch(_TRAILER) as mock_lookup:
            result = await service.fetch_trailer(
                media_id="movie-1",
                request=request,
                uow=uow,
                provider=provider,
                api_token="token",
            )

        assert result == {"youtube_key": "cached-key"}
        mock_lookup.assert_not_called()
        uow.tmdb_cache.put.assert_not_called()

    async def test_cache_hit_empty_sentinel_returns_404(self):
        """Cache hit with {} sentinel returns 404 without a TMDB lookup."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=self._make_cache_record({}))
        provider = self._make_provider()
        request = self._make_request()

        with patch(_TRAILER) as mock_lookup:
            result = await service.fetch_trailer(
                media_id="movie-2",
                request=request,
                uow=uow,
                provider=provider,
                api_token="token",
            )

        assert result.status_code == 404
        mock_lookup.assert_not_called()
        uow.tmdb_cache.put.assert_not_called()

    async def test_cache_miss_stores_wrapped_youtube_key(self):
        """Trailer miss calls lookup, stores {"youtube_key": key}, returns it."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=None)
        provider = self._make_provider()
        request = self._make_request()

        with patch(_TRAILER, return_value="abc123") as mock_lookup:
            result = await service.fetch_trailer(
                media_id="movie-3",
                request=request,
                uow=uow,
                provider=provider,
                api_token="token",
            )

        assert result == {"youtube_key": "abc123"}
        mock_lookup.assert_called_once_with("Test Movie", 2024, api_token="token")
        put = uow.tmdb_cache.put.call_args
        assert put[0][0] == "movie-3"
        assert put[0][1] == "trailer"
        assert json.loads(put[0][2]) == {"youtube_key": "abc123"}
        uow.session.commit.assert_not_called()

    async def test_cache_miss_no_trailer_stores_empty_sentinel(self):
        """Trailer miss with no key stores {} (not {"youtube_key": null}) and 404s."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=None)
        provider = self._make_provider()
        request = self._make_request()

        with patch(_TRAILER, return_value=None):
            result = await service.fetch_trailer(
                media_id="movie-4",
                request=request,
                uow=uow,
                provider=provider,
                api_token="token",
            )

        assert result.status_code == 404
        put = uow.tmdb_cache.put.call_args
        assert json.loads(put[0][2]) == {}

    async def test_item_lookup_runtime_error_returns_404(self):
        """RuntimeError 'item lookup failed' from provider returns 404."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=None)
        provider = self._make_provider()
        provider.resolve_item_for_tmdb.side_effect = RuntimeError(
            "Jellyfin item lookup failed"
        )
        request = self._make_request()

        with patch(_TRAILER) as mock_lookup:
            result = await service.fetch_trailer(
                media_id="movie-5",
                request=request,
                uow=uow,
                provider=provider,
                api_token="token",
            )

        assert result.status_code == 404
        assert "Movie metadata not found" in result.body.decode()
        mock_lookup.assert_not_called()

    async def test_generic_exception_returns_500(self):
        """Generic exception from provider returns 500."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=None)
        provider = self._make_provider()
        provider.resolve_item_for_tmdb.side_effect = Exception("network error")
        request = self._make_request()

        with patch(_TRAILER) as mock_lookup:
            result = await service.fetch_trailer(
                media_id="movie-6",
                request=request,
                uow=uow,
                provider=provider,
                api_token="token",
            )

        assert result.status_code == 500
        mock_lookup.assert_not_called()

    async def test_cache_read_failure_returns_500(self):
        """A cache-store failure on read returns 500, not a propagated error."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=None)
        uow.tmdb_cache.get = AsyncMock(side_effect=Exception("db down"))
        provider = self._make_provider()
        request = self._make_request()

        with patch(_TRAILER) as mock_lookup:
            result = await service.fetch_trailer(
                media_id="movie-cache-err",
                request=request,
                uow=uow,
                provider=provider,
                api_token="token",
            )

        assert result.status_code == 500
        mock_lookup.assert_not_called()


@pytest.mark.anyio
class TestFetchCast(MediaEnrichmentTestBase):
    """Unit tests for MediaEnrichmentService.fetch_cast()."""

    async def test_cache_miss_stores_raw_list(self):
        """Cast miss stores the raw list and returns {"cast": [...]}."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=None)
        provider = self._make_provider()
        request = self._make_request()
        cast = [{"name": "Actor", "character": "Role", "profile_path": None}]

        with patch(_CAST, return_value=cast) as mock_lookup:
            result = await service.fetch_cast(
                media_id="movie-7",
                request=request,
                uow=uow,
                provider=provider,
                api_token="token",
            )

        assert result == {"cast": cast}
        mock_lookup.assert_called_once_with("Test Movie", 2024, api_token="token")
        put = uow.tmdb_cache.put.call_args
        assert put[0][0] == "movie-7"
        assert put[0][1] == "cast"
        assert json.loads(put[0][2]) == cast
        uow.session.commit.assert_not_called()

    async def test_empty_cast_stores_raw_empty_list(self):
        """Empty cast stores [] (not the {} sentinel) and returns {"cast": []}."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=None)
        provider = self._make_provider()
        request = self._make_request()

        with patch(_CAST, return_value=[]):
            result = await service.fetch_cast(
                media_id="movie-8",
                request=request,
                uow=uow,
                provider=provider,
                api_token="token",
            )

        assert result == {"cast": []}
        put = uow.tmdb_cache.put.call_args
        assert json.loads(put[0][2]) == []

    async def test_cache_hit_old_format_raw_list_wrapped(self):
        """Cast cache hit with old-format raw list is wrapped for the response."""
        service = MediaEnrichmentService()
        raw = [{"name": "Actor", "character": "Role", "profile_path": None}]
        uow = self._make_uow(cached=self._make_cache_record(raw))
        provider = self._make_provider()
        request = self._make_request()

        with patch(_CAST) as mock_lookup:
            result = await service.fetch_cast(
                media_id="movie-9",
                request=request,
                uow=uow,
                provider=provider,
                api_token="token",
            )

        assert result == {"cast": raw}
        mock_lookup.assert_not_called()
        uow.tmdb_cache.put.assert_not_called()

    async def test_cache_hit_new_format_dict_returned_directly(self):
        """Cast cache hit with new-format dict is returned directly."""
        service = MediaEnrichmentService()
        new_format = {"cast": [{"name": "Actor"}]}
        uow = self._make_uow(cached=self._make_cache_record(new_format))
        provider = self._make_provider()
        request = self._make_request()

        with patch(_CAST) as mock_lookup:
            result = await service.fetch_cast(
                media_id="movie-10",
                request=request,
                uow=uow,
                provider=provider,
                api_token="token",
            )

        assert result == new_format
        mock_lookup.assert_not_called()
        uow.tmdb_cache.put.assert_not_called()

    async def test_item_lookup_runtime_error_returns_404_with_empty_cast(self):
        """RuntimeError 'item lookup failed' returns 404 with {"cast": []}."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=None)
        provider = self._make_provider()
        provider.resolve_item_for_tmdb.side_effect = RuntimeError(
            "Jellyfin item lookup failed"
        )
        request = self._make_request()

        with patch(_CAST) as mock_lookup:
            result = await service.fetch_cast(
                media_id="movie-11",
                request=request,
                uow=uow,
                provider=provider,
                api_token="token",
            )

        assert result.status_code == 404
        assert "Movie metadata not found" in result.body.decode()
        assert json.loads(result.body)["cast"] == []
        mock_lookup.assert_not_called()

    async def test_generic_exception_returns_500_with_empty_cast(self):
        """Generic exception returns 500 with {"cast": []} extra field."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=None)
        provider = self._make_provider()
        provider.resolve_item_for_tmdb.side_effect = Exception("network error")
        request = self._make_request()

        with patch(_CAST) as mock_lookup:
            result = await service.fetch_cast(
                media_id="movie-12",
                request=request,
                uow=uow,
                provider=provider,
                api_token="token",
            )

        assert result.status_code == 500
        body = json.loads(result.body)
        assert "Internal server error" in body["error"]
        assert body["cast"] == []
        mock_lookup.assert_not_called()

    async def test_cache_read_failure_returns_500_with_empty_cast(self):
        """A cache-store failure on read returns 500 with {"cast": []}."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=None)
        uow.tmdb_cache.get = AsyncMock(side_effect=Exception("db down"))
        provider = self._make_provider()
        request = self._make_request()

        with patch(_CAST) as mock_lookup:
            result = await service.fetch_cast(
                media_id="movie-cache-err",
                request=request,
                uow=uow,
                provider=provider,
                api_token="token",
            )

        assert result.status_code == 500
        body = json.loads(result.body)
        assert body["cast"] == []
        mock_lookup.assert_not_called()
