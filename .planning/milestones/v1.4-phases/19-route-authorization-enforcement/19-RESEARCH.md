# Phase 19 Research: Route Authorization Enforcement

**Date:** 2026-04-25  
**Phase:** 19 — Route Authorization Enforcement  
**Inputs:** `19-CONTEXT.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `jellyswipe/__init__.py`

## Goal-Oriented Findings

Phase 19 should normalize all protected, user-scoped endpoints to enforce verified identity and return a uniform unauthorized contract. Current behavior is inconsistent:

- `/room/swipe` can fall back to request-body `user_id` and returns `400` when identity is missing.
- `/matches` returns an empty array when unauthorized.
- `/matches/delete` and `/undo` return `400` when identity is missing.
- `/watchlist/add` already returns `401` for missing token but does not currently enforce the shared verified-identity helper path.

## Codebase Pattern Assessment

### Existing identity primitives (from Phase 18)
- `_provider_user_id_from_request()` centralizes trust boundaries and resolves identity from delegated identity or validated token.
- `_identity_rejection_reason()` exposes server-side rejection metadata for internal use.
- Alias header spoofing is already rejected centrally.

### Existing route inconsistency
- Protected routes do not all branch on the same auth helper output.
- Error payload/status vary (`400`, empty array fallback, `401`).

## Implementation Strategy

1. Add a small shared helper for unauthorized responses (e.g., `_unauthorized_response()` returning `{"error":"Unauthorized"}`, `401`).
2. Update all protected routes in phase scope to fail fast on missing verified identity via `_provider_user_id_from_request()`.
3. Remove request-body identity fallback in `/room/swipe` so body `user_id` is ignored.
4. Ensure data operations (`SELECT`, `INSERT`, `DELETE`) continue to be scoped by verified identity fields only.
5. Keep identity rejection reason server-only (no client response leakage).

## Endpoint-Specific Recommendations

### `/room/swipe`
- Read `user_id` from verified helper only.
- Do not use `request.json["user_id"]` for identity.
- Return uniform `401` payload when helper fails.
- Preserve existing match mechanics while ensuring `matches.user_id` writes use verified identity only.

### `/matches`
- Replace empty-list unauthorized fallback with strict `401`.
- Keep current active/history query split, both filtered by verified identity.

### `/matches/delete`
- Replace `400 Missing user identity` with uniform `401`.
- Keep delete filter `(movie_id, user_id)` where `user_id` is verified identity.

### `/undo`
- Replace `400 Missing user identity` with uniform `401`.
- Keep `matches` delete scoped by verified identity.

### `/watchlist/add`
- Keep unauthorized as `401`, but align payload contract exactly (`{"error":"Unauthorized"}`).
- Prefer consistent verified-identity check path for route-level enforcement semantics.

## Risk Notes

- Existing clients may rely on `/matches` returning `[]` when unauthenticated; this is an intentional breaking security hardening per Phase 19 decisions.
- `/room/swipe` currently stores swipe rows keyed by session `my_user_id` while matches use verified provider identity; this dual identity model is legacy behavior and should not be expanded in this phase.

## Verification Targets for Planning

- All five protected routes in scope return `401` + `{"error":"Unauthorized"}` when identity is missing/unverifiable.
- `/room/swipe` no longer reads body `user_id` as identity fallback.
- DB operations remain scoped by verified identity where identity-based filtering/writes occur.
- No client response includes identity rejection internals.

## Validation Architecture

### Dimension Mapping

1. **Security correctness:** unauthorized responses are uniform and strict across protected routes.
2. **Trust boundary integrity:** client-controlled identity fields do not influence identity selection.
3. **Data-scope safety:** user-scoped reads/writes/deletes are bound to verified identity.
4. **Compatibility awareness:** expected behavioral deltas are explicit and testable.

### Sampling Plan

- Static inspection of route handlers in `jellyswipe/__init__.py` for identity branch behavior and status codes.
- Targeted tests in Phase 20 to validate spoof resistance and valid identity flows.
- Grep checks for removal of body `user_id` fallback and empty-array unauthorized behavior.

### Evidence Artifacts

- Updated route code in `jellyswipe/__init__.py`
- Phase 19 PLAN docs mapping requirements (`SEC-03`, `SEC-04`, `SEC-05`)
- Phase 20 automated tests (`VER-01`, `VER-02`, `VER-03`) for regression confidence
