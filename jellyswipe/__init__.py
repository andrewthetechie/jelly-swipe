from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.templating import Jinja2Templates
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from contextlib import asynccontextmanager
from typing import Dict, Optional, Tuple
import typing
import hashlib
import logging
import traceback
import sqlite3, os, random, re, json, secrets, time
import requests

from jellyswipe.http_client import make_http_request
from jellyswipe.rate_limiter import rate_limiter as _rate_limiter
from jellyswipe.ssrf_validator import validate_jellyfin_url

_RATE_LIMITS = {
    'get-trailer': 200,
    'cast': 200,
    'watchlist/add': 300,
    'proxy': 200,
}

_logger = logging.getLogger(__name__)


def generate_request_id() -> str:
    return f"req_{int(time.time())}_{secrets.token_hex(4)}"


# Default: repo ./data/jellyswipe.db (local dev). Docker: set DB_PATH=/app/data/jellyswipe.db or keep default when WORKDIR is /app.
_APP_ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.abspath(
    os.getenv("DB_PATH", os.path.join(_APP_ROOT, "..", "data", "jellyswipe.db"))
)
CLIENT_ID = 'JellySwipe-AndrewTheTechie-2026'

# Validate required environment variables
missing = []
for v in ("TMDB_ACCESS_TOKEN", "FLASK_SECRET"):
    if not os.getenv(v):
        missing.append(v)

if not os.getenv("JELLYFIN_URL", "").strip():
    missing.append("JELLYFIN_URL")
has_api = bool(os.getenv("JELLYFIN_API_KEY", "").strip())
has_user_pass = bool(os.getenv("JELLYFIN_USERNAME", "").strip()) and bool(
    os.getenv("JELLYFIN_PASSWORD", "").strip()
)
if not has_api and not has_user_pass:
    missing.append(
        "JELLYFIN_API_KEY or (JELLYFIN_USERNAME and JELLYFIN_PASSWORD)"
    )

if missing:
    raise RuntimeError(f"Missing env vars: {missing}")

# SSRF protection: validate JELLYFIN_URL at boot (per D-06)
validate_jellyfin_url(os.getenv("JELLYFIN_URL"))

# Direct Jellyfin provider instantiation (no factory pattern)
from .jellyfin_library import JellyfinLibraryProvider

_provider_singleton: Optional[JellyfinLibraryProvider] = None
TOKEN_USER_ID_CACHE_TTL_SECONDS = 300
_token_user_id_cache: Dict[str, Tuple[str, float]] = {}
IDENTITY_ALIAS_HEADERS = (
    "X-Provider-User-Id",
    "X-Jellyfin-User-Id",
    "X-Emby-UserId",
)

from jellyswipe.auth import create_session, destroy_session


class XSSSafeJSONResponse(JSONResponse):
    """JSON response that escapes HTML-sensitive characters for XSS defense.

    Per OWASP recommendation, < > & are encoded as \\u003c \\u003e \\u0026
    in JSON output so that raw HTTP bodies cannot contain executable HTML tags.
    JSON parsers correctly decode these back to the original characters.
    """

    def render(self, content: typing.Any) -> bytes:
        result = super().render(content)
        return (result
                .replace(b"<", b"\\u003c")
                .replace(b">", b"\\u003e")
                .replace(b"&", b"\\u0026"))


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Middleware that generates a unique request ID and adds security headers.

    Per D-07: generates req_{unix_ts}_{4-byte hex} ID, stores in request.state.request_id,
    and injects X-Request-Id response header.
    Per D-08: also adds Content-Security-Policy header to all responses.
    """

    CSP_POLICY = (
        "default-src 'self'; "
        "script-src 'self'; "
        "object-src 'none'; "
        "img-src 'self' https://image.tmdb.org; "
        "frame-src https://www.youtube.com"
    )

    async def dispatch(self, request: Request, call_next):
        request.state.request_id = generate_request_id()
        response = await call_next(request)
        response.headers['X-Request-Id'] = request.state.request_id
        response.headers['Content-Security-Policy'] = self.CSP_POLICY
        return response


def _get_cursor(conn, code, user_id):
    """Get user's deck cursor position. Returns 0 if no position stored."""
    room = conn.execute('SELECT deck_position FROM rooms WHERE pairing_code = ?', (code,)).fetchone()
    if room and room['deck_position']:
        positions = json.loads(room['deck_position'])
        return positions.get(user_id, 0)
    return 0


def _set_cursor(conn, code, user_id, position):
    """Set user's deck cursor position."""
    room = conn.execute('SELECT deck_position FROM rooms WHERE pairing_code = ?', (code,)).fetchone()
    positions = json.loads(room['deck_position']) if room and room['deck_position'] else {}
    positions[user_id] = position
    conn.execute('UPDATE rooms SET deck_position = ? WHERE pairing_code = ?',
                 (json.dumps(positions), code))


def _resolve_movie_meta(movie_data_json, movie_id):
    """Resolve rating, duration, year from stored movie_data JSON (per D-09, D-10)."""
    try:
        movies = json.loads(movie_data_json)
        for m in movies:
            if str(m.get('id', '')) == str(movie_id):
                rating = m.get('rating')
                duration = m.get('duration')
                year = m.get('year')
                return {
                    'rating': str(rating) if rating is not None else '',
                    'duration': duration or '',
                    'year': str(year) if year is not None else '',
                }
    except (json.JSONDecodeError, TypeError):
        pass
    return {'rating': '', 'duration': '', 'year': ''}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    import jellyswipe.db
    jellyswipe.db.DB_PATH = DB_PATH  # set before init
    from .db import init_db
    init_db()
    _logger.info("jellyswipe_startup")
    yield
    # Teardown
    global _provider_singleton
    _provider_singleton = None
    _logger.info("jellyswipe_shutdown")


def create_app(test_config=None):
    """
    Create and configure a FastAPI application instance.

    Args:
        test_config: Optional dictionary of test configuration to override defaults.
                     If provided, DB_PATH will be overridden before database initialization.

    Returns:
        A configured FastAPI application instance.
    """
    app = FastAPI(
        lifespan=lifespan,
        default_response_class=XSSSafeJSONResponse,
    )

    # Middleware stack — add in LIFO order (last added = outermost):
    # 1. RequestIdMiddleware (innermost — sees request after session decoded)
    # 2. SessionMiddleware (middle)
    # 3. ProxyHeadersMiddleware (outermost — rewrites X-Forwarded first)

    # Add 1st: RequestIdMiddleware (innermost in request processing)
    app.add_middleware(RequestIdMiddleware)

    # Add 2nd: SessionMiddleware
    app.add_middleware(
        SessionMiddleware,
        secret_key=os.environ["FLASK_SECRET"],
        max_age=14 * 24 * 60 * 60,  # 14 days per D-05
        same_site="lax",
        https_only=os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true',
    )

    # Add 3rd: ProxyHeadersMiddleware (outermost) per D-04
    app.add_middleware(ProxyHeadersMiddleware)

    # Config (accessible via module-level variables)
    JELLYFIN_URL = os.getenv("JELLYFIN_URL", "").rstrip("/")
    TMDB_AUTH_HEADERS = {"Authorization": f"Bearer {os.getenv('TMDB_ACCESS_TOKEN')}"}

    # Test config override
    if test_config:
        if 'DB_PATH' in test_config:
            import jellyswipe.db
            jellyswipe.db.DB_PATH = test_config['DB_PATH']

    # Templates
    templates = Jinja2Templates(directory=os.path.join(_APP_ROOT, 'templates'))

    # Provider factory (module-level singleton stays)
    def get_provider() -> JellyfinLibraryProvider:
        """Get or create the JellyfinLibraryProvider singleton."""
        global _provider_singleton
        if _provider_singleton is None:
            _provider_singleton = JellyfinLibraryProvider(JELLYFIN_URL)
        return _provider_singleton

    from .db import get_db, get_db_closing

    def _check_rate_limit(endpoint: str, req: Request) -> Optional[Tuple[dict, int]]:
        """Check rate limit. Returns (error_body, status) tuple if limited, None otherwise."""
        allowed, retry_after = _rate_limiter.check(
            endpoint,
            req.client.host if req.client else "unknown",
            _RATE_LIMITS[endpoint]
        )
        if not allowed:
            _logger.warning("rate_limit_exceeded", extra={
                'endpoint': endpoint,
                'ip': req.client.host if req.client else "unknown",
                'retry_after': retry_after,
            })
            return {'error': 'Rate limit exceeded', 'request_id': getattr(req.state, 'request_id', 'unknown')}, 429
        return None

    def make_error_response(message: str, status_code: int, request: Request, extra_fields: dict = None) -> JSONResponse:
        if status_code >= 500:
            message = 'Internal server error'
        body = {'error': message}
        body['request_id'] = getattr(request.state, 'request_id', 'unknown')
        if extra_fields:
            body.update(extra_fields)
        return JSONResponse(content=body, status_code=status_code)

    def log_exception(exc: Exception, request: Request, context: dict = None) -> None:
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
        _logger.error(
            "unhandled_exception",
            extra=log_data
        )

    def _require_login(request: Request):
        """Phase 31 bridge: replaces @login_required. Phase 32 replaces with Depends(require_auth)."""
        sid = request.session.get('session_id')
        if not sid:
            raise HTTPException(status_code=401, detail='Authentication required')
        with get_db_closing() as conn:
            row = conn.execute(
                'SELECT jellyfin_token, jellyfin_user_id FROM user_tokens WHERE session_id = ?',
                (sid,)
            ).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail='Authentication required')
        request.state.jf_token = row['jellyfin_token']
        request.state.user_id = row['jellyfin_user_id']

    def _jellyfin_user_token_from_request(request: Request) -> str:
        if request.session.get("jf_delegate_server_identity"):
            prov = get_provider()
            try:
                return prov.server_access_token_for_delegate()
            except RuntimeError:
                return ""
        auth_header = request.headers.get("Authorization", "")
        token = None
        if auth_header:
            try:
                token = get_provider().extract_media_browser_token(auth_header)
            except Exception:
                token = None
        return token or ""

    def _request_has_identity_alias_headers(request: Request) -> bool:
        for header in IDENTITY_ALIAS_HEADERS:
            if request.headers.get(header):
                return True
        return False

    def _set_identity_rejection_reason(request: Request, reason: str) -> None:
        request.state.identity_rejected = reason

    def _identity_rejection_reason(request: Request) -> Optional[str]:
        value = getattr(request.state, "identity_rejected", None)
        return str(value) if value else None

    def _token_cache_key(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _resolve_user_id_from_token_cached(token: str) -> Optional[str]:
        now = time.time()
        cache_key = _token_cache_key(token)
        cached = _token_user_id_cache.get(cache_key)
        if cached:
            user_id, expires_at = cached
            if expires_at > now:
                return user_id
            _token_user_id_cache.pop(cache_key, None)

        try:
            user_id = get_provider().resolve_user_id_from_token(token)
        except Exception:
            return None

        _token_user_id_cache[cache_key] = (
            user_id,
            now + TOKEN_USER_ID_CACHE_TTL_SECONDS,
        )
        return user_id

    def _provider_user_id_from_request(request: Request):
        if request.session.get("jf_delegate_server_identity"):
            prov = get_provider()
            try:
                return prov.server_primary_user_id_for_delegate()
            except RuntimeError:
                pass
        if _request_has_identity_alias_headers(request):
            _set_identity_rejection_reason(request, "spoofed_alias_header")
            return None

        token = _jellyfin_user_token_from_request(request)
        if not token:
            return None
        user_id = _resolve_user_id_from_token_cached(token)
        if user_id:
            return user_id
        _set_identity_rejection_reason(request, "token_resolution_failed")
        return None

    @app.get('/')
    def index(request: Request):
        return templates.TemplateResponse('index.html', {"request": request, "media_provider": "jellyfin"})

    @app.get('/get-trailer/{movie_id}')
    def get_trailer(movie_id: str, request: Request):
        rl = _check_rate_limit('get-trailer', request)
        if rl:
            return JSONResponse(content=rl[0], status_code=rl[1])
        try:
            item = get_provider().resolve_item_for_tmdb(movie_id)
            search_url = f"https://api.themoviedb.org/3/search/movie?query={item.title}&year={item.year}"
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

    @app.get('/cast/{movie_id}')
    def get_cast(movie_id: str, request: Request):
        rl = _check_rate_limit('cast', request)
        if rl:
            return JSONResponse(content=rl[0], status_code=rl[1])
        try:
            item = get_provider().resolve_item_for_tmdb(movie_id)
            search_url = f"https://api.themoviedb.org/3/search/movie?query={item.title}&year={item.year}"
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

    @app.post('/watchlist/add')
    def add_to_watchlist(request: Request, body: dict = None):
        _require_login(request)
        rl = _check_rate_limit('watchlist/add', request)
        if rl:
            return JSONResponse(content=rl[0], status_code=rl[1])
        try:
            movie_id = (body or {}).get('movie_id')
            get_provider().add_to_user_favorites(request.state.jf_token, movie_id)
            return {'status': 'success'}
        except Exception as e:
            log_exception(e, request)
            return make_error_response('Internal server error', 500, request)

    @app.get('/auth/provider')
    def auth_provider(request: Request):
        payload = {"provider": "jellyfin", "jellyfin_browser_auth": "delegate"}
        return payload

    @app.post("/auth/jellyfin-use-server-identity")
    def jellyfin_use_server_identity(request: Request):
        prov = get_provider()
        try:
            token = prov.server_access_token_for_delegate()
            uid = prov.server_primary_user_id_for_delegate()
        except RuntimeError:
            return make_error_response("Jellyfin delegate unavailable", 401, request)
        create_session(token, uid, request.session)
        return {"userId": uid}

    @app.post('/auth/jellyfin-login')
    async def jellyfin_login(request: Request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        username = (data.get("username") or "").strip()
        password = (data.get("password") or "").strip()
        if not username or not password:
            return JSONResponse(content={"error": "Username and password are required"}, status_code=400)
        try:
            out = get_provider().authenticate_user_session(username, password)
            create_session(out["token"], out["user_id"], request.session)
            return {"userId": out["user_id"]}
        except Exception:
            return make_error_response("Jellyfin login failed", 401, request)

    @app.post('/auth/logout')
    def logout(request: Request):
        _require_login(request)
        destroy_session(request.session)
        return {'status': 'logged_out'}

    @app.get('/me')
    def get_me(request: Request):
        _require_login(request)
        active_room = request.session.get('active_room')
        if active_room:
            with get_db_closing() as conn:
                row = conn.execute('SELECT 1 FROM rooms WHERE pairing_code = ?', (active_room,)).fetchone()
            if not row:
                request.session.pop('active_room', None)
                request.session.pop('solo_mode', None)
                active_room = None
        info = get_provider().server_info()
        return {
            'userId': request.state.user_id,
            'displayName': request.state.user_id,
            'serverName': info.get('name', ''),
            'serverId': info.get('machineIdentifier', ''),
            'activeRoom': active_room,
        }

    @app.get("/jellyfin/server-info")
    def jellyfin_server_info(request: Request):
        try:
            info = get_provider().server_info()
            return {"baseUrl": info.get("machineIdentifier", ""), "webUrl": info.get("webUrl", "")}
        except Exception:
            return JSONResponse(content={"baseUrl": "", "webUrl": ""}, status_code=200)

    @app.post('/room')
    def create_room(request: Request):
        _require_login(request)
        pairing_code = str(random.randint(1000, 9999))
        movie_list = get_provider().fetch_deck()
        with get_db_closing() as conn:
            conn.execute('INSERT INTO rooms (pairing_code, movie_data, ready, current_genre, solo_mode) VALUES (?, ?, ?, ?, ?)',
                         (pairing_code, json.dumps(movie_list), 0, 'All', 0))
            conn.execute('UPDATE rooms SET deck_position = ? WHERE pairing_code = ?',
                         (json.dumps({request.state.user_id: 0}), pairing_code))
        request.session['active_room'] = pairing_code
        request.session['solo_mode'] = False
        return {'pairing_code': pairing_code}

    @app.post('/room/solo')
    def create_solo_room(request: Request):
        _require_login(request)
        pairing_code = str(random.randint(1000, 9999))
        movie_list = get_provider().fetch_deck()
        with get_db_closing() as conn:
            conn.execute(
                'INSERT INTO rooms (pairing_code, movie_data, ready, current_genre, solo_mode) VALUES (?, ?, ?, ?, ?)',
                (pairing_code, json.dumps(movie_list), 1, 'All', 1)
            )
            conn.execute(
                'UPDATE rooms SET deck_position = ? WHERE pairing_code = ?',
                (json.dumps({request.state.user_id: 0}), pairing_code)
            )
        request.session['active_room'] = pairing_code
        request.session['solo_mode'] = True
        return {'pairing_code': pairing_code}

    @app.post('/room/{code}/join')
    def join_room(code: str, request: Request):
        _require_login(request)
        with get_db_closing() as conn:
            room = conn.execute('SELECT * FROM rooms WHERE pairing_code = ?', (code,)).fetchone()
            if room:
                conn.execute('UPDATE rooms SET ready = 1 WHERE pairing_code = ?', (code,))
                room2 = conn.execute('SELECT deck_position FROM rooms WHERE pairing_code = ?', (code,)).fetchone()
                positions = json.loads(room2['deck_position']) if room2 and room2['deck_position'] else {}
                positions[request.state.user_id] = 0
                conn.execute('UPDATE rooms SET deck_position = ? WHERE pairing_code = ?',
                             (json.dumps(positions), code))
                request.session['active_room'] = code
                request.session['solo_mode'] = False
                return {'status': 'success'}
        return JSONResponse(content={'error': 'Invalid Code'}, status_code=404)

    @app.post('/room/{code}/swipe')
    async def swipe(code: str, request: Request):
        _require_login(request)
        try:
            data = await request.json()
        except Exception:
            data = {}
        mid = str(data.get('movie_id'))

        title = None
        thumb = None
        try:
            resolved = get_provider().resolve_item_for_tmdb(mid)
            title = resolved.title
            thumb = f"/proxy?path=jellyfin/{mid}/Primary"
        except RuntimeError as exc:
            _logger.warning(f"Failed to resolve metadata for movie_id={mid}: {exc}")

        with get_db_closing() as conn:
            conn.execute('INSERT INTO swipes (room_code, movie_id, user_id, direction, session_id) VALUES (?, ?, ?, ?, ?)',
                         (code, mid, request.state.user_id, data.get('direction'), request.session.get('session_id')))

            current_pos = _get_cursor(conn, code, request.state.user_id)
            _set_cursor(conn, code, request.state.user_id, current_pos + 1)

            if data.get('direction') == 'right':
                if title is not None and thumb is not None:
                    room = conn.execute('SELECT solo_mode, movie_data FROM rooms WHERE pairing_code = ?', (code,)).fetchone()

                    meta = _resolve_movie_meta(room['movie_data'], mid) if room else {'rating': '', 'duration': '', 'year': ''}
                    deep_link = f"{JELLYFIN_URL}/web/#/details?id={mid}" if JELLYFIN_URL else ''

                    if room and room['solo_mode']:
                        conn.execute(
                            'INSERT OR IGNORE INTO matches (room_code, movie_id, title, thumb, status, user_id, deep_link, rating, duration, year) VALUES (?, ?, ?, ?, "active", ?, ?, ?, ?, ?)',
                            (code, mid, title, thumb, request.state.user_id, deep_link, meta['rating'], meta['duration'], meta['year'])
                        )
                        match_data = json.dumps({
                            'type': 'match', 'title': title, 'thumb': thumb,
                            'movie_id': mid, 'rating': meta['rating'],
                            'duration': meta['duration'], 'year': meta['year'],
                            'deep_link': deep_link, 'ts': time.time()
                        })
                        conn.execute('UPDATE rooms SET last_match_data = ? WHERE pairing_code = ?', (match_data, code))
                    else:
                        conn.commit()

                        conn.execute('BEGIN IMMEDIATE')
                        try:
                            other_swipe = conn.execute('SELECT user_id, session_id FROM swipes WHERE room_code = ? AND movie_id = ? AND direction = "right" AND session_id != ?',
                                                     (code, mid, request.session.get('session_id'))).fetchone()

                            if other_swipe:
                                conn.execute(
                                    'INSERT OR IGNORE INTO matches (room_code, movie_id, title, thumb, status, user_id, deep_link, rating, duration, year) VALUES (?, ?, ?, ?, "active", ?, ?, ?, ?, ?)',
                                    (code, mid, title, thumb, request.state.user_id, deep_link, meta['rating'], meta['duration'], meta['year'])
                                )

                                if other_swipe['user_id'] and other_swipe['user_id'] != request.state.user_id:
                                    conn.execute(
                                        'INSERT OR IGNORE INTO matches (room_code, movie_id, title, thumb, status, user_id, deep_link, rating, duration, year) VALUES (?, ?, ?, ?, "active", ?, ?, ?, ?, ?)',
                                        (code, mid, title, thumb, other_swipe['user_id'], deep_link, meta['rating'], meta['duration'], meta['year'])
                                    )

                                match_data = json.dumps({
                                    'type': 'match', 'title': title, 'thumb': thumb,
                                    'movie_id': mid, 'rating': meta['rating'],
                                    'duration': meta['duration'], 'year': meta['year'],
                                    'deep_link': deep_link, 'ts': time.time()
                                })
                                conn.execute('UPDATE rooms SET last_match_data = ? WHERE pairing_code = ?', (match_data, code))

                            conn.execute('COMMIT')
                        except Exception:
                            conn.execute('ROLLBACK')
                            raise

        return {'accepted': True}

    @app.get('/matches')
    def get_matches(request: Request):
        _require_login(request)
        code = request.session.get('active_room')
        view = request.query_params.get('view')

        with get_db_closing() as conn:
            if view == 'history':
                rows = conn.execute('SELECT title, thumb, movie_id, deep_link, rating, duration, year FROM matches WHERE status = "archived" AND user_id = ?', (request.state.user_id,)).fetchall()
            else:
                rows = conn.execute('SELECT title, thumb, movie_id, deep_link, rating, duration, year FROM matches WHERE room_code = ? AND status = "active" AND user_id = ?', (code, request.state.user_id)).fetchall()
            return [dict(row) for row in rows]

    @app.post('/room/{code}/quit')
    def quit_room(code: str, request: Request):
        _require_login(request)
        with get_db_closing() as conn:
            conn.execute('DELETE FROM rooms WHERE pairing_code = ?', (code,))
            conn.execute('DELETE FROM swipes WHERE room_code = ?', (code,))
            conn.execute('UPDATE matches SET status = "archived", room_code = "HISTORY" WHERE room_code = ? AND status = "active"', (code,))
        request.session.pop('active_room', None)
        request.session.pop('solo_mode', None)
        return {'status': 'session_ended'}

    @app.post('/matches/delete')
    async def delete_match(request: Request):
        _require_login(request)
        try:
            data = await request.json()
        except Exception:
            data = {}
        mid = str(data.get('movie_id'))
        with get_db_closing() as conn:
            conn.execute('DELETE FROM matches WHERE movie_id = ? AND user_id = ?', (mid, request.state.user_id))
        return {'status': 'deleted'}

    @app.post('/room/{code}/undo')
    async def undo_swipe(code: str, request: Request):
        _require_login(request)
        try:
            data = await request.json()
        except Exception:
            data = {}
        mid = str(data.get('movie_id'))
        with get_db_closing() as conn:
            conn.execute('DELETE FROM swipes WHERE room_code = ? AND movie_id = ? AND session_id = ?', (code, mid, request.session.get('session_id')))
            conn.execute('DELETE FROM matches WHERE room_code = ? AND movie_id = ? AND status = "active" AND user_id = ?', (code, mid, request.state.user_id))
        return {'status': 'undone'}

    @app.get('/plex/server-info')
    def get_server_info(request: Request):
        try:
            return get_provider().server_info()
        except Exception as e:
            log_exception(e, request)
            return make_error_response('Internal server error', 500, request)

    @app.get('/room/{code}/deck')
    def get_deck(code: str, request: Request):
        _require_login(request)
        page = int(request.query_params.get('page', 1))
        page_size = 20
        with get_db_closing() as conn:
            cursor_pos = _get_cursor(conn, code, request.state.user_id)
            room = conn.execute('SELECT movie_data FROM rooms WHERE pairing_code = ?', (code,)).fetchone()
            if not room:
                return []
            movies = json.loads(room['movie_data'])
            start = cursor_pos + (page - 1) * page_size
            end = start + page_size
            page_items = movies[start:end]
            return page_items

    @app.post('/room/{code}/genre')
    async def set_genre(code: str, request: Request):
        _require_login(request)
        try:
            data = await request.json()
        except Exception:
            data = {}
        genre = data.get('genre')
        if not genre:
            return JSONResponse(content={'error': 'Genre required'}, status_code=400)
        new_list = get_provider().fetch_deck(genre)
        with get_db_closing() as conn:
            conn.execute('UPDATE rooms SET movie_data = ?, deck_position = ?, current_genre = ? WHERE pairing_code = ?',
                         (json.dumps(new_list), json.dumps({}), genre, code))
        return new_list

    @app.get('/genres')
    def get_genres(request: Request):
        try:
            return get_provider().list_genres()
        except Exception:
            return []

    @app.get('/room/{code}/status')
    def room_status(code: str, request: Request):
        with get_db_closing() as conn:
            room = conn.execute('SELECT ready, current_genre, solo_mode, last_match_data FROM rooms WHERE pairing_code = ?', (code,)).fetchone()
            if room:
                last_match = json.loads(room['last_match_data']) if room['last_match_data'] else None
                return {'ready': bool(room['ready']), 'genre': room['current_genre'], 'solo': bool(room['solo_mode']), 'last_match': last_match}
            return {'ready': False}

    @app.get('/room/{code}/stream')
    def room_stream(code: str, request: Request):
        def generate():
            last_genre = None
            last_ready = None
            last_match_ts = None
            POLL = 1.5
            TIMEOUT = 3600
            _last_event_time = time.time()

            # Per DB-02: Hold one persistent connection for the entire
            # stream lifetime instead of opening/closing per poll cycle.
            # WAL mode (set in init_db) eliminates file-lock contention
            # so concurrent readers don't block this connection.
            import jellyswipe.db
            conn = sqlite3.connect(jellyswipe.db.DB_PATH)
            conn.row_factory = sqlite3.Row
            try:
                deadline = time.time() + TIMEOUT
                while time.time() < deadline:
                    try:
                        row = conn.execute(
                            'SELECT ready, current_genre, solo_mode, last_match_data FROM rooms WHERE pairing_code = ?',
                            (code,)
                        ).fetchone()

                        if row is None:
                            yield f"data: {json.dumps({'closed': True})}\n\n"
                            return

                        ready = bool(row['ready'])
                        genre = row['current_genre']
                        solo = bool(row['solo_mode'])
                        last_match = json.loads(row['last_match_data']) if row['last_match_data'] else None
                        match_ts = last_match['ts'] if last_match else None

                        payload = {}
                        if ready != last_ready:
                            payload['ready'] = ready
                            payload['solo'] = solo
                            last_ready = ready
                        if genre != last_genre:
                            payload['genre'] = genre
                            last_genre = genre
                        if match_ts and match_ts != last_match_ts:
                            payload['last_match'] = last_match
                            last_match_ts = match_ts

                        if payload:
                            yield f"data: {json.dumps(payload)}\n\n"
                            _last_event_time = time.time()
                        elif time.time() - _last_event_time >= 15:
                            yield ": ping\n\n"
                            _last_event_time = time.time()

                        delay = POLL + random.uniform(0, 0.5)
                        time.sleep(delay)
                    except GeneratorExit:
                        return
                    except Exception:
                        delay = POLL + random.uniform(0, 0.5)
                        time.sleep(delay)
            finally:
                conn.close()

        return StreamingResponse(
            generate(),
            media_type='text/event-stream',
            headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
        )

    @app.get('/proxy')
    def proxy(request: Request):
        rl = _check_rate_limit('proxy', request)
        if rl:
            return JSONResponse(content=rl[0], status_code=rl[1])
        path = request.query_params.get('path')
        if not path:
            raise HTTPException(status_code=403)
        if not JELLYFIN_URL:
            raise HTTPException(status_code=503)
        if not re.match(r"^jellyfin/(?:[0-9a-fA-F]{32}|[0-9a-fA-F-]{36})/Primary$", path):
            raise HTTPException(status_code=403)
        try:
            body, content_type = get_provider().fetch_library_image(path)
        except PermissionError:
            raise HTTPException(status_code=403)
        except FileNotFoundError:
            raise HTTPException(status_code=404)
        except requests.exceptions.RequestException as exc:
            _logger.warning("proxy: upstream error fetching %s: %s", path, exc)
            return JSONResponse(content={"error": "Upstream server error"}, status_code=502)
        return Response(content=body, media_type=content_type)

    @app.get('/manifest.json')
    def serve_manifest(request: Request):
        return FileResponse(
            path=os.path.join(_APP_ROOT, 'static', 'manifest.json'),
            media_type='application/manifest+json'
        )

    @app.get('/sw.js')
    def serve_sw(request: Request):
        return FileResponse(
            path=os.path.join(_APP_ROOT, 'static', 'sw.js'),
            media_type='application/javascript'
        )

    @app.get('/static/{path:path}')
    def serve_static_route(path: str, request: Request):
        return FileResponse(path=os.path.join(_APP_ROOT, 'static', path))

    @app.get('/favicon.ico')
    def serve_favicon(request: Request):
        return FileResponse(
            path=os.path.join(_APP_ROOT, 'static', 'favicon.ico'),
            media_type='image/x-icon'
        )

    return app


# Create global app instance for backwards compatibility
# Dockerfile CMD uses: uvicorn jellyswipe:app
app = create_app()
