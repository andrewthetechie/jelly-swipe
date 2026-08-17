"""Shared cache-aside enrichment service for TMDB lookups.

Extracts the duplicated cache-check → fetch → store flow from media route
handlers into a single parameterized service. The service does NOT commit;
the caller owns the commit, consistent with the documented convention that
request-scoped services defer transaction completion to their route callers.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from fastapi import Request

from jellyswipe.db_uow import DatabaseUnitOfWork
from jellyswipe.http_utils import log_exception, make_error_response

if TYPE_CHECKING:
    from jellyswipe import XSSSafeJSONResponse

logger = logging.getLogger(__name__)


def _server_error(
    exc: Exception, request: Request, extra_fields: dict | None
) -> XSSSafeJSONResponse:
    """Log an unexpected exception and build the generic 500 response."""
    log_exception(exc, request, logger=logger)
    return make_error_response(
        "Internal server error", 500, request, extra_fields=extra_fields
    )


class MediaEnrichmentService:
    """Cache-aside service for TMDB enrichment lookups.

    This service does NOT commit the caller's transaction. The caller
    (route handler) is responsible for committing the UoW session after
    the fetch completes, consistent with the documented convention that
    request-scoped services defer transaction completion to their callers.

    Parameterizes the differences between trailer and cast routes:
    - How to check if a result is empty
    - How to wrap the result for the response
    - What shape to store in the cache
    - What to return on empty results
    - Extra fields for error responses

    Storage format: on a miss the service stores
    ``cache_transform(raw_result)`` when a transform is supplied, otherwise
    the response-wrapped value. On a cache hit, stored dicts are returned
    directly (they are already in response shape) while non-dict values
    (e.g. cast rows storing a raw list) are wrapped via ``response_wrapper``.
    Empty results always store the sentinel ``{}`` so that a subsequent
    read can distinguish a cached miss from a missing row.
    """

    async def fetch(
        self,
        *,
        media_id: str,
        lookup_type: str,
        request: Request,
        uow: DatabaseUnitOfWork,
        provider: Any,
        api_token: str,
        fetch_fn: Callable[[str, int | None, str], Any],
        response_wrapper: Callable[[Any], dict],
        empty_response: Callable[[Request], Any],
        is_empty: Callable[[Any], bool] = lambda result: not result,
        cache_transform: Callable[[Any], Any] | None = None,
        error_extra_fields: dict | None = None,
    ) -> dict | XSSSafeJSONResponse:
        """Execute the cache-aside flow for a TMDB enrichment lookup.

        The caller owns the commit. This method stages writes via
        ``uow.tmdb_cache.put()`` but does not commit the transaction.

        Steps:
        1. Check cache (TTL enforced by repository, default 7 days)
        2. On miss: resolve item from Jellyfin, call TMDB via fetch_fn
        3. Cache result, return wrapped response (caller commits)
        4. Handle errors (RuntimeError for lookup failures, generic Exception)

        Args:
            media_id: The media identifier to look up.
            lookup_type: Cache lookup type (e.g. "trailer", "cast").
            request: FastAPI request for error responses and logging.
            uow: Database unit of work.
            provider: Jellyfin provider with resolve_item_for_tmdb method.
            api_token: TMDB API token.
            fetch_fn: Callable(title, year, api_token) returning raw result.
            response_wrapper: Callable wrapping raw result into response dict.
            empty_response: Callable(request) returning error response on empty.
            is_empty: Callable checking if raw result is empty (default: falsy check).
            cache_transform: Optional callable mapping the raw result to the
                value stored in cache. Defaults to storing the wrapped
                response; pass an identity transform to store the raw result.
            error_extra_fields: Extra fields for error responses.

        Returns:
            dict on success, or an error response (XSSSafeJSONResponse) on failure.
        """
        try:
            # Step 1: Check cache
            cached = await uow.tmdb_cache.get(media_id, lookup_type)
            if cached:
                cached_data = json.loads(cached.result_json)
                if is_empty(cached_data):
                    return empty_response(request)
                # Dicts are already in response shape (response_wrapper was
                # applied at storage time). Non-dict values are raw results
                # (e.g. cast rows storing a bare list) and are wrapped now.
                if not isinstance(cached_data, dict):
                    return response_wrapper(cached_data)
                return cached_data

            # Step 2: Cache miss — resolve item and call TMDB
            item = await provider.resolve_item_for_tmdb(media_id)
            raw_result = fetch_fn(item.title, item.year, api_token)

            # Step 3: Check for empty result
            if is_empty(raw_result):
                # Always store the sentinel {} for empty results so a
                # subsequent read can distinguish a cached miss from a
                # missing row.
                await uow.tmdb_cache.put(media_id, lookup_type, json.dumps({}))
                return empty_response(request)

            # Step 4: Cache and return wrapped result
            wrapped = response_wrapper(raw_result)
            storable = cache_transform(raw_result) if cache_transform else wrapped
            await uow.tmdb_cache.put(media_id, lookup_type, json.dumps(storable))
            return wrapped

        except RuntimeError as e:
            if "item lookup failed" in str(e).lower():
                return make_error_response(
                    "Movie metadata not found",
                    404,
                    request,
                    extra_fields=error_extra_fields,
                )
            return _server_error(e, request, error_extra_fields)
        except Exception as e:
            return _server_error(e, request, error_extra_fields)
