# Roadmap: Jelly Swipe

**Planning root:** **v1.2** is active (uv + `jellyswipe/` package + Docker-only). **v1.0** / **v1.1** are shipped — see [MILESTONES.md](MILESTONES.md) and [milestones/](milestones/).

## Milestones

- ✅ **v1.0 — Jellyfin as alternative backend** — Phases 1–9 — 2026-04-24 — [Roadmap archive](milestones/v1.0-ROADMAP.md) · [Requirements](milestones/v1.0-REQUIREMENTS.md)
- ✅ **v1.1 — Jelly Swipe rename** — Branding & maintainer identity — 2026-04-24 — [Roadmap archive](milestones/v1.1-ROADMAP.md) · [Requirements](milestones/v1.1-REQUIREMENTS.md)
- 🔄 **v1.2 — uv + `jellyswipe` package layout** — Phases 10–12 — [REQUIREMENTS.md](REQUIREMENTS.md)

**Phase history (prior):** [v1.0-phases/](milestones/v1.0-phases/) (Phases 1–9). **v1.1** had no new numbered phase directories.

---

## v1.2 — Phase overview

| # | Phase | Goal | Requirements | Success criteria |
|---|--------|------|--------------|------------------|
| 10 | uv & Python 3.13 lockfile | Introduce `pyproject.toml`, `uv.lock`, and 3.13-aligned pins; retire `requirements.txt` as canonical | UV-01, UV-02, DEP-01 | 3 |
| 11 | `jellyswipe/` package | Move Flask app and `media_provider` under `jellyswipe/` with working imports | PKG-01, PKG-02 | 3 |
| 12 | Docker & docs | Image uses uv; README and distribution story match Docker-only | DOCK-01, DOC-01, DIST-01 | 3 |
| 13 | Remove Plex support | Remove all Plex code, dependencies, and references; project becomes Jellyfin-only | PLEX-REM-01, PLEX-REM-02, PLEX-REM-03 | 3 |

---

## Phase 10: uv & Python 3.13 lockfile

**Goal:** Dependency management is **uv**-first with a committed lockfile on **Python 3.13**; versions are newest compatible for this codebase.

**Requirements:** UV-01, UV-02, DEP-01

**Success criteria:**

1. `uv lock` (or equivalent) produces **`uv.lock`** checked in; **`pyproject.toml`** lists runtime deps and **`requires-python`** for 3.13.  
2. A clean **`uv sync`** on Python 3.13 installs successfully.  
3. Quick smoke: application module imports (after any temporary shim) or **`python -m compileall`** on packaged paths passes; no known incompatible major bumps left unaddressed.

---

## Phase 11: `jellyswipe/` package layout

**Goal:** All server Python for the web app lives under **`jellyswipe/`**; Gunicorn targets one explicit attribute.

**Requirements:** PKG-01, PKG-02

**Plans:** 5 plans (4 original + 1 gap closure)

**Plan list:**
- [x] 11-01-PLAN.md — Create jellyswipe package structure and flatten media_provider modules
- [x] 11-02-PLAN.md — Move database functions to jellyswipe/db.py and create Flask app in jellyswipe/__init__.py
- [x] 11-03-PLAN.md — Move templates/ and static/ under jellyswipe/ and configure package data
- [x] 11-04-PLAN.md — Update imports throughout codebase and update Gunicorn entry point to jellyswipe:app
- [x] 11-05-PLAN.md — Fix SSE stream with Gunicorn gevent workers (gap closure)

**Status:** ✅ **COMPLETE** — 2026-04-25

**Success criteria:**

1. No remaining production logic in a repo-root **`app.py`** monolith unless it is a documented thin re-export (prefer none).
2. **`media_provider`** (and related modules) import cleanly from **`jellyswipe`**.
3. **`gunicorn 'jellyswipe.<module>:app'`** (exact module from implementation) starts with the same env contract as today.

---

## Phase 12: Docker & maintainer docs

**Goal:** **`Dockerfile`** uses **uv** for installs; README documents uv; **no PyPI** narrative or automation.

**Requirements:** DOCK-01, DOC-01, DIST-01

**Plans:** 2 plans

**Plan list:**
- [x] 12-01-PLAN.md — Convert Dockerfile to multi-stage build with uv
- [x] 12-02-PLAN.md — Add Development section to README with uv documentation

**Status:** Complete (2/2 plans executed, 2026-04-25)

**Success criteria:**

1. **`docker build .`** succeeds using the lockfile; container listens on **5005** and supports persistent DB path patterns used in compose.
2. README "Development / install" (or equivalent) uses **uv** commands.
3. No new GitHub Actions or docs implying **`pip install jellyswipe`** from PyPI; **DIST-01** satisfied.

---

## Phase 13: Remove Plex support

**Goal:** Remove all Plex-related code, dependencies, configuration, and documentation from the codebase. The project will be **Jellyfin-only** going forward.

**Requirements:** PLEX-REM-01, PLEX-REM-02, PLEX-REM-03

**Plans:** 3 plans

**Plan list:**
- [ ] 13-01-PLAN.md — Remove Plex implementation code (plex_library.py, factory.py, Plex routes)
- [ ] 13-02-PLAN.md — Update dependencies, database schema, and documentation to Jellyfin-only
- [ ] 13-03-PLAN.md — Verify application works with Jellyfin-only configuration

**Status:** 🔄 **PLANNING** — 2026-04-24

**Success criteria:**

1. No `plexapi` or Plex-related imports remain in the codebase; `pyproject.toml` and `uv.lock` contain no Plex dependencies.
2. Application starts and runs successfully with only Jellyfin configuration; no Plex environment variables are referenced.
3. All documentation (README.md, PROJECT.md, Docker examples) reflects Jellyfin-only support with no Plex references.

---

## Backlog

### Phase 999.1: Follow-up — Phase 1 incomplete plans (BACKLOG)

**Goal:** Resolve plans that ran without producing summaries during Phase 1 execution  
**Source phase:** 1  
**Deferred at:** 2026-04-23 during /gsd-next advancement to Phase 5  
**Plans:**

- [x] 1-01: configuration-startup plan 1 (ran, no SUMMARY.md)
- [x] 1-02: configuration-startup plan 2 (ran, no SUMMARY.md)

### Phase 999.2: Follow-up — Phase 3 missing planning artifacts (BACKLOG)

**Goal:** Create and execute missing plans for Phase 3 after context was gathered  
**Source phase:** 3  
**Deferred at:** 2026-04-23 during /gsd-next advancement to Phase 5  
**Plans:**

- [x] 3-01: create PLAN.md artifacts for auth/http client scope (context exists, no plans)

### Phase 999.3: Follow-up — Phase 4 missing planning artifacts (BACKLOG)

**Goal:** Create and execute missing plans for Phase 4 after context was gathered  
**Source phase:** 4  
**Deferred at:** 2026-04-23 during /gsd-next advancement to Phase 5  
**Plans:**

- [x] 4-01: create PLAN.md artifacts for library/media scope (context exists, no plans)
