# Jelly Swipe

## What This Is

Jelly Swipe is a small Flask app for shared "Tinder for movies" sessions: a host creates a room, guests join, everyone swipes on a deck pulled from a Jellyfin media server, and matches surface when two people swipe right on the same title. Trailers and cast come from TMDB. **v1.0** shipped Jellyfin backend, **v1.1** renamed to Jelly Swipe, **v1.2** migrated to uv + removed Plex, **v1.3** added 48 unit tests with CI, **v1.4** hardened authorization, and **v1.5** added comprehensive route tests (159 total) achieving 75% coverage with CSP compliance.

## Core Value

**Users can run a swipe session backed by Jellyfin**, with library browsing and deck behavior equivalent to the original Plex path.

## Current Milestone: Planning v1.6

**Next:** Define scope via `/gsd-new-milestone`

## Requirements

### Validated

- ✓ **Jellyfin server auth** — Configure base URL and credentials; obtain and reuse access token for server API calls. *v1.0.*
- ✓ **Jellyfin library parity** — Build movie list from Jellyfin; genre filtering and sort. *v1.0.*
- ✓ **Images** — Serve Jellyfin artwork through `/proxy` without exposing secrets. *v1.0.*
- ✓ **User-scoped parity** — Per-user match/history/undo using Jellyfin identity. *v1.0.*
- ✓ **Milestone evidence and validation closure** — E2E narrative and validation artifacts. *v1.0.*
- ✓ **Jellyfin browser delegate path** — SPA binds to server session without token leakage. *v1.0.*
- ✓ **Poster containment** — `object-fit: contain` with black backing. *v1.0.*
- ✓ **Jelly Swipe branding & packaging** — BRAND-01–04 complete. *v1.1.*
- ✓ **UV-01** — uv canonical dependency workflow. *v1.2.*
- ✓ **UV-02** — Python 3.13 target. *v1.2.*
- ✓ **DEP-01** — Newest 3.13-compatible versions. *v1.2.*
- ✓ **PKG-01** — `jellyswipe/` package with coherent imports. *v1.2.*
- ✓ **PKG-02** — Gunicorn loads from `jellyswipe:app`. *v1.2.*
- ✓ **DOCK-01** — Docker installs via uv, runs packaged app. *v1.2.*
- ✓ **DOC-01** — README describes uv-based setup. *v1.2.*
- ✓ **PLEX-REM-01/02/03** — All Plex code removed, Jellyfin-only. *v1.2.*
- ✓ **TEST-01/02/03/04** — 48 unit tests, CI workflow, coverage reporting. *v1.3.*
- ✓ **SEC-01/02** — Identity from trusted sources only; client headers rejected. *v1.4.*
- ✓ **FACTORY-01** — `create_app(test_config=None)` factory function with backwards-compatible global `app` instance. *v1.5 Phase 21.*
- ✓ **TEST-ROUTE-01** — 14 auth route tests (20 parametrized cases) with EPIC-01 header-spoof protection. *v1.5 Phase 23.*
- ✓ **TEST-ROUTE-02** — 13 XSS security tests with `_XSSSafeJSONProvider` for OWASP JSON XSS defense. *v1.5 Phase 24.*
- ✓ **TEST-ROUTE-03** — 27 room lifecycle tests covering all 6 endpoints. *v1.5 Phase 25.*
- ✓ **TEST-ROUTE-04** — 16 proxy SSRF prevention tests. *v1.5 Phase 26.*
- ✓ **TEST-ROUTE-05** — 8 SSE streaming tests achieving 78% coverage for `__init__.py`. *v1.5 Phase 27.*
- ✓ **COV-01** — `--cov-fail-under=70` CI enforcement; 75% total coverage. *v1.5 Phase 28.*

### Active

(No active requirements — awaiting v1.6 scope definition)

### Out of Scope

- **Plex support** — Explicit product decision: removed in v1.2, application is Jellyfin-only.
- **Replacing TMDB** — Trailers/cast stay on TMDB; no requirement to use Jellyfin plugins for trailers in v1.
- **TV shows / music** — Movies library only, matching current Plex `Movies` section assumption.
- **PyPI distribution** — `jellyswipe` package is for repo layout and Docker/runtime imports only.
- **Flask route integration tests** — Framework-agnostic approach required; route tests added in v1.5.
- **Real Jellyfin/TMDB API calls in tests** — Unit tests isolated from external dependencies.
- **Parallel test execution (pytest-xdist)** — Deferred to v2.
- **Property-based testing (Hypothesis)** — Deferred to v2.
- **End-to-end integration tests** — Deferred to v2+.

## Current state

- **Shipped:** **v1.0** (Jellyfin), **v1.1** (rename), **v1.2** (uv + package), **v1.3** (unit tests), **v1.4** (auth hardening), **v1.5** (route test coverage + CSP compliance).
- **In flight:** Next milestone definition (`/gsd-new-milestone`).
- **Runtime:** Flask + SQLite + SSE; `JellyfinLibraryProvider` under `jellyswipe/` package; Python 3.13 with uv; app factory pattern (`create_app(test_config=None)`).
- **Security:** `_XSSSafeJSONProvider` escapes HTML in all JSON responses; CSP-compliant HTML with external CSS/JS; verified identity hardening (v1.4).
- **UI:** External CSS (`jellyswipe/static/styles.css`), JS (`jellyswipe/static/app.js`), self-hosted Allura font (`jellyswipe/static/fonts/`), CSP-compliant HTML template.
- **Publish:** Docker Hub `andrewthetechie/jelly-swipe:latest`; GHCR `ghcr.io/andrewthetechie/jelly-swipe` on GitHub Release.
- **Tests:** 159 tests across 8 test files; GitHub Actions on every push/PR; 75% total coverage; CI enforces 70% threshold (`--cov-fail-under=70`).

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
| Verified identity hardening (v1.4) | Close Issue #4 by removing client-controlled identity trust and enforcing strict route authorization. | Shipped v1.4 Phases 18-20 |
| Flask app factory pattern (v1.5) | `create_app(test_config=None)` enables test isolation while preserving `jellyswipe:app` import. | ✓ Shipped v1.5 Phase 21 |
| Global XSS-safe JSON provider (v1.5) | `_XSSSafeJSONProvider` escapes `<`, `>`, `&` in all JSON output (OWASP recommendation). | ✓ Shipped v1.5 Phase 24 |
| External CSS/JS for CSP compliance (v1.5) | All inline styles/JS externalized; self-hosted font. CSP `default-src 'self'` compliant. | ✓ Shipped v1.5 Phase 29 |

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
*Last updated: 2026-04-26 after v1.5 milestone*
