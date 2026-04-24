<!-- gsd-project-start source:PROJECT.md -->
## Project

**Jelly Swipe**

Jelly Swipe is a small Flask app for shared “Tinder for movies” sessions: a host creates a room, guests join, everyone swipes on a deck pulled from a home media server, and matches surface when two people swipe right on the same title. Trailers and cast come from TMDB. **v1.0** shipped **Jellyfin** as a first-class alternative alongside Plex (one backend per deployment). **v1.1** is the public rename and packaging under **AndrewTheTechie** (see `README.md` / `LICENSE` for upstream fork link).

**Core Value:** **Users can run a swipe session backed by either Plex or Jellyfin** (one backend per deployment), with library browsing and deck behavior equivalent to today’s Plex path.

### Constraints

- **Compatibility**: Support recent stable Jellyfin (10.8+) unless research proves a narrower window; call out version assumptions in README.
- **Security**: Do not log tokens; prefer headers over query-string API keys; HTTPS assumed for remote servers.
- **Minimal churn**: Prefer a clear provider abstraction over duplicating route handlers, while keeping the diff reviewable.
<!-- gsd-project-end -->

<!-- gsd-stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.11 — All server logic in `app.py` (see `Dockerfile` base image `python:3.11-slim`).
- HTML, CSS, JavaScript — Embedded in `templates/index.html` and duplicated/simplified in `data/index.html` (PWA-oriented copy).
- YAML — `docker-compose.yml`, `.github/workflows/docker-image.yml`.
- Shell / deployment notes — `docker run.txt`.
## Runtime
- CPython 3.11 inside Docker (`Dockerfile` `CMD ["python", "app.py"]`).
- Local dev: `python app.py` when `__name__ == "__main__"` binds `0.0.0.0:5005` in `app.py`.
- pip (no lockfile in repo; dependencies pinned only via `requirements.txt` text).
## Frameworks
- Flask — Web app, routing, sessions, `render_template`, JSON responses (`app.py`).
- Werkzeug — `ProxyFix` middleware for reverse-proxy headers (`app.py`).
- Not detected — No pytest/unittest config or test dependencies in `requirements.txt`.
- Docker — Image build in `Dockerfile`; compose in `docker-compose.yml`.
- GitHub Actions — `docker/build-push-action` in `.github/workflows/docker-image.yml`.
## Key Dependencies
- `flask` — HTTP API, SSE (`/room/stream`), static/template serving.
- `plexapi` — `PlexServer`, `MyPlexAccount` for library and watchlist (`app.py`).
- `requests` — TMDB JSON APIs and Plex image proxy streaming (`app.py`).
- `werkzeug` — Proxy-aware WSGI stack.
- SQLite3 — Standard library; persistent rooms/swipes/matches at `DB_PATH` in `app.py` (`/app/data/jellyswipe.db` by default in container).
## Configuration
- Required at process start: `PLEX_URL`, `PLEX_TOKEN`, `TMDB_API_KEY`, `FLASK_SECRET` (validated in `app.py`; process exits with `RuntimeError` if missing).
- Optional in practice vs README: README describes TMDB as optional for trailers, but code requires `TMDB_API_KEY` to boot.
- `Dockerfile` — `pip install -r requirements.txt`, copies repo, exposes port 5005.
- `docker-compose.yml` — Documents env vars and volume mounts for `./data` and `./static`.
## Platform Requirements
- Python 3.11+ compatible environment, network access to Plex and TMDB, writable `data/` directory for SQLite when not using default container path.
- Linux container or host running Flask; reverse proxy with HTTPS recommended for PWA install (see `README.md`); outbound HTTPS to `plex.tv`, `api.themoviedb.org`, and the configured `PLEX_URL`.
<!-- gsd-stack-end -->

<!-- gsd-conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Single backend module `app.py`; template `templates/index.html`; static assets under `static/` with descriptive names.
- Use `snake_case` for Python functions and helpers (`get_db`, `fetch_plex_movies`, `init_db`, `room_status`) in `app.py`.
- `snake_case` for locals and module-level names (`pairing_code`, `movie_list`, `_plex_instance`).
- UPPER_SNAKE for module-level configuration derived from env (`PLEX_URL`, `DB_PATH`, `CLIENT_ID`).
- Not applicable — No `typing` annotations or `mypy` config; SQLite rows use `sqlite3.Row` factory in `get_db()`.
## Code Style
- No Black, Ruff, or flake8 config files in repo — style is informal consistent with CPython defaults.
- Frequent one-line early returns in route handlers (`app.py`), e.g. `def index(): return render_template('index.html')`.
- Not detected — Add project tooling if team wants enforced style.
## Import Organization
- Not applicable — No `src` layout or import aliases.
## Error Handling
- Wrap external IO (Plex, TMDB) in `try`/`except`, often returning `jsonify({'error': str(e)}), 500` to clients (`get_trailer`, `get_cast`, `watchlist` in `app.py`).
- Some routes return empty structures on failure (`get_cast` returns `cast` list with error payload).
- Generator in `/room/stream` swallows generic exceptions and continues polling (`app.py`).
## Logging
- Prefer adding structured `logging` calls if debugging production issues — not established today.
## Comments
- Sparse inline comments; schema migration blocks in `init_db()` are self-documenting via SQL strings.
- Not used — Client code is plain `<script>` in `templates/index.html`.
## Function Design
## Module Design
<!-- gsd-conventions-end -->

<!-- gsd-architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- All HTTP routes and business logic live in `app.py` (~460 lines).
- Real-time-ish coordination uses Server-Sent Events (SSE) plus short-interval polling on the server side over SQLite.
- Plex is the source of truth for titles/posters; SQLite holds ephemeral session state (rooms, swipes, matches).
## Layers
- Purpose: UI, swipe gestures, modals, EventSource client for room updates.
- Location: `templates/index.html`, `data/index.html` (parallel PWA-oriented asset).
- Contains: Inline CSS and JavaScript calling Flask JSON routes.
- Depends on: Flask-served JSON, static files under `static/`, service worker from `data/sw.js`.
- Used by: End users in the browser or installed PWA.
- Purpose: Routing, session management, authorization headers for Plex user operations, JSON APIs.
- Location: `app.py`
- Contains: `@app.route` handlers, `init_db`, helpers `get_plex`, `fetch_plex_movies`, DB access via `get_db()`.
- Depends on: `plexapi`, `requests`, stdlib `sqlite3`, env configuration.
- Used by: Front-end in `templates/index.html`.
- Purpose: Persist rooms, swipe rows, match rows; drive SSE state transitions.
- Location: SQLite schema and queries in `app.py` (`init_db`, route handlers).
- Contains: Tables `rooms`, `swipes`, `matches` with pragmatic `ALTER TABLE` migrations on startup.
- Depends on: Filesystem path `DB_PATH`.
- Used by: All room/match routes and `/room/stream` generator.
- Purpose: Talk to Plex and TMDB; stream poster bytes through the app.
- Location: `app.py` functions using `PlexServer`, `MyPlexAccount`, `requests.get`, `/proxy`.
- Depends on: Network, tokens in environment.
- Used by: Movie listing, trailers, cast, watchlist, poster URLs via `/proxy`.
## Data Flow
- Server: SQLite rows per room; in-memory Plex/genre caches (`_plex_instance`, `_genre_cache`).
- Client: JavaScript state in `templates/index.html` (not modularized); session cookie for Flask session.
## Key Abstractions
- Purpose: Tie pairing code, serialized movie deck, readiness, genre label, solo flag, last match notification blob.
- Examples: `rooms` table and `create_room`, `/movies`, `/room/status` in `app.py`.
- Pattern: Single JSON blob `movie_data` for the deck; refetched when genre changes.
- Purpose: Reuse `PlexServer` until errors trigger `reset_plex()` and reconnect.
- Examples: `get_plex`, `reset_plex` in `app.py`.
- Pattern: Lazy global with manual invalidation on exceptions.
## Entry Points
- Location: `app.py` — `app = Flask(__name__)`; `init_db()` runs at import; `if __name__ == "__main__"` runs dev server.
- Triggers: Gunicorn/uwsgi not in repo — Docker CMD runs `python app.py` (`Dockerfile`).
- Responsibilities: Wire routes, enforce env vars, start DB.
- Location: `GET /` → `render_template('index.html')` in `app.py`.
- Triggers: User navigates to app origin.
- Responsibilities: Load SPA-like shell and client script.
## Error Handling
- Plex operations: retry path via `reset_plex()` then second attempt (`fetch_plex_movies`, `get_trailer`, etc. in `app.py`).
- TMDB: first search result used without disambiguation — failures surface as 404/500 JSON.
## Cross-Cutting Concerns
<!-- gsd-architecture-end -->

<!-- gsd-skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.cursor/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- gsd-skills-end -->

<!-- gsd-workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- gsd-workflow-end -->



<!-- gsd-profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- gsd-profile-end -->
