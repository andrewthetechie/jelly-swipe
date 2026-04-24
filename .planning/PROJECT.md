# Jelly Swipe

## What This Is

Jelly Swipe is a small Flask app for shared “Tinder for movies” sessions: a host creates a room, guests join, everyone swipes on a deck pulled from a home media server, and matches surface when two people swipe right on the same title. Trailers and cast come from TMDB. **v1.0 shipped** a first-class **Jellyfin** alternative alongside Plex: one active backend per process (`MEDIA_PROVIDER`), the same card JSON and routes for the swipe experience, and (Phase 9) optional **server-delegated** Jellyfin browser identity plus poster letterboxing in the embedded UI.

**v1.1** completes the public rename from **Kino Swipe** (default database filename, Docker image, UI titles, Plex client id, and maintainer-facing docs). Upstream attribution lives only in `README.md` and `LICENSE` (see fork link there).

## Core Value

**Users can run a swipe session backed by either Plex or Jellyfin** (one backend per deployment), with library browsing and deck behavior equivalent to today’s Plex path.

## Requirements

### Validated

- ✓ **Plex-backed sessions** — Rooms load shuffled movie decks from a configured Plex `Movies` library; genres (including “Recently Added”) drive refetches (`fetch_plex_movies`, `/movies`, `/genres`). *Existing — codebase map.*
- ✓ **Plex metadata in UI** — Posters via `/proxy` (Plex library paths + admin token), runtime/year/summary on cards. *Existing.*
- ✓ **TMDB enrichment** — Trailers and cast from TMDB using title/year from the media item (`get_trailer`, `get_cast`). *Existing.*
- ✓ **Plex end-user flows** — Plex.tv pin auth for user token; watchlist add; `X-Plex-User-ID` for per-user matches/history/undo (`/watchlist/add`, `/matches`, etc.). *Existing.*
- ✓ **Jellyfin server auth** — Configure base URL and credentials (or API key per server policy); obtain and reuse an access token for server API calls. *Phases 3–5 (milestone).*
- ✓ **Jellyfin library parity** — Build the same in-app movie list shape the front end expects (`id`, `title`, `summary`, `thumb`, `rating`, `duration`, `year`) from Jellyfin movies; genre filtering and a “Recently Added”–style sort where the API allows. *Phases 4–5 (milestone).*
- ✓ **Images** — Serve Jellyfin artwork through the app (extend or complement `/proxy` so thumbs work without exposing secrets in the browser). *Phases 4–5 (milestone).*
- ✓ **Either/or configuration** — Exactly one active media provider per process (`plex` **or** `jellyfin`); env and startup validation reflect the choice. Users who want both run two instances. *Phases 1–5 (milestone).*
- ✓ **User-scoped parity (within reason)** — Per-user match/history/undo and “add to list” behavior work in Jellyfin mode using Jellyfin identity (not Plex headers). Exact UX may use Jellyfin login/token headers instead of Plex pin, but outcomes should mirror Plex mode. *Phase 5.*
- ✓ **Milestone evidence and validation closure** — Jellyfin-forward operator E2E narrative, Nyquist-aligned `01–05` validation artifacts, and re-audit inputs consolidated for `/gsd-audit-milestone`. *Phase 8.*
- ✓ **Jellyfin browser delegate path** — When env credentials are configured, the SPA can bind to the server session without exposing API tokens in JSON; stale `localStorage` tokens cleared on success. *Phase 9.*
- ✓ **Poster containment** — Main deck, mini-posters, and match popup use `object-fit: contain` with black backing so wide one-sheets are not cropped. *Phase 9.*

### Active (next milestone candidates)

- [ ] **ARC-02 closure** — Formal Plex regression matrix in `02-VERIFICATION.md` still partial at v1.0 close; treat as v1.1 hardening unless explicitly descoped.
- [ ] **OPS-01 / PRD-01** — Neutral DB column naming and multi-library selection (see archived `v1.0-REQUIREMENTS.md` v2 section).

### Out of Scope

- **Both Plex and Jellyfin in a single process** — Explicit product decision: dual stacks require two deployments/instances.
- **Replacing TMDB** — Trailers/cast stay on TMDB; no requirement to use Jellyfin plugins for trailers in v1.
- **TV shows / music** — Movies library only, matching current Plex `Movies` section assumption.

## Current state

- **Shipped:** v1.0 tagged; planning archives under `.planning/milestones/v1.0-*`.
- **v1.1 (active):** Jelly Swipe naming in UI, PWA manifest, `app.py` defaults (`DB_PATH`, `CLIENT_ID`, Plex product string), Jellyfin `MediaBrowser` client string, Docker Hub / compose coordinates (`andrewthetechie/jelly-swipe`), Unraid template `jelly-swipe.html`.
- **Runtime:** Flask + SQLite + SSE; `media_provider` package with `PlexLibraryProvider` and `JellyfinLibraryProvider`.
- **UI:** Embedded HTML in `templates/index.html` and mirrored `data/index.html` (PWA-oriented copy).

## Context

- Monolithic `app.py` Flask app; SQLite for rooms/swipes/matches; SSE for room updates (see `.planning/codebase/ARCHITECTURE.md`).
- Plex uses admin `PLEX_URL` + `PLEX_TOKEN` for library access and `plexapi`; users optionally authenticate via Plex.tv for watchlist and per-user rows keyed by `plex_id` in DB columns.
- Jellyfin exposes a documented REST API ([api.jellyfin.org](https://api.jellyfin.org/)); auth is token-based with a recommended `Authorization: MediaBrowser ...` header; legacy `X-Emby-Token` may be disabled on some servers — implementation should follow current server expectations and test against target versions.

## Constraints

- **Compatibility**: Support recent stable Jellyfin (10.8+) unless research proves a narrower window; call out version assumptions in README.
- **Security**: Do not log tokens; prefer headers over query-string API keys; HTTPS assumed for remote servers.
- **Minimal churn**: Prefer a clear provider abstraction over duplicating route handlers, while keeping the diff reviewable.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Either-or media provider per instance | User request; keeps config and caching simple; avoids two libraries fighting for globals. | Adopted (Phase 1+) |
| Two instances for Plex + Jellyfin together | User request; avoids multi-tenant complexity in one DB/session model. | Adopted (Phase 1+) |
| Keep TMDB for trailers/cast | Already works from title/year; Jellyfin metadata is optional enhancement later. | Adopted |
| Jellyfin delegate browser auth | Remove redundant browser password collection when server env auth exists; session-only token resolution server-side. | Shipped v1.0 Phase 9 |

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
*Last updated: 2026-04-24 — **v1.1** rebrand milestone in progress*
