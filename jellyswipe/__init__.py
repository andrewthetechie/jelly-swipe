try:
    from pathlib import Path

    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

from flask import Flask, send_from_directory, jsonify, request, session, Response, render_template, abort
from werkzeug.middleware.proxy_fix import ProxyFix
from typing import Optional
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

JELLYFIN_URL = os.getenv("JELLYFIN_URL", "").rstrip("/")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

# Direct Jellyfin provider instantiation (no factory pattern)
from .jellyfin_library import JellyfinLibraryProvider

_provider_singleton: Optional[JellyfinLibraryProvider] = None

def get_provider() -> JellyfinLibraryProvider:
    """Get or create the JellyfinLibraryProvider singleton."""
    global _provider_singleton
    if _provider_singleton is None:
        _provider_singleton = JellyfinLibraryProvider(JELLYFIN_URL)
    return _provider_singleton

# Import database functions
from .db import get_db, init_db

# Set DB_PATH in db module
import jellyswipe.db
jellyswipe.db.DB_PATH = DB_PATH


@app.route('/')
def index(): return render_template('index.html', media_provider="jellyfin")


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


def _provider_user_id_from_request():
    if session.get("jf_delegate_server_identity"):
        prov = get_provider()
        try:
            return prov.server_primary_user_id_for_delegate()
        except RuntimeError:
            pass
    alias = (
        request.headers.get("X-Provider-User-Id")
        or request.headers.get("X-Jellyfin-User-Id")
        or request.headers.get("X-Emby-UserId")
    )
    if alias:
        return alias
    token = _jellyfin_user_token_from_request()
    if not token:
        return None
    try:
        return get_provider().resolve_user_id_from_token(token)
    except Exception:
        return None

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
def add_to_watchlist():
    try:
        data = request.json
        movie_id = data.get('movie_id')
        user_token = _jellyfin_user_token_from_request()
        if not user_token:
            return jsonify({'error': 'Unauthorized'}), 401
        get_provider().add_to_user_favorites(user_token, movie_id)
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
        prov.server_access_token_for_delegate()
        uid = prov.server_primary_user_id_for_delegate()
    except RuntimeError:
        return jsonify({"error": "Jellyfin delegate unavailable"}), 401
    session["jf_delegate_server_identity"] = True
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
        return jsonify({"authToken": out["token"], "userId": out["user_id"]})
    except Exception:
        return jsonify({"error": "Jellyfin login failed"}), 401

@app.route('/room/create', methods=['POST'])
def create_room():
    pairing_code = str(random.randint(1000, 9999))
    movie_list = get_provider().fetch_deck()
    with get_db() as conn:
        conn.execute('INSERT INTO rooms (pairing_code, movie_data, ready, current_genre, solo_mode) VALUES (?, ?, ?, ?, ?)',
                     (pairing_code, json.dumps(movie_list), 0, 'All', 0))
    session['active_room'] = pairing_code
    session['my_user_id'] = 'host_' + secrets.token_hex(8)
    session['solo_mode'] = False
    return jsonify({'pairing_code': pairing_code})

@app.route('/room/go-solo', methods=['POST'])
def go_solo():

    code = session.get('active_room')
    if not code:
        return jsonify({'error': 'No active room'}), 400
    with get_db() as conn:
        conn.execute('UPDATE rooms SET ready = 1, solo_mode = 1 WHERE pairing_code = ?', (code,))
    session['solo_mode'] = True
    return jsonify({'status': 'solo'})

@app.route('/room/join', methods=['POST'])
def join_room():
    code = request.json.get('code')
    with get_db() as conn:
        room = conn.execute('SELECT * FROM rooms WHERE pairing_code = ?', (code,)).fetchone()
        if room:
            conn.execute('UPDATE rooms SET ready = 1 WHERE pairing_code = ?', (code,))
            session['active_room'] = code
            session['my_user_id'] = 'guest_' + secrets.token_hex(8)
            session['solo_mode'] = False
            return jsonify({'status': 'success'})
    return jsonify({'error': 'Invalid Code'}), 404

@app.route('/room/swipe', methods=['POST'])
def swipe():
    code = session.get('active_room')
    uid = session.get('my_user_id')
    data = request.json
    mid, title, thumb = str(data.get('movie_id')), data.get('title'), data.get('thumb')
    user_id = data.get('user_id')
    user_id = _provider_user_id_from_request() or user_id
    if not user_id:
        return jsonify({'error': 'Missing Jellyfin user identity', 'match': False}), 400

    if not code: return jsonify({'match': False})

    with get_db() as conn:
        conn.execute('INSERT INTO swipes (room_code, movie_id, user_id, direction) VALUES (?, ?, ?, ?)',
                     (code, mid, uid, data.get('direction')))

        if data.get('direction') == 'right':
            room = conn.execute('SELECT solo_mode FROM rooms WHERE pairing_code = ?', (code,)).fetchone()
            if room and room['solo_mode']:
                conn.execute(
                    'INSERT OR IGNORE INTO matches (room_code, movie_id, title, thumb, status, user_id) VALUES (?, ?, ?, ?, "active", ?)',
                    (code, mid, title, thumb, user_id)
                )
                return jsonify({'match': True, 'title': title, 'thumb': thumb, 'solo': True})

            other_swipe = conn.execute('SELECT user_id FROM swipes WHERE room_code = ? AND movie_id = ? AND direction = "right" AND user_id != ?',
                                     (code, mid, uid)).fetchone()

            if other_swipe:
                conn.execute(
                    'INSERT OR IGNORE INTO matches (room_code, movie_id, title, thumb, status, user_id) VALUES (?, ?, ?, ?, "active", ?)',
                    (code, mid, title, thumb, user_id)
                )

                if other_swipe['user_id'] and other_swipe['user_id'] != user_id:
                    conn.execute(
                        'INSERT OR IGNORE INTO matches (room_code, movie_id, title, thumb, status, user_id) VALUES (?, ?, ?, ?, "active", ?)',
                        (code, mid, title, thumb, other_swipe['user_id'])
                    )

                match_data = json.dumps({'title': title, 'thumb': thumb, 'ts': time.time()})
                conn.execute('UPDATE rooms SET last_match_data = ? WHERE pairing_code = ?', (match_data, code))

                return jsonify({'match': True, 'title': title, 'thumb': thumb})

    return jsonify({'match': False})

@app.route('/matches')
def get_matches():
    code = session.get('active_room')
    view = request.args.get('view')
    user_id = _provider_user_id_from_request()
    if not user_id:
        return jsonify([]) if view else jsonify([])

    with get_db() as conn:
        if view == 'history':
            rows = conn.execute('SELECT title, thumb, movie_id FROM matches WHERE status = "archived" AND user_id = ?', (user_id,)).fetchall()
        else:
            rows = conn.execute('SELECT title, thumb, movie_id FROM matches WHERE room_code = ? AND status = "active" AND user_id = ?', (code, user_id)).fetchall()
        return jsonify([dict(row) for row in rows])

@app.route('/room/quit', methods=['POST'])
def quit_room():
    code = session.get('active_room')
    if code:
        with get_db() as conn:
            conn.execute('DELETE FROM rooms WHERE pairing_code = ?', (code,))
            conn.execute('DELETE FROM swipes WHERE room_code = ?', (code,))
            conn.execute('UPDATE matches SET status = "archived", room_code = "HISTORY" WHERE room_code = ? AND status = "active"', (code,))
        session.pop('active_room', None)
        session.pop('solo_mode', None)
    return jsonify({'status': 'session_ended'})

@app.route('/matches/delete', methods=['POST'])
def delete_match():
    mid = str(request.json.get('movie_id'))
    user_id = _provider_user_id_from_request()
    if not user_id:
        return jsonify({'error': 'Missing user identity'}), 400
    with get_db() as conn:
        conn.execute('DELETE FROM matches WHERE movie_id = ? AND user_id = ?', (mid, user_id))
    return jsonify({'status': 'deleted'})

@app.route('/undo', methods=['POST'])
def undo_swipe():
    code = session.get('active_room')
    uid = session.get('my_user_id')
    mid = str(request.json.get('movie_id'))
    user_id = _provider_user_id_from_request()
    if not user_id:
        return jsonify({'error': 'Missing user identity'}), 400
    with get_db() as conn:
        conn.execute('DELETE FROM swipes WHERE room_code = ? AND movie_id = ? AND user_id = ?', (code, mid, uid))
        conn.execute('DELETE FROM matches WHERE room_code = ? AND movie_id = ? AND status = "active" AND user_id = ?', (code, mid, user_id))
    return jsonify({'status': 'undone'})

@app.route('/plex/server-info')
def get_server_info():
    try:
        return jsonify(get_provider().server_info())
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/movies')
def get_movies():
    code = session.get('active_room')
    genre = request.args.get('genre')
    if not code: return jsonify([])
    with get_db() as conn:
        if genre:
            new_list = get_provider().fetch_deck(genre)
            conn.execute('UPDATE rooms SET movie_data = ?, current_genre = ? WHERE pairing_code = ?', (json.dumps(new_list), genre, code))
            return jsonify(new_list)
        room = conn.execute('SELECT movie_data FROM rooms WHERE pairing_code = ?', (code,)).fetchone()
        return Response(room['movie_data'], mimetype='application/json') if room else jsonify([])

@app.route('/genres')
def get_genres():
    try:
        return jsonify(get_provider().list_genres())
    except Exception:
        return jsonify([])

@app.route('/room/status')
def room_status():
    code = session.get('active_room')
    if not code: return jsonify({'ready': False})
    with get_db() as conn:
        room = conn.execute('SELECT ready, current_genre, solo_mode, last_match_data FROM rooms WHERE pairing_code = ?', (code,)).fetchone()
        if room:
            last_match = json.loads(room['last_match_data']) if room['last_match_data'] else None
            return jsonify({'ready': bool(room['ready']), 'genre': room['current_genre'], 'solo': bool(room['solo_mode']), 'last_match': last_match})
        return jsonify({'ready': False})

@app.route('/room/stream')
def room_stream():
    code = session.get('active_room')
    if not code:
        return Response("data: {}\n\n", mimetype='text/event-stream')

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

@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')

@app.route('/sw.js')
def serve_sw():
    return send_from_directory('data', 'sw.js', mimetype='application/javascript')

@app.route('/static/<path:path>')
def serve_static(path): return send_from_directory('static', path)


# Initialize database at module load time
init_db()
