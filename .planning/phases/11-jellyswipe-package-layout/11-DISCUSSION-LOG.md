# Phase 11: `jellyswipe/` package layout - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the discussion.

**Date:** 2026-04-24
**Phase:** 11-jellyswipe-package-layout
**Mode:** discuss
**Areas discussed:** Package structure, Import paths, Gunicorn entry point, Template/static paths

## Package Structure

### Q1: Where should the Flask app live within the jellyswipe/ package?

**Options presented:**
- `jellyswipe/web.py` — Separate module for web/routes; `jellyswipe/__init__.py` only exports metadata
- `jellyswipe/app.py` — Keep same filename, just move into package; clear mapping from current `app.py`
- `jellyswipe/__init__.py` — Flask app created at package import; typical pattern for smaller Flask apps

**User selected:** `jellyswipe/__init__.py`

**Rationale:** User chose the typical pattern for smaller Flask apps — creating the app at package import time.

---

### Q2: How should media_provider/ be organized under jellyswipe/?

**Options presented:**
- `jellyswipe/media_provider/` — Keep same structure, just move under `jellyswipe/`; minimal change to imports
- `jellyswipe/providers/` — Rename to `providers/` for clarity; `jellyswipe.providers.base`, `jellyswipe.providers.plex`, etc.
- Flatten into `jellyswipe/` — Move `base.py`, `plex_library.py`, `jellyfin_library.py` directly into `jellyswipe/` root

**User selected:** Flatten into `jellyswipe/`

**Rationale:** User chose to flatten the media_provider modules into the package root, eliminating the subdirectory structure.

---

### Q3: How should the provider factory (get_provider, reset) be organized?

**Options presented:**
- Keep `factory.py` — `jellyswipe/factory.py` with `get_provider()` and `reset()` functions; same pattern as today
- Merge into `__init__.py` — Factory functions live in `jellyswipe/__init__.py` alongside the Flask app
- You decide — Choose the approach that best fits the overall structure and import patterns

**User selected:** You decide

**Rationale:** User left the factory organization to agent discretion.

---

### Q4: Should jellyswipe/ have a clear module separation or keep everything flat?

**Options presented:**
- Logical modules — Separate concerns: `jellyswipe/web.py` for Flask routes, `jellyswipe/db.py` for database, `jellyswipe/providers.py` for media providers
- Keep flat — All code in `jellyswipe/__init__.py`; simple but monolithic (matches current `app.py` style)

**User selected:** Keep flat

**Rationale:** User chose to keep the package flat, maintaining the monolithic pattern despite CONCERNS.md flagging it as tech debt.

---

### Q5: What should jellyswipe/__init__.py export?

**Options presented:**
- Everything — Export Flask app, all provider classes, factory functions, DB helpers — `from jellyswipe import *` works
- Only app and key symbols — Export `app` and `get_provider` primarily; other internals are `jellyswipe._private`
- Only app — Export only the Flask `app` object; everything else is accessed via module paths

**User selected:** Only app

**Rationale:** User chose to export only the Flask `app` object; all other symbols accessed via module paths.

---

### Q6: How should database functions (get_db, init_db) be organized?

**Options presented:**
- In `__init__.py` — Keep DB functions in `jellyswipe/__init__.py` alongside Flask app and routes
- Separate `jellyswipe/db.py` — Isolate database concerns; cleaner separation even in a flat package
- You decide — Choose the approach that best fits the package organization

**User selected:** Separate `jellyswipe/db.py`

**Rationale:** User chose to separate database concerns into their own module for cleaner separation.

---

## Import Paths

### Q7: How should the code import from the new jellyswipe/ structure?

**Options presented:**
- Update all imports — Change `from media_provider import ...` to `from jellyswipe import ...` throughout the codebase
- Backward compatible — Keep `media_provider` working via re-export in `jellyswipe/__init__.py`; gradual migration
- You decide — Choose the approach based on what makes the migration cleaner

**User selected:** Update all imports

**Rationale:** User chose to update all imports to use the new package structure directly.

---

### Q8: How should intra-package imports work within jellyswipe/?

**Options presented:**
- Absolute imports — Use `from jellyswipe import ...` even within `jellyswipe/__init__.py` itself
- Relative imports — Use `from .db import ...` within `jellyswipe/__init__.py`; standard Python practice
- You decide — Choose the Python convention that fits best

**User selected:** Relative imports

**Rationale:** User chose to use relative imports within the package, following standard Python practice.

---

### Q9: Should jellyswipe/__init__.py use lazy imports or import everything at module load?

**Options presented:**
- Import at module load — All imports (flask, sqlite3, provider classes) at top of `__init__.py`; simple and explicit
- Lazy imports — Import heavy dependencies only when needed; can speed up package import time
- You decide — Choose based on what makes sense for this Flask app's usage pattern

**User selected:** Import at module load

**Rationale:** User chose to import everything at module load time, matching the current `app.py` pattern.

---

## Gunicorn Entry Point

### Q10: What should be the Gunicorn module:attribute to start the app?

**Options presented:**
- `jellyswipe:app` — Direct import of the app attribute from `jellyswipe/__init__.py`; standard pattern
- `jellyswipe.web:app` — If you had chosen `jellyswipe/web.py` for the Flask app (not selected)
- `jellyswipe.app:app` — If you had chosen `jellyswipe/app.py` for the Flask app (not selected)

**User selected:** `jellyswipe:app`

**Rationale:** User chose the standard pattern of importing the `app` attribute directly from `jellyswipe/__init__.py`.

---

### Q11: Should the Gunicorn entry point be documented anywhere beyond the Dockerfile?

**Options presented:**
- Only in Dockerfile — The Gunicorn CMD in Dockerfile is the primary documentation; no extra docs needed
- Document in README — Add a note about the entry point in README for local dev reference
- You decide — Add documentation where it makes sense for maintainers

**User selected:** Only in Dockerfile

**Rationale:** User chose to document the Gunicorn entry point only in the Dockerfile, not in the README.

---

## Template/Static Paths

### Q12: Where should templates/ and static/ directories live?

**Options presented:**
- Stay at repo root — `templates/` and `static/` remain at repo root; `Flask(__name__)` finds them from package location
- Move under `jellyswipe/` — `jellyswipe/templates/` and `jellyswipe/static/`; all app assets in the package
- You decide — Choose the approach that fits the package organization best

**User selected:** Move them into jellyswipe and update references to them and make sure they are packaged into the package

**Rationale:** User chose to move templates and static under `jellyswipe/` and ensure they're properly packaged.

---

### Q13: How should Flask be instantiated to find templates/static under jellyswipe/?

**Options presented:**
- `Flask(__name__)` with package_data — Keep `Flask(__name__)`; add `templates/` and `static/` to `pyproject.toml` package_data so they're found
- `Flask('jellyswipe')` — Use package name directly; Flask will find templates/static from the package location
- You decide — Choose the Flask instantiation pattern that works reliably with the package layout

**User selected:** You decide

**Rationale:** User left the Flask instantiation to agent discretion, ensuring assets are found correctly.

---

### Q14: What about the data/ directory (service worker, runtime DB)?

**Options presented:**
- Keep at repo root — `data/` stays at repo root; it's for runtime state, not package code
- Move under `jellyswipe/` — `jellyswipe/data/`; all app-related files in one place
- You decide — Choose based on what makes sense for the `data/` directory's purpose

**User selected:** Keep at repo root, it has to copy into the root of /app for the app to function properly.

**Rationale:** User chose to keep `data/` at repo root because it must be at `/app/data` for Docker volume mounts to work correctly.

---

## Summary

**Total questions asked:** 14
**Total areas discussed:** 4 (Package structure, Import paths, Gunicorn entry point, Template/static paths)
**Decisions delegated to agent:** 4 (factory organization, Flask instantiation, plus 2 implied by "You decide" selections)

**Key user preferences:**
- Flat package structure (monolithic `jellyswipe/__init__.py`)
- All imports updated to new structure (no backward compatibility)
- `jellyswipe:app` as Gunicorn entry point
- Templates/static moved under `jellyswipe/` and packaged
- `data/` stays at repo root for Docker

---

*Discussion log captured: 2026-04-24*
