# Phase 19 Pattern Map: Route Authorization Enforcement

**Phase:** 19 — Route Authorization Enforcement  
**Generated:** 2026-04-25  
**Primary implementation file:** `jellyswipe/__init__.py`

## Pattern 1: Centralized identity resolution

- **Canonical function:** `_provider_user_id_from_request()`
- **Why it matters:** Encodes trusted identity precedence and spoofing rejection from Phase 18.
- **Plan implication:** Every protected route should gate on this helper (or a single wrapper that uses it).

## Pattern 2: Uniform unauthorized payload style

- **Existing analog:** `add_to_watchlist()` currently returns `jsonify({'error': 'Unauthorized'}), 401` for missing token.
- **Plan implication:** Reuse this exact payload/status contract for all protected routes in scope.

## Pattern 3: Route-level early-return auth guard

- **Existing analogs:** `delete_match()`, `undo_swipe()`, and `get_matches()` have early auth checks but inconsistent status behavior.
- **Plan implication:** Normalize all protected routes to immediate unauthorized return before DB work.

## Pattern 4: User-scoped DB query filters

- **Existing analog:** `get_matches()` queries by `user_id`; `delete_match()` and `undo_swipe()` mutate with `user_id` filters.
- **Plan implication:** Preserve and tighten verified identity usage for all user-scoped reads/writes/deletes.

## Pattern 5: Avoid exposing internal rejection reasons

- **Existing analog:** `_identity_rejection_reason()` reads internal server-side reason from `request.environ`.
- **Plan implication:** Keep this internal-only and avoid propagating reason codes in client payloads.

## File Touch Recommendations

- **Must modify:** `jellyswipe/__init__.py`
- **Likely add/modify in Phase 20 (not this phase):** route-level tests under `tests/`

## Suggested Plan Task Grouping

1. Introduce shared unauthorized response helper + optional auth guard helper.
2. Normalize protected routes to strict unauthorized checks and remove body `user_id` fallback.
3. Verify query/mutation scoping still uses verified identity only.
4. Run compile/test verification and capture behavior delta notes in summary.
