"""Media-related routes: trailer, cast, genres, and watchlist.

Per D-06, D-07: 4 media routes with TMDB API integration and rate limiting.
"""

import json
import logging

from fastapi import APIRouter, Depends, Request
from jellyswipe.config import AppConfig, get_config
from jellyswipe.dependencies import (
    AuthUser,
    DBUoW,
    check_rate_limit,
    get_provider,
    require_auth,
)
from jellyswipe.routers._helpers import log_exception, make_error_response
from jellyswipe.schemas.common import ErrorResponse
from jellyswipe.schemas.media import (
    CastResponse,
    GenreListResponse,
    TrailerResponse,
    WatchlistAddRequest,
    WatchlistAddResponse,
)
from jellyswipe.tmdb import lookup_cast, lookup_trailer

_logger = logging.getLogger(__name__)

# Create router with no prefix (D-14)
media_router = APIRouter()


@media_router.get(
    "/get-trailer/{movie_id}",
    tags=["Media"],
    response_model=TrailerResponse,
    responses={
        404: {
            "model": ErrorResponse,
            "description": "Movie not found in Jellyfin or no trailer exists on TMDB",
        },
        502: {
            "model": ErrorResponse,
            "description": "Upstream failure from TMDB or Jellyfin",
        },
    },
    summary="Get trailer for a movie",
)
async def get_trailer(
    movie_id: str,
    request: Request,
    uow: DBUoW,
    config: AppConfig = Depends(get_config),
    provider=Depends(get_provider),
    _: None = Depends(check_rate_limit),
):
    """Get the YouTube trailer key for a movie.

    Consults the local TMDB cache first. On a cache miss, resolves the item
    from Jellyfin and calls TMDB to look up the trailer.

    **Upstream behaviour:**

    - If Jellyfin cannot resolve the item, returns ``404`` with ``ErrorResponse``.
    - If TMDB returns no trailer, caches the miss and returns ``404``.
    - Any unhandled upstream error returns ``502`` with ``ErrorResponse``; the
      frontend should surface a generic "trailer unavailable" message.
    """
    try:
        # Check cache first
        cached = await uow.tmdb_cache.get(movie_id, "trailer")
        if cached:
            result = json.loads(cached.result_json)
            if result.get("youtube_key"):
                return result
            return make_error_response("Not found", 404, request)

        # Cache miss — resolve item and call TMDB
        item = provider.resolve_item_for_tmdb(movie_id)
        youtube_key = lookup_trailer(
            item.title, item.year, api_token=config.tmdb_access_token
        )

        if youtube_key:
            result = {"youtube_key": youtube_key}
            await uow.tmdb_cache.put(movie_id, "trailer", json.dumps(result))
            await uow.session.commit()
            return result

        # No trailer found — cache the miss to avoid repeated lookups
        await uow.tmdb_cache.put(movie_id, "trailer", json.dumps({}))
        await uow.session.commit()
        return make_error_response("Not found", 404, request)
    except RuntimeError as e:
        if "item lookup failed" in str(e).lower():
            return make_error_response("Movie metadata not found", 404, request)
        log_exception(e, request, logger=_logger)
        return make_error_response("Internal server error", 500, request)
    except Exception as e:
        log_exception(e, request, logger=_logger)
        return make_error_response("Internal server error", 500, request)


@media_router.get(
    "/cast/{movie_id}",
    tags=["Media"],
    response_model=CastResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Movie not found in Jellyfin"},
        502: {
            "model": ErrorResponse,
            "description": "Upstream failure from TMDB or Jellyfin",
        },
    },
    summary="Get cast for a movie",
)
async def get_cast(
    movie_id: str,
    request: Request,
    uow: DBUoW,
    config: AppConfig = Depends(get_config),
    provider=Depends(get_provider),
    _: None = Depends(check_rate_limit),
):
    """Get cast information for a movie.

    Consults the local TMDB cache first. On a cache miss, resolves the item
    from Jellyfin and calls TMDB for cast data.

    **Upstream behaviour:**

    - If Jellyfin cannot resolve the item, returns ``404`` with ``ErrorResponse``
      and an empty ``cast`` list.
    - An empty cast from TMDB is valid and cached; the response will have
      ``cast: []``.
    - Any unhandled upstream error returns ``502`` with ``ErrorResponse`` and
      an empty ``cast`` list.
    """
    try:
        # Check cache first
        cached = await uow.tmdb_cache.get(movie_id, "cast")
        if cached:
            return {"cast": json.loads(cached.result_json)}

        # Cache miss — resolve item and call TMDB
        item = provider.resolve_item_for_tmdb(movie_id)
        cast = lookup_cast(item.title, item.year, api_token=config.tmdb_access_token)

        # Store in cache (even if empty)
        await uow.tmdb_cache.put(movie_id, "cast", json.dumps(cast))
        await uow.session.commit()
        return {"cast": cast}
    except RuntimeError as e:
        if "item lookup failed" in str(e).lower():
            return make_error_response(
                "Movie metadata not found", 404, request, extra_fields={"cast": []}
            )
        log_exception(e, request, logger=_logger)
        return make_error_response(
            "Internal server error", 500, request, extra_fields={"cast": []}
        )
    except Exception as e:
        log_exception(e, request, logger=_logger)
        return make_error_response(
            "Internal server error", 500, request, extra_fields={"cast": []}
        )


@media_router.get(
    "/genres",
    tags=["Media"],
    response_model=GenreListResponse,
    summary="List available genres",
)
def get_genres(request: Request, provider=Depends(get_provider)):
    """List all genres available in the connected Jellyfin library.

    Queries Jellyfin directly on each call. Returns an empty array if
    Jellyfin is unreachable rather than surfacing an error, so the frontend
    can always render a genre picker (possibly empty).
    """
    try:
        return provider.list_genres()
    except Exception:
        return []


@media_router.post(
    "/watchlist/add",
    tags=["Media"],
    response_model=WatchlistAddResponse,
    responses={
        422: {"description": "Validation error — media_id is required"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Add a movie to the watchlist",
)
def add_to_watchlist(
    body: WatchlistAddRequest,
    request: Request,
    user: AuthUser = Depends(require_auth),
    _: None = Depends(check_rate_limit),
    provider=Depends(get_provider),
):
    """Add a movie to the authenticated user's Jellyfin favourites/watchlist.

    Requires ``media_id`` in the request body. Omitting ``media_id`` or
    sending a malformed body returns ``422``.

    Jellyfin is called synchronously; any upstream error returns ``500``
    with ``ErrorResponse``.
    """
    try:
        provider.add_to_user_favorites(user.jf_token, body.media_id)
        return {"status": "success"}
    except Exception as e:
        log_exception(e, request, logger=_logger)
        return make_error_response("Internal server error", 500, request)
