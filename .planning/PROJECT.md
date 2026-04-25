# Jelly Swipe

## What This Is

Jelly Swipe is a small Flask app for shared "Tinder for movies" sessions: a host creates a room, guests join, everyone swipes on a deck pulled from a home media server, and matches surface when two people swipe right on the same title. Trailers and cast come from TMDB. **v1.0 shipped** a first-class **Jellyfin** backend, and **v1.3** removed all Plex support to become Jellyfin-only.

**v1.1** shipped the public rename from **Kino Swipe** (default database filename, Docker image, UI titles, Plex client id, and maintainer-facing docs). Upstream attribution lives only in `README.md` and `LICENSE` (see fork link there); Unraid template includes a one-line fork note.

**v1.2** shipped **uv** dependency management with **Python 3.13** lockfile, **`jellyswipe/`** package layout with all code under a single importable package, multi-stage Docker build using uv, and comprehensive maintainer documentation. **v1.3** removed all Plex support to become Jellyfin-only.

## Core Value

**Users can run a swipe session backed by Jellyfin**, with library browsing and deck behavior equivalent to the original Plex path.

## Current Milestone: v1.3 — Add unit tests

**Goal:** Add unit tests that improve reliability when making changes to this software

**Target features:**
- Unit test suite for existing codebase
- Framework-agnostic tests (not tied to Flask directly)
- Modern pytest methods with fixtures and parametrize

**v1.2 shipped features:**

- **uv** — `pyproject.toml` + `uv.lock`; install/sync path for Docker and maintainer docs uses uv instead of `pip install -r requirements.txt`.
- **Python 3.13** — `requires-python` and runtime images align on 3.13; direct dependencies pinned to **newest versions compatible** with 3.13 and the app.
- **Package layout** — Flask app and media provider live under **`jellyswipe/`**; Gunicorn (and local `uv run`) target `jellyswipe:app`.
- **Docker-only distribution** — Multi-stage Dockerfile uses uv; no PyPI publish workflow or "install from PyPI" story.
- **Jellyfin-only** — All Plex code, dependencies, and references removed; application assumes Jellyfin-only configuration.

## Requirements

### Validated

- ✓ **Jellyfin server auth** — Configure base URL and credentials (or API key per server policy); obtain and reuse an access token for server API calls. *Phases 3–5 (milestone).*
- ✓ **Jellyfin library parity** — Build the same in-app movie list shape the front end expects (`id`, `title`, `summary`, `thumb`, `rating`, `duration`, `year`) from Jellyfin movies; genre filtering and a “Recently Added”–style sort where the API allows. *Phases 4–5 (milestone).*
- ✓ **Images** — Serve Jellyfin artwork through the app (extend or complement `/proxy` so thumbs work without exposing secrets in the browser). *Phases 4–5 (milestone).*
- ✓ **User-scoped parity (within reason)** — Per-user match/history/undo and “add to list” behavior work in Jellyfin mode using Jellyfin identity (not Plex headers). Exact UX may use Jellyfin login/token headers instead of Plex pin, but outcomes should mirror Plex mode. *Phase 5.*
- ✓ **Milestone evidence and validation closure** — Jellyfin-forward operator E2E narrative, Nyquist-aligned `01–05` validation artifacts, and re-audit inputs consolidated for `/gsd-audit-milestone`. *Phase 8.*
- ✓ **Jellyfin browser delegate path** — When env credentials are configured, the SPA can bind to the server session without exposing API tokens in JSON; stale `localStorage` tokens cleared on success. *Phase 9.*
- ✓ **Poster containment** — Main deck, mini-posters, and match popup use `object-fit: contain` with black backing so wide one-sheets are not cropped. *Phase 9.*
- ✓ **Jelly Swipe branding & packaging (v1.1)** — BRAND-01–04: UI titles and PWA manifest; README/LICENSE fork policy; Unraid `jelly-swipe.html`; default DB path and Docker/CI image `andrewthetechie/jelly-swipe`; Jellyfin client identifier as Jelly Swipe.
- ✓ **UV-01** — uv is the canonical dependency workflow; `pyproject.toml` + committed `uv.lock`; root `requirements.txt` explicitly non-canonical for local dev. *Validated in Phase 10 (v1.2).*
- ✓ **UV-02** — Tooling targets **Python 3.13** (`requires-python = ">=3.13,<3.14"`, `.python-version`). *Validated in Phase 10 (v1.2).*
- ✓ **DEP-01** — Direct runtime dependencies resolved to **newest 3.13-compatible** versions; `uv sync` and `py_compile` smoke pass. *Validated in Phase 10 (v1.2).*
- ✓ **PKG-01** — Application modules (Flask routes/DB/SSE and media provider) live under **`jellyswipe/`** with coherent imports. *Validated in Phase 11 (v1.2).*
- ✓ **PKG-02** — Gunicorn CMD (and documented local command) load the WSGI app from the **`jellyswipe`** package (`jellyswipe:app`). *Validated in Phase 11 (v1.2).*
- ✓ **DOCK-01** — `Dockerfile` installs dependencies via **uv** and runs the packaged application; behavior parity for operators (port, data dir, env contract). *Validated in Phase 12 (v1.2).*
- ✓ **DOC-01** — README (and compose snippets if present) describe **uv**-based setup for contributors/maintainers. *Validated in Phase 12 (v1.2).*
- ✓ **PLEX-REM-01** — Plex implementation code (plex_library.py, factory.py) removed; JellyfinLibraryProvider used directly. *Validated in Phase 13 (v1.2).*
- ✓ **PLEX-REM-02** — plexapi dependency removed; database schema updated (plex_id → user_id); documentation updated. *Validated in Phase 13 (v1.2).*
- ✓ **PLEX-REM-03** — Application verified to work with Jellyfin-only configuration; Docker image builds successfully. *Validated in Phase 13 (v1.2).*

### Active (v1.3 — unit tests)

- [ ] **TEST-01** — Unit test suite for existing codebase with framework-agnostic approach
- [ ] **TEST-02** — Modern pytest methods with fixtures and parametrize
- [ ] **TEST-03** — Test coverage for core modules (db.py, jellyfin_library.py)
- [ ] **TEST-04** — Test configuration and CI integration

### Active (future milestone candidates)

- [ ] **ARC-02 closure** — Formal Plex regression matrix in archived `v1.0-phases/02-media-provider-abstraction/02-VERIFICATION.md` still partial; hardening unless descoped.
- [ ] **OPS-01 / PRD-01** — Neutral DB column naming and multi-library selection (see archived `v1.0-REQUIREMENTS.md` v2 section).

### Out of Scope

- **Plex support** — Explicit product decision: removed in v1.3, application is Jellyfin-only.
- **Replacing TMDB** — Trailers/cast stay on TMDB; no requirement to use Jellyfin plugins for trailers in v1.
- **TV shows / music** — Movies library only, matching current Plex `Movies` section assumption.
- **PyPI distribution (v1.2)** — The `jellyswipe` package is for repo layout and Docker/runtime imports only; no publishing to PyPI or `pip install jellyswipe` product story.

## Current state

- **Shipped:** **v1.0** (Jellyfin), **v1.1** (rename), and **v1.2** (uv + package layout + Plex removal) tagged; archives under `.planning/milestones/v1.0-*`, `v1.1-*`, and `v1.2-*`.
- **In flight:** No active milestone — v1.2 is complete and shipped. Future candidates: ARC-02 closure, OPS-01/PRD-01 (see Active candidates).
- **Runtime:** Flask + SQLite + SSE; `JellyfinLibraryProvider` under `jellyswipe/` package; Python 3.13 with uv dependency management.
- **UI:** Embedded HTML in `jellyswipe/templates/index.html` and mirrored `data/index.html` (PWA-oriented copy); product string **Jelly-Swipe** / **JellySwipe** throughout defaults.
- **Publish:** Docker Hub `andrewthetechie/jelly-swipe:latest` (push to `main`); GHCR `ghcr.io/andrewthetechie/jelly-swipe` on GitHub Release (see `.github/workflows/release-ghcr.yml`).

## Context

- Flask app lives under `jellyswipe/` package with `jellyswipe/__init__.py` (main app), `jellyswipe/db.py` (database), and `jellyswipe/jellyfin_library.py` (media provider); SQLite for rooms/swipes/matches; SSE for room updates (see `.planning/codebase/ARCHITECTURE.md`).
- Dependency management via uv with `pyproject.toml` and `uv.lock`; Python 3.13 required; multi-stage Docker build uses `uv sync --frozen` for reproducible installs.
- Application is Jellyfin-only; all Plex code, dependencies, and configuration removed in v1.2.
- Jellyfin exposes a documented REST API ([api.jellyfin.org](https://api.jellyfin.org/)); auth is token-based with a recommended `Authorization: MediaBrowser ...` header; legacy `X-Emby-Token` may be disabled on some servers — implementation should follow current server expectations and test against target versions.

## Constraints

- **Compatibility**: Support recent stable Jellyfin (10.8+) unless research proves a narrower window; call out version assumptions in README.
- **Security**: Do not log tokens; prefer headers over query-string API keys; HTTPS assumed for remote servers.
- **Minimal churn**: Prefer a clear provider abstraction over duplicating route handlers, while keeping the diff reviewable.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Keep TMDB for trailers/cast | Already works from title/year; Jellyfin metadata is optional enhancement later. | Adopted |
| Jellyfin delegate browser auth | Remove redundant browser password collection when server env auth exists; session-only token resolution server-side. | Shipped v1.0 Phase 9 |
| Jelly Swipe rename (v1.1) | Public fork under AndrewTheTechie; single upstream link in README/LICENSE. | Shipped v1.1 |
| uv + package layout (v1.2) | Faster reproducible installs; clearer module boundaries; Docker remains the operator-facing artifact. | Shipped v1.2 |
| Multi-stage Docker build (v1.2) | Smaller final images, layer caching optimization, reproducible builds from frozen lockfile. | Shipped v1.2 |
| Remove Plex support (v1.2) | Simplify codebase, remove maintenance burden, focus on Jellyfin as single backend. | Shipped v1.2 |
| Gunicorn gevent workers (v1.2) | Enable stable SSE streaming without SystemExit errors; standard solution for async I/O with Gunicorn. | Shipped v1.2 |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):

1. Requirements invalidated? → Move to Out of Scope with reason  
2. Requirements validated? → Move to Validated with phase reference  
3. New requirements emerged? → Add to Active  
4. Decisions to log? → Add to Key Decisions  
5. “What This Is” still accurate? → Update if drifted  

**After each milestone** (via `/gsd-complete-milestone`):

1. Full review of all sections  
2. Core Value check — still the right priority?  
3. Audit Out of Scope — reasons still valid?  
4. Update Context with current state  

---
*Last updated: 2026-04-25 — v1.3 started (unit tests with framework-agnostic pytest)*
