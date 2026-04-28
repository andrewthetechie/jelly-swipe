try:
    from pathlib import Path

    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

from flask import Flask, send_from_directory, jsonify, request, session, Response, render_template, abort, g
from flask.json.provider import DefaultJSONProvider
from werkzeug.middleware.proxy_fix import ProxyFix
from typing import Dict, Optional, Tuple
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


def _check_rate_limit(endpoint: str) -> Optional[Tuple[Response, int]]:
    allowed, retry_after = _rate_limiter.check(endpoint, request.remote_addr, _RATE_LIMITS[endpoint])
    if not allowed:
        _logger.warning("rate_limit_exceeded", extra={
            'endpoint': endpoint,
            'ip': request.remote_addr,
            'retry_after': retry_after,
        })
        body = jsonify({'error': 'Rate limit exceeded', 'request_id': request.environ.get('jellyswipe.request_id', 'unknown')})
        resp = body, 429
        response = Response(response=body.response, status=429, content_type='application/json')
        response.headers['Retry-After'] = str(int(retry_after) + 1)
        return response
    return None

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

from jellyswipe.auth import create_session, login_required, destroy_session


class _XSSSafeJSONProvider(DefaultJSONProvider):
    """JSON provider that escapes HTML-sensitive characters for XSS defense.

    Per OWASP recommendation, < > & are encoded as \\u003c \\u003e \\u0026
    in JSON output so that raw HTTP bodies cannot contain executable HTML tags.
    JSON parsers correctly decode these back to the original characters.
    """

    def dumps(self, obj, **kwargs):
        result = super().dumps(obj, **kwargs)
        return (result
                .replace("<", "\\u003c")
                .replace(">", "\\u003e")
                .replace("&", "\\u0026"))


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


def create_app(test_config=None):
    """
    Create and configure a Flask application instance.

    Args:
        test_config: Optional dictionary of test configuration to override defaults.
                     If provided, these values will update app.config before database initialization.

    Returns:
        A configured Flask application instance.
    """
    app = Flask(__name__,
                template_folder=os.path.join(_APP_ROOT, 'templates'),
                static_folder=os.path.join(_APP_ROOT, 'static'))

    app.json = _XSSSafeJSONProvider(app)

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

    app.secret_key = os.environ["FLASK_SECRET"]
    # SESSION_COOKIE_SECURE must match the transport layer:
    # - HTTP deployments (Docker, local dev) need Secure=False or cookies are never stored
    # - HTTPS deployments (reverse proxy with X-Forwarded-Proto) should set Secure=True
    # Default to False (safe for HTTP); set SESSION_COOKIE_SECURE env var to 'true' for HTTPS
    app.config['SESSION_COOKIE_SECURE'] = os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    @app.after_request
    def add_csp_header(response):
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self'; "
            "object-src 'none'; "
            "img-src 'self' https://image.tmdb.org; "
            "frame-src https://www.youtube.com"
        )
        response.headers['Content-Security-Policy'] = csp_policy
        return response

    @app.before_request
    def inject_request_id():
        request.environ['jellyswipe.request_id'] = generate_request_id()

    @app.after_request
    def add_request_id_header(response):
        response.headers['X-Request-Id'] = get_request_id()
        return response

    def get_request_id() -> str:
        return request.environ.get('jellyswipe.request_id', 'unknown')

    def make_error_response(message: str, status_code: int, include_request_id: bool = True, extra_fields: dict = None) -> Tuple[Response, int]:
        if status_code >= 500:
            message = 'Internal server error'
        body = {'error': message}
        if include_request_id:
            body['request_id'] = get_request_id()
        if extra_fields:
            body.update(extra_fields)
        return jsonify(body), status_code

    def log_exception(exc: Exception, context: dict = None) -> None:
        log_data = {
            'request_id': get_request_id(),
            'route': request.path,
            'method': request.method,
            'exception_type': type(exc).__name__,
            'exception_message': str(exc),
            'stack_trace': traceback.format_exc(),
        }
        if context:
            log_data.update(context)
        app.logger.error(
            "unhandled_exception",
            extra=log_data
        )

    app.config['JELLYFIN_URL'] = os.getenv("JELLYFIN_URL", "").rstrip("/")
    app.config['TMDB_ACCESS_TOKEN'] = os.getenv("TMDB_ACCESS_TOKEN")
    TMDB_AUTH_HEADERS = {"Authorization": f"Bearer {app.config['TMDB_ACCESS_TOKEN']}"}
    JELLYFIN_URL = app.config['JELLYFIN_URL']

    if test_config:
        app.config.update(test_config)

    def get_provider() -> JellyfinLibraryProvider:
        """Get or create the JellyfinLibraryProvider singleton."""
        global _provider_singleton
        if _provider_singleton is None:
            _provider_singleton = JellyfinLibraryProvider(app.config['JELLYFIN_URL'])
        return _provider_singleton

    from .db import get_db, get_db_closing, init_db

    import jellyswipe.db
    if test_config and 'DB_PATH' in test_config:
        jellyswipe.db.DB_PATH = test_config['DB_PATH']
    else:
        jellyswipe.db.DB_PATH = DB_PATH

    init_db()

    @app.route('/')
    def index():
        return render_template('index.html', media_provider="jellyfin")

    def _jellyfin_user_token_from_request() -> str:
        if session.get("jf_delegate_server_identity"):
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

    def _request_has_identity_alias_headers() -> bool:
        for header in IDENTITY_ALIAS_HEADERS:
            if request.headers.get(header):
                return True
        return False

    def _set_identity_rejection_reason(reason: str) -> None:
        request.environ["jellyswipe.identity_rejected"] = reason

    def _identity_rejection_reason() -> Optional[str]:
        value = request.environ.get("jellyswipe.identity_rejected")
        return str(value) if value else None

    def _unauthorized_response():
        return make_error_response('Unauthorized', 401)

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

    def _provider_user_id_from_request():
        if session.get("jf_delegate_server_identity"):
            prov = get_provider()
            try:
                return prov.server_primary_user_id_for_delegate()
            except RuntimeError:
                pass
        if _request_has_identity_alias_headers():
            _set_identity_rejection_reason("spoofed_alias_header")
            return None

        token = _jellyfin_user_token_from_request()
        if not token:
            return None
        user_id = _resolve_user_id_from_token_cached(token)
        if user_id:
            return user_id
        _set_identity_rejection_reason("token_resolution_failed")
        return None

    @app.route('/get-trailer/<movie_id>')
    def get_trailer(movie_id):
        rl = _check_rate_limit('get-trailer')
        if rl:
            return rl
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
                    return jsonify({'youtube_key': trailers[0]['key']})
            return make_error_response('Not found', 404)
        except RuntimeError as e:
            if "item lookup failed" in str(e).lower():
                return make_error_response('Movie metadata not found', 404)
            log_exception(e)
            return make_error_response('Internal server error', 500)
        except Exception as e:
            log_exception(e)
            return make_error_response('Internal server error', 500)

    @app.route('/cast/<movie_id>')
    def get_cast(movie_id):
        rl = _check_rate_limit('cast')
        if rl:
            return rl
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
                return jsonify({'cast': cast})
            return jsonify({'cast': []})
        except RuntimeError as e:
            if "item lookup failed" in str(e).lower():
                return make_error_response('Movie metadata not found', 404, extra_fields={'cast': []})
            log_exception(e)
            return make_error_response('Internal server error', 500, extra_fields={'cast': []})
        except Exception as e:
            log_exception(e)
            return make_error_response('Internal server error', 500, extra_fields={'cast': []})

    @app.route('/watchlist/add', methods=['POST'])
    @login_required
    def add_to_watchlist():
        rl = _check_rate_limit('watchlist/add')
        if rl:
            return rl
        try:
            data = request.json
            movie_id = data.get('movie_id')
            get_provider().add_to_user_favorites(g.jf_token, movie_id)
            return jsonify({'status': 'success'})
        except Exception as e:
            log_exception(e)
            return make_error_response('Internal server error', 500)

    @app.route('/auth/provider')
    def auth_provider():
        payload = {"provider": "jellyfin", "jellyfin_browser_auth": "delegate"}
        return jsonify(payload)

    @app.route("/auth/jellyfin-use-server-identity", methods=["POST"])
    def jellyfin_use_server_identity():
        prov = get_provider()
        try:
            token = prov.server_access_token_for_delegate()
            uid = prov.server_primary_user_id_for_delegate()
        except RuntimeError:
            return make_error_response("Jellyfin delegate unavailable", 401)
        create_session(token, uid)
        return jsonify({"userId": uid})

    @app.route('/auth/jellyfin-login', methods=['POST'])
    def jellyfin_login():
        data = request.json or {}
        username = (data.get("username") or "").strip()
        password = (data.get("password") or "").strip()
        if not username or not password:
            return jsonify({"error": "Username and password are required"}), 400
        try:
            out = get_provider().authenticate_user_session(username, password)
            create_session(out["token"], out["user_id"])
            return jsonify({"userId": out["user_id"]})
        except Exception:
            return make_error_response("Jellyfin login failed", 401)

    @app.route('/auth/logout', methods=['POST'])
    @login_required
    def logout():
        destroy_session()
        return jsonify({'status': 'logged_out'})

    @app.route('/me')
    @login_required
    def get_me():
        active_room = session.get('active_room')
        if active_room:
            with get_db() as conn:
                row = conn.execute('SELECT 1 FROM rooms WHERE pairing_code = ?', (active_room,)).fetchone()
            if not row:
                session.pop('active_room', None)
                session.pop('solo_mode', None)
                active_room = None
        info = get_provider().server_info()
        return jsonify({
            'userId': g.user_id,
            'displayName': g.user_id,
            'serverName': info.get('name', ''),
            'serverId': info.get('machineIdentifier', ''),
            'activeRoom': active_room,
        })

    @app.route("/jellyfin/server-info", methods=["GET"])
    def jellyfin_server_info():
        try:
            info = get_provider().server_info()
            return jsonify({"baseUrl": info.get("machineIdentifier", ""), "webUrl": info.get("webUrl", "")})
        except Exception:
            return jsonify({"baseUrl": "", "webUrl": ""}), 200

    @app.route('/room', methods=['POST'])
    @login_required
    def create_room():
        pairing_code = str(random.randint(1000, 9999))
        movie_list = get_provider().fetch_deck()
        with get_db() as conn:
            conn.execute('INSERT INTO rooms (pairing_code, movie_data, ready, current_genre, solo_mode) VALUES (?, ?, ?, ?, ?)',
                         (pairing_code, json.dumps(movie_list), 0, 'All', 0))
            conn.execute('UPDATE rooms SET deck_position = ? WHERE pairing_code = ?',
                         (json.dumps({g.user_id: 0}), pairing_code))
        session['active_room'] = pairing_code
        session['solo_mode'] = False
        return jsonify({'pairing_code': pairing_code})

    @app.route('/room/solo', methods=['POST'])
    @login_required
    def create_solo_room():
        pairing_code = str(random.randint(1000, 9999))
        movie_list = get_provider().fetch_deck()
        with get_db() as conn:
            conn.execute(
                'INSERT INTO rooms (pairing_code, movie_data, ready, current_genre, solo_mode) VALUES (?, ?, ?, ?, ?)',
                (pairing_code, json.dumps(movie_list), 1, 'All', 1)
            )
            conn.execute(
                'UPDATE rooms SET deck_position = ? WHERE pairing_code = ?',
                (json.dumps({g.user_id: 0}), pairing_code)
            )
        session['active_room'] = pairing_code
        session['solo_mode'] = True
        return jsonify({'pairing_code': pairing_code})

    @app.route('/room/<code>/join', methods=['POST'])
    @login_required
    def join_room(code):
        with get_db() as conn:
            room = conn.execute('SELECT * FROM rooms WHERE pairing_code = ?', (code,)).fetchone()
            if room:
                conn.execute('UPDATE rooms SET ready = 1 WHERE pairing_code = ?', (code,))
                room2 = conn.execute('SELECT deck_position FROM rooms WHERE pairing_code = ?', (code,)).fetchone()
                positions = json.loads(room2['deck_position']) if room2 and room2['deck_position'] else {}
                positions[g.user_id] = 0
                conn.execute('UPDATE rooms SET deck_position = ? WHERE pairing_code = ?',
                             (json.dumps(positions), code))
                session['active_room'] = code
                session['solo_mode'] = False
                return jsonify({'status': 'success'})
        return jsonify({'error': 'Invalid Code'}), 404

    @app.route('/room/<code>/swipe', methods=['POST'])
    @login_required
    def swipe(code):
        data = request.json
        mid = str(data.get('movie_id'))

        title = None
        thumb = None
        try:
            resolved = get_provider().resolve_item_for_tmdb(mid)
            title = resolved.title
            thumb = f"/proxy?path=jellyfin/{mid}/Primary"
        except RuntimeError as exc:
            app.logger.warning(f"Failed to resolve metadata for movie_id={mid}: {exc}")

        with get_db() as conn:
            conn.execute('INSERT INTO swipes (room_code, movie_id, user_id, direction, session_id) VALUES (?, ?, ?, ?, ?)',
                         (code, mid, g.user_id, data.get('direction'), session.get('session_id')))

            current_pos = _get_cursor(conn, code, g.user_id)
            _set_cursor(conn, code, g.user_id, current_pos + 1)

            if data.get('direction') == 'right':
                if title is not None and thumb is not None:
                    room = conn.execute('SELECT solo_mode, movie_data FROM rooms WHERE pairing_code = ?', (code,)).fetchone()

                    meta = _resolve_movie_meta(room['movie_data'], mid) if room else {'rating': '', 'duration': '', 'year': ''}
                    deep_link = f"{JELLYFIN_URL}/web/#/details?id={mid}" if JELLYFIN_URL else ''

                    if room and room['solo_mode']:
                        conn.execute(
                            'INSERT OR IGNORE INTO matches (room_code, movie_id, title, thumb, status, user_id, deep_link, rating, duration, year) VALUES (?, ?, ?, ?, "active", ?, ?, ?, ?, ?)',
                            (code, mid, title, thumb, g.user_id, deep_link, meta['rating'], meta['duration'], meta['year'])
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
                                                     (code, mid, session.get('session_id'))).fetchone()

                            if other_swipe:
                                conn.execute(
                                    'INSERT OR IGNORE INTO matches (room_code, movie_id, title, thumb, status, user_id, deep_link, rating, duration, year) VALUES (?, ?, ?, ?, "active", ?, ?, ?, ?, ?)',
                                    (code, mid, title, thumb, g.user_id, deep_link, meta['rating'], meta['duration'], meta['year'])
                                )

                                if other_swipe['user_id'] and other_swipe['user_id'] != g.user_id:
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

        return jsonify({'accepted': True})

    @app.route('/matches')
    @login_required
    def get_matches():
        code = session.get('active_room')
        view = request.args.get('view')

        with get_db() as conn:
            if view == 'history':
                rows = conn.execute('SELECT title, thumb, movie_id, deep_link, rating, duration, year FROM matches WHERE status = "archived" AND user_id = ?', (g.user_id,)).fetchall()
            else:
                rows = conn.execute('SELECT title, thumb, movie_id, deep_link, rating, duration, year FROM matches WHERE room_code = ? AND status = "active" AND user_id = ?', (code, g.user_id)).fetchall()
            return jsonify([dict(row) for row in rows])

    @app.route('/room/<code>/quit', methods=['POST'])
    @login_required
    def quit_room(code):
        with get_db() as conn:
            conn.execute('DELETE FROM rooms WHERE pairing_code = ?', (code,))
            conn.execute('DELETE FROM swipes WHERE room_code = ?', (code,))
            conn.execute('UPDATE matches SET status = "archived", room_code = "HISTORY" WHERE room_code = ? AND status = "active"', (code,))
        session.pop('active_room', None)
        session.pop('solo_mode', None)
        return jsonify({'status': 'session_ended'})

    @app.route('/matches/delete', methods=['POST'])
    @login_required
    def delete_match():
        mid = str(request.json.get('movie_id'))
        with get_db() as conn:
            conn.execute('DELETE FROM matches WHERE movie_id = ? AND user_id = ?', (mid, g.user_id))
        return jsonify({'status': 'deleted'})

    @app.route('/room/<code>/undo', methods=['POST'])
    @login_required
    def undo_swipe(code):
        mid = str(request.json.get('movie_id'))
        with get_db() as conn:
            conn.execute('DELETE FROM swipes WHERE room_code = ? AND movie_id = ? AND session_id = ?', (code, mid, session.get('session_id')))
            conn.execute('DELETE FROM matches WHERE room_code = ? AND movie_id = ? AND status = "active" AND user_id = ?', (code, mid, g.user_id))
        return jsonify({'status': 'undone'})

    @app.route('/plex/server-info')
    def get_server_info():
        try:
            return jsonify(get_provider().server_info())
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/room/<code>/deck')
    @login_required
    def get_deck(code):
        page = request.args.get('page', 1, type=int)
        page_size = 20
        with get_db() as conn:
            cursor_pos = _get_cursor(conn, code, g.user_id)
            room = conn.execute('SELECT movie_data FROM rooms WHERE pairing_code = ?', (code,)).fetchone()
            if not room:
                return jsonify([])
            movies = json.loads(room['movie_data'])
            start = cursor_pos + (page - 1) * page_size
            end = start + page_size
            page_items = movies[start:end]
            return jsonify(page_items)

    @app.route('/room/<code>/genre', methods=['POST'])
    @login_required
    def set_genre(code):
        genre = request.json.get('genre')
        if not genre:
            return jsonify({'error': 'Genre required'}), 400
        new_list = get_provider().fetch_deck(genre)
        with get_db() as conn:
            conn.execute('UPDATE rooms SET movie_data = ?, deck_position = ?, current_genre = ? WHERE pairing_code = ?',
                         (json.dumps(new_list), json.dumps({}), genre, code))
        return jsonify(new_list)

    @app.route('/genres')
    def get_genres():
        try:
            return jsonify(get_provider().list_genres())
        except Exception:
            return jsonify([])

    @app.route('/room/<code>/status')
    def room_status(code):
        with get_db_closing() as conn:
            room = conn.execute('SELECT ready, current_genre, solo_mode, last_match_data FROM rooms WHERE pairing_code = ?', (code,)).fetchone()
            if room:
                last_match = json.loads(room['last_match_data']) if room['last_match_data'] else None
                return jsonify({'ready': bool(room['ready']), 'genre': room['current_genre'], 'solo': bool(room['solo_mode']), 'last_match': last_match})
            return jsonify({'ready': False})

    @app.route('/room/<code>/stream')
    def room_stream(code):
        def generate():
            last_genre = None
            last_ready = None
            last_match_ts = None
            POLL = 1.5
            TIMEOUT = 3600

            deadline = time.time() + TIMEOUT
            while time.time() < deadline:
                try:
                    with get_db_closing() as conn:
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

                    time.sleep(POLL)
                except GeneratorExit:
                    return
                except Exception:
                    time.sleep(POLL)

        return Response(generate(), mimetype='text/event-stream',
                       headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    @app.route('/proxy')
    def proxy():
        rl = _check_rate_limit('proxy')
        if rl:
            return rl
        path = request.args.get('path')
        if not path:
            abort(403)
        if not app.config['JELLYFIN_URL']:
            abort(503)
        if not re.match(r"^jellyfin/(?:[0-9a-fA-F]{32}|[0-9a-fA-F-]{36})/Primary$", path):
            abort(403)
        try:
            body, content_type = get_provider().fetch_library_image(path)
        except PermissionError:
            abort(403)
        except FileNotFoundError:
            abort(404)
        except requests.exceptions.RequestException as exc:
            app.logger.warning("proxy: upstream error fetching %s: %s", path, exc)
            return jsonify({"error": "Upstream server error"}), 502
        return Response(body, content_type=content_type)

    def serve_static(path: str, mimetype: str = None) -> Response:
        call_args = ('static', path)
        call_kwargs = {}
        if mimetype:
            call_kwargs['mimetype'] = mimetype
        return send_from_directory(*call_args, **call_kwargs)

    @app.route('/manifest.json')
    def serve_manifest():
        return serve_static(path='manifest.json', mimetype='application/manifest+json')

    @app.route('/sw.js')
    def serve_sw():
        return serve_static(path="sw.js", mimetype='application/javascript')

    @app.route('/static/<path:path>')
    def serve_static_route(path):
        return serve_static(path=path)

    @app.route('/favicon.ico')
    def serve_favicon():
        return serve_static(path="favicon.ico", mimetype='image/x-icon')

    return app


# Create global app instance for backwards compatibility
# Dockerfile CMD uses: gunicorn jellyswipe:app
app = create_app()
