"""Media-related routes: trailer, cast, genres, and watchlist.

Per D-06, D-07: 4 media routes with TMDB API integration and rate limiting.
"""

import json
import logging

from fastapi import APIRouter, Request, Depends
from jellyswipe import XSSSafeJSONResponse

from jellyswipe.dependencies import (
    require_auth,
    AuthUser,
    check_rate_limit,
    get_provider,
    DBUoW,
)
from jellyswipe.tmdb import lookup_trailer, lookup_cast
from jellyswipe.routers._helpers import make_error_response, log_exception

_logger = logging.getLogger(__name__)

# Create router with no prefix (D-14)
media_router = APIRouter()


@media_router.get("/get-trailer/{movie_id}")
async def get_trailer(
    movie_id: str, request: Request, uow: DBUoW, _: None = Depends(check_rate_limit)
):
    """Get YouTube trailer key for a movie."""
    try:
        # Check cache first
        cached = await uow.tmdb_cache.get(movie_id, "trailer")
        if cached:
            result = json.loads(cached.result_json)
            if result.get("youtube_key"):
                return result
            return make_error_response("Not found", 404, request)

        # Cache miss — resolve item and call TMDB
        item = get_provider().resolve_item_for_tmdb(movie_id)
        youtube_key = lookup_trailer(item.title, item.year)

        if youtube_key:
            result = {"youtube_key": youtube_key}
            await uow.tmdb_cache.put(movie_id, "trailer", json.dumps(result))
            return result

        # No trailer found — cache the miss to avoid repeated lookups
        await uow.tmdb_cache.put(movie_id, "trailer", json.dumps({}))
        return make_error_response("Not found", 404, request)
    except RuntimeError as e:
        if "item lookup failed" in str(e).lower():
            return make_error_response("Movie metadata not found", 404, request)
        log_exception(e, request, logger=_logger)
        return make_error_response("Internal server error", 500, request)
    except Exception as e:
        log_exception(e, request, logger=_logger)
        return make_error_response("Internal server error", 500, request)


@media_router.get("/cast/{movie_id}")
async def get_cast(
    movie_id: str, request: Request, uow: DBUoW, _: None = Depends(check_rate_limit)
):
    """Get cast information for a movie."""
    try:
        # Check cache first
        cached = await uow.tmdb_cache.get(movie_id, "cast")
        if cached:
            return {"cast": json.loads(cached.result_json)}

        # Cache miss — resolve item and call TMDB
        item = get_provider().resolve_item_for_tmdb(movie_id)
        cast = lookup_cast(item.title, item.year)

        # Store in cache (even if empty)
        await uow.tmdb_cache.put(movie_id, "cast", json.dumps(cast))
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


@media_router.get("/genres")
def get_genres(request: Request):
    """Get list of available genres from Jellyfin."""
    try:
        return get_provider().list_genres()
    except Exception:
        return []


@media_router.post("/watchlist/add")
def add_to_watchlist(
    request: Request,
    user: AuthUser = Depends(require_auth),
    _: None = Depends(check_rate_limit),
    body: dict = None,
):
    """Add a movie to the user's watchlist/favorites."""
    try:
        media_id = (body or {}).get("media_id")
        if not media_id:
            return XSSSafeJSONResponse(
                content={"error": "media_id required"}, status_code=400
            )
        get_provider().add_to_user_favorites(user.jf_token, media_id)
        return {"status": "success"}
    except Exception as e:
        log_exception(e, request, logger=_logger)
        return make_error_response("Internal server error", 500, request)
