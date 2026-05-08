"""Media-related routes: trailer, cast, genres, and watchlist.

Per D-06, D-07: 4 media routes with TMDB API integration and rate limiting.
"""

import logging
import traceback

from fastapi import APIRouter, Request, Depends, HTTPException
from jellyswipe import XSSSafeJSONResponse
from urllib.parse import urlencode

from jellyswipe.dependencies import require_auth, AuthUser, check_rate_limit, get_provider
from jellyswipe.http_client import make_http_request
from jellyswipe.config import TMDB_AUTH_HEADERS

_logger = logging.getLogger(__name__)

# Create router with no prefix (D-14)
media_router = APIRouter()


def make_error_response(message: str, status_code: int, request: Request, extra_fields: dict = None) -> XSSSafeJSONResponse:
    """Create a standardized error response with request ID tracking."""
    if status_code >= 500:
        message = 'Internal server error'
    body = {'error': message}
    body['request_id'] = getattr(request.state, 'request_id', 'unknown')
    if extra_fields:
        body.update(extra_fields)
    return XSSSafeJSONResponse(content=body, status_code=status_code)


def log_exception(exc: Exception, request: Request, context: dict = None) -> None:
    """Log exception with request context."""
    log_data = {
        'request_id': getattr(request.state, 'request_id', 'unknown'),
        'route': request.url.path,
        'method': request.method,
        'exception_type': type(exc).__name__,
        'exception_message': str(exc),
        'stack_trace': traceback.format_exc(),
    }
    if context:
        log_data.update(context)
    logging.getLogger().error("unhandled_exception", extra=log_data)


@media_router.get('/get-trailer/{movie_id}')
def get_trailer(movie_id: str, request: Request, _: None = Depends(check_rate_limit)):
    """Get YouTube trailer key for a movie."""
    try:
        item = get_provider().resolve_item_for_tmdb(movie_id)
        params = urlencode({'query': item.title, 'year': item.year})
        search_url = f"https://api.themoviedb.org/3/search/movie?{params}"
        search_response = make_http_request(
            method='GET',
            url=search_url,
            headers=TMDB_AUTH_HEADERS,
            timeout=(5, 15)
        )
        r = search_response.json()
        if r.get('results'):
            tmdb_id = r['results'][0]['id']
            v_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/videos"
            videos_response = make_http_request(
                method='GET',
                url=v_url,
                headers=TMDB_AUTH_HEADERS,
                timeout=(5, 15)
            )
            v_res = videos_response.json()
            trailers = [v for v in v_res.get('results', []) if v['site'] == 'YouTube' and v['type'] == 'Trailer']
            if trailers:
                return {'youtube_key': trailers[0]['key']}
        return make_error_response('Not found', 404, request)
    except RuntimeError as e:
        if "item lookup failed" in str(e).lower():
            return make_error_response('Movie metadata not found', 404, request)
        log_exception(e, request)
        return make_error_response('Internal server error', 500, request)
    except Exception as e:
        log_exception(e, request)
        return make_error_response('Internal server error', 500, request)


@media_router.get('/cast/{movie_id}')
def get_cast(movie_id: str, request: Request, _: None = Depends(check_rate_limit)):
    """Get cast information for a movie."""
    try:
        item = get_provider().resolve_item_for_tmdb(movie_id)
        params = urlencode({'query': item.title, 'year': item.year})
        search_url = f"https://api.themoviedb.org/3/search/movie?{params}"
        search_response = make_http_request(
            method='GET',
            url=search_url,
            headers=TMDB_AUTH_HEADERS,
            timeout=(5, 15)
        )
        r = search_response.json()
        if r.get('results'):
            tmdb_id = r['results'][0]['id']
            credits_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/credits"
            credits_response = make_http_request(
                method='GET',
                url=credits_url,
                headers=TMDB_AUTH_HEADERS,
                timeout=(5, 15)
            )
            c_res = credits_response.json()
            cast = []
            for actor in c_res.get('cast', [])[:8]:
                cast.append({
                    'name': actor['name'],
                    'character': actor.get('character', ''),
                    'profile_path': f"https://image.tmdb.org/t/p/w185{actor['profile_path']}" if actor.get('profile_path') else None
                })
            return {'cast': cast}
        return {'cast': []}
    except RuntimeError as e:
        if "item lookup failed" in str(e).lower():
            return make_error_response('Movie metadata not found', 404, request, extra_fields={'cast': []})
        log_exception(e, request)
        return make_error_response('Internal server error', 500, request, extra_fields={'cast': []})
    except Exception as e:
        log_exception(e, request)
        return make_error_response('Internal server error', 500, request, extra_fields={'cast': []})


@media_router.get('/genres')
def get_genres(request: Request):
    """Get list of available genres from Jellyfin."""
    try:
        return get_provider().list_genres()
    except Exception:
        return []


@media_router.post('/watchlist/add')
def add_to_watchlist(request: Request, user: AuthUser = Depends(require_auth), _: None = Depends(check_rate_limit), body: dict = None):
    """Add a movie to the user's watchlist/favorites."""
    try:
        media_id = (body or {}).get('media_id')
        if not media_id:
            return XSSSafeJSONResponse(
                content={'error': 'media_id required'}, status_code=400
            )
        get_provider().add_to_user_favorites(user.jf_token, media_id)
        return {'status': 'success'}
    except Exception as e:
        log_exception(e, request)
        return make_error_response('Internal server error', 500, request)
