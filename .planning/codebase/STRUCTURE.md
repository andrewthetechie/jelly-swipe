# Codebase Structure

**Analysis Date:** 2026-05-01

## Directory Layout

```
jelly-swipe/
├── jellyswipe/                 # Python package — entire application
│   ├── __init__.py             # Flask app factory, all routes, middleware
│   ├── base.py                 # LibraryMediaProvider ABC
│   ├── auth.py                 # Token vault CRUD, @login_required decorator
│   ├── db.py                   # SQLite schema, init_db(), get_db(), migrations
│   ├── http_client.py          # Centralized outbound HTTP helper
│   ├── jellyfin_library.py     # JellyfinLibraryProvider (REST client + deck logic)
│   ├── rate_limiter.py         # In-memory token-bucket rate limiter
│   ├── ssrf_validator.py       # Boot-time JELLYFIN_URL SSRF safety check
│   ├── static/                 # Static assets served at /static/*
│   │   ├── app.js              # SPA client — all UI, swipe engine, SSE consumer
│   │   ├── styles.css          # CSS
│   │   ├── sw.js               # Service worker (PWA)
│   │   ├── manifest.json       # PWA manifest
│   │   └── *.png / *.ico       # Icons and branding images
│   │   └── fonts/              # Allura-Regular.woff2
│   └── templates/
│       └── index.html          # Single HTML shell served at /
├── tests/                      # pytest test suite
│   ├── conftest.py             # Fixtures: app, client, db_path, FakeProvider
│   ├── test_auth.py            # Unit tests for auth.py
│   ├── test_db.py              # Unit tests for db.py (schema, migrations)
│   ├── test_error_handling.py  # Route error response format tests
│   ├── test_http_client.py     # Unit tests for http_client.py
│   ├── test_infrastructure.py  # App factory and config tests
│   ├── test_jellyfin_library.py# Unit tests for JellyfinLibraryProvider
│   ├── test_migration_23.py    # Migration regression tests (schema v23)
│   ├── test_rate_limiter.py    # Unit tests for rate_limiter.py
│   ├── test_route_authorization.py  # Auth/authorization route tests
│   ├── test_routes_auth.py     # /auth/* and /me route integration tests
│   ├── test_routes_proxy.py    # /proxy route tests (SSRF allowlist)
│   ├── test_routes_room.py     # /room/* route integration tests
│   ├── test_routes_sse.py      # SSE stream comprehensive tests
│   ├── test_routes_xss.py      # XSS defense regression tests
│   ├── test_ssrf_validator.py  # Unit tests for ssrf_validator.py
│   └── test_tmdb_auth.py       # TMDB auth header tests
├── scripts/                    # Utility scripts (not part of app)
├── screenshots/                # README screenshots
├── unraid_template/            # Unraid community app template XML
├── .planning/                  # GSD planning artifacts (not shipped)
│   ├── codebase/               # Codebase map documents
│   ├── phases/                 # Phase plans
│   ├── milestones/             # Milestone phase sets
│   └── ...
├── .github/
│   └── workflows/              # GitHub Actions CI
├── .cursor/
│   └── rules/                  # Cursor IDE rules
├── pyproject.toml              # Package metadata, deps, pytest config
├── uv.lock                     # uv lockfile (committed)
├── Dockerfile                  # Multi-stage Docker build (python:3.13-slim)
├── docker-compose.yml          # Docker Compose example config
├── ARCHITECTURE.md             # Public architecture doc (repo root)
└── README.md                   # Public documentation
```

## Directory Purposes

**`jellyswipe/` (package root):**
- Purpose: The entire Python application — no src/ layout, package is at repo root
- Key file: `jellyswipe/__init__.py` contains the Flask app factory AND all route definitions in one file

**`jellyswipe/static/`:**
- Purpose: Browser-side assets served directly by Flask's static file handler at `/static/<path>`
- Special routes: `/manifest.json`, `/sw.js`, `/favicon.ico` have dedicated route handlers (not served via the catch-all `/static/<path>`)
- `app.js` is 790 lines — the entire SPA logic; no bundler, no transpilation

**`jellyswipe/templates/`:**
- Purpose: Jinja2 templates; currently only `index.html`
- `index.html` receives `media_provider` variable (always `"jellyfin"`) — a remnant from multi-provider era

**`tests/`:**
- Purpose: pytest test suite; mirrors the `jellyswipe/` module structure
- No `__init__.py` duplication of package structure — flat directory of test files

**`data/` (runtime, not in repo):**
- Purpose: SQLite database file (`jellyswipe.db`) written at runtime
- Default path: `jellyswipe/../data/jellyswipe.db` (relative to package root)
- Overridden by `DB_PATH` env var
- In Docker: mounted at `/app/data` via volume

**`.planning/`:**
- Purpose: GSD planning artifacts — not shipped in Docker image, not imported by application code
- `codebase/`: Machine-written analysis docs consumed by `/gsd-plan-phase` and `/gsd-execute-phase`

## Key File Locations

**Entry Points:**
- `jellyswipe/__init__.py`: Flask app factory `create_app()` and module-level `app = create_app()` for gunicorn
- `pyproject.toml`: Package definition, Python version constraint (`>=3.13,<3.14`), dev extras

**Configuration:**
- `pyproject.toml`: pytest options (`testpaths`, `addopts` with `--cov-fail-under=70`)
- `Dockerfile`: gunicorn command, port (5005), gevent worker
- `docker-compose.yml`: Required env vars (`JELLYFIN_URL`, `JELLYFIN_API_KEY`, `FLASK_SECRET`, `TMDB_ACCESS_TOKEN`)

**Core Logic:**
- `jellyswipe/__init__.py`: All Flask routes, middleware, security headers — ~840 lines
- `jellyswipe/jellyfin_library.py`: Jellyfin REST client, deck/genre/image logic — ~520 lines
- `jellyswipe/static/app.js`: SPA client — ~790 lines

**Testing:**
- `tests/conftest.py`: `app`, `client`, `db_path`, `db_connection`, `FakeProvider`, `mocker` fixtures
- `tests/test_routes_sse.py`: SSE-specific tests including heartbeat, jitter, room disappearance

## Naming Conventions

**Files:**
- Python modules: `snake_case.py`
- Test files: `test_{module_or_feature}.py` (mirrors module name where applicable)
- Static assets: `lowercase` with hyphens for multi-word (e.g., `apple-touch-icon.png`)

**Directories:**
- Lowercase, no separators (`jellyswipe/`, `tests/`, `static/`, `templates/`)

**Python symbols:**
- Classes: `PascalCase` (`JellyfinLibraryProvider`, `TokenBucket`, `RateLimiter`)
- Functions: `snake_case`
- Private helpers: `_leading_underscore` (`_check_rate_limit`, `_get_cursor`, `_media_browser_header`)
- Module-level singletons: `_snake_case_with_leading_underscore` (`_provider_singleton`, `_rate_limiter`)
- Constants: `UPPER_SNAKE_CASE` (`DB_PATH`, `CLIENT_ID`, `IDENTITY_ALIAS_HEADERS`)

## Where to Add New Code

**New Flask route:**
- Add inside the `create_app()` function body in `jellyswipe/__init__.py`
- Apply `@login_required` if authentication is required
- Apply `_check_rate_limit(endpoint_name)` at the top if the route hits external services
- Add `endpoint_name: limit` to `_RATE_LIMITS` dict near the top of `__init__.py`
- Add corresponding test file `tests/test_routes_{feature}.py`

**New outbound HTTP call:**
- Use `make_http_request()` from `jellyswipe/http_client.py` — do NOT use `requests.get()` directly
- Specify explicit `timeout=(connect_sec, read_sec)` tuple

**New library provider feature:**
- Add abstract method to `jellyswipe/base.py` first
- Implement in `jellyswipe/jellyfin_library.py`
- Add to `FakeProvider` in `tests/conftest.py`
- Add unit tests in `tests/test_jellyfin_library.py`

**New database table or column:**
- Add `CREATE TABLE IF NOT EXISTS` in `init_db()` in `jellyswipe/db.py`
- Add `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` migration block in `init_db()` for in-place upgrades on existing databases
- Add migration regression test in `tests/test_migration_23.py` (or a new numbered file)

**New security check:**
- SSRF-type boot validation: add to `jellyswipe/ssrf_validator.py`, call inside `create_app()`
- Per-request validation: add inside the route handler in `jellyswipe/__init__.py`

**New client feature:**
- Edit `jellyswipe/static/app.js` (no build step)
- All API calls must use `apiFetch()` (not bare `fetch()`) to get session handling and 401 detection

**New test:**
- Place in `tests/test_{feature}.py`
- Use `client` fixture for route tests, `db_connection` fixture for direct DB tests
- Use `monkeypatch.setattr(jellyswipe_module, "_provider_singleton", FakeProvider())` to inject mock provider

## Special Directories

**`data/` (runtime):**
- Purpose: SQLite database file (`jellyswipe.db`)
- Generated: Yes, at runtime
- Committed: No (`.gitignore`)
- In Docker: persisted via `./data:/app/data` volume mount

**`.venv/` (runtime):**
- Purpose: uv-managed virtual environment
- Generated: Yes, by `uv sync`
- Committed: No

**`jellyswipe/static/`:**
- Purpose: Browser assets (served verbatim, no build step)
- Generated: No
- Committed: Yes

**`.planning/`:**
- Purpose: GSD planning artifacts — phase plans, codebase maps, debug logs
- Generated: Partially (codebase maps written by agents)
- Committed: Yes

---

*Structure analysis: 2026-05-01*
