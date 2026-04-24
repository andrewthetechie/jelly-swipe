# Codebase Concerns

**Analysis Date:** 2026-04-23

## Tech Debt

**Monolithic `app.py`:**
- Issue: All routes, DB migrations, caching, and integrations live in one module (~460 lines, growing).
- Files: `app.py`
- Impact: Harder to test in isolation, higher merge conflict risk, unclear boundaries for new features.
- Fix approach: Split into blueprints (`room_routes.py`, `plex_service.py`) or a small `src/jelly_swipe/` package; keep `app.py` as thin factory.

**Duplicate front-end copies:**
- Issue: `templates/index.html` and `data/index.html` diverge (different styling/structure in headers).
- Files: `templates/index.html`, `data/index.html`
- Impact: Bug fixes or UX changes may be applied to only one copy; PWA vs server template confusion.
- Fix approach: Single source template or build step; document which file is authoritative for deployments.

**Global caches:**
- Issue: `_genre_cache` and `_plex_instance` survive for process lifetime without TTL.
- Files: `app.py`
- Impact: Genre list and Plex connection can become stale across library updates or auth changes until process restart.
- Fix approach: Time-based invalidation or explicit admin reload endpoint.

## Known Bugs

**README vs startup requirements for TMDB:**
- Symptoms: README states TMDB is optional for trailers, but `app.py` lists `TMDB_API_KEY` in `required` env vars and raises if missing.
- Files: `README.md`, `app.py`
- Trigger: Deploy without TMDB key following README "optional" guidance.
- Workaround: Provide any placeholder key or align code with docs (make variable optional).

**Docker Compose env incomplete vs code:**
- Symptoms: `docker-compose.yml` omits `TMDB_API_KEY` while application requires it at startup.
- Files: `docker-compose.yml`, `app.py`
- Trigger: `docker compose up` using only compose file as reference.
- Workaround: Add `TMDB_API_KEY` to compose environment block.

## Security Considerations

**Proxy route token forwarding:**
- Risk: `/proxy` streams Plex content using admin token query parameter (`app.py`).
- Files: `app.py`
- Current mitigation: Path prefix check `path.startswith("/library/metadata/")` before forwarding.
- Recommendations: Rate-limit `/proxy`; consider signed short-lived URLs instead of exposing full Plex paths to clients; ensure reverse proxy blocks open redirects.

**Broad exception reporting:**
- Risk: `str(e)` in JSON errors can leak internal details to browsers (`get_trailer`, `get_cast`, auth routes).
- Files: `app.py`
- Current mitigation: None beyond generic try/except.
- Recommendations: Log full traceback server-side; return generic client messages in production.

**Session and CSRF:**
- Risk: JSON POST endpoints rely on browser same-site session cookie behavior; no explicit CSRF tokens on mutating routes.
- Files: `app.py`, `templates/index.html`
- Current mitigation: Same-site deployment assumptions.
- Recommendations: Evaluate Flask-WTF or double-submit cookie if exposing app across origins.

## Performance Bottlenecks

**SSE polling loop:**
- Problem: `/room/stream` wakes every ~1.5s per connected client and hits SQLite (`app.py`).
- Files: `app.py`
- Cause: Synchronous polling design; SQLite under concurrent readers/writers.
- Improvement path: Longer poll interval with push on write (channel/redis), or WebSocket with shared pub/sub; upgrade DB if scale demands.

**Plex movie fetch on room create:**
- Problem: `create_room` blocks on `fetch_plex_movies()` network + CPU work.
- Files: `app.py`
- Cause: Synchronous Plex search up to 150 titles before response.
- Improvement path: Background prefetch or lazy deck fill with loading UI.

## Fragile Areas

**TMDB first-result matching:**
- Files: `app.py` (`get_trailer`, `get_cast`)
- Why fragile: Uses first TMDB search hit for title+year — collisions and wrong-year matches produce incorrect trailers/cast.
- Safe modification: Add user-visible pick or TMDB id from Plex metadata if available.
- Test coverage: No automated tests for disambiguation.

**Schema migrations in `init_db`:**
- Files: `app.py`
- Why fragile: Ad-hoc `PRAGMA table_info` checks; easy to miss ordering or new column defaults when adding features.
- Safe modification: Introduce versioned migrations (Alembic) if schema complexity grows.

## Scaling Limits

**SQLite + multi-worker:**
- Current capacity: Single-file DB suits single-container or single-worker Flask.
- Limit: Multiple gunicorn workers or horizontal replicas cause file locking contention and inconsistent SSE views.
- Scaling path: External database (Postgres) and centralized pub/sub for room events.

**4-digit room codes:**
- Current capacity: ~9000 codes; random collision possible under high churn (low probability).
- Limit: Guest joins wrong active room if collision occurs.
- Scaling path: Longer codes or UUID room ids with shareable short tokens.

## Dependencies at Risk

**`plexapi` / Plex server API drift:**
- Risk: Undocumented Plex API changes can break `PlexServer` usage.
- Impact: Movie fetch, watchlist, proxy paths fail at runtime.
- Migration plan: Pin `plexapi` version in `requirements.txt`; add integration smoke test against recorded responses.

## Missing Critical Features

**Automated tests:**
- Problem: No CI test stage — regressions ship unnoticed.
- Blocks: Confident refactoring of `app.py` and large `templates/index.html`.

## Test Coverage Gaps

**Room lifecycle and match logic:**
- What's not tested: Solo vs paired match insertion, duplicate `plex_id` rows, `/undo` behavior, `/room/stream` event sequencing.
- Files: `app.py`
- Risk: Subtle race or ordering bugs when two users swipe quickly.
- Priority: High if user-facing reliability complaints exist; Medium otherwise.

---

*Concerns audit: 2026-04-23*
