"""Tests for the MediaEnrichmentService cache-aside logic.

Covers cache hit/miss behavior, empty result handling, and error handling
for the shared enrichment service.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from jellyswipe.services.media_enrichment import MediaEnrichmentService


@pytest.mark.anyio
class TestMediaEnrichmentService:
    """Unit tests for MediaEnrichmentService.fetch()."""

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
        provider.resolve_item_for_tmdb = MagicMock(
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

    async def test_cache_hit_returns_cached_data_without_fetch(self):
        """Cache hit returns cached data without calling fetch_fn."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=self._make_cache_record(["actor1"]))
        provider = self._make_provider()
        request = self._make_request()
        fetch_fn = AsyncMock(return_value=["actor1"])

        result = await service.fetch(
            media_id="test-1",
            lookup_type="cast",
            request=request,
            uow=uow,
            provider=provider,
            api_token="token",
            fetch_fn=fetch_fn,
            response_wrapper=lambda data: {"cast": data},
            empty_response=lambda req: "empty",
        )

        assert result == {"cast": ["actor1"]}
        fetch_fn.assert_not_called()
        uow.tmdb_cache.put.assert_not_called()

    async def test_cache_miss_calls_fetch_stores_and_returns_wrapped(self):
        """Cache miss calls fetch_fn, stores result, returns wrapped response."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=None)
        provider = self._make_provider()
        request = self._make_request()
        fetch_fn = MagicMock(return_value="abc123")

        result = await service.fetch(
            media_id="test-1",
            lookup_type="trailer",
            request=request,
            uow=uow,
            provider=provider,
            api_token="token",
            fetch_fn=fetch_fn,
            response_wrapper=lambda key: {"youtube_key": key},
            empty_response=lambda req: "empty",
        )

        assert result == {"youtube_key": "abc123"}
        fetch_fn.assert_called_once_with("Test Movie", 2024, "token")
        uow.tmdb_cache.put.assert_called_once()
        uow.session.commit.assert_not_called()

    async def test_empty_result_triggers_empty_response_callback(self):
        """Empty result from fetch_fn triggers empty_response callback."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=None)
        provider = self._make_provider()
        request = self._make_request()
        fetch_fn = MagicMock(return_value=None)
        empty_fn = MagicMock(return_value="not-found")

        result = await service.fetch(
            media_id="test-1",
            lookup_type="trailer",
            request=request,
            uow=uow,
            provider=provider,
            api_token="token",
            fetch_fn=fetch_fn,
            response_wrapper=lambda key: {"youtube_key": key},
            empty_response=empty_fn,
        )

        assert result == "not-found"
        empty_fn.assert_called_once_with(request)
        uow.tmdb_cache.put.assert_called_once()
        uow.session.commit.assert_not_called()

    async def test_runtime_error_item_lookup_failed_returns_404(self):
        """RuntimeError with 'item lookup failed' returns 404 with error extras."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=None)
        provider = self._make_provider()
        provider.resolve_item_for_tmdb.side_effect = RuntimeError("item lookup failed")
        request = self._make_request()
        fetch_fn = MagicMock()

        result = await service.fetch(
            media_id="test-1",
            lookup_type="cast",
            request=request,
            uow=uow,
            provider=provider,
            api_token="token",
            fetch_fn=fetch_fn,
            response_wrapper=lambda data: {"cast": data},
            empty_response=lambda req: "empty",
            error_extra_fields={"cast": []},
        )

        assert result.status_code == 404
        assert "Movie metadata not found" in result.body.decode()
        assert "cast" in json.loads(result.body)
        fetch_fn.assert_not_called()

    async def test_generic_exception_returns_500(self):
        """Generic Exception returns 500 with configured error extras."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=None)
        provider = self._make_provider()
        provider.resolve_item_for_tmdb.side_effect = Exception("network error")
        request = self._make_request()
        fetch_fn = MagicMock()

        result = await service.fetch(
            media_id="test-1",
            lookup_type="cast",
            request=request,
            uow=uow,
            provider=provider,
            api_token="token",
            fetch_fn=fetch_fn,
            response_wrapper=lambda data: {"cast": data},
            empty_response=lambda req: "empty",
            error_extra_fields={"cast": []},
        )

        assert result.status_code == 500
        body = json.loads(result.body)
        assert "Internal server error" in body["error"]
        assert body["cast"] == []
        fetch_fn.assert_not_called()

    async def test_cache_hit_empty_triggers_empty_response(self):
        """Empty cached data triggers empty_response callback."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=self._make_cache_record({}))
        provider = self._make_provider()
        request = self._make_request()
        fetch_fn = MagicMock()
        empty_fn = MagicMock(return_value="not-found")

        result = await service.fetch(
            media_id="test-1",
            lookup_type="trailer",
            request=request,
            uow=uow,
            provider=provider,
            api_token="token",
            fetch_fn=fetch_fn,
            response_wrapper=lambda key: {"youtube_key": key},
            empty_response=empty_fn,
        )

        assert result == "not-found"
        empty_fn.assert_called_once_with(request)
        fetch_fn.assert_not_called()
        uow.tmdb_cache.put.assert_not_called()

    async def test_response_wrapper_applied_to_stored_value(self):
        """response_wrapper is applied to the value stored in cache."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=None)
        provider = self._make_provider()
        request = self._make_request()
        fetch_fn = MagicMock(return_value="abc123")

        await service.fetch(
            media_id="test-1",
            lookup_type="trailer",
            request=request,
            uow=uow,
            provider=provider,
            api_token="token",
            fetch_fn=fetch_fn,
            response_wrapper=lambda key: {"youtube_key": key},
            empty_response=lambda req: "empty",
        )

        # Verify the stored value is the wrapped response
        put_call = uow.tmdb_cache.put.call_args
        assert put_call[0][0] == "test-1"
        assert put_call[0][1] == "trailer"
        assert json.loads(put_call[0][2]) == {"youtube_key": "abc123"}

    async def test_cache_hit_returns_wrapped_data_directly(self):
        """Cache hit with wrapped data returns it directly without re-wrapping."""
        service = MediaEnrichmentService()
        # Cache stores wrapped format {"youtube_key": "key"}
        uow = self._make_uow(
            cached=self._make_cache_record({"youtube_key": "cached-key"})
        )
        provider = self._make_provider()
        request = self._make_request()
        fetch_fn = MagicMock()

        result = await service.fetch(
            media_id="test-1",
            lookup_type="trailer",
            request=request,
            uow=uow,
            provider=provider,
            api_token="token",
            fetch_fn=fetch_fn,
            response_wrapper=lambda key: {"youtube_key": key},
            empty_response=lambda req: "empty",
        )

        assert result == {"youtube_key": "cached-key"}
        fetch_fn.assert_not_called()

    # -----------------------------------------------------------------------
    # Real trailer wiring tests — mirror the callbacks from routers/media.py
    # -----------------------------------------------------------------------

    async def test_trailer_cache_miss_stores_wrapped_youtube_key(self):
        """Trailer cache miss stores response_wrapped value {"youtube_key": key}."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=None)
        provider = self._make_provider()
        request = self._make_request()
        fetch_fn = MagicMock(return_value="trailer-abc")

        result = await service.fetch(
            media_id="movie-1",
            lookup_type="trailer",
            request=request,
            uow=uow,
            provider=provider,
            api_token="token",
            fetch_fn=fetch_fn,
            response_wrapper=lambda key: {"youtube_key": key},
            empty_response=lambda req: "not-found",
            is_empty=lambda result: not result,
        )

        assert result == {"youtube_key": "trailer-abc"}
        put_call = uow.tmdb_cache.put.call_args
        assert json.loads(put_call[0][2]) == {"youtube_key": "trailer-abc"}

    async def test_trailer_cache_miss_no_trailer_stores_empty_sentinel(self):
        """Trailer cache miss with no key stores {} (not {"youtube_key": null})."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=None)
        provider = self._make_provider()
        request = self._make_request()
        fetch_fn = MagicMock(return_value=None)

        result = await service.fetch(
            media_id="movie-2",
            lookup_type="trailer",
            request=request,
            uow=uow,
            provider=provider,
            api_token="token",
            fetch_fn=fetch_fn,
            response_wrapper=lambda key: {"youtube_key": key},
            empty_response=lambda req: "not-found",
            is_empty=lambda result: not result,
        )

        assert result == "not-found"
        put_call = uow.tmdb_cache.put.call_args
        assert json.loads(put_call[0][2]) == {}

    async def test_trailer_cache_hit_wrapped_data_returns_directly(self):
        """Trailer cache hit with {"youtube_key": key} returns it directly."""
        service = MediaEnrichmentService()
        uow = self._make_uow(
            cached=self._make_cache_record({"youtube_key": "cached-trailer"})
        )
        provider = self._make_provider()
        request = self._make_request()
        fetch_fn = MagicMock()

        result = await service.fetch(
            media_id="movie-3",
            lookup_type="trailer",
            request=request,
            uow=uow,
            provider=provider,
            api_token="token",
            fetch_fn=fetch_fn,
            response_wrapper=lambda key: {"youtube_key": key},
            empty_response=lambda req: "not-found",
            is_empty=lambda result: not result,
        )

        assert result == {"youtube_key": "cached-trailer"}
        fetch_fn.assert_not_called()
        uow.tmdb_cache.put.assert_not_called()

    async def test_trailer_cache_hit_empty_sentinel_returns_404(self):
        """Trailer cache hit with {} returns 404 without calling fetch_fn."""
        service = MediaEnrichmentService()
        uow = self._make_uow(cached=self._make_cache_record({}))
        provider = self._make_provider()
        request = self._make_request()
        fetch_fn = MagicMock()
        empty_fn = MagicMock(return_value="not-found")

        result = await service.fetch(
            media_id="movie-4",
            lookup_type="trailer",
            request=request,
            uow=uow,
            provider=provider,
            api_token="token",
            fetch_fn=fetch_fn,
            response_wrapper=lambda key: {"youtube_key": key},
            empty_response=empty_fn,
            is_empty=lambda result: not result,
        )

        assert result == "not-found"
        empty_fn.assert_called_once_with(request)
        fetch_fn.assert_not_called()
        uow.tmdb_cache.put.assert_not_called()

    async def test_cast_cache_hit_old_format_wrapped_for_backward_compat(self):
        """Cast cache hit with old-format raw list is wrapped via response_wrapper."""
        service = MediaEnrichmentService()
        # Old-format cast cache row stores raw list (pre-migration)
        uow = self._make_uow(
            cached=self._make_cache_record(
                [{"name": "Actor", "character": "Role", "profile_path": None}]
            )
        )
        provider = self._make_provider()
        request = self._make_request()
        fetch_fn = MagicMock()

        result = await service.fetch(
            media_id="movie-5",
            lookup_type="cast",
            request=request,
            uow=uow,
            provider=provider,
            api_token="token",
            fetch_fn=fetch_fn,
            response_wrapper=lambda cast: {"cast": cast},
            empty_response=lambda req: "not-found",
            is_empty=lambda result: False,
        )

        assert result == {
            "cast": [{"name": "Actor", "character": "Role", "profile_path": None}]
        }
        fetch_fn.assert_not_called()

    async def test_cast_cache_hit_new_format_returned_directly(self):
        """Cast cache hit with new-format wrapped dict is returned directly."""
        service = MediaEnrichmentService()
        # New-format cast cache row stores wrapped dict
        uow = self._make_uow(
            cached=self._make_cache_record(
                {"cast": [{"name": "Actor", "character": "Role", "profile_path": None}]}
            )
        )
        provider = self._make_provider()
        request = self._make_request()
        fetch_fn = MagicMock()

        result = await service.fetch(
            media_id="movie-6",
            lookup_type="cast",
            request=request,
            uow=uow,
            provider=provider,
            api_token="token",
            fetch_fn=fetch_fn,
            response_wrapper=lambda cast: {"cast": cast},
            empty_response=lambda req: "not-found",
            is_empty=lambda result: False,
        )

        assert result == {
            "cast": [{"name": "Actor", "character": "Role", "profile_path": None}]
        }
        fetch_fn.assert_not_called()
