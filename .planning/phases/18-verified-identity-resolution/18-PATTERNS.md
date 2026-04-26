# Phase 18 Pattern Map

**Phase:** 18 — Verified Identity Resolution  
**Generated:** 2026-04-25

## Target Files

- `jellyswipe/__init__.py`
- `jellyswipe/jellyfin_library.py` (read-only reference unless compatibility fix needed)

## Reusable Patterns

### Pattern A: Central request helper for route auth context
- **Reference:** `_provider_user_id_from_request()` and `_jellyfin_user_token_from_request()` in `jellyswipe/__init__.py`
- **Use in Phase 18:** Keep identity policy centralized in helper functions to avoid per-route divergence.

### Pattern B: Provider-mediated identity trust
- **Reference:** `resolve_user_id_from_token()` in `jellyswipe/jellyfin_library.py`
- **Use in Phase 18:** Trust only resolved user IDs returned from Jellyfin API calls.

### Pattern C: Process-local in-memory caching
- **Reference:** `_cached_user_id`, `_cached_library_id`, `_genre_cache` in `JellyfinLibraryProvider`
- **Use in Phase 18:** Implement token-hash cache as process-local map with explicit TTL checks.

## Data-Flow Constraints

1. `Authorization` header token extraction remains tolerant (`Token="..."` parse).
2. Token trust must still be established by Jellyfin user lookup.
3. Alias headers must not be interpreted as identity source.
4. Delegate identity path remains first-priority for session-based flow.

## Integration Notes

- Phase 18 should avoid route-level response contract rewrites; those belong to Phase 19.
- If helper return semantics are expanded (e.g., unauthorized classification), keep the adapter small and backward-compatible for existing call sites until Phase 19 refactors route behavior.
