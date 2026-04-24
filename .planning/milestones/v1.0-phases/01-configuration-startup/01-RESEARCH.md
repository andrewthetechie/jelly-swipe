# Phase 1 — Technical research

**Phase:** 01 configuration-startup  
**Question:** What do we need to know to plan env validation and startup well?

## Findings

### Current startup coupling

- `app.py` validates a fixed `required` list at import time and raises `RuntimeError(f"Missing env vars: {missing}")`.
- `plexapi` is imported at module top (`PlexServer`, `MyPlexAccount`), so **import always loads Plex client libraries** even if only env validation is desired for Jellyfin-oriented installs.
- `FLASK_SECRET` is read with `os.environ["FLASK_SECRET"]` before the `missing` check; if unset, behavior is `KeyError` rather than the same `RuntimeError` pattern (pre-existing quirk).

### Lazy-import strategy (D-10)

- Move `from plexapi.server import PlexServer` inside `get_plex()` after confirming `MEDIA_PROVIDER == "plex"`.
- Move `from plexapi.myplex import MyPlexAccount` inside `add_to_watchlist()` (only Plex route that needs it) and guard route when `MEDIA_PROVIDER != "plex"`.
- Routes that call `get_plex()` in Jellyfin mode should fail with a **single clear `RuntimeError` or HTTP error** rather than obscure import errors; Phase 1 does not implement Jellyfin library calls (later phases).

### Validation rules (from CONTEXT)

- Normalize `MEDIA_PROVIDER`: unset → `plex`; invalid non-empty value → `RuntimeError` listing accepted values.
- Global: `TMDB_API_KEY`, `FLASK_SECRET` always required (non-empty `os.getenv`).
- Plex: `PLEX_URL`, `PLEX_TOKEN` required.
- Jellyfin: `JELLYFIN_URL` required (strip trailing slash like `PLEX_URL`); credentials: non-empty `JELLYFIN_API_KEY` **or** (`JELLYFIN_USERNAME` and `JELLYFIN_PASSWORD` both non-empty).

### Documentation surfaces

- `README.md`: operator-focused; add env table and minimal `.env` snippets; cite two-instance rule from `PROJECT.md`.
- `docker-compose.yml`: single service; add short comments for `MEDIA_PROVIDER` and Jellyfin vars pointing to README (no duplicate service definitions).

### Testing gap

- No `pytest` in repo today. Phase 1 verification leans on **import smoke** with controlled env vars and optional small script or `python -c` checks documented in plans.

## Validation Architecture

Nyquist / execution feedback for this phase:

- **Primary signal:** Process boot (`python -c "import app"`) with three env matrices: (A) minimal Plex, (B) minimal Jellyfin without any Plex vars, (C) intentional missing var → expect `RuntimeError` containing `Missing env vars`.
- **Secondary:** `python -m py_compile app.py` after edits.
- **Manual:** Operator reads README table and can copy a minimal `.env` per mode.

Dimension mapping:

| Dimension | How sampled |
|-----------|-------------|
| Correctness | Import matrices + grep for `MEDIA_PROVIDER` / `JELLYFIN_URL` handling |
| Security | No new logging of secrets; `/proxy` remains path-restricted |
| Regression | Plex-mode required list unchanged in substance (`PLEX_URL`, `PLEX_TOKEN`, `TMDB_API_KEY`, `FLASK_SECRET`) |

---

## RESEARCH COMPLETE
