# Phase 13: Remove Plex support - Research

**Researched:** 2026-04-24
**Status:** Complete

<research_findings>
## Research Findings

### Current Plex Code Locations

Based on codebase analysis, Plex-related code is found in:

1. **`jellyswipe/plex_library.py`** — Entire Plex implementation (to be removed)
2. **`jellyswipe/factory.py`** — Provider factory with Plex conditional logic (to be removed/simplified)
3. **`jellyswipe/__init__.py`** — May contain Plex-specific route handlers or env validation
4. **`pyproject.toml`** — Contains `plexapi` dependency
5. **`README.md`** — Contains Plex setup instructions and configuration examples
6. **Database schema** — May contain Plex user ID columns (to be verified)

### Dependencies to Remove

- `plexapi` — Python library for Plex API interaction
- Any transitive dependencies that become unused after `plexapi` removal

### Configuration Variables to Remove

- `PLEX_URL`
- `PLEX_TOKEN`
- `PLEX_CLIENT_IDENTIFIER`
- `MEDIA_PROVIDER` (no longer needed since only Jellyfin remains)

### Documentation Sections to Update

- README.md: Remove "Plex vs Jellyfin" comparison, Plex setup steps
- PROJECT.md: Update core value to reflect Jellyfin-only support
- Any Docker compose examples showing Plex configuration
- Unraid template Plex fields (if present)

### Potential Risks

1. **Database migration** — If existing users have Plex data in their databases, removing Plex columns may cause issues. Recommend adding a migration script or documenting manual cleanup.
2. **Breaking change** — Existing Plex users will need to migrate to Jellyfin or lose data. This should be clearly communicated in release notes.
3. **Test coverage** — Ensure all existing tests still pass after Plex removal; may need to update test fixtures.

### Success Criteria Validation

After Plex removal, the following should be true:
1. Application starts with only Jellyfin configuration
2. No `plexapi` or Plex-related imports remain in codebase
3. No Plex environment variables are referenced in code or documentation
4. All tests pass with Jellyfin-only configuration
5. Docker image builds successfully without Plex dependencies

</research_findings>

<open_questions>
## Open Questions

1. Should we keep the `LibraryMediaProvider` base class for future extensibility, or inline everything into `JellyfinLibraryProvider`?
2. How should we handle database migration for existing Plex users? (Drop columns, migrate data, or document manual cleanup?)
3. Should we add a deprecation period or communication plan for existing Plex users?

</open_questions>

<external_references>
## External References

None — this is an internal cleanup phase with no external dependencies.

</external_references>

---

*Phase: 13-remove-plex-support*
*Research completed: 2026-04-24*