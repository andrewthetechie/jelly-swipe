"""Named cache-aside enrichment lookups for TMDB data.

Each named lookup (``fetch_trailer`` / ``fetch_cast``) owns its full
cache-aside flow — cache check, TMDB fetch, miss sentinel, and storage
policy — so sentinel/storage behavior is visible in one place per lookup
rather than being split across callback plumbing in the route handlers.

The service never commits; it stages writes through the unit of work and
leaves transaction completion to the ``get_db_uow`` request boundary, which
commits on success (routes never call ``session.commit()``).
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from fastapi import Request

from jellyswipe.db_uow import DatabaseUnitOfWork
from jellyswipe.http_utils import log_exception, make_error_response
from jellyswipe.tmdb import lookup_cast, lookup_trailer

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

    This service never commits. It stages writes via ``uow.tmdb_cache.put()``
    and transaction completion is owned by the ``get_db_uow`` request
    boundary (which commits on success); route handlers never call
    ``session.commit()``.

    Each public method is a single named lookup with its own storage
    policy:

    - ``fetch_trailer`` stores the wrapped response ``{"youtube_key": key}``
      on a hit and the sentinel ``{}`` on a miss (an empty TMDB result is a
      real miss, returned as 404). Cached dicts are returned directly.
    - ``fetch_cast`` stores the raw cast list (empty ``[]`` is a valid
      result, not a sentinel) and returns ``{"cast": cast}``. On a cache
      hit, a raw-list row (pre-format migration) is wrapped for the
      response while a dict row is returned directly.
    """

    async def fetch_trailer(
        self,
        *,
        media_id: str,
        request: Request,
        uow: DatabaseUnitOfWork,
        provider: Any,
        api_token: str,
    ) -> dict | XSSSafeJSONResponse:
        """Get the YouTube trailer key for a movie, cache-aside.

        On a cache hit the stored dict is returned directly (it is already
        in response shape); a ``{}`` sentinel hit is returned as a 404.
        On a miss the item is resolved from the provider and ``lookup_trailer``
        is called. An empty result stores the sentinel ``{}`` and returns 404;
        a normal hit stores and returns ``{"youtube_key": key}``.

        The caller owns the commit; this method only stages writes via
        ``uow.tmdb_cache.put()``.
        """
        # Step 1: Check cache (TTL enforced by repository, default 7 days)
        cached = await uow.tmdb_cache.get(media_id, "trailer")
        if cached:
            cached_data = json.loads(cached.result_json)
            if not cached_data:
                return make_error_response("Not found", 404, request)
            return cached_data

        # Step 2: Cache miss — resolve item and call TMDB
        try:
            item = await provider.resolve_item_for_tmdb(media_id)
            key = lookup_trailer(item.title, item.year, api_token=api_token)
        except RuntimeError as e:
            if "item lookup failed" in str(e).lower():
                return make_error_response("Movie metadata not found", 404, request)
            return _server_error(e, request, None)
        except Exception as e:
            return _server_error(e, request, None)

        # Step 3: Empty result — store sentinel so we can distinguish a
        # cached miss from a missing row, and return 404.
        if not key:
            await uow.tmdb_cache.put(media_id, "trailer", json.dumps({}))
            return make_error_response("Not found", 404, request)

        # Step 4: Store and return the wrapped response.
        wrapped = {"youtube_key": key}
        await uow.tmdb_cache.put(media_id, "trailer", json.dumps(wrapped))
        return wrapped

    async def fetch_cast(
        self,
        *,
        media_id: str,
        request: Request,
        uow: DatabaseUnitOfWork,
        provider: Any,
        api_token: str,
    ) -> dict | XSSSafeJSONResponse:
        """Get the cast for a movie, cache-aside.

        An empty cast is a valid result, stored as ``[]`` (never the
        ``{}`` sentinel) and returned as ``{"cast": []}``. On a cache hit a
        raw-list row (old cache format) is wrapped as ``{"cast": [...]}``
        while a dict row is returned directly.

        Transaction completion is owned by the ``get_db_uow`` request
        boundary; this method only stages writes via ``uow.tmdb_cache.put()``.
        """
        # Step 1: Check cache (TTL enforced by repository, default 7 days)
        cached = await uow.tmdb_cache.get(media_id, "cast")
        if cached:
            cached_data = json.loads(cached.result_json)
            # Dicts are already in response shape; raw lists are wrapped.
            if not isinstance(cached_data, dict):
                return {"cast": cached_data}
            return cached_data

        # Step 2: Cache miss — resolve item and call TMDB
        try:
            item = await provider.resolve_item_for_tmdb(media_id)
            cast = lookup_cast(item.title, item.year, api_token=api_token)
        except RuntimeError as e:
            if "item lookup failed" in str(e).lower():
                return make_error_response(
                    "Movie metadata not found", 404, request, extra_fields={"cast": []}
                )
            return _server_error(e, request, {"cast": []})
        except Exception as e:
            return _server_error(e, request, {"cast": []})

        # Step 3/4: An empty cast is valid — always store the raw list
        # (which may be []) and return the wrapped response.
        await uow.tmdb_cache.put(media_id, "cast", json.dumps(cast))
        return {"cast": cast}
