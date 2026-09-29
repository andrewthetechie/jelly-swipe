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
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from jellyswipe.db_uow import DatabaseUnitOfWork
from jellyswipe.jellyfin.library import ItemResolutionError
from jellyswipe.tmdb import lookup_cast, lookup_trailer

logger = logging.getLogger(__name__)

LookupKind = Literal["found", "miss", "item_unresolved", "upstream_error"]


@dataclass(frozen=True)
class LookupResult:
    """Typed outcome of an enrichment lookup (trailer or cast).

    ``kind`` discriminates the outcome:

    - ``"found"``: a payload is available; ``payload`` holds the response
      body dict. An empty cast is a valid found result.
    - ``"miss"``: TMDB returned nothing or the ``{}`` sentinel was cached —
      a real miss that maps to 404. Only ``fetch_trailer`` produces this
      kind; ``fetch_cast`` has no miss sentinel (an empty cast is found).
    - ``"item_unresolved"``: the item could not be resolved (typed
      ``ItemResolutionError`` was caught).
    - ``"upstream_error"``: an unexpected cache/upstream error; ``exc``
      carries the exception so the router can log it.

    Invariants (enforced in ``__post_init__``): ``payload`` is present
    exactly when ``kind`` is ``"found"``, and ``exc`` is present exactly
    when ``kind`` is ``"upstream_error"``.
    """

    kind: LookupKind
    payload: dict | None = None
    exc: Exception | None = None

    def __post_init__(self) -> None:
        if (self.kind == "found") != (self.payload is not None):
            raise ValueError("payload must be present exactly when kind is 'found'")
        if (self.kind == "upstream_error") != (self.exc is not None):
            raise ValueError(
                "exc must be present exactly when kind is 'upstream_error'"
            )


class EnrichmentProvider(Protocol):
    """Provider seam for enrichment lookups (production: ``JellyfinLibrary``).

    ``resolve_item_for_tmdb`` returns an object exposing ``title`` and
    ``year`` for the TMDB search. Implementations must raise
    ``ItemResolutionError`` when the item cannot be resolved; the service
    maps that to ``kind="item_unresolved"`` (a 404 in the router), while any
    other exception becomes ``kind="upstream_error"``.
    """

    async def resolve_item_for_tmdb(self, media_id: str) -> Any: ...


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
      real miss). Cached dicts are returned directly.
    - ``fetch_cast`` stores the raw cast list (empty ``[]`` is a valid
      result, not a sentinel). On a cache hit a raw-list row (pre-format
      migration) is wrapped for the response while a dict row is returned
      directly.

    Neither method constructs HTTP responses or status codes; the router maps
    the typed result to HTTP.
    """

    async def fetch_trailer(
        self,
        *,
        media_id: str,
        uow: DatabaseUnitOfWork,
        provider: EnrichmentProvider,
        api_token: str,
    ) -> LookupResult:
        """Get the YouTube trailer key for a movie, cache-aside.

        On a cache hit the stored dict is returned as a ``"found"`` result
        (it is already in response shape); a ``{}`` sentinel hit is a
        ``"miss"``. On a miss the item is resolved from the provider and
        ``lookup_trailer`` is called. An empty result stores the sentinel
        ``{}`` and returns ``"miss"``; a normal hit stores and returns
        ``"found"`` with ``{"youtube_key": key}``.

        The caller owns the commit; this method only stages writes via
        ``uow.tmdb_cache.put()``.
        """
        # Step 1: Check cache (TTL enforced by repository, default 7 days).
        # A cache-store or parse failure is an upstream error, not a miss.
        try:
            cached = await uow.tmdb_cache.get(media_id, "trailer")
            if cached:
                cached_data = json.loads(cached.result_json)
                if not cached_data:
                    return LookupResult(kind="miss")
                return LookupResult(kind="found", payload=cached_data)
        except Exception as e:
            return LookupResult(kind="upstream_error", exc=e)

        # Step 2: Cache miss — resolve item and call TMDB
        try:
            item = await provider.resolve_item_for_tmdb(media_id)
            key = lookup_trailer(item.title, item.year, api_token=api_token)
        except ItemResolutionError:
            return LookupResult(kind="item_unresolved")
        except Exception as e:
            return LookupResult(kind="upstream_error", exc=e)

        # Step 3: Empty result — store sentinel so we can distinguish a
        # cached miss from a missing row.
        if not key:
            await uow.tmdb_cache.put(media_id, "trailer", json.dumps({}))
            return LookupResult(kind="miss")

        # Step 4: Store and return the wrapped response.
        wrapped = {"youtube_key": key}
        await uow.tmdb_cache.put(media_id, "trailer", json.dumps(wrapped))
        return LookupResult(kind="found", payload=wrapped)

    async def fetch_cast(
        self,
        *,
        media_id: str,
        uow: DatabaseUnitOfWork,
        provider: EnrichmentProvider,
        api_token: str,
    ) -> LookupResult:
        """Get the cast for a movie, cache-aside.

        An empty cast is a valid result, stored as ``[]`` (never the ``{}``
        sentinel) and returned as a ``"found"`` result with ``{"cast": []}``.
        On a cache hit a raw-list row (old cache format) is wrapped as
        ``{"cast": [...]}`` while a dict row is returned directly.

        Transaction completion is owned by the ``get_db_uow`` request
        boundary; this method only stages writes via ``uow.tmdb_cache.put()``.
        """
        # Step 1: Check cache (TTL enforced by repository, default 7 days).
        # A cache-store or parse failure is an upstream error, not a miss.
        try:
            cached = await uow.tmdb_cache.get(media_id, "cast")
            if cached:
                cached_data = json.loads(cached.result_json)
                # Dicts are already in response shape; raw lists are wrapped.
                if not isinstance(cached_data, dict):
                    return LookupResult(kind="found", payload={"cast": cached_data})
                return LookupResult(kind="found", payload=cached_data)
        except Exception as e:
            return LookupResult(kind="upstream_error", exc=e)

        # Step 2: Cache miss — resolve item and call TMDB
        try:
            item = await provider.resolve_item_for_tmdb(media_id)
            cast = lookup_cast(item.title, item.year, api_token=api_token)
        except ItemResolutionError:
            return LookupResult(kind="item_unresolved")
        except Exception as e:
            return LookupResult(kind="upstream_error", exc=e)

        # Step 3/4: An empty cast is valid — always store the raw list
        # (which may be []) and return the wrapped response.
        await uow.tmdb_cache.put(media_id, "cast", json.dumps(cast))
        return LookupResult(kind="found", payload={"cast": cast})
