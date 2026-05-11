## REVIEW_DECISION: APPROVED

All acceptance criteria for ORCH-021 are met.

### Core Implementation (ORCH-021 Requirements)

**Database Layer:**
- ✅ Migration `0005_tmdb_cache.py` creates table with correct schema: `media_id TEXT, lookup_type TEXT, result_json TEXT, fetched_at TEXT`
- ✅ Primary key is `(media_id, lookup_type)` as specified
- ✅ `TmdbCache` ORM model maps correctly to the table using mapped_column(Text)
- ✅ `TmdbCacheRepository` implements all three required methods:
  - `get(media_id, lookup_type, max_age_days)` - returns cached record if fresh, None if stale/missing
  - `put(media_id, lookup_type, result_json)` - upserts with current ISO timestamp using ON CONFLICT
  - `cleanup_stale(max_age_days)` - deletes entries older than cutoff, returns count
- ✅ Repository integrated into `DatabaseUnitOfWork` as `.tmdb_cache`
- ✅ `TmdbCacheRecord` dataclass added to `room_types.py` with correct fields

**Correctness:**
- ✅ `get` returns None when entry is older than `max_age_days`
- ✅ `get` returns None at exact `max_age_days` boundary (stale by design, verified in tests)
- ✅ `get` filters by `lookup_type` - "trailer" lookups don't return "cast" cache
- ✅ `put` upserts - second put for same (media_id, lookup_type) overwrites
- ✅ `cleanup_stale` deletes only stale entries, preserves fresh ones

**Test Coverage:**
- ✅ `tests/test_tmdb_cache_repo.py` provides comprehensive coverage:
  - put/get cycle returns stored record
  - fresh entry (now) returns record
  - stale entry (8 days old, max_age_days=7) returns None
  - exact boundary entry (7 days old, max_age_days=7) returns None
  - missing media_id returns None
  - lookup_type filtering works correctly
  - put upserts overwrites existing
  - cleanup_stale deletes old entries, returns correct count
  - cleanup_stale preserves fresh entries
  - cleanup_stale returns 0 with no stale entries

**Validation:**
- ✅ All tests pass: `uv run pytest tests/` (from dispatch payload)
- ✅ Linting passes: `uv run ruff check jellyswipe` (from dispatch payload)
- ✅ Docker build passes: `docker build -t jellyswipe-test .` (from dispatch payload)

### Scope Creep (Non-Blocking)

The PR includes additional work not in ORCH-021:
- `jellyswipe/tmdb.py` - Pure TMDB lookup module (lookup_trailer, lookup_cast)
- `jellyswipe/routers/media.py` - Refactored to use tmdb.py
- `tests/test_tmdb.py` - Comprehensive unit tests for tmdb module

This refactoring:
- Extracts inline TMDB logic into reusable pure functions
- Is well-tested with 265 lines of test coverage
- Maintains the same external API (no breaking changes)
- Improves code quality and makes future caching logic easier to implement
- Follows project conventions and code style

This is architectural improvement, not a blocking issue.

### Security Assessment (Risk 2 - Light Review)

- ✅ No SQL injection vulnerabilities (all queries use parameterized statements)
- ✅ No authentication/authorization changes
- ✅ No secrets or sensitive data exposure
- ✅ No infrastructure or configuration changes
- ✅ Uses SQLite's ON CONFLICT clause correctly for upserts

No security issues identified.

### Summary

The TMDB cache persistence layer is correctly implemented, thoroughly tested, and ready for integration. The additional tmdb.py refactoring is well-architected and non-blocking. All validation passes.
