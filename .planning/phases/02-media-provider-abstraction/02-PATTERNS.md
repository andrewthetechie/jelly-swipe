# Phase 2 — Pattern mapping (media provider abstraction)

**Repo:** `kino-swipe`  
**Analog source:** `app.py` (Flask monolith; all current Plex library I/O)

This document maps planned artifacts to **closest existing analogs** so implementers can lift behavior mechanically while preserving retry/reset, JSON error handling, and route shapes.

---

## Files to create / modify

### Create (`media_provider/` package)

| Path (proposed) | Role | Closest analog in `app.py` |
|-----------------|------|----------------------------|
| `media_provider/__init__.py` | Public exports (`get_provider`, types if needed) | N/A — new surface; mirrors “import Plex bits lazily” style of `get_plex()` |
| `media_provider/base.py` | `abc.ABC` contract (genres, deck, resolve-by-id, server info, image/proxy behavior) | Behaviors currently split across `get_plex_genres`, `fetch_plex_movies`, `fetchItem` usage, `get_server_info`, `proxy` |
| `media_provider/plex_library.py` (name discretionary) | `PlexLibraryProvider` — `plexapi` + caching + retry/reset | `get_plex`, `reset_plex`, `_plex_instance`, `_genre_cache`, `get_plex_genres`, `fetch_plex_movies`, Plex branches of trailer/cast/server-info/proxy |
| `media_provider/factory.py` | `get_provider()`, `reset()` / invalidation; `MEDIA_PROVIDER=jellyfin` fail-fast | `get_plex` jellyfin guard + `MEDIA_PROVIDER` normalization at top of `app.py` |

**Explicitly not created in Phase 2:** `jellyfin*.py` / Jellyfin client module (Phase 3).

### Modify

| Path | Role | Notes |
|------|------|--------|
| `app.py` | Routes call `get_provider()` instead of `get_plex` / `fetch_plex_movies` / `get_plex_genres`; remove module-level `_plex_instance` / `_genre_cache` and free `get_plex`/`reset_plex` once migrated | Keep `/auth/*`, `/watchlist/add` as Plex-specific surfaces (may still call narrow resolve-by-id helper or shared Plex code **without** expanding ABC to “watchlist”) |

**Unchanged for packaging:** `Dockerfile` uses `COPY . .` — new package is picked up automatically; no entrypoint change required (`CMD ["python", "app.py"]`).

---

## Classification by responsibility

| Concern | Today | After Phase 2 |
|---------|--------|----------------|
| **Singleton + invalidation** | `_plex_instance`, `get_plex`, `reset_plex` | Factory-held provider + `reset()` |
| **Genre cache** | `_genre_cache` global in `app.py` | Cache on provider instance (per D-08) |
| **Deck JSON** | `fetch_plex_movies` | Provider method backing same card fields + shuffle / Recently Added / Sci-Fi mapping |
| **Genres list** | `get_plex_genres` | Provider method |
| **Resolve movie by library id (TMDB prep)** | `get_plex().fetchItem` in `get_trailer`, `get_cast`, watchlist | Single provider path; TMDB HTTP can stay in routes |
| **Server identity JSON** | `/plex/server-info` | Provider method; route unchanged path/shape |
| **Poster upstream** | `/proxy` | Provider owns validation + fetch; route stays thin |
| **Out of ABC** | Plex.tv pins, watchlist add | Remain in `app.py` with optional internal reuse of resolve-by-id |

---

## Analog patterns (code excerpts)

### A. Env + `MEDIA_PROVIDER` normalization (factory / fail-fast alignment)

```9:20:app.py
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
```

### B. Lazy singleton + jellyfin guard + `reset_plex`

```97:113:app.py
def get_plex():
    global _plex_instance
    if MEDIA_PROVIDER != "plex":
        raise RuntimeError(
            "Plex library access is unavailable when MEDIA_PROVIDER=jellyfin "
            "(not implemented until later phases)."
        )
    from plexapi.server import PlexServer

    if _plex_instance is not None:
        return _plex_instance
    _plex_instance = PlexServer(PLEX_URL, ADMIN_TOKEN)
    return _plex_instance

def reset_plex():
    global _plex_instance
    _plex_instance = None
```

### C. Genre list + module-level cache

```115:127:app.py
def get_plex_genres():
    global _genre_cache
    if _genre_cache is not None:
        return _genre_cache
    try:
        plex = get_plex()
        section = plex.library.section('Movies')
        genres = sorted({g.title for g in section.listFilterChoices(field='genre')})
        display = ["Sci-Fi" if g == "Science Fiction" else g for g in genres]
        _genre_cache = display
        return display
    except Exception:
        return []
```

### D. Deck fetch — retry section access, genre semantics, card shape

```129:162:app.py
def fetch_plex_movies(genre_name=None):
    try:
        plex = get_plex()
        movie_section = plex.library.section('Movies')
    except Exception:
        reset_plex()
        plex = get_plex()
        movie_section = plex.library.section('Movies')
    do_shuffle = True
    search_genre = "Science Fiction" if genre_name == "Sci-Fi" else genre_name

    if genre_name == "Recently Added":
        movies = movie_section.search(libtype='movie', sort='addedAt:desc', maxresults=100)
        do_shuffle = False
    elif search_genre and search_genre != "All":
        movies = movie_section.search(libtype='movie', genre=search_genre, sort='random', maxresults=100)
        if not movies and search_genre != genre_name:
            movies = movie_section.search(libtype='movie', genre=genre_name, sort='random', maxresults=100)
    else:
        movies = movie_section.search(libtype='movie', sort='random', maxresults=150)
    
    movie_list = []
    for m in movies:
        runtime_str = ""
        if m.duration:
            hrs = m.duration // 3600000
            mins = (m.duration % 3600000) // 60000
            runtime_str = f"{hrs}h {mins}m" if hrs > 0 else f"{mins}m"
        movie_list.append({
            'id': str(m.ratingKey), 'title': m.title, 'summary': m.summary, 'thumb': f"/proxy?path={m.thumb}",
            'rating': m.audienceRating or m.rating, 'duration': runtime_str, 'year': m.year
        })
    if do_shuffle: random.shuffle(movie_list)
    return movie_list
```

### E. Routes — `try` / `reset` / retry on `fetchItem` (TMDB chain)

```167:175:app.py
@app.route('/get-trailer/<movie_id>')
def get_trailer(movie_id):
    try:
        try:
            plex = get_plex()
            item = plex.fetchItem(int(movie_id))
        except Exception:
            reset_plex()
            item = get_plex().fetchItem(int(movie_id))
        search_url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={item.title}&year={item.year}"
```

### F. Server info JSON shape (must stay stable in Plex mode)

```382:392:app.py
@app.route('/plex/server-info')
def get_server_info():
    try:
        try:
            plex = get_plex()
            return jsonify({'machineIdentifier': plex.machineIdentifier, 'name': plex.friendlyName})
        except Exception:
            reset_plex()
            plex = get_plex()
            return jsonify({'machineIdentifier': plex.machineIdentifier, 'name': plex.friendlyName})
    except Exception as e: return jsonify({'error': str(e)}), 500
```

### G. `/proxy` — mode gate, path validation, upstream stream

```478:486:app.py
@app.route('/proxy')
def proxy():
    if MEDIA_PROVIDER != "plex" or not PLEX_URL or not ADMIN_TOKEN:
        abort(503)
    path = request.args.get('path')
    if not path or not path.startswith("/library/metadata/"):
        abort(403)
    res = requests.get(f"{PLEX_URL}{path}?X-Plex-Token={ADMIN_TOKEN}", stream=True)
    return Response(res.content, content_type=res.headers['Content-Type'])
```

### H. Room + genre routes (integration points — swap to `get_provider()`)

```257:267:app.py
@app.route('/room/create', methods=['POST'])
def create_room():
    pairing_code = str(random.randint(1000, 9999))
    movie_list = fetch_plex_movies()
    with get_db() as conn:
        conn.execute('INSERT INTO rooms (pairing_code, movie_data, ready, current_genre, solo_mode) VALUES (?, ?, ?, ?, ?)', 
                     (pairing_code, json.dumps(movie_list), 0, 'All', 0))
```

```394:409:app.py
@app.route('/movies')
def get_movies():
    code = session.get('active_room')
    genre = request.args.get('genre')
    if not code: return jsonify([])
    with get_db() as conn:
        if genre:
            new_list = fetch_plex_movies(genre)
            conn.execute('UPDATE rooms SET movie_data = ?, current_genre = ? WHERE pairing_code = ?', (json.dumps(new_list), genre, code))
            return jsonify(new_list)
        room = conn.execute('SELECT movie_data FROM rooms WHERE pairing_code = ?', (code,)).fetchone()
        return Response(room['movie_data'], mimetype='application/json') if room else jsonify([])

@app.route('/genres')
def get_genres():
    return jsonify(get_plex_genres())
```

### I. Out-of-scope route (stay in `app.py`; shows same `fetchItem` retry pattern)

```214:232:app.py
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
        try:
            plex = get_plex()
            item = plex.fetchItem(int(movie_id))
        except Exception:
            reset_plex()
            item = get_plex().fetchItem(int(movie_id))
        account.addToWatchlist(item)
```

---

## Grep invariants (post-migration checklist)

- `get_plex`, `reset_plex`, `fetch_plex_movies`, `get_plex_genres` should disappear from `app.py` (or exist only in comments) except where research explicitly allows a narrow exception for watchlist.
- `get_provider` (or chosen factory name) appears at former library call sites; `plexapi` imports in `app.py` limited to out-of-scope routes per plan allowlist.

---

## PATTERN MAPPING COMPLETE
