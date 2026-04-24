# Codebase Structure

**Analysis Date:** 2026-04-23

## Directory Layout

```
jelly-swipe/   # repo checkout may still be named kino-swipe locally
├── app.py                 # Flask app, routes, DB, Plex/TMDB integration
├── requirements.txt       # Python dependencies
├── Dockerfile             # Container image
├── docker-compose.yml     # Local/stack deployment example
├── docker run.txt         # Example docker run invocation
├── README.md              # User-facing setup and features
├── LICENSE
├── .gitignore
├── .github/
│   └── workflows/
│       └── docker-image.yml   # CI build + push to Docker Hub
├── templates/
│   └── index.html         # Main UI (HTML + CSS + JS)
├── static/
│   ├── manifest.json      # PWA manifest (also served via route)
│   ├── icon-192.png, icon-512.png, logo.png, main.png, sad.png, brick.png
├── data/
│   ├── index.html         # Alternate UI copy (PWA-related)
│   ├── sw.js              # Service worker (served at /sw.js)
│   └── manifest.json      # Duplicate manifest metadata
├── unraid_template/
│   └── jelly-swipe.html   # Unraid community template
└── screenshots/           # Marketing / demo assets (not imported by app)
```

## Directory Purposes

**Root:**
- Purpose: Project configuration, primary Python module, container definitions.
- Contains: `app.py`, compose, Docker, requirements.
- Key files: `app.py`, `requirements.txt`, `Dockerfile`, `docker-compose.yml`

**`templates/`:**
- Purpose: Jinja templates rendered by Flask.
- Contains: `index.html` (primary application page).
- Key files: `templates/index.html`

**`static/`:**
- Purpose: Static assets served under `/static/<path>` and `/manifest.json`.
- Contains: Icons, background texture, PWA manifest.
- Key files: `static/manifest.json`, `static/icon-192.png`

**`data/`:**
- Purpose: Writable volume mount target in Docker for SQLite DB and service worker; hosts alternate `index.html`.
- Contains: `sw.js`, optional `jellyswipe.db` (or legacy `kinoswipe.db`; gitignored when present locally).
- Key files: `data/sw.js`

**`.github/workflows/`:**
- Purpose: CI automation.
- Key files: `.github/workflows/docker-image.yml`

**`unraid_template/`:**
- Purpose: Template snippet for Unraid deployments.
- Key files: `unraid_template/jelly-swipe.html`

**`screenshots/`:**
- Purpose: Documentation and demo media only.

## Key File Locations

**Entry Points:**
- `app.py`: Flask application and route definitions.
- `Dockerfile`: `CMD ["python", "app.py"]`.

**Configuration:**
- `docker-compose.yml`, `docker run.txt`: Example environment variable wiring (verify against required vars in `app.py`).
- `.gitignore`: Ignores `data/jellyswipe.db`, `data/kinoswipe.db`, `.env`, bytecode.

**Core Logic:**
- `app.py`: All backend behavior (no `src/` package layout).

**Testing:**
- Not applicable — No `tests/` directory or `*_test.py` files detected.

## Naming Conventions

**Files:**
- Python: `app.py` single module (snake_case would be typical for multi-file packages; here everything is one file).
- Templates: `index.html` lowercase.
- Static assets: kebab-case or descriptive names (`icon-192.png`, `brick.png`).

**Directories:**
- Lowercase plural for assets (`templates`, `static`, `screenshots`).

## Where to Add New Code

**New Feature:**
- Primary code: Add routes and helpers to `app.py` (current pattern) or introduce a `package/` layout if splitting (would require Dockerfile/workflow updates to match).
- Front-end behavior: Extend `templates/index.html` (large single file — consider extracting JS/CSS if growing further).

**New Component/Module:**
- Implementation: Prefer new Python modules only if refactoring `app.py` first; today there is no package namespace.

**Utilities:**
- Shared helpers: Today colocated at bottom/top of `app.py`; a future `utils.py` or `services/plex.py` would match common Flask growth patterns.

## Special Directories

**`data/`:**
- Purpose: Runtime database and PWA files for mounted deployments.
- Generated: `jellyswipe.db` (default) created at runtime by `init_db()` in `app.py`; legacy `kinoswipe.db` if `DB_PATH` points at it.
- Committed: `sw.js` and `index.html` yes; database files no (see `.gitignore`).

---

*Structure analysis: 2026-04-23*
