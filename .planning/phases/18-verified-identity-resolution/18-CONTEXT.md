# Phase 18: Verified Identity Resolution - Context

**Gathered:** 2026-04-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 18 hardens identity resolution so user identity for protected operations is derived only from trusted server-side sources. The phase is limited to identity derivation logic and source acceptance rules; broader route authorization behavior remains in Phase 19.

</domain>

<decisions>
## Implementation Decisions

### Identity Source Precedence
- **D-01:** Resolve identity from delegated server identity first (`session["jf_delegate_server_identity"]` path), then from validated Jellyfin user token.
- **D-02:** No other fallback sources are allowed for identity establishment.

### Spoofed Header Handling
- **D-03:** Presence of client-supplied identity headers (`X-Provider-User-Id`, `X-Jellyfin-User-Id`, `X-Emby-UserId`) is treated as unauthorized and should fail immediately.

### Token Resolution Caching
- **D-04:** Cache token-to-user-id resolutions in memory using a token hash key with short TTL (5 minutes).
- **D-05:** Cache scope is process-local and exists to reduce repeated Jellyfin `/Users/Me` calls while keeping stale-identity risk low.

### Authorization Header Parsing
- **D-06:** Keep tolerant parsing for `Token="..."` extraction in `Authorization` header, then rely on Jellyfin validation for trust.

### Claude's Discretion
- Exact cache data structure and TTL eviction implementation details.
- Exact unauthorized error message text and logging verbosity, as long as behavior matches D-03.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone Scope and Security Requirements
- `.planning/ROADMAP.md` — Phase 18 goal, requirements mapping (`SEC-01`, `SEC-02`), and success criteria.
- `.planning/REQUIREMENTS.md` — Security requirement definitions that this phase must satisfy.
- `.planning/PROJECT.md` — Current milestone intent and constraints for authorization hardening.

### Current Identity and Provider Implementation
- `jellyswipe/__init__.py` — Current `_provider_user_id_from_request()` and affected route integration points.
- `jellyswipe/jellyfin_library.py` — Token parsing and `resolve_user_id_from_token()` behavior relied on by identity resolution.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_provider_user_id_from_request()` in `jellyswipe/__init__.py`: current central identity resolver to harden instead of duplicating per-route logic.
- `_jellyfin_user_token_from_request()` in `jellyswipe/__init__.py`: existing helper to extract delegated or header token paths.
- `resolve_user_id_from_token()` in `jellyswipe/jellyfin_library.py`: existing server-validated user-id lookup.
- `extract_media_browser_token()` in `jellyswipe/jellyfin_library.py`: existing tolerant token extraction helper to keep.

### Established Patterns
- Request auth failures currently use JSON error payloads with status codes (401/400/500) in route handlers.
- Session-based delegate identity flag (`jf_delegate_server_identity`) is already the trusted server path.
- In-memory provider caches are already used in the codebase (`_cached_user_id`, `_cached_library_id`, `_genre_cache`), making short-lived identity cache aligned with current patterns.

### Integration Points
- Identity resolver helpers in `jellyswipe/__init__.py` are the integration seam for route-level behavior.
- Provider methods in `jellyswipe/jellyfin_library.py` are the integration seam for token validation and user-id lookup.

</code_context>

<specifics>
## Specific Ideas

- User-selected strictness: delegate identity first, then token fallback, with no alias fallback.
- Security posture for spoof headers is explicit unauthorized failure (not silent ignore).
- Cache preference: short TTL (5 minutes) keyed by token hash.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 18-verified-identity-resolution*
*Context gathered: 2026-04-25*
