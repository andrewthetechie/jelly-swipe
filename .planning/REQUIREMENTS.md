# Requirements: Kino Swipe — Jellyfin support

**Defined:** 2026-04-22  
**Core Value:** Users can run a swipe session backed by either Plex or Jellyfin (one backend per deployment), with library browsing and deck behavior equivalent to today’s Plex path.

## v1 Requirements

### Configuration

- [ ] **CFG-01**: Operator can set a single `MEDIA_PROVIDER` (or equivalent) to `plex` or `jellyfin` so the process uses exactly one backend for all library operations.
- [ ] **CFG-02**: On startup, the app validates environment variables for the **active** provider only (Jellyfin mode must not require `PLEX_URL` / `PLEX_TOKEN`).
- [ ] **CFG-03**: `README.md` and `docker-compose` documentation list provider-specific variables and the “two instances for both” deployment note.

### Architecture / abstraction

- [ ] **ARC-01**: Library access (genres, movie deck fetch, single-item metadata for TMDB, server display name/identifier, image fetch) flows through a provider abstraction callable from routes.
- [ ] **ARC-02**: With `MEDIA_PROVIDER=plex`, behavior matches the pre-change Plex integration (deck shape, genres, proxy rules, watchlist, per-user headers).
- [ ] **ARC-03**: Jellyfin-specific HTTP and auth live in a dedicated module or class, not scattered across unrelated helpers.

### Jellyfin — server auth & client

- [x] **JAUTH-01**: Jellyfin mode supports configurable base URL plus server-side credentials appropriate for unattended access (document supported patterns: e.g. username/password login and/or API key, per final plan).
- [x] **JAUTH-02**: The app obtains and reuses a Jellyfin access token (or equivalent) and recovers cleanly after connection/auth errors (similar spirit to `reset_plex()`).
- [x] **JAUTH-03**: Secrets are not written to logs or returned in JSON error payloads.

### Jellyfin — library & media

- [x] **JLIB-01**: Jellyfin mode builds the same per-movie JSON objects the UI already consumes (`id`, `title`, `summary`, `thumb`, `rating`, `duration`, `year`) from Jellyfin movie items.
- [x] **JLIB-02**: Jellyfin mode exposes a genre list and filtering behavior equivalent to current Plex behavior, including a time-ordered “Recently Added” style deck when that option is selected.
- [x] **JLIB-03**: Thumbnails for Jellyfin-backed cards load through the Flask app with validation that prevents open proxy abuse.
- [x] **JLIB-04**: `/get-trailer/<movie_id>` and `/cast/<movie_id>` work in Jellyfin mode using metadata from the Jellyfin item (title/year) into the existing TMDB flow.
- [x] **JLIB-05**: A server-info style endpoint returns a stable machine/server identifier and display name in Jellyfin mode (for UI parity with `/plex/server-info` or a renamed shared route).

### Jellyfin — user scope & parity

- [ ] **JUSR-01**: In Jellyfin mode, per-user match lists, history, delete, and undo key off a Jellyfin-derived user identifier carried like today’s `X-Plex-User-ID` / `plex_id` columns (same columns may store Jellyfin user IDs; document semantics).
- [ ] **JUSR-02**: In Jellyfin mode, “add to watchlist” (or equivalent user list) succeeds when the client supplies a valid Jellyfin user token/session established by the app’s auth flow.
- [ ] **JUSR-03**: The front end uses one coherent auth path per provider (Plex pin unchanged; Jellyfin uses a Jellyfin-appropriate login or token capture documented in README).
- [ ] **JUSR-04**: Docker image and `requirements.txt` install all Jellyfin-mode dependencies; CI/build still passes.

## v2 Requirements

### Operations

- **OPS-01**: Optional DB migration renaming `plex_id` to a neutral `provider_user_id` for clarity.

### Product

- **PRD-01**: Single instance supporting multiple configured libraries (pick Movies library by ID).

## Out of Scope

| Feature | Reason |
|---------|--------|
| Plex and Jellyfin active in one process | Explicit product decision; use two instances. |
| TV episodes or music libraries | Matches current Plex movies-only scope. |
| Replacing TMDB for trailers/cast | Not required for parity; keep existing TMDB stack. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CFG-01 | Phase 1 | Pending |
| CFG-02 | Phase 1 | Pending |
| CFG-03 | Phase 1 | Pending |
| ARC-01 | Phase 2 | Pending |
| ARC-02 | Phase 2 | Pending |
| ARC-03 | Phase 2 | Pending |
| JAUTH-01 | Phase 3 | Done |
| JAUTH-02 | Phase 3 | Done |
| JAUTH-03 | Phase 3 | Done |
| JLIB-01 | Phase 4 | Done |
| JLIB-02 | Phase 4 | Done |
| JLIB-03 | Phase 4 | Done |
| JLIB-04 | Phase 4 | Done |
| JLIB-05 | Phase 4 | Done |
| JUSR-01 | Phase 5 | Pending |
| JUSR-02 | Phase 5 | Pending |
| JUSR-03 | Phase 5 | Pending |
| JUSR-04 | Phase 5 | Pending |

**Coverage:**

- v1 requirements: 17 total  
- Mapped to phases: 17  
- Unmapped: 0 ✓  

---
*Requirements defined: 2026-04-22*  
*Last updated: 2026-04-24 after Phase 4 execution (JLIB-01–05 verified)*
