# Phase 13: Remove Plex support - Discussion Log

**Phase started:** 2026-04-24

## Discussion Summary

### Initial Scope Discussion (2026-04-24)

**Decision:** Remove all Plex code and references — project will be Jellyfin-only going forward.

**Rationale:** 
- Simplify codebase by removing dual-provider complexity
- Focus development effort on single backend (Jellyfin)
- Reduce maintenance burden and technical debt
- Align with project's current direction and user feedback

**Scope confirmed:**
- Remove `PlexLibraryProvider` and all Plex implementation code
- Remove `plexapi` dependency
- Remove Plex environment variables and configuration
- Remove Plex-specific routes and authentication flows
- Update all documentation to reflect Jellyfin-only support
- Clean up database schema to remove Plex-specific columns

**Out of scope:**
- Adding new Jellyfin features (future phases)
- Improving existing Jellyfin functionality (future phases)
- Migrating Plex user data to Jellyfin (not supported)

### Implementation Approach (2026-04-24)

**Key decisions:**
1. Remove provider factory pattern — directly instantiate `JellyfinLibraryProvider`
2. Keep `LibraryMediaProvider` base class for potential future extensibility
3. Drop Plex database columns rather than migrate (no data migration needed)
4. Update all documentation to remove Plex references completely
5. Add clear deprecation notice in release notes for Plex users

**Open questions resolved:**
- Base class: Keep `LibraryMediaProvider` for future extensibility
- Database migration: Drop Plex columns, no data migration
- User communication: Add deprecation notice in release notes

---

*Phase: 13-remove-plex-support*
*Discussion log last updated: 2026-04-24*