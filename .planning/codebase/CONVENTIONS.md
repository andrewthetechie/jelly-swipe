# Coding Conventions

**Analysis Date:** 2026-04-23

## Naming Patterns

**Files:**
- Single backend module `app.py`; template `templates/index.html`; static assets under `static/` with descriptive names.

**Functions:**
- Use `snake_case` for Python functions and helpers (`get_db`, `fetch_plex_movies`, `init_db`, `room_status`) in `app.py`.

**Variables:**
- `snake_case` for locals and module-level names (`pairing_code`, `movie_list`, `_plex_instance`).
- UPPER_SNAKE for module-level configuration derived from env (`PLEX_URL`, `DB_PATH`, `CLIENT_ID`).

**Types:**
- Not applicable — No `typing` annotations or `mypy` config; SQLite rows use `sqlite3.Row` factory in `get_db()`.

## Code Style

**Formatting:**
- No Black, Ruff, or flake8 config files in repo — style is informal consistent with CPython defaults.
- Frequent one-line early returns in route handlers (`app.py`), e.g. `def index(): return render_template('index.html')`.

**Linting:**
- Not detected — Add project tooling if team wants enforced style.

## Import Organization

**Order:**
1. Third-party (`flask`, `plexapi`, `werkzeug`, `requests`).
2. Standard library grouped on one line in `app.py`: `import sqlite3, os, random, requests, json, secrets, time`.

**Path Aliases:**
- Not applicable — No `src` layout or import aliases.

## Error Handling

**Patterns:**
- Wrap external IO (Plex, TMDB) in `try`/`except`, often returning `jsonify({'error': str(e)}), 500` to clients (`get_trailer`, `get_cast`, `watchlist` in `app.py`).
- Some routes return empty structures on failure (`get_cast` returns `cast` list with error payload).
- Generator in `/room/stream` swallows generic exceptions and continues polling (`app.py`).

## Logging

**Framework:** Implicit Werkzeug HTTP logging when running Flask dev server or equivalent.

**Patterns:**
- Prefer adding structured `logging` calls if debugging production issues — not established today.

## Comments

**When to Comment:**
- Sparse inline comments; schema migration blocks in `init_db()` are self-documenting via SQL strings.

**JSDoc/TSDoc:**
- Not used — Client code is plain `<script>` in `templates/index.html`.

## Function Design

**Size:** Route handlers mix I/O, SQL, and control flow in one function — acceptable at current size but growing complexity increases regression risk.

**Parameters:** Prefer `request.json.get(...)` with defaults for JSON APIs (`/room/swipe`, `/watchlist/add`).

**Return Values:** JSON via `jsonify(...)` for APIs; `Response` for SSE and raw JSON from stored `movie_data`; `render_template` for `/`.

## Module Design

**Exports:** Single Flask `app` instance; no `__all__` or package `__init__.py`.

**Barrel Files:** Not used — single-module application.

---

*Convention analysis: 2026-04-23*
