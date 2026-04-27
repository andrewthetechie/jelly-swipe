# Phase 24: Auth Module + Server-Owned Identity - Context

**Gathered:** 2026-04-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Create `jellyswipe/auth.py` module with token vault CRUD, `@login_required` decorator, and unified identity resolution. Server resolves user identity from session cookie + vault lookup — no client-supplied identity headers. Refactor login/delegate routes to use vault. All mutation endpoints require auth.

**Requirements:** AUTH-01 (server resolves identity from session cookie alone)

**Depends on:** Phase 23 (user_tokens table exists)

</domain>

<decisions>
## Implementation Decisions

### Login Endpoint Response
- **D-01:** Login endpoint returns minimal `{userId, displayName}` only. Jellyfin token is stored in `user_tokens` vault and never returned to client JavaScript.
- **D-02:** Both `/auth/jellyfin-login` and `/auth/jellyfin-use-server-identity` follow the same pattern: authenticate → store token in vault → return minimal user info.

### Delegate Mode
- **D-03:** Delegate mode is unified with regular login — server token stored in `user_tokens` vault just like user credentials. Both paths produce the same `g.user_id` + `g.jf_token` via `@login_required`.
- **D-04:** The `session["jf_delegate_server_identity"]` flag is replaced by the vault lookup — no need for a separate session flag.

### Identity Unification
- **D-05:** Jellyfin UUID becomes the canonical `user_id` everywhere — swipes, matches, watchlist. The synthetic `host_`/`guest_` IDs (`session['my_user_id']`) are eliminated.
- **D-06:** Existing swipes with old `host_`/`guest_` IDs become orphaned (acceptable — they're ephemeral session data in a self-hosted app).
- **D-07:** `swipe()` route uses `g.user_id` (from vault) instead of `session.get('my_user_id')` for the `swipes.user_id` column.

### Auth Scope
- **D-08:** All POST and DELETE endpoints require `@login_required`. GET endpoints for public data (genres, server-info, static assets) remain open.
- **D-09:** `@login_required` decorator populates `g.user_id` and `g.jf_token` for every authenticated request. Unauthenticated requests get a clear 401 error.

### Module Structure
- **D-10:** New `jellyswipe/auth.py` module contains: `create_session()`, `get_current_token()`, `cleanup_expired_tokens()`, `@login_required` decorator.
- **D-11:** Auth functions use `db.get_db()` for vault queries — consistent with existing database patterns.

### SSE Compatibility
- **D-12:** SSE generator (`/room/stream`) remains context-free — session values captured in view function, passed as closure arguments. No session reads inside the generator loop. This preserves the Flask + gevent pattern documented in research.

### the agent's Discretion
- Exact `@login_required` implementation (before_request vs per-route decorator)
- How to handle missing vault entries (redirect to login vs 401 JSON)
- Session ID generation format (secrets.token_hex length)

</decisions>

<canonical_refs>
## Canonical References

### Phase requirements and research
- `.planning/REQUIREMENTS.md` §Identity & Auth — AUTH-01 acceptance criteria
- `.planning/ROADMAP.md` §Phase 24 — Success criteria and plan outline
- `.planning/research/SUMMARY.md` §Architecture Approach — Token vault pattern, auth module design
- `.planning/research/ARCHITECTURE.md` §NEW: auth.py — Full component boundary specification
- `.planning/research/PITFALLS.md` — SSE generator context-free requirement, gevent session caveats

### Existing codebase patterns
- `jellyswipe/__init__.py:96-180` — Current auth helpers: `_jellyfin_user_token_from_request()`, `_provider_user_id_from_request()`, `_resolve_user_id_from_token_cached()`
- `jellyswipe/__init__.py:261-272` — Current `/auth/jellyfin-login` route
- `jellyswipe/__init__.py:249-258` — Current `/auth/jellyfin-use-server-identity` delegate route
- `jellyswipe/db.py` — Database access patterns for new auth module

### Prior phase decisions
- `.planning/phases/23-database-schema-token-vault/23-CONTEXT.md` — Schema decisions: user_tokens table structure, cleanup trigger

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `jellyswipe/__init__.py:138-158` — `_resolve_user_id_from_token_cached()` — Token → user_id resolution with TTL cache. Can be moved to auth.py and reused.
- `jellyswipe/__init__.py:77-82` — `get_provider()` singleton pattern for JellyfinLibraryProvider
- `jellyswipe/jellyfin_library.py` — `authenticate_user_session()`, `server_access_token_for_delegate()`, `resolve_user_id_from_token()` methods

### Established Patterns
- Route handlers use inline auth checks calling `_provider_user_id_from_request()` — these get replaced by `@login_required` decorator
- Session stores `active_room` and `my_user_id` — `my_user_id` gets eliminated, `active_room` stays
- Error responses use `jsonify({'error': 'message'}), 401` pattern

### Integration Points
- `jellyswipe/__init__.py:84-85` — Import `get_db, init_db` from `db.py` — new `auth.py` module needs similar import pattern
- All routes that call `_provider_user_id_from_request()` need refactoring to use `g.user_id`
- All routes that call `_jellyfin_user_token_from_request()` need refactoring to use `g.jf_token`

</code_context>

<specifics>
## Specific Ideas

- The `_resolve_user_id_from_token_cached()` function with its in-memory TTL cache should be preserved — it's a good pattern that avoids hitting Jellyfin API on every request
- The `IDENTITY_ALIAS_HEADERS` check (`X-Provider-User-Id`, `X-Jellyfin-User-Id`, `X-Emby-UserId`) should be removed — these headers won't be needed when identity comes from the vault

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 24-auth-module-server-identity*
*Context gathered: 2026-04-26*
