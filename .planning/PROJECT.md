# Jelly Swipe

## What This Is

Jelly Swipe is a FastAPI app for shared "Tinder for movies" sessions backed by Jellyfin. A host creates a room, guests join, everyone swipes on a Jellyfin movie deck, and matches appear when participants swipe right on the same title. Trailers and cast metadata continue to come from TMDB.

## Core Value

Users can run a swipe session backed by Jellyfin, with library browsing, deck behavior, and match behavior preserved across framework changes.

## Current State

**Shipped:** v2.0 Flask → FastAPI + MVC Refactor on 2026-05-05.

The app now runs as FastAPI on Uvicorn, with `jellyswipe/__init__.py` reduced to an app factory that mounts domain routers for auth, rooms, media, proxy, and static assets. Shared request logic lives in `jellyswipe/dependencies.py`, session state uses Starlette `SessionMiddleware`, and the test suite uses FastAPI `TestClient`.

**Current verification:** 328 tests pass locally after the final PR fixes. The milestone archive records the earlier audit gaps and later closure artifacts.

## Current Milestone: v2.1 Alembic + Async SQLAlchemy Persistence

**Goal:** Replace ad hoc SQLite schema management with Alembic migrations and async SQLAlchemy persistence while preserving Jelly Swipe behavior.

**Target features:**
- Alembic owns schema creation and versioned migrations instead of `init_db()` ad hoc DDL and PRAGMA column checks.
- SQLAlchemy declarative ORM models define the app schema; SQLModel is explicitly excluded.
- All application database interactions use async SQLAlchemy APIs and fit the existing FastAPI MVC/domain-router organization.
- Existing room, swipe, match, token, SSE, and test behaviors remain compatible during and after the migration.

## Validated Requirements

### v2.0

- ✓ **FAPI-01** — FastAPI replaces Flask; Uvicorn replaces Gunicorn+gevent. *Validated in Phases 31 and 35.*
- ✓ **FAPI-02** — Existing HTTP endpoints retain URL paths, methods, status codes, and response shapes. *Validated in Phase 33.*
- ✓ **FAPI-03** — `/room/{code}/stream` runs as an async SSE path using non-blocking sleep and connection cleanup. *Validated in Phase 34.*
- ✓ **FAPI-04** — Session management uses Starlette `SessionMiddleware` with the existing `FLASK_SECRET` operator env var. *Validated in Phase 31.*
- ✓ **ARCH-01** — Route handlers split into auth, rooms, media, proxy, and static routers. *Validated in Phase 33.*
- ✓ **ARCH-03** — Auth, DB, provider access, and rate limiting shared through FastAPI dependency helpers. *Validated in Phase 32.*
- ✓ **ARCH-04** — `jellyswipe/__init__.py` is a thin app factory. *Validated in Phase 33.*
- ✓ **DEP-01** — Dependencies and Docker CMD updated for FastAPI/Uvicorn. *Validated in Phase 30.*
- ✓ **TST-01** — Tests migrated to FastAPI `TestClient`; full suite passes. *Validated in Phase 35 and post-PR fixes.*

### Previous Milestones

Validated requirements from v1.0–v1.7 are archived under `.planning/milestones/`.

## Active Requirements

- [ ] Replace ad hoc migrations with Alembic-managed migrations.
- [ ] Replace handwritten SQLite schema definitions with SQLAlchemy declarative models, not SQLModel.
- [ ] Convert database access paths to async SQLAlchemy sessions and queries.
- [ ] Preserve current MVC/router boundaries and existing Jelly Swipe runtime behavior.

## Deferred

- **ARCH-02** — Pydantic v2 models for request bodies and significant response shapes. Deferred from v2.0 to a future milestone.
- Provider dependency purity — Some route handlers still call `get_provider()` directly instead of declaring `Depends(get_provider)`. This is functional but worth revisiting if dependency override/testing ergonomics matter.
- Naming cleanup — `FLASK_SECRET` remains the session-secret env var for backward compatibility, but the name is now historically misleading.
- Router utility duplication — Error/logging helpers are duplicated across routers and can be consolidated later.

## Out of Scope

- **Plex support** — Removed in v1.2; Jelly Swipe is Jellyfin-only.
- **Replacing TMDB** — Trailers and cast stay on TMDB.
- **TV shows / music** — Movies library only.
- **PyPI distribution** — Docker/runtime repository package only.
- **WebSocket upgrade** — SSE remains sufficient until product needs change.

## Context

- Runtime: Python 3.13, uv, FastAPI, Uvicorn, SQLite, SSE, Jellyfin, TMDB.
- Main package: `jellyswipe/`.
- Planning archives: `.planning/milestones/`.
- Current roadmap: `.planning/ROADMAP.md`.
- Fresh requirements file is intentionally absent after v2.0 close; the next milestone should create one.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Keep Jellyfin as the only media backend | Plex was removed in v1.2 to reduce scope and maintenance burden. | Adopted |
| Keep TMDB for trailers/cast | Existing title/year lookup works and avoids expanding Jellyfin plugin assumptions. | Adopted |
| Use uv and Python 3.13 | Reproducible dependency management and current Python target. | Shipped v1.2 |
| Migrate Flask to FastAPI | Cleaner async/SSE story, dependency injection, and current proof-of-concept hardening. | Shipped v2.0 |
| Preserve `FLASK_SECRET` env var | Avoid breaking existing deployments during framework migration. | Shipped v2.0; revisit naming later |
| Defer Pydantic models | Keep v2.0 focused on behavior parity and framework migration. | Deferred to future milestone |
| Use browser session identity for room participants | Two windows using the same Jellyfin account should still be able to match. | Shipped post-v2.0 PR fix |

## Evolution

This document is updated at milestone boundaries. Historical requirement detail now lives in milestone archives so the active context stays small.

---
*Last updated: 2026-05-05 after v2.1 milestone start*
