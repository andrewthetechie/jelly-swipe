# Architecture

**Analysis Date:** 2026-04-23

## Pattern Overview

**Overall:** Single-process monolithic Flask application with server-rendered shell and rich client-side behavior in one HTML template.

**Key Characteristics:**
- All HTTP routes and business logic live in `app.py` (~460 lines).
- Real-time-ish coordination uses Server-Sent Events (SSE) plus short-interval polling on the server side over SQLite.
- Plex is the source of truth for titles/posters; SQLite holds ephemeral session state (rooms, swipes, matches).

## Layers

**Presentation (browser):**
- Purpose: UI, swipe gestures, modals, EventSource client for room updates.
- Location: `templates/index.html`, `data/index.html` (parallel PWA-oriented asset).
- Contains: Inline CSS and JavaScript calling Flask JSON routes.
- Depends on: Flask-served JSON, static files under `static/`, service worker from `data/sw.js`.
- Used by: End users in the browser or installed PWA.

**HTTP / application layer:**
- Purpose: Routing, session management, authorization headers for Plex user operations, JSON APIs.
- Location: `app.py`
- Contains: `@app.route` handlers, `init_db`, helpers `get_plex`, `fetch_plex_movies`, DB access via `get_db()`.
- Depends on: `plexapi`, `requests`, stdlib `sqlite3`, env configuration.
- Used by: Front-end in `templates/index.html`.

**Data layer:**
- Purpose: Persist rooms, swipe rows, match rows; drive SSE state transitions.
- Location: SQLite schema and queries in `app.py` (`init_db`, route handlers).
- Contains: Tables `rooms`, `swipes`, `matches` with pragmatic `ALTER TABLE` migrations on startup.
- Depends on: Filesystem path `DB_PATH`.
- Used by: All room/match routes and `/room/stream` generator.

**Integration layer:**
- Purpose: Talk to Plex and TMDB; stream poster bytes through the app.
- Location: `app.py` functions using `PlexServer`, `MyPlexAccount`, `requests.get`, `/proxy`.
- Depends on: Network, tokens in environment.
- Used by: Movie listing, trailers, cast, watchlist, poster URLs via `/proxy`.

## Data Flow

**Host creates room:**

1. Client `POST /room/create` — server generates 4-digit `pairing_code`, fetches shuffled movies from Plex (`fetch_plex_movies`), stores JSON in `rooms.movie_data`, sets Flask session (`app.py`).
2. Guest `POST /room/join` with code — `rooms.ready` set; session assigned guest `my_user_id`.
3. Clients open `EventSource` to `/room/stream` — generator polls SQLite every ~1.5s and emits JSON when `ready`, `genre`, or `last_match` changes (`app.py`).

**Swipe and match:**

1. Client `POST /room/swipe` with direction and movie fields — insert into `swipes`.
2. If solo mode, right swipes insert into `matches` immediately; else server looks for another user's right swipe on same `movie_id` (`app.py`).
3. On mutual match, `last_match_data` JSON on `rooms` updated; SSE consumers receive `last_match` payload.

**State Management:**
- Server: SQLite rows per room; in-memory Plex/genre caches (`_plex_instance`, `_genre_cache`).
- Client: JavaScript state in `templates/index.html` (not modularized); session cookie for Flask session.

## Key Abstractions

**Room record:**
- Purpose: Tie pairing code, serialized movie deck, readiness, genre label, solo flag, last match notification blob.
- Examples: `rooms` table and `create_room`, `/movies`, `/room/status` in `app.py`.
- Pattern: Single JSON blob `movie_data` for the deck; refetched when genre changes.

**Plex connection singleton:**
- Purpose: Reuse `PlexServer` until errors trigger `reset_plex()` and reconnect.
- Examples: `get_plex`, `reset_plex` in `app.py`.
- Pattern: Lazy global with manual invalidation on exceptions.

## Entry Points

**WSGI / CLI entry:**
- Location: `app.py` — `app = Flask(__name__)`; `init_db()` runs at import; `if __name__ == "__main__"` runs dev server.
- Triggers: Gunicorn/uwsgi not in repo — Docker CMD runs `python app.py` (`Dockerfile`).
- Responsibilities: Wire routes, enforce env vars, start DB.

**Browser entry:**
- Location: `GET /` → `render_template('index.html')` in `app.py`.
- Triggers: User navigates to app origin.
- Responsibilities: Load SPA-like shell and client script.

## Error Handling

**Strategy:** Broad `try`/`except` around Plex and TMDB calls; often returns JSON `{ 'error': str(e) }` with 4xx/5xx.

**Patterns:**
- Plex operations: retry path via `reset_plex()` then second attempt (`fetch_plex_movies`, `get_trailer`, etc. in `app.py`).
- TMDB: first search result used without disambiguation — failures surface as 404/500 JSON.

## Cross-Cutting Concerns

**Logging:** Implicit Werkzeug request logging only; no application-level logger.

**Validation:** `/proxy` restricts `path` query to prefix `/library/metadata/`; room codes validated by DB lookup; minimal schema validation on JSON bodies (mostly `.get` with defaults).

**Authentication:** Admin token for Plex server operations; per-user Plex token header for user-specific endpoints; Flask signed session cookie.

---

*Architecture analysis: 2026-04-23*
