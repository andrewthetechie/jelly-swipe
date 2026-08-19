"""Media-related routes: trailer, cast, genres, and watchlist.

Per D-06, D-07: 4 media routes with TMDB API integration and rate limiting.
"""

import logging

from fastapi import APIRouter, Depends, Request

from jellyswipe.config import AppConfig, get_config
from jellyswipe.dependencies import (
    AuthUser,
    DBUoW,
    check_rate_limit,
    get_provider,
    get_watchlist,
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
from jellyswipe.services.media_enrichment import MediaEnrichmentService

_logger = logging.getLogger(__name__)

_enrichment = MediaEnrichmentService()

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
    result = await _enrichment.fetch_trailer(
        media_id=movie_id,
        request=request,
        uow=uow,
        provider=provider,
        api_token=config.tmdb_access_token,
    )
    return result


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
    result = await _enrichment.fetch_cast(
        media_id=movie_id,
        request=request,
        uow=uow,
        provider=provider,
        api_token=config.tmdb_access_token,
    )
    return result


@media_router.get(
    "/genres",
    tags=["Media"],
    response_model=GenreListResponse,
    summary="List available genres",
)
async def get_genres(request: Request, provider=Depends(get_provider)):
    """List all genres available in the connected Jellyfin library.

    Queries Jellyfin directly on each call. Returns an empty array if
    Jellyfin is unreachable rather than surfacing an error, so the frontend
    can always render a genre picker (possibly empty).
    """
    try:
        return await provider.list_genres()
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
async def add_to_watchlist(
    body: WatchlistAddRequest,
    request: Request,
    user: AuthUser = Depends(require_auth),
    _: None = Depends(check_rate_limit),
    writer=Depends(get_watchlist),
):
    """Add a movie to the authenticated user's Jellyfin favourites/watchlist.

    Requires ``media_id`` in the request body. Omitting ``media_id`` or
    sending a malformed body returns ``422``.

    Jellyfin is called asynchronously; any upstream error returns ``500``
    with ``ErrorResponse``.
    """
    try:
        await writer.add_to_favorites(body.media_id)
        return {"status": "success"}
    except Exception as e:
        log_exception(e, request, logger=_logger)
        return make_error_response("Internal server error", 500, request)
