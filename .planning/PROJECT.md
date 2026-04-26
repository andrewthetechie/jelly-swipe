# Jelly Swipe

## What This Is

Jelly Swipe is a small Flask app for shared "Tinder for movies" sessions: a host creates a room, guests join, everyone swipes on a deck pulled from a home media server, and matches surface when two people swipe right on the same title. Trailers and cast come from TMDB. **v1.0 shipped** a first-class **Jellyfin** backend, **v1.1** renamed the project to Jelly Swipe, **v1.2** migrated to uv dependency management and removed all Plex support, and **v1.3** added comprehensive unit tests with 48 tests and CI workflow.

**v1.1** shipped the public rename from **Kino Swipe** (default database filename, Docker image, UI titles, Plex client id, and maintainer-facing docs). Upstream attribution lives only in `README.md` and `LICENSE` (see fork link there); Unraid template includes a one-line fork note.

**v1.2** shipped **uv** dependency management with **Python 3.13** lockfile, **`jellyswipe/`** package layout with all code under a single importable package, multi-stage Docker build using uv, and comprehensive maintainer documentation. Plex support was removed to become Jellyfin-only.

**v1.3** shipped comprehensive unit tests with 48 tests covering database and Jellyfin provider modules, pytest-cov terminal coverage reporting, and GitHub Actions workflow for automated testing on every push/PR.

## Core Value

**Users can run a swipe session backed by Jellyfin**, with library browsing and deck behavior equivalent to the original Plex path.

## Current Milestone: v1.4 — Authorization Hardening

**Goal:** Resolve Issue #4 by eliminating client-controlled identity trust and enforcing verified user identity across all user-scoped routes.

**Target features:**
- Derive requester identity only from delegated server identity or validated Jellyfin token (`/Users/Me` resolution)
- Reject spoofable identity sources (`X-Provider-User-Id`, `X-Jellyfin-User-Id`, `X-Emby-UserId`, request-body `user_id`)
- Enforce 401 behavior when identity cannot be verified on protected endpoints
- Guarantee reads/writes/deletes are scoped to the verified identity only
- Add route-level tests proving spoofed headers are rejected and valid-token access still works

## Requirements

### Validated

- ✓ **Jellyfin server auth** — Configure base URL and credentials (or API key per server policy); obtain and reuse an access token for server API calls. *Phases 3–5 (v1.0).*
- ✓ **Jellyfin library parity** — Build the same in-app movie list shape the front end expects (`id`, `title`, `summary`, `thumb`, `rating`, `duration`, `year`) from Jellyfin movies; genre filtering and a “Recently Added”–style sort where the API allows. *Phases 4–5 (v1.0).*
- ✓ **Images** — Serve Jellyfin artwork through the app (extend or complement `/proxy` so thumbs work without exposing secrets in the browser). *Phases 4–5 (v1.0).*
- ✓ **User-scoped parity (within reason)** — Per-user match/history/undo and “add to list” behavior work in Jellyfin mode using Jellyfin identity (not Plex headers). Exact UX may use Jellyfin login/token headers instead of Plex pin, but outcomes should mirror Plex mode. *Phase 5 (v1.0).*
- ✓ **Milestone evidence and validation closure** — Jellyfin-forward operator E2E narrative, Nyquist-aligned `01–05` validation artifacts, and re-audit inputs consolidated for `/gsd-audit-milestone`. *Phase 8 (v1.0).*
- ✓ **Jellyfin browser delegate path** — When env credentials are configured, the SPA can bind to the server session without exposing API tokens in JSON; stale `localStorage` tokens cleared on success. *Phase 9 (v1.0).*
- ✓ **Poster containment** — Main deck, mini-posters, and match popup use `object-fit: contain` with black backing so wide one-sheets are not cropped. *Phase 9 (v1.0).*
- ✓ **Jelly Swipe branding & packaging (v1.1)** — BRAND-01–04: UI titles and PWA manifest; README/LICENSE fork policy; Unraid `jelly-swipe.html`; default DB path and Docker/CI image `andrewthetechie/jelly-swipe`; Jellyfin client identifier as Jelly Swipe. *v1.1.*
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
- ✓ **TEST-01** — Unit test suite for existing codebase with framework-agnostic approach. *Validated in Phase 14 (v1.3).*
- ✓ **TEST-02** — Modern pytest methods with fixtures and parametrize. *Validated in Phase 14 (v1.3).*
- ✓ **TEST-03** — Test coverage for core modules (db.py, jellyfin_library.py) — 48 tests total, 87% db.py coverage, 95%+ jellyfin_library.py coverage. *Validated in Phases 15-16 (v1.3).*
- ✓ **TEST-04** — Test configuration and CI integration — pytest-cov terminal output, GitHub Actions workflow on push/PR. *Validated in Phase 17 (v1.3).*

### Active

- [ ] **SEC-01** — Identity is resolved only from delegated server identity or validated Jellyfin token.
- [ ] **SEC-02** — Client-supplied identity headers and request-body identity fields are ignored/rejected.
- [ ] **SEC-03** — Protected endpoints return 401 when identity cannot be verified.
- [ ] **SEC-04** — User-scoped operations (`/room/swipe`, `/matches`, `/matches/delete`, `/undo`, `/watchlist/add`) operate only on the verified identity.
- [ ] **VER-01** — Automated tests prove header spoofing and body `user_id` injection cannot read/write/delete another user's data.

### Out of Scope

- **Plex support** — Explicit product decision: removed in v1.2, application is Jellyfin-only.
- **Replacing TMDB** — Trailers/cast stay on TMDB; no requirement to use Jellyfin plugins for trailers in v1.
- **TV shows / music** — Movies library only, matching current Plex `Movies` section assumption.
- **PyPI distribution (v1.2)** — The `jellyswipe` package is for repo layout and Docker/runtime imports only; no publishing to PyPI or `pip install jellyswipe` product story.
- **Flask route integration tests** — Framework-agnostic approach required for v1.3; can be added in future as integration tests.
- **Real Jellyfin/TMDB API calls in tests** — Unit tests should be isolated from external dependencies.
- **Parallel test execution (pytest-xdist)** — Not needed for initial test suite; can be added when test count grows.
- **Property-based testing (Hypothesis)** — Nice to have, not critical for v1.3.
- **End-to-end integration tests** — Separate concern from unit testing; can be added in v2+.

## Current state

- **Shipped:** **v1.0** (Jellyfin), **v1.1** (rename), **v1.2** (uv + package layout + Plex removal), and **v1.3** (unit tests) tagged; archives under `.planning/milestones/v1.0-*`, `v1.1-*`, `v1.2-*`, and `v1.3-*`.
- **In flight:** **v1.4 Authorization Hardening** planning to close Issue #4 (`https://github.com/andrewthetechie/jelly-swipe/issues/4`).
- **Runtime:** Flask + SQLite + SSE; `JellyfinLibraryProvider` under `jellyswipe/` package; Python 3.13 with uv dependency management.
- **UI:** Embedded HTML in `jellyswipe/templates/index.html` and mirrored `data/index.html` (PWA-oriented copy); product string **Jelly-Swipe** / **JellySwipe** throughout defaults.
- **Publish:** Docker Hub `andrewthetechie/jelly-swipe:latest` (push to `main`); GHCR `ghcr.io/andrewthetechie/jelly-swipe` on GitHub Release (see `.github/workflows/release-ghcr.yml`).
- **Tests:** 48 tests across 3 test files (test_infrastructure.py, test_db.py, test_jellyfin_library.py) with pytest framework; GitHub Actions workflow runs tests on every push/PR; pytest-cov provides terminal coverage reporting.

## Context

- Flask app lives under `jellyswipe/` package with `jellyswipe/__init__.py` (main app), `jellyswipe/db.py` (database), and `jellyswipe/jellyfin_library.py` (media provider); SQLite for rooms/swipes/matches; SSE for room updates (see `.planning/codebase/ARCHITECTURE.md`).
- Dependency management via uv with `pyproject.toml` and `uv.lock`; Python 3.13 required; multi-stage Docker build uses `uv sync --frozen` for reproducible installs.
- Application is Jellyfin-only; all Plex code, dependencies, and configuration removed in v1.2.
- Jellyfin exposes a documented REST API ([api.jellyfin.org](https://api.jellyfin.org/)); auth is token-based with a recommended `Authorization: MediaBrowser ...` header; legacy `X-Emby-Token` may be disabled on some servers — implementation should follow current server expectations and test against target versions.
- Test suite uses pytest with framework-agnostic imports (monkeypatching load_dotenv and Flask in conftest.py); all HTTP calls mocked in tests; function-scoped fixtures ensure complete test isolation.

## Constraints

- **Compatibility**: Support recent stable Jellyfin (10.8+) unless research proves a narrower window; call out version assumptions in README.
- **Security**: Do not log tokens; prefer headers over query-string API keys; HTTPS assumed for remote servers.
- **Minimal churn**: Prefer a clear provider abstraction over duplicating route handlers, while keeping the diff reviewable.
- **Test isolation**: All unit tests must be framework-agnostic and mock external dependencies to ensure fast, reliable execution in CI.

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
| pytest with framework-agnostic imports (v1.3) | Test modules directly without Flask app side effects; monkeypatch load_dotenv and Flask for clean imports. | Shipped v1.3 Phase 14 |
| Terminal-only coverage reporting (v1.3) | Simple, meets COV-01, no extra files or directories; HTML/XML deferred to v2. | Shipped v1.3 Phase 17 |
| Independent test CI workflow (v1.3) | Tests run on every PR for code review quality; Docker workflow focuses on deployment; no workflow coupling. | Shipped v1.3 Phase 17 |
| No coverage threshold in v1.3 (v1.3) | ADV-01 is v2 requirement; track coverage in reports but don't fail builds. | Shipped v1.3 Phase 17 |

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
*Last updated: 2026-04-25 after starting v1.4 milestone planning*
