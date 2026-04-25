# Phase 13: Remove Plex support - Context

**Gathered:** 2026-04-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Remove all Plex-related code, configuration, dependencies, and documentation from the codebase. This project will be **Jellyfin-only** going forward. All Plex client IDs, authentication flows, media provider implementations, and references must be completely removed.

**Explicitly out of this phase:** Adding new Jellyfin features, improving existing Jellyfin functionality, or other enhancements — this is purely a removal/cleanup phase.
</domain>

<decisions>
## Implementation Decisions

### Code Removal

- **D-01:** Remove **`PlexLibraryProvider`** class and all Plex-specific implementation code from `jellyswipe/` (formerly `media_provider/plex_library.py`).
- **D-02:** Remove **`get_provider()`** factory function and `reset()` function since only Jellyfin will remain — simplify to direct instantiation of `JellyfinLibraryProvider`.
- **D-03:** Remove all Plex-related environment variables: `PLEX_URL`, `PLEX_TOKEN`, `PLEX_CLIENT_IDENTIFIER`, and any Plex.tv authentication endpoints or logic.
- **D-04:** Remove Plex-specific routes and handlers: any `/plex/*` routes, Plex.tv pin auth flows, and Plex user identity extraction from headers (`X-Plex-User-ID`, etc.).
- **D-05:** Remove Plex-specific database schema elements if any exist (Plex user ID columns, Plex token storage, etc.) and migrate or drop as appropriate.
- **D-06:** Remove all conditional logic that checks `MEDIA_PROVIDER` environment variable — the app will now assume Jellyfin-only and validate only Jellyfin configuration.

### Dependency Cleanup

- **D-07:** Remove **`plexapi`** from `pyproject.toml` dependencies and regenerate `uv.lock`.
- **D-08:** Remove any Plex-related imports throughout the codebase (e.g., `from plexapi.server import PlexServer`, `from plexapi.myplex import MyPlexAccount`, etc.).

### Configuration & Environment

- **D-09:** Remove `MEDIA_PROVIDER` environment variable from documentation, Docker examples, and runtime validation — the app is now Jellyfin-only.
- **D-10:** Update all configuration validation to only check for Jellyfin-required environment variables: `JELLYFIN_URL`, `JELLYFIN_API_KEY` (or `JELLYFIN_USERNAME`/`JELLYFIN_PASSWORD` if auth flow remains).
- **D-11:** Remove any Plex-specific configuration sections from `README.md`, Docker compose examples, and Unraid template.

### Documentation Updates

- **D-12:** Update **`README.md`** to remove all Plex references — the app is now "Jelly Swipe: a Jellyfin-based Tinder for movies" (no "either Plex or Jellyfin" language).
- **D-13:** Remove or update any documentation describing Plex setup, Plex.tv authentication, or Plex-specific features.
- **D-14:** Update **`PROJECT.md`** core value statement to reflect Jellyfin-only support (remove "either Plex or Jellyfin" language).
- **D-15:** Archive or remove any Plex-specific documentation files (e.g., if there are separate Plex setup guides).

### Testing & Validation

- **D-16:** Remove any Plex-specific test cases, test fixtures, or test data.
- **D-17:** Update integration tests to only validate Jellyfin flows.
- **D-18:** Verify the application starts successfully with only Jellyfin configuration and that no Plex-related errors occur in logs.

### the agent's Discretion

- Specific approach to database schema migration (drop columns vs migrate data, though no Plex user data should need preservation)
- Whether to keep a minimal `LibraryMediaProvider` base class or inline all functionality into `JellyfinLibraryProvider`
- Exact wording updates in documentation (as long as Plex references are completely removed)

</decisions>

<specifics>
## Specific Ideas

- User wants to simplify the codebase by removing the Plex abstraction layer entirely
- User values a clean, single-backend codebase over maintaining dual provider support
- This is a strategic decision to focus on Jellyfin as the sole supported backend
- All Plex user data, matches, and history will be lost (acceptable for this cleanup phase)

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements

- `.planning/ROADMAP.md` — Phase 13 goal, success criteria, boundary
- `.planning/REQUIREMENTS.md` — Any requirements that reference Plex support (to be removed or updated)
- `.planning/PROJECT.md` — Core value statement and current milestone context

### Prior phase context

- `.planning/phases/11-jellyswipe-package-layout/11-CONTEXT.md` — Current package structure under `jellyswipe/`
- `.planning/phases/10-uv-python-3-13-lockfile/10-CONTEXT.md` — Dependency management via `pyproject.toml` and `uv.lock`

### Current code state (pre-change)

- `jellyswipe/__init__.py` — Main Flask app with provider factory and conditional logic
- `jellyswipe/plex_library.py` — Plex implementation (to be removed)
- `jellyswipe/jellyfin_library.py` — Jellyfin implementation (will remain)
- `jellyswipe/base.py` — Abstract `LibraryMediaProvider` class (may be removed or kept)
- `jellyswipe/factory.py` — Provider factory functions (to be removed/simplified)
- `pyproject.toml` — Contains `plexapi` dependency (to be removed)
- `README.md` — Contains Plex setup instructions and "either/or" language (to be updated)
- `Dockerfile` — May reference Plex environment variables (to be cleaned up)

### Codebase maps

- `.planning/codebase/STRUCTURE.md` — Current directory layout and file purposes
- `.planning/codebase/ARCHITECTURE.md` — Current layers and data flow (will simplify after Plex removal)

No external specs or ADRs for this phase — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`jellyswipe/jellyfin_library.py`** — Will become the sole media provider implementation
- **`jellyswipe/db.py`** — Database functions may need updates to remove Plex-specific columns
- **`uv.lock`** — Will need regeneration after removing `plexapi` from `pyproject.toml`

### Established Patterns

- **Provider abstraction** — `LibraryMediaProvider` base class with `JellyfinLibraryProvider` implementation; after removal, may simplify to just `JellyfinLibraryProvider`
- **Factory pattern** — `get_provider()` and `reset()` functions currently instantiate based on `MEDIA_PROVIDER`; after removal, app can directly instantiate `JellyfinLibraryProvider`
- **Environment-based configuration** — Currently checks `MEDIA_PROVIDER` env var; after removal, only Jellyfin env vars are required

### Integration Points

- **Flask routes** — Remove any Plex-specific routes (`/plex/*`, `/auth/plex`, etc.)
- **Database schema** — Remove Plex user ID columns if present; may need migration script
- **Docker environment** — Update Dockerfile and compose examples to remove Plex env vars
- **Authentication** — Remove Plex.tv pin auth flow; keep only Jellyfin auth (if browser delegate path remains)

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

### Reviewed Todos (not folded)

No todos matched for Phase 13.

</deferred>

---

*Phase: 13-remove-plex-support*
*Context gathered: 2026-04-24*