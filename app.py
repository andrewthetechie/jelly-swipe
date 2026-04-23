try:
    from pathlib import Path

    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

from flask import Flask, send_from_directory, jsonify, request, session, Response, render_template, abort
from werkzeug.middleware.proxy_fix import ProxyFix
import sqlite3, os, random, re, requests, json, secrets, time

# Default: repo ./data/kinoswipe.db (local dev). Docker: set DB_PATH=/app/data/kinoswipe.db or keep default when WORKDIR is /app.
_APP_ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.abspath(
    os.getenv("DB_PATH", os.path.join(_APP_ROOT, "data", "kinoswipe.db"))
)
CLIENT_ID = 'KinoSwipe-Bergasha-2026'


def _normalized_media_provider():
    raw = (os.getenv("MEDIA_PROVIDER") or "").strip().lower()
    if not raw:
        return "plex"
    if raw not in ("plex", "jellyfin"):
        raise RuntimeError(
            f"Invalid MEDIA_PROVIDER={os.getenv('MEDIA_PROVIDER')!r}; use 'plex' or 'jellyfin'"
        )
    return raw


MEDIA_PROVIDER = _normalized_media_provider()

missing = []
for v in ("TMDB_API_KEY", "FLASK_SECRET"):
    if not os.getenv(v):
        missing.append(v)
if MEDIA_PROVIDER == "plex":
    for v in ("PLEX_URL", "PLEX_TOKEN"):
        if not os.getenv(v):
            missing.append(v)
else:
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

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
app.secret_key = os.environ["FLASK_SECRET"]

PLEX_URL = os.getenv("PLEX_URL", "").rstrip("/")
ADMIN_TOKEN = os.getenv("PLEX_TOKEN")
JELLYFIN_URL = os.getenv("JELLYFIN_URL", "").rstrip("/")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

from media_provider import get_provider


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS rooms (pairing_code TEXT PRIMARY KEY, movie_data TEXT, ready INTEGER, current_genre TEXT, solo_mode INTEGER DEFAULT 0)')
        conn.execute('CREATE TABLE IF NOT EXISTS swipes (room_code TEXT, movie_id TEXT, user_id TEXT, direction TEXT, plex_id TEXT)')
        conn.execute('''CREATE TABLE IF NOT EXISTS matches (
            room_code TEXT, movie_id TEXT, title TEXT, thumb TEXT,
            status TEXT DEFAULT "active", plex_id TEXT,
            UNIQUE(room_code, movie_id, plex_id)
        )''')
        
        cursor = conn.execute("PRAGMA table_info(matches)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'status' not in columns:
            conn.execute('ALTER TABLE matches ADD COLUMN status TEXT DEFAULT "active"')
        if 'plex_id' not in columns:
            conn.execute('ALTER TABLE matches ADD COLUMN plex_id TEXT')
            
        cursor = conn.execute("PRAGMA table_info(swipes)")
        sw_cols = [col[1] for col in cursor.fetchall()]
        if 'plex_id' not in sw_cols:
            conn.execute('ALTER TABLE swipes ADD COLUMN plex_id TEXT')

        cursor = conn.execute("PRAGMA table_info(rooms)")
        room_cols = [col[1] for col in cursor.fetchall()]
        if 'solo_mode' not in room_cols:
            conn.execute('ALTER TABLE rooms ADD COLUMN solo_mode INTEGER DEFAULT 0')
        if 'last_match_data' not in room_cols:
            conn.execute('ALTER TABLE rooms ADD COLUMN last_match_data TEXT')

       
        conn.execute('DELETE FROM swipes WHERE room_code NOT IN (SELECT pairing_code FROM rooms)')

@app.route('/')
def index(): return render_template('index.html')

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
    except Exception as e:
        return jsonify({'error': str(e), 'cast': []}), 500

@app.route('/watchlist/add', methods=['POST'])
def add_to_watchlist():
    try:
        if MEDIA_PROVIDER != "plex":
            return jsonify({"error": "Watchlist is only available in Plex mode"}), 400
        data = request.json
        movie_id = data.get('movie_id')
        user_token = request.headers.get('X-Plex-Token')
        if not user_token: return jsonify({'error': 'Unauthorized'}), 401
        from plexapi.myplex import MyPlexAccount

        account = MyPlexAccount(token=user_token)
        # D-03: watchlist remains Plex-specific; provider used only for library item resolution.
        item = get_provider().resolve_item_for_tmdb(movie_id)
        account.addToWatchlist(item)
        return jsonify({'status': 'success'})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/auth/plex-url')
def get_plex_url():
    REDIRECT_URL = f"{request.scheme}://{request.host}"
    headers = {'X-Plex-Product': 'KinoSwipe', 'X-Plex-Client-Identifier': CLIENT_ID, 'Accept': 'application/json'}
    try:
        res = requests.post('https://plex.tv/api/v2/pins?strong=true', headers=headers).json()
        forward = f"{REDIRECT_URL}?pin_id={res['id']}"
        auth_url = f"https://app.plex.tv/auth/#!?clientID={CLIENT_ID}&code={res['code']}&context%5Bdevice%5D%5Bproduct%5D=KinoSwipe&forwardUrl={requests.utils.quote(forward, safe='')}"
        return jsonify({'auth_url': auth_url})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/auth/check-returned-pin')
def check_pin():
    pin_id = request.args.get('pin_id') or session.get('pending_pin_id')
    if not pin_id: return jsonify({'authToken': None})
    headers = {'X-Plex-Client-Identifier': CLIENT_ID, 'Accept': 'application/json'}
    res = requests.get(f"https://plex.tv/api/v2/pins/{pin_id}", headers=headers).json()
    token = res.get('authToken')
    if token: session.pop('pending_pin_id', None)
    return jsonify({'authToken': token})

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
    plex_id = data.get('plex_id')
    
    if not code: return jsonify({'match': False})
    
    with get_db() as conn:
        conn.execute('INSERT INTO swipes (room_code, movie_id, user_id, direction, plex_id) VALUES (?, ?, ?, ?, ?)', 
                     (code, mid, uid, data.get('direction'), plex_id))
        
        if data.get('direction') == 'right':
            room = conn.execute('SELECT solo_mode FROM rooms WHERE pairing_code = ?', (code,)).fetchone()
            if room and room['solo_mode']:
                conn.execute(
                    'INSERT OR IGNORE INTO matches (room_code, movie_id, title, thumb, status, plex_id) VALUES (?, ?, ?, ?, "active", ?)',
                    (code, mid, title, thumb, plex_id)
                )
                return jsonify({'match': True, 'title': title, 'thumb': thumb, 'solo': True})

            other_swipe = conn.execute('SELECT plex_id FROM swipes WHERE room_code = ? AND movie_id = ? AND direction = "right" AND user_id != ?', 
                                     (code, mid, uid)).fetchone()
            
            if other_swipe:
                conn.execute(
                    'INSERT OR IGNORE INTO matches (room_code, movie_id, title, thumb, status, plex_id) VALUES (?, ?, ?, ?, "active", ?)',
                    (code, mid, title, thumb, plex_id)
                )
             
                if other_swipe['plex_id'] and other_swipe['plex_id'] != plex_id:
                    conn.execute(
                        'INSERT OR IGNORE INTO matches (room_code, movie_id, title, thumb, status, plex_id) VALUES (?, ?, ?, ?, "active", ?)',
                        (code, mid, title, thumb, other_swipe['plex_id'])
                    )

                match_data = json.dumps({'title': title, 'thumb': thumb, 'ts': time.time()})
                conn.execute('UPDATE rooms SET last_match_data = ? WHERE pairing_code = ?', (match_data, code))

                return jsonify({'match': True, 'title': title, 'thumb': thumb})
                
    return jsonify({'match': False})

@app.route('/matches')
def get_matches():
    code = session.get('active_room')
    view = request.args.get('view')
    plex_id = request.headers.get('X-Plex-User-ID')
    
    with get_db() as conn:
        if view == 'history':
            rows = conn.execute('SELECT title, thumb, movie_id FROM matches WHERE status = "archived" AND plex_id = ?', (plex_id,)).fetchall()
        else:
            rows = conn.execute('SELECT title, thumb, movie_id FROM matches WHERE room_code = ? AND status = "active" AND plex_id = ?', (code, plex_id)).fetchall()
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
    plex_id = request.headers.get('X-Plex-User-ID')
    with get_db() as conn:
        conn.execute('DELETE FROM matches WHERE movie_id = ? AND plex_id = ?', (mid, plex_id))
    return jsonify({'status': 'deleted'})

@app.route('/undo', methods=['POST'])
def undo_swipe():
    code = session.get('active_room')
    uid = session.get('my_user_id')
    mid = str(request.json.get('movie_id'))
    plex_id = request.headers.get('X-Plex-User-ID')
    with get_db() as conn:
        conn.execute('DELETE FROM swipes WHERE room_code = ? AND movie_id = ? AND user_id = ?', (code, mid, uid))
        conn.execute('DELETE FROM matches WHERE room_code = ? AND movie_id = ? AND status = "active" AND plex_id = ?', (code, mid, plex_id))
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
    if MEDIA_PROVIDER == "plex":
        if not PLEX_URL or not ADMIN_TOKEN:
            abort(503)
        if not path.startswith("/library/metadata/"):
            abort(403)
        try:
            body, content_type = get_provider().fetch_library_image(path)
        except PermissionError:
            abort(403)
        return Response(body, content_type=content_type)
    if MEDIA_PROVIDER == "jellyfin":
        if not JELLYFIN_URL:
            abort(503)
        if not re.match(r"^jellyfin/[0-9a-fA-F-]{36}/Primary$", path):
            abort(403)
        try:
            body, content_type = get_provider().fetch_library_image(path)
        except PermissionError:
            abort(403)
        return Response(body, content_type=content_type)
    abort(503)

@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')

@app.route('/sw.js')
def serve_sw():
    return send_from_directory('data', 'sw.js', mimetype='application/javascript')

@app.route('/static/<path:path>')
def serve_static(path): return send_from_directory('static', path)


init_db()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5005)
