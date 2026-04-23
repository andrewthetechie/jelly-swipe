# Phase 2: Media provider abstraction - Context

**Gathered:** 2026-04-22  
**Status:** Ready for planning

<domain>
## Phase Boundary

Introduce a **stable library-facing provider API** so genres, deck fetch, per-item metadata for TMDB, server identity, and poster/image access flow through one abstraction (ARC-01). With `MEDIA_PROVIDER=plex`, behavior matches the pre-refactor Plex integration (ARC-02). Jellyfin-specific HTTP and auth live in a **dedicated module** in later phases—not scattered helpers (ARC-03); Phase 2 does **not** add a Jellyfin implementation file.

In `jellyfin` mode before Phases 3–4, **startup continues to fail fast** with a clear message (roadmap); this phase does not make Jellyfin library calls work.

</domain>

<decisions>
## Implementation Decisions

### Provider interface shape

- **D-01:** Express the contract with **`abc.ABC`** and a concrete **`PlexLibraryProvider`** (or equivalent name) so Phase 3 can add a sibling concrete class with an obvious method set.
- **D-02:** The Phase 2 interface **covers** all of: **(A)** genre list, **(B)** deck JSON (same shape as today’s card objects), **(C)** resolve movie item by provider id for TMDB title/year, **(D)** server stable id + display name, **(E)** image bytes / streaming for card thumbs (equivalent responsibilities to today’s `/proxy` rules—not necessarily a single method name, but the abstraction owns the behavior).
- **D-03:** **Do not** fold **Plex.tv pin auth** (`/auth/*`) or **`/watchlist/add`** into the library provider; they stay **Plex-specific in `app.py`** (or adjacent small helpers) until user-parity work—this phase stays library + TMDB chain + proxy + server-info.
- **D-04:** Provider/library code **raises exceptions** on failure; Flask routes keep the existing **try/except → JSON error** pattern unless a route intentionally changes later.

### Module layout

- **D-05:** New code lives under a package directory **`media_provider/`** (with `__init__.py` and split modules as needed: base, Plex implementation, factory). Imports from `app.py` stay standard `from media_provider import ...` with **no** `pip` / Docker entrypoint changes.
- **D-06:** **No** `jellyfin.py` stub file in Phase 2; Jellyfin client module arrives with Phase 3. ARC-03 is satisfied when that module exists—not by an empty placeholder.

### Singleton vs per-request

- **D-07:** **Process-wide singleton** provider (factory `get_provider()` or equivalent) with an explicit **`reset()`** mirroring today’s `reset_plex()` invalidation after connection errors.
- **D-08:** **Genre cache** moves off loose `app.py` globals into **state held by the Plex provider instance** (or the singleton), not a separate module-level `_genre_cache` in `app.py` after the refactor.

### Refactor sequencing

- **D-09:** Prefer **one mechanical pass**: introduce the factory and route call sites behind `get_provider()` while moving Plex logic into `media_provider/` in a **single coherent change set** (appropriate for current app size).
- **D-10:** Keep **`/plex/server-info`** and the existing JSON shape **`{ machineIdentifier, name }`** for Plex mode—no neutral rename in this phase (front-end unchanged).

### Discussion note

- **D-11:** Gray areas 1–4 were discussed; user replied **`defaults`**, accepting the **recommended** option for every presented sub-question in the session (see `02-DISCUSSION-LOG.md`).

### Claude's Discretion

- Exact **method names** on the ABC and small internal helpers.
- Order of migrating call sites and any **tiny** shims needed only if a one-shot diff is hard to review.
- Exact **wording** of docstrings and error messages.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning / product

- `.planning/PROJECT.md` — Either-or provider, minimal churn, Plex vs Jellyfin scope.
- `.planning/REQUIREMENTS.md` — ARC-01, ARC-02, ARC-03 wording.
- `.planning/ROADMAP.md` — Phase 2 goal and success criteria (including fail-fast Jellyfin before Phases 3–4).
- `.planning/phases/01-configuration-startup/01-CONTEXT.md` — `MEDIA_PROVIDER`, env validation, and Phase 1 locked behavior.

### Implementation (pre-refactor / integration map)

- `app.py` — `get_plex`, `reset_plex`, `get_plex_genres`, `fetch_plex_movies`, `/proxy`, `/plex/server-info`, `/get-trailer/<id>`, `/cast/<id>`, `/genres`, `/movies`, room create + genre refetch paths.

### Codebase intelligence

- `.planning/codebase/ARCHITECTURE.md` — Monolith, globals, SSE, Plex singleton pattern.
- `.planning/codebase/STRUCTURE.md` — Where new modules fit; no `src/` layout today.
- `.planning/codebase/INTEGRATIONS.md` — Plex, TMDB, proxy, env vars.

No separate SPEC for this phase — requirements are in `REQUIREMENTS.md` and roadmap success criteria.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets

- **`get_plex` / `reset_plex` / `_plex_instance`** — Behavior to encapsulate inside `PlexLibraryProvider` with `reset()` instead of free functions + global.
- **`get_plex_genres` / `_genre_cache`** — Move caching onto the provider singleton per D-08.
- **`fetch_plex_movies`** — Core deck shape and genre/Recently Added semantics; becomes provider-backed deck fetch.
- **`/proxy`** — Already branches on `MEDIA_PROVIDER`; poster path validation and upstream fetch belong behind the provider for parity work in later phases (interface owns “image for thumb” responsibility per D-02E).

### Established patterns

- **Retry then reset** — `try` / `reset_plex()` / retry around `fetchItem` and server info; preserve inside Plex implementation or thin route wrappers as appropriate.
- **JSON error responses** — `{ 'error': str(e) }` style; keep after abstraction (D-04).

### Integration points

- **`app.py` routes** — Primary migration surface: replace direct `get_plex()` / `fetch_plex_movies()` / `get_plex_genres()` calls with `get_provider()` (or equivalent) while leaving Plex.tv auth routes untouched (D-03).

</code_context>

<specifics>
## Specific Ideas

- User chose **`defaults`** for all recommended options in the discuss-phase batch (interface ABC, full API surface A–E, watchlist outside provider, exceptions, `media_provider/` package, no Jellyfin stub file yet, singleton + reset, cache on provider, one-pass refactor, keep `/plex/server-info`).

</specifics>

<deferred>
## Deferred Ideas

- **Neutral `/media/server-info` route** — Deferred; keep `/plex/server-info` for Phase 2 (D-10).
- **Facade-first two-step refactor** — User chose one mechanical pass (D-09); optional follow-up if review needs smaller chunks.
- **Fold watchlist / pin auth into provider** — Explicitly out of Phase 2 scope (D-03).

### Reviewed Todos (not folded)

- None — `todo.match-phase` returned no matches for phase 2.

</deferred>

---

*Phase: 02-media-provider-abstraction*  
*Context gathered: 2026-04-22*
