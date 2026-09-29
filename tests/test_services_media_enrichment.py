"""Tests for the MediaEnrichmentService named lookups.

Covers fetch_trailer / fetch_cast cache-aside logic: cache hit/miss,
empty/sentinel handling, storage policy, and error handling. Tests target
the named methods (not a parameterized callback interface) and assert both
the typed result and the stored ``result_json`` so that storage policy is
covered directly. The service never constructs HTTP responses and never
commits; it stages writes via ``uow.tmdb_cache.put()``.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jellyswipe.jellyfin.library import ItemResolutionError
from jellyswipe.services.media_enrichment import LookupResult, MediaEnrichmentService

# Patch targets for the TMDB lookup functions owned by the service module.
_TRAILER = "jellyswipe.services.media_enrichment.lookup_trailer"
_CAST = "jellyswipe.services.media_enrichment.lookup_cast"


class TestLookupResultInvariants:
    """LookupResult rejects constructions that violate its kind invariants."""

    def test_found_without_payload_is_rejected(self):
        with pytest.raises(ValueError, match="payload"):
            LookupResult(kind="found")

    def test_non_found_with_payload_is_rejected(self):
        with pytest.raises(ValueError, match="payload"):
            LookupResult(kind="miss", payload={})

    def test_upstream_error_without_exc_is_rejected(self):
        with pytest.raises(ValueError, match="exc"):
            LookupResult(kind="upstream_error")

    def test_non_upstream_error_with_exc_is_rejected(self):
        with pytest.raises(ValueError, match="exc"):
            LookupResult(kind="item_unresolved", exc=Exception("boom"))

    def test_valid_constructions_pass(self):
        assert LookupResult(kind="miss").payload is None
        assert LookupResult(kind="found", payload={"cast": []}).kind == "found"
        result = LookupResult(kind="upstream_error", exc=Exception("db down"))
        assert isinstance(result.exc, Exception)
        assert LookupResult(kind="item_unresolved").kind == "item_unresolved"


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

    def _make_cache_record(self, result_json):
        """Build a mock TmdbCacheRecord."""
        record = MagicMock()
        record.result_json = json.dumps(result_json)
        return record


@pytest.mark.anyio
class TestFetchTrailer(MediaEnrichmentTestBase):
    """Unit tests for MediaEnrichmentService.fetch_trailer()."""

    async def test_cache_hit_returns_found_without_lookup(self):
        """Cache hit returns a found result with the cached dict, no TMDB lookup."""
        service = MediaEnrichmentService()
        uow = self._make_uow(
            cached=self._make_cache_record({"youtube_key": "cached-key"})
        )
        provider = self._make_provider()

        with patch(_TRAILER) as mock_lookup:
            result = await service.fetch_trailer(
                media_id="movie-1",
                uow=uow,
                provider=provider,
                api_token="token",
            )

        assert result.kind == "found"
        assert result.payload == {"youtube_key": "cached-key"}
        mock_lookup.assert_not_called()
        uow.tmdb_cache.put.assert_not_called()

    async def test_cache_hit_empty_sentinel_returns_miss(self):
        """Cache hit with {} sentinel returns a miss result without a lookup."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=self._make_cache_record({}))
        provider = self._make_provider()

        with patch(_TRAILER) as mock_lookup:
            result = await service.fetch_trailer(
                media_id="movie-2",
                uow=uow,
                provider=provider,
                api_token="token",
            )

        assert result.kind == "miss"
        assert result.payload is None
        mock_lookup.assert_not_called()
        uow.tmdb_cache.put.assert_not_called()

    async def test_cache_miss_stores_wrapped_youtube_key(self):
        """Trailer miss calls lookup, stores {"youtube_key": key}, returns found."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=None)
        provider = self._make_provider()

        with patch(_TRAILER, return_value="abc123") as mock_lookup:
            result = await service.fetch_trailer(
                media_id="movie-3",
                uow=uow,
                provider=provider,
                api_token="token",
            )

        assert result.kind == "found"
        assert result.payload == {"youtube_key": "abc123"}
        mock_lookup.assert_called_once_with("Test Movie", 2024, api_token="token")
        put = uow.tmdb_cache.put.call_args
        assert put[0][0] == "movie-3"
        assert put[0][1] == "trailer"
        assert json.loads(put[0][2]) == {"youtube_key": "abc123"}
        uow.session.commit.assert_not_called()

    async def test_cache_miss_no_trailer_stores_empty_sentinel(self):
        """Trailer miss with no key stores {} and returns a miss result."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=None)
        provider = self._make_provider()

        with patch(_TRAILER, return_value=None):
            result = await service.fetch_trailer(
                media_id="movie-4",
                uow=uow,
                provider=provider,
                api_token="token",
            )

        assert result.kind == "miss"
        put = uow.tmdb_cache.put.call_args
        assert json.loads(put[0][2]) == {}

    async def test_item_lookup_error_returns_item_unresolved(self):
        """ItemResolutionError from provider returns an item_unresolved result."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=None)
        provider = self._make_provider()
        provider.resolve_item_for_tmdb.side_effect = ItemResolutionError()

        with patch(_TRAILER) as mock_lookup:
            result = await service.fetch_trailer(
                media_id="movie-5",
                uow=uow,
                provider=provider,
                api_token="token",
            )

        assert result.kind == "item_unresolved"
        mock_lookup.assert_not_called()
        uow.tmdb_cache.put.assert_not_called()

    async def test_generic_exception_returns_upstream_error(self):
        """Generic exception from provider returns an upstream_error result."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=None)
        provider = self._make_provider()
        provider.resolve_item_for_tmdb.side_effect = Exception("network error")

        with patch(_TRAILER) as mock_lookup:
            result = await service.fetch_trailer(
                media_id="movie-6",
                uow=uow,
                provider=provider,
                api_token="token",
            )

        assert result.kind == "upstream_error"
        assert isinstance(result.exc, Exception)
        mock_lookup.assert_not_called()

    async def test_cache_read_failure_returns_upstream_error(self):
        """A cache-store failure on read returns upstream_error, not a miss."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=None)
        uow.tmdb_cache.get = AsyncMock(side_effect=Exception("db down"))
        provider = self._make_provider()

        with patch(_TRAILER) as mock_lookup:
            result = await service.fetch_trailer(
                media_id="movie-cache-err",
                uow=uow,
                provider=provider,
                api_token="token",
            )

        assert result.kind == "upstream_error"
        assert isinstance(result.exc, Exception)
        mock_lookup.assert_not_called()

    async def test_storage_write_failure_propagates(self):
        """A storage-write exception propagates rather than being reclassified."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=None)
        uow.tmdb_cache.put = AsyncMock(side_effect=Exception("db down"))
        provider = self._make_provider()

        with (
            patch(_TRAILER, return_value="abc123"),
            pytest.raises(Exception, match="db down"),
        ):
            await service.fetch_trailer(
                media_id="movie-store-err",
                uow=uow,
                provider=provider,
                api_token="token",
            )


@pytest.mark.anyio
class TestFetchCast(MediaEnrichmentTestBase):
    """Unit tests for MediaEnrichmentService.fetch_cast()."""

    async def test_cache_miss_stores_raw_list(self):
        """Cast miss stores the raw list and returns a found result."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=None)
        provider = self._make_provider()
        cast = [{"name": "Actor", "character": "Role", "profile_path": None}]

        with patch(_CAST, return_value=cast) as mock_lookup:
            result = await service.fetch_cast(
                media_id="movie-7",
                uow=uow,
                provider=provider,
                api_token="token",
            )

        assert result.kind == "found"
        assert result.payload == {"cast": cast}
        mock_lookup.assert_called_once_with("Test Movie", 2024, api_token="token")
        put = uow.tmdb_cache.put.call_args
        assert put[0][0] == "movie-7"
        assert put[0][1] == "cast"
        assert json.loads(put[0][2]) == cast
        uow.session.commit.assert_not_called()

    async def test_empty_cast_stores_raw_empty_list(self):
        """Empty cast stores [] (not the {} sentinel) and returns found."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=None)
        provider = self._make_provider()

        with patch(_CAST, return_value=[]):
            result = await service.fetch_cast(
                media_id="movie-8",
                uow=uow,
                provider=provider,
                api_token="token",
            )

        assert result.kind == "found"
        assert result.payload == {"cast": []}
        put = uow.tmdb_cache.put.call_args
        assert json.loads(put[0][2]) == []

    async def test_cache_hit_old_format_raw_list_wrapped(self):
        """Cast cache hit with old-format raw list is wrapped for the response."""
        service = MediaEnrichmentService()
        raw = [{"name": "Actor", "character": "Role", "profile_path": None}]
        uow = self._make_uow(cached=self._make_cache_record(raw))
        provider = self._make_provider()

        with patch(_CAST) as mock_lookup:
            result = await service.fetch_cast(
                media_id="movie-9",
                uow=uow,
                provider=provider,
                api_token="token",
            )

        assert result.kind == "found"
        assert result.payload == {"cast": raw}
        mock_lookup.assert_not_called()
        uow.tmdb_cache.put.assert_not_called()

    async def test_cache_hit_new_format_dict_returned_directly(self):
        """Cast cache hit with new-format dict is returned directly."""
        service = MediaEnrichmentService()
        new_format = {"cast": [{"name": "Actor"}]}
        uow = self._make_uow(cached=self._make_cache_record(new_format))
        provider = self._make_provider()

        with patch(_CAST) as mock_lookup:
            result = await service.fetch_cast(
                media_id="movie-10",
                uow=uow,
                provider=provider,
                api_token="token",
            )

        assert result.kind == "found"
        assert result.payload == new_format
        mock_lookup.assert_not_called()
        uow.tmdb_cache.put.assert_not_called()

    async def test_item_lookup_error_returns_item_unresolved(self):
        """ItemResolutionError returns an item_unresolved result."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=None)
        provider = self._make_provider()
        provider.resolve_item_for_tmdb.side_effect = ItemResolutionError()

        with patch(_CAST) as mock_lookup:
            result = await service.fetch_cast(
                media_id="movie-11",
                uow=uow,
                provider=provider,
                api_token="token",
            )

        assert result.kind == "item_unresolved"
        mock_lookup.assert_not_called()
        uow.tmdb_cache.put.assert_not_called()

    async def test_generic_exception_returns_upstream_error(self):
        """Generic exception returns an upstream_error result."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=None)
        provider = self._make_provider()
        provider.resolve_item_for_tmdb.side_effect = Exception("network error")

        with patch(_CAST) as mock_lookup:
            result = await service.fetch_cast(
                media_id="movie-12",
                uow=uow,
                provider=provider,
                api_token="token",
            )

        assert result.kind == "upstream_error"
        assert isinstance(result.exc, Exception)
        mock_lookup.assert_not_called()

    async def test_cache_read_failure_returns_upstream_error(self):
        """A cache-store failure on read returns upstream_error."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=None)
        uow.tmdb_cache.get = AsyncMock(side_effect=Exception("db down"))
        provider = self._make_provider()

        with patch(_CAST) as mock_lookup:
            result = await service.fetch_cast(
                media_id="movie-cache-err",
                uow=uow,
                provider=provider,
                api_token="token",
            )

        assert result.kind == "upstream_error"
        assert isinstance(result.exc, Exception)
        mock_lookup.assert_not_called()

    async def test_storage_write_failure_propagates(self):
        """A storage-write exception propagates rather than being reclassified."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=None)
        uow.tmdb_cache.put = AsyncMock(side_effect=Exception("db down"))
        provider = self._make_provider()

        with (
            patch(_CAST, return_value=[{"name": "Actor"}]),
            pytest.raises(Exception, match="db down"),
        ):
            await service.fetch_cast(
                media_id="movie-store-err",
                uow=uow,
                provider=provider,
                api_token="token",
            )
