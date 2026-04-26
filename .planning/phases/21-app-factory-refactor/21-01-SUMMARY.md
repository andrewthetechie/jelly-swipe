---
phase: 21-app-factory-refactor
plan: 01
subsystem: Flask Application Factory
tags: [refactor, factory-pattern, backwards-compatibility, test-isolation]
dependency_graph:
  requires: []
  provides: [21-02]
  affects: []
tech_stack:
  added: []
  patterns:
    - name: Flask App Factory Pattern
      description: create_app(test_config=None) function for application instantiation
    - name: Module-level Singletons
      description: Provider and token cache remain at module level for backwards compatibility
key_files:
  created: []
  modified:
    - jellyswipe/__init__.py
decisions:
  - id: D-01
    title: Factory signature
    content: Factory function named exactly create_app(test_config=None) as specified in FACTORY-01
  - id: D-05
    title: Environment validation timing
    content: Keep environment variable validation at module import time for early production failure
  - id: D-10
    title: Database initialization timing
    content: Database initialization (init_db()) moved into factory, not at module import
  - id: D-13
    title: Provider singleton pattern
    content: Keep _provider_singleton and _token_user_id_cache at module level for test compatibility
metrics:
  duration: "PT8M"
  completed_date: "2026-04-26"
  lines_added: 465
  lines_removed: 437
  files_modified: 1
  test_results: "27/27 tests passed (test_route_authorization.py)"
  coverage_before: "24% (jellyswipe/__init__.py)"
  coverage_after: "47% (jellyswipe/__init__.py)"
---

# Phase 21 Plan 01: App Factory Refactor Summary

Refactored `jellyswipe/__init__.py` from side-effecting module body to an explicit `create_app(test_config=None)` factory function, enabling test isolation while maintaining full backwards compatibility.

## One-Liner

Flask app factory pattern with `create_app(test_config=None)` enabling isolated test instances while preserving `jellyswipe:app` global import for Dockerfile/Gunicorn compatibility.

## Objective Completed

✓ Refactored `jellyswipe/__init__.py` into factory pattern
✓ Maintained full backwards compatibility with existing imports
✓ Enabled test isolation via test_config parameter
✓ All 27 existing route authorization tests pass

## Implementation Summary

### Task 1: Create create_app() factory function
- Moved Flask app creation, ProxyFix middleware, and secret_key configuration into factory
- Stored JELLYFIN_URL and TMDB_API_KEY in app.config for consistency
- Imported and initialized JellyfinLibraryProvider singleton within factory
- Moved database initialization (init_db()) into factory execution
- Defined all routes inline within factory to capture app closure
- Implemented test_config parameter to override app.config and DB_PATH

### Task 2: Create global app instance for backwards compatibility
- Added module-level `app = create_app()` at bottom of file
- Ensures Dockerfile CMD `jellyswipe:app` continues to work
- All existing imports (`from jellyswipe import app`) work without changes

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed token cache accessibility for test compatibility**
- **Found during:** Task 2 verification (running test_route_authorization.py)
- **Issue:** Tests failed with `AttributeError: module 'jellyswipe' has no attribute '_token_user_id_cache'` because token cache was moved into factory function scope
- **Fix:** Moved `_token_user_id_cache`, `TOKEN_USER_ID_CACHE_TTL_SECONDS`, and `IDENTITY_ALIAS_HEADERS` to module level, matching the provider singleton pattern (D-13)
- **Files modified:** jellyswipe/__init__.py
- **Commit:** efb3084
- **Rationale:** Maintains backwards compatibility with existing tests that access module-level cache for test isolation

## Authentication Gates

None encountered.

## Threat Surface Scan

No new threat surfaces introduced. The refactor is structural only:
- Test configuration is limited to test environment (no production exposure)
- Environment variable validation unchanged (still runs at module import)
- Secret handling unchanged (FLASK_SECRET from environment)
- No new endpoints, file access patterns, or auth paths introduced

## Technical Details

### Factory Pattern Benefits
- **Test Isolation:** Tests can create fresh app instances with in-memory databases via `test_config={'DB_PATH': ':memory:'}`
- **Configuration Flexibility:** Production uses env vars, tests can override specific settings
- **No Breaking Changes:** Global `app` instance ensures Dockerfile/Gunicorn compatibility
- **Clean Separation:** Environment validation (module-level) vs app initialization (factory-level)

### Module-Level Singletons Preserved
- `_provider_singleton`: JellyfinLibraryProvider instance cache
- `_token_user_id_cache`: Token-to-user-id mapping cache
- `IDENTITY_ALIAS_HEADERS`: Tuple of spoofed header names

These remain at module level per D-13 to maintain backwards compatibility with existing tests that access `jellyswipe._token_user_id_cache.clear()` for test isolation.

## Verification Results

### Phase Verification Checklist
- ✅ `create_app(test_config=None)` function exists in jellyswipe/__init__.py
- ✅ Factory returns configured Flask app instance
- ✅ Global `app` instance exists at module level (created by `app = create_app()`)
- ✅ `from jellyswipe import app` works (backwards compatibility)
- ✅ `from jellyswipe import create_app; app = create_app()` works
- ✅ Environment variable validation still runs at module import time
- ✅ Database initialization (init_db()) happens inside factory, not at module import
- ✅ All routes are registered on factory-returned app instance
- ✅ Existing route tests (test_route_authorization.py) still pass (27/27)
- ✅ Application runs without breaking changes (verified by importing and basic route check)

### Test Results
```
pytest tests/test_route_authorization.py
============================== 27 passed in 0.28s ==============================
```

### Coverage Improvement
- Before: 24% coverage for jellyswipe/__init__.py
- After: 47% coverage for jellyswipe/__init__.py (+23 percentage points)

## Files Modified

### jellyswipe/__init__.py
- **Lines changed:** 465 insertions, 437 deletions (net +28 lines)
- **Key changes:**
  - Added `create_app(test_config=None)` factory function
  - Moved app creation, configuration, route registration into factory
  - Moved database initialization into factory
  - Added global `app = create_app()` at module level
  - Preserved module-level singletons for test compatibility

## Commits

1. **1549f18** - refactor(21-01): create create_app() factory function
2. **22c221e** - feat(21-01): create global app instance for backwards compatibility
3. **efb3084** - fix(21-01): keep token cache at module level for test compatibility

## Next Steps

This refactor enables the next phase (21-02) which will add comprehensive route tests using the new factory pattern. The factory allows tests to create isolated app instances with test-specific configuration (in-memory databases, test secrets), achieving the v1.5 milestone goal of 70% coverage for jellyswipe/__init__.py.

## Known Limitations

None. The refactor achieves all stated goals without introducing known limitations or technical debt.

---

**Plan Status:** ✅ Complete
**All Success Criteria Met:** ✅ Yes
**Breaking Changes:** ❌ None
