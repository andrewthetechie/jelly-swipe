# Technology Stack

**Analysis Date:** 2026-04-23

## Languages

**Primary:**
- Python 3.11 — All server logic in `app.py` (see `Dockerfile` base image `python:3.11-slim`).

**Secondary:**
- HTML, CSS, JavaScript — Embedded in `templates/index.html` and duplicated/simplified in `data/index.html` (PWA-oriented copy).
- YAML — `docker-compose.yml`, `.github/workflows/docker-image.yml`.
- Shell / deployment notes — `docker run.txt`.

## Runtime

**Environment:**
- CPython 3.11 inside Docker (`Dockerfile` `CMD ["python", "app.py"]`).
- Local dev: `python app.py` when `__name__ == "__main__"` binds `0.0.0.0:5005` in `app.py`.

**Package Manager:**
- pip (no lockfile in repo; dependencies pinned only via `requirements.txt` text).

## Frameworks

**Core:**
- Flask — Web app, routing, sessions, `render_template`, JSON responses (`app.py`).
- Werkzeug — `ProxyFix` middleware for reverse-proxy headers (`app.py`).

**Testing:**
- Not detected — No pytest/unittest config or test dependencies in `requirements.txt`.

**Build/Dev:**
- Docker — Image build in `Dockerfile`; compose in `docker-compose.yml`.
- GitHub Actions — `docker/build-push-action` in `.github/workflows/docker-image.yml`.

## Key Dependencies

**Critical:**
- `flask` — HTTP API, SSE (`/room/stream`), static/template serving.
- `plexapi` — `PlexServer`, `MyPlexAccount` for library and watchlist (`app.py`).
- `requests` — TMDB JSON APIs and Plex image proxy streaming (`app.py`).
- `werkzeug` — Proxy-aware WSGI stack.

**Infrastructure:**
- SQLite3 — Standard library; persistent rooms/swipes/matches at `DB_PATH` in `app.py` (`/app/data/jellyswipe.db` by default in container).

## Configuration

**Environment:**
- Required at process start: `PLEX_URL`, `PLEX_TOKEN`, `TMDB_API_KEY`, `FLASK_SECRET` (validated in `app.py`; process exits with `RuntimeError` if missing).
- Optional in practice vs README: README describes TMDB as optional for trailers, but code requires `TMDB_API_KEY` to boot.

**Build:**
- `Dockerfile` — `pip install -r requirements.txt`, copies repo, exposes port 5005.
- `docker-compose.yml` — Documents env vars and volume mounts for `./data` and `./static`.

## Platform Requirements

**Development:**
- Python 3.11+ compatible environment, network access to Plex and TMDB, writable `data/` directory for SQLite when not using default container path.

**Production:**
- Linux container or host running Flask; reverse proxy with HTTPS recommended for PWA install (see `README.md`); outbound HTTPS to `plex.tv`, `api.themoviedb.org`, and the configured `PLEX_URL`.

---

*Stack analysis: 2026-04-23*
