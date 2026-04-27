try:
    from pathlib import Path

    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

from flask import Flask, send_from_directory, jsonify, request, session, Response, render_template, abort, g
from werkzeug.middleware.proxy_fix import ProxyFix
import sqlite3, os, random, re, requests, json, secrets, time

# Default: repo ./data/jellyswipe.db (local dev). Docker: set DB_PATH=/app/data/jellyswipe.db or keep default when WORKDIR is /app.
_APP_ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.abspath(
    os.getenv("DB_PATH", os.path.join(_APP_ROOT, "..", "data", "jellyswipe.db"))
)
CLIENT_ID = 'JellySwipe-AndrewTheTechie-2026'

# Validate required environment variables
missing = []
for v in ("TMDB_API_KEY", "FLASK_SECRET"):
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

app = Flask(__name__,
            template_folder=os.path.join(_APP_ROOT, 'templates'),
            static_folder=os.path.join(_APP_ROOT, 'static'))
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
app.secret_key = os.environ["FLASK_SECRET"]
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

@app.after_request
def add_csp_header(response):
    """Add Content Security Policy header to block inline scripts and restrict external resources."""
    csp_policy = (
        "default-src 'self'; "
        "script-src 'self'; "
        "object-src 'none'; "
        "img-src 'self' https://image.tmdb.org; "
        "frame-src https://www.youtube.com"
    )
    response.headers['Content-Security-Policy'] = csp_policy
    return response

JELLYFIN_URL = os.getenv("JELLYFIN_URL", "").rstrip("/")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

# Direct Jellyfin provider instantiation (no factory pattern)
from .jellyfin_library import JellyfinLibraryProvider

_provider_singleton = None

def get_provider() -> JellyfinLibraryProvider:
    """Get or create the JellyfinLibraryProvider singleton."""
    global _provider_singleton
    if _provider_singleton is None:
        _provider_singleton = JellyfinLibraryProvider(JELLYFIN_URL)
    return _provider_singleton

# Import database functions
from .db import get_db, init_db
from jellyswipe.auth import create_session, login_required, destroy_session

# Set DB_PATH in db module
import jellyswipe.db
jellyswipe.db.DB_PATH = DB_PATH


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


@app.route('/')
def index(): return render_template('index.html', media_provider="jellyfin")


@app.route('/get-trailer/<movie_id>')
def get_trailer(movie_id):
    try:
        item = get_provider().resolve_item_for_tmdb(movie_id)
        search_url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={item.title}&year={item.year}"
        r = requests.get(search_url).json()
        if r.get('results'):
            tmdb_id = r['results'][0]['id']
            v_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/videos?api_key={TMDB_API_KEY}"
            v_res = requests.get(v_url).json()
            trailers = [v for v in v_res.get('results', []) if v['site'] == 'YouTube' and v['type'] == 'Trailer']
            if trailers: return jsonify({'youtube_key': trailers[0]['key']})
        return jsonify({'error': 'Not found'}), 404
    except RuntimeError as e:
        if "item lookup failed" in str(e).lower():
            return jsonify({'error': 'Movie metadata not found'}), 404
        return jsonify({'error': str(e)}), 500
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/cast/<movie_id>')
def get_cast(movie_id):
    try:
        item = get_provider().resolve_item_for_tmdb(movie_id)
        search_url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={item.title}&year={item.year}"
        r = requests.get(search_url).json()
        if r.get('results'):
            tmdb_id = r['results'][0]['id']
            credits_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/credits?api_key={TMDB_API_KEY}"
            c_res = requests.get(credits_url).json()
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
            return jsonify({'error': 'Movie metadata not found', 'cast': []}), 404
        return jsonify({'error': str(e), 'cast': []}), 500
    except Exception as e:
        return jsonify({'error': str(e), 'cast': []}), 500

@app.route('/watchlist/add', methods=['POST'])
@login_required
def add_to_watchlist():
    try:
        data = request.json
        movie_id = data.get('movie_id')
        get_provider().add_to_user_favorites(g.jf_token, movie_id)
        return jsonify({'status': 'success'})
    except Exception as e: return jsonify({'error': str(e)}), 500


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
        return jsonify({"error": "Jellyfin delegate unavailable"}), 401
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
        return jsonify({"error": "Jellyfin login failed"}), 401

@app.route('/auth/logout', methods=['POST'])
@login_required
def logout():
    destroy_session()
    return jsonify({'status': 'logged_out'})

@app.route('/me')
@login_required
def get_me():
    info = get_provider().server_info()
    return jsonify({
        'userId': g.user_id,
        'displayName': g.user_id,
        'serverName': info.get('name', ''),
        'serverId': info.get('machineIdentifier', ''),
        'activeRoom': session.get('active_room'),
    })

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
            # Read existing deck_position, add this user with cursor 0
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

    # Resolve title and thumb server-side from Jellyfin (XSS fix per SSV-01, SSV-02)
    title = None
    thumb = None
    try:
        resolved = get_provider().resolve_item_for_tmdb(mid)
        title = resolved.title
        # Thumb URL follows established pattern from _item_to_card()
        thumb = f"/proxy?path=jellyfin/{mid}/Primary"
    except RuntimeError as exc:
        # Per D-01, D-02: Allow swipe to complete but skip match creation
        app.logger.warning(f"Failed to resolve metadata for movie_id={mid}: {exc}")
        # Fall through - swipe record will be created, but matches will be skipped

    with get_db() as conn:
        conn.execute('INSERT INTO swipes (room_code, movie_id, user_id, direction) VALUES (?, ?, ?, ?)',
                     (code, mid, g.user_id, data.get('direction')))

        # Advance cursor (per D-06: cursor advances on swipe, not on view)
        current_pos = _get_cursor(conn, code, g.user_id)
        _set_cursor(conn, code, g.user_id, current_pos + 1)

        if data.get('direction') == 'right':
            # Only create matches if we successfully resolved metadata server-side
            if title is not None and thumb is not None:
                room = conn.execute('SELECT solo_mode, movie_data FROM rooms WHERE pairing_code = ?', (code,)).fetchone()

                # Resolve enriched metadata from stored movie_data JSON (per D-09, D-10)
                meta = _resolve_movie_meta(room['movie_data'], mid) if room else {'rating': '', 'duration': '', 'year': ''}
                deep_link = f"{JELLYFIN_URL}/web/#/details?id={mid}" if JELLYFIN_URL else ''

                if room and room['solo_mode']:
                    # Solo mode: create match directly, update last_match_data (per D-01)
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
                    # Two-player mode: commit swipe + cursor before IMMEDIATE transaction
                    conn.commit()

                    # Per D-11: Wrap match check-and-insert in BEGIN IMMEDIATE
                    conn.execute('BEGIN IMMEDIATE')
                    try:
                        other_swipe = conn.execute('SELECT user_id FROM swipes WHERE room_code = ? AND movie_id = ? AND direction = "right" AND user_id != ?',
                                                 (code, mid, g.user_id)).fetchone()

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
        conn.execute('DELETE FROM swipes WHERE room_code = ? AND movie_id = ? AND user_id = ?', (code, mid, g.user_id))
        conn.execute('DELETE FROM matches WHERE room_code = ? AND movie_id = ? AND status = "active" AND user_id = ?', (code, mid, g.user_id))
    return jsonify({'status': 'undone'})

@app.route('/plex/server-info')
def get_server_info():
    try:
        return jsonify(get_provider().server_info())
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/room/<code>/deck')
@login_required
def get_deck(code):
    page = request.args.get('page', 1, type=int)
    page_size = 20  # per D-09
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
    with get_db() as conn:
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
                with get_db() as conn:
                    row = conn.execute(
                        'SELECT ready, current_genre, solo_mode, last_match_data FROM rooms WHERE pairing_code = ?',
                        (code,)
                    ).fetchone()

                if row is None:
                    yield f"data: {json.dumps({'closed': True})}\n\n"
                    return

                ready = bool(row['ready'])
                genre = row['current_genre']
                solo  = bool(row['solo_mode'])
                last_match = json.loads(row['last_match_data']) if row['last_match_data'] else None
                match_ts   = last_match['ts'] if last_match else None

                payload = {}
                if ready != last_ready:
                    payload['ready'] = ready
                    payload['solo']  = solo
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
    path = request.args.get('path')
    if not path:
        abort(403)
    if not JELLYFIN_URL:
        abort(503)
    if not re.match(r"^jellyfin/(?:[0-9a-fA-F]{32}|[0-9a-fA-F-]{36})/Primary$", path):
        abort(403)
    try:
        body, content_type = get_provider().fetch_library_image(path)
    except PermissionError:
        abort(403)
    return Response(body, content_type=content_type)

def serve_static(path: str, mimetype: str = None) -> Response:
    """ Serve static assets from the static directory. """
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

# Initialize database at module load time
init_db()
