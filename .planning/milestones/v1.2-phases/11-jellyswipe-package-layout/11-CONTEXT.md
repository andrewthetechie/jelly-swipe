# Phase 11: `jellyswipe/` package layout - Context

**Gathered:** 2026-04-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Reorganize server code into an importable **`jellyswipe/`** package with working imports; Gunicorn targets one explicit module:attribute. This is a **structural refactoring phase** — behavior stays the same, only code organization changes.

**Explicitly out of this phase:** Dockerfile uv instructions, README uv documentation, DIST-01 copy — these belong in Phase 12.

</domain>

<decisions>
## Implementation Decisions

### Package Structure

- **D-01:** Flask app lives in **`jellyswipe/__init__.py`** and is created at package import time (typical pattern for smaller Flask apps).
- **D-02:** **`media_provider/`** modules are flattened into **`jellyswipe/`** root: `base.py`, `plex_library.py`, `jellyfin_library.py`, `factory.py` all move directly into `jellyswipe/` (no subdirectory).
- **D-03:** Package structure is **flat** — all Flask routes, env validation, and business logic live in `jellyswipe/__init__.py` except database functions (see D-05).
- **D-04:** **`jellyswipe/__init__.py`** exports **only the Flask `app` object**; all other symbols are accessed via module paths (e.g., `jellyswipe.get_provider()`, `jellyswipe.PlexLibraryProvider`).
- **D-05:** Database functions (`get_db`, `init_db`, schema migrations) live in a separate **`jellyswipe/db.py`** module for separation of concerns.
- **D-06:** Provider factory functions (`get_provider`, `reset`) organization is left to **the agent's discretion** (may stay in `jellyswipe/__init__.py`, move to `jellyswipe/factory.py`, or integrate with provider classes).

### Import Paths

- **D-07:** Update all imports throughout the codebase to use the new package structure (e.g., `from media_provider import get_provider` → `from jellyswipe import get_provider`; `from media_provider.base import LibraryMediaProvider` → `from jellyswipe import LibraryMediaProvider`).
- **D-08:** Intra-package imports within `jellyswipe/` use **relative imports** (e.g., `from .db import get_db` in `jellyswipe/__init__.py`).
- **D-09:** All imports in `jellyswipe/__init__.py` happen at **module load time** (no lazy imports); matches current `app.py` pattern.

### Gunicorn Entry Point

- **D-10:** Gunicorn module:attribute is **`jellyswipe:app`** (direct import of `app` from `jellyswipe/__init__.py`).
- **D-11:** Gunicorn entry point is documented **only in the Dockerfile** (not in README or other docs).

### Template/Static Paths

- **D-12:** **`templates/`** and **`static/`** directories are moved under **`jellyswipe/`**: `jellyswipe/templates/` and `jellyswipe/static/`.
- **D-13:** Templates and static assets **must be included in package data** (via `pyproject.toml` `[tool.hatch.build]` or equivalent) so they are packaged with the module.
- **D-14:** Flask instantiation approach (e.g., `Flask(__name__)` vs `Flask('jellyswipe')`) is left to **the agent's discretion**, ensuring templates and static assets are found correctly from their new location.
- **D-15:** **`data/`** directory **stays at repo root** (not under `jellyswipe/`) because it must be at the root of `/app` for Docker volume mounts and runtime DB to function properly.

### the agent's Discretion

- Provider factory function organization (`get_provider`, `reset`)
- Flask instantiation pattern for finding templates/static assets under `jellyswipe/`
- Any minor module naming or internal organization details not specified above

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements

- `.planning/ROADMAP.md` — Phase 11 goal, success criteria, boundary vs Phases 10 and 12
- `.planning/REQUIREMENTS.md` — PKG-01, PKG-02 wording
- `.planning/PROJECT.md` — Current Milestone v1.2 goals and context

### Prior phase context (Phase 10)

- `.planning/phases/10-uv-python-3-13-lockfile/10-CONTEXT.md` — D-01 (pyproject.toml metadata), D-02 (hatchling build backend), D-04 (uv.lock committed), D-06 (requirements.txt deprecated)

### Current code structure (pre-change)

- `app.py` — Current monolithic Flask app (all routes, DB, env validation, SSE)
- `media_provider/__init__.py` — Current exports: `LibraryMediaProvider`, `JellyfinLibraryProvider`, `PlexLibraryProvider`, `get_provider`, `reset`
- `media_provider/base.py` — Abstract `LibraryMediaProvider` class contract
- `media_provider/plex_library.py` — Plex implementation
- `media_provider/jellyfin_library.py` — Jellyfin implementation
- `media_provider/factory.py` — Provider factory functions
- `templates/index.html` — Main UI template
- `static/` — Static assets (icons, manifest, PWA files)
- `Dockerfile` — Current Gunicorn CMD: `["gunicorn", "-b", "0.0.0.0:5005", "app:app"]`

### Codebase maps

- `.planning/codebase/STRUCTURE.md` — Current directory layout and file purposes
- `.planning/codebase/CONVENTIONS.md` — Naming patterns, import organization, code style
- `.planning/codebase/ARCHITECTURE.md` — Layers, data flow, entry points
- `.planning/codebase/CONCERNS.md` — Tech debt and known issues (context only — not addressing monolithic app.py split in this phase)

### Configuration

- `pyproject.toml` — Current package metadata (name = "jellyswipe", requires-python, dependencies, hatchling backend)
- `uv.lock` — Committed lockfile from Phase 10 (read-only for this phase)

No external specs or ADRs for this phase — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`pyproject.toml`** — Already has `name = "jellyswipe"` and `hatchling` build backend; package discovery/wiring needs update for new structure.
- **`uv.lock`** — Committed lockfile from Phase 10; dependency installation path is frozen.
- **`media_provider/`** package — Four modules (`base.py`, `plex_library.py`, `jellyfin_library.py`, `factory.py`) with `__init__.py` exports; will be flattened into `jellyswipe/`.

### Established Patterns

- **Monolithic Flask app** — All routes, DB, env validation in one module (`app.py`, ~560 lines); Phase 11 moves this into `jellyswipe/__init__.py` but keeps the monolithic pattern (not splitting into blueprints or submodules per D-03).
- **Provider abstraction** — `LibraryMediaProvider` base class with concrete `PlexLibraryProvider` and `JellyfinLibraryProvider`; factory pattern (`get_provider()`, `reset()`) for obtaining instances.
- **SQLite at import time** — `init_db()` runs at module import in current `app.py`; will run at `jellyswipe` package import after D-01.
- **Flask `__name__`** — Current `app = Flask(__name__)`; may need adjustment after moving templates/static under `jellyswipe/` (D-14).

### Integration Points

- **Gunicorn entry point** — Currently `app:app` in Dockerfile; will change to `jellyswipe:app` (D-10).
- **Template/static discovery** — Flask currently finds `templates/` and `static/` at repo root via `__name__`; after D-12/D-14, Flask must find them under `jellyswipe/templates/` and `jellyswipe/static/`.
- **Package data** — `templates/` and `static/` must be included in package (via `pyproject.toml` or hatch config) so they're installed/packaged (D-13).
- **Docker `/app` mount** — `data/` directory must stay at repo root for `/app/data` volume mount to work (D-15).

</code_context>

<specifics>
## Specific Ideas

- Phase 11 is purely structural — no new features or behavior changes. The goal is a clean package layout that works with `uv` and Gunicorn.
- User chose to keep the package flat (monolithic `jellyswipe/__init__.py`) rather than splitting into submodules, despite CONCERNS.md flagging `app.py` as tech debt. That refactoring is a future concern.
- `data/` directory stays at repo root because it's for runtime state and Docker volume mounts, not package code.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

### Reviewed Todos (not folded)

No todos matched for Phase 11.

</deferred>

---

*Phase: 11-jellyswipe-package-layout*
*Context gathered: 2026-04-24*
