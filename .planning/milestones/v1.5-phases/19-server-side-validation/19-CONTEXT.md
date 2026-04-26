# Phase 19: Server-Side Validation - Context

**Gathered:** 2026-04-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 19 removes client-supplied `title` and `thumb` parameters from the `/room/swipe` endpoint and resolves all movie metadata server-side from `movie_id` via Jellyfin API calls. This ensures malicious data cannot enter the system at the source, addressing the root cause of the XSS vulnerability.

</domain>

<decisions>
## Implementation Decisions

### Error Handling Strategy
- **D-01:** When `resolve_item_for_tmdb()` fails (invalid movie_id, Jellyfin API error, network timeout), silently skip match creation but allow the swipe to complete.
- **D-02:** The swipe record is still inserted into the database, but no match entry is created (user swipes, no match recorded).
- **D-03:** When client sends `title` or `thumb` parameters after the fix, log this as a security warning with client IP and payload to detect potential malicious activity patterns.

### Thumb Resolution Approach
- **D-04:** Use a separate Jellyfin API call to fetch the thumb URL after `resolve_item_for_tmdb()` successfully resolves the title and year.
- **D-05:** Separate call provides clearer separation of concerns and keeps the `resolve_item_for_tmdb()` method focused on metadata resolution only.
- **D-06:** The thumb URL is fetched using the `/Items/{movie_id}/Images/Primary` endpoint or extracted from the full item response.

### Existing Data Handling
- **D-07:** No migration needed for existing matches — the application is not in production use and has no existing data.
- **D-08:** All new matches will have server-resolved title and thumb values; no legacy data compatibility concerns.

### the Agent's Discretion
- Exact error response format when match creation is skipped (as long as behavior aligns with D-01)
- Thumb URL fallback strategy if the separate image fetch fails (e.g., use default placeholder, return empty string)
- Log message format and details for security warning (as long as behavior aligns with D-03)
- Caching strategy for resolved thumb URLs (process-local cache aligned with existing patterns from Phase 18)

</decisions>

<specifics>
## Specific Ideas

- Security logging should help detect when old clients or malicious actors attempt to send client-supplied metadata
- Separate thumb resolution call allows for clearer error handling (can fail to get thumb but still create match with title)
- Consider adding thumb URL to the process-local cache to reduce repeated Jellyfin API calls for the same movie_id

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Issue and Vulnerability Details
- `.planning/research/FEATURES.md` — XSS vulnerability description, vulnerable code locations, and fix outline
- `https://github.com/andrewthetechie/jelly-swipe/issues/6` — Issue #6: EPIC-03 — Eliminate stored XSS via match `title` / `thumb`

### Phase Requirements and Success Criteria
- `.planning/ROADMAP.md` — Phase 19 goal, requirements mapping (SSV-01, SSV-02, SSV-03), and 4 success criteria
- `.planning/REQUIREMENTS.md` — Server-Side Validation requirements (SSV-01, SSV-02, SSV-03) with acceptance criteria

### Current Implementation
- `jellyswipe/__init__.py` lines 240-279 — `/room/swipe` endpoint showing current client-supplied title/thumb usage
- `jellyswipe/jellyfin_library.py` lines 329-344 — `resolve_item_for_tmdb()` method that currently returns only title and year

### Prior Phase Context
- `.planning/phases/18-verified-identity-resolution/18-CONTEXT.md` — Identity resolution patterns (process-local caching, error handling) that inform this phase

### Codebase Patterns
- `.planning/codebase/CONVENTIONS.md` — Error handling patterns (try/except with JSON error responses)
- `.planning/codebase/STRUCTURE.md` — Package layout and where to add new helper functions
- `.planning/codebase/STACK.md` — Flask and Jellyfin API integration patterns

### Security Research
- `.planning/research/STACK.md` — Stack additions and security best practices for CSP and escaping
- `.planning/research/ARCHITECTURE.md` — Three-layer defense strategy (server validation → safe DOM → CSP)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `resolve_item_for_tmdb()` in `jellyswipe/jellyfin_library.py`: existing method for fetching movie title and year from movie_id — will be called before thumb resolution
- `_provider_user_id_from_request()` in `jellyswipe/__init__.py`: existing identity resolver (from Phase 18) for user-scoped operations
- In-memory caching patterns from Phase 18: `_cached_user_id`, `_cached_library_id` — can be adapted for thumb URL caching

### Established Patterns
- Error handling in route handlers: wrap external API calls in try/except, return JSON error responses with status codes
- Database operations: use `with get_db() as conn:` context manager for safe connection handling
- Match insertion logic: exists in 3 places (solo mode, mutual match, partner match) — all need to use server-resolved metadata

### Integration Points
- `/room/swipe` endpoint in `jellyswipe/__init__.py`: primary integration point — modify to ignore client title/thumb and call server resolution
- `jellyswipe/jellyfin_library.py`: add new method for thumb URL resolution or enhance existing provider
- Database `matches` table: has `title` and `thumb` columns — will be populated with server-resolved values

### Technical Constraints
- `resolve_item_for_tmdb()` currently returns `SimpleNamespace(title=..., year=...)` — thumb resolution will need separate implementation
- Match insertion happens in 3 places with similar patterns — refactoring may be needed to avoid code duplication
- Jellyfin API requires authentication tokens — reuse existing provider authentication logic

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 19-server-side-validation*
*Context gathered: 2026-04-26*
