# External Integrations

**Analysis Date:** 2026-04-23

## APIs & External Services

**Plex Media Server (admin / library):**
- Used for movie metadata, posters, library search, and item fetch — `plexapi.server.PlexServer` with `PLEX_URL` and `PLEX_TOKEN` in `app.py` (`get_plex`, `fetch_plex_movies`, trailer/cast helpers).
- Thumbnail proxy — `GET` to `{PLEX_URL}{path}` with `X-Plex-Token` query param in `/proxy` route (`app.py`).

**Plex.tv (OAuth-style pin flow):**
- Pin creation: `POST https://plex.tv/api/v2/pins?strong=true` with product headers (`/auth/plex-url` in `app.py`).
- Pin polling: `GET https://plex.tv/api/v2/pins/{pin_id}` (`/auth/check-returned-pin` in `app.py`).
- Client identifier constant: `CLIENT_ID = 'JellySwipe-AndrewTheTechie-2026'` in `app.py`.

**The Movie Database (TMDB) v3 REST:**
- Movie search and videos for trailers — `https://api.themoviedb.org/3/search/movie` and `/movie/{id}/videos` (`get_trailer` in `app.py`).
- Cast — `/movie/{id}/credits` (`get_cast` in `app.py`).
- API key from env `TMDB_API_KEY` (required at startup in `app.py`).

**Google Fonts (browser):**
- Stylesheet import for Allura font in `templates/index.html` and `data/index.html` (no server-side dependency).

## Data Storage

**Databases:**
- SQLite file at `/app/data/jellyswipe.db` by default in container (`DB_PATH` in `app.py`); host path `./data` mounted in `docker-compose.yml`.
- Schema created/migrated in `init_db()` in `app.py` (`rooms`, `swipes`, `matches`).

**File Storage:**
- Local filesystem — `data/` for DB and `data/sw.js`; `static/` for icons, manifest, images; `templates/` for `index.html`.

**Caching:**
- In-process only — `_genre_cache` and `_plex_instance` globals in `app.py` (not Redis or similar).

## Authentication & Identity

**Auth Provider:**
- Hybrid: Server uses admin `PLEX_TOKEN` for library access; end users obtain a Plex user token via pin flow and send `X-Plex-Token` for watchlist (`/watchlist/add`) and `X-Plex-User-ID` for per-user match views and undo (`app.py`).
- Flask `session` for room code, synthetic `my_user_id`, solo flag, pending pin.

## Monitoring & Observability

**Error Tracking:**
- None detected — Errors returned as JSON with exception strings in several routes (`app.py`).

**Logs:**
- Default Flask/Werkzeug logging when run directly; no structured logging module.

## CI/CD & Deployment

**Hosting:**
- Docker Hub image `andrewthetechie/jelly-swipe:latest` (see `README.md` and workflow tags).

**CI Pipeline:**
- GitHub Actions on push to `main` — builds and pushes Docker image (`.github/workflows/docker-image.yml`).

## Environment Configuration

**Required env vars:**
- `PLEX_URL`, `PLEX_TOKEN`, `FLASK_SECRET`, `TMDB_API_KEY` — enforced at import time in `app.py`.

**Secrets location:**
- Environment variables / compose `environment:` blocks; `.env` is gitignored (`.gitignore`) — do not commit values.

## Webhooks & Callbacks

**Incoming:**
- None — Room sync uses SSE (`/room/stream`) polling DB, not inbound webhooks.

**Outgoing:**
- Outbound HTTP only (Plex, plex.tv, TMDB); no registered outgoing webhooks.

---

*Integration audit: 2026-04-23*
