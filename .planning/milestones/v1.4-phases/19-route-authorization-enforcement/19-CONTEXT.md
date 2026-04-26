# Phase 19: Route Authorization Enforcement - Context

**Gathered:** 2026-04-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 19 enforces verified-identity behavior at route level for protected endpoints. It removes fallback trust in request-body identity fields, standardizes unauthorized responses, and ensures user-scoped operations only act on verified identity.

</domain>

<decisions>
## Implementation Decisions

### Unauthorized Response Contract
- **D-01:** Use a uniform unauthorized response contract across protected routes: HTTP `401` with payload `{ "error": "Unauthorized" }`.

### `/room/swipe` Identity Source Policy
- **D-02:** Ignore request-body `user_id` completely; always use verified identity from resolver output.
- **D-03:** No compatibility fallback to request-body identity is allowed.

### Identity Rejection Reason Exposure
- **D-04:** Do not expose identity rejection reason codes in client responses.
- **D-05:** Rejection reasons remain server-side only (internal handling/logging path).

### `/matches` Unauthorized Behavior
- **D-06:** `/matches` uses strict `401` unauthorized behavior instead of returning empty arrays when identity is missing/rejected.

### Rollout Mode
- **D-07:** Apply immediate enforcement to all protected routes in scope (`/room/swipe`, `/matches`, `/matches/delete`, `/undo`, `/watchlist/add`) with no feature flag.

### Claude's Discretion
- Exact helper function shape for reusing unauthorized response payload generation.
- Internal logging strategy for rejection reason observability without leaking to clients.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone and Requirement Scope
- `.planning/ROADMAP.md` — Phase 19 goals and success criteria.
- `.planning/REQUIREMENTS.md` — `SEC-03`, `SEC-04`, `SEC-05` requirement definitions.
- `.planning/PROJECT.md` — milestone-level authorization hardening objective.

### Prior Phase Decisions and Current Auth Helpers
- `.planning/phases/18-verified-identity-resolution/18-CONTEXT.md` — locked identity-source and spoof-header decisions from Phase 18.
- `jellyswipe/__init__.py` — current protected-route implementations and identity helper behavior to enforce.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_provider_user_id_from_request()` provides centralized verified identity lookup.
- `_identity_rejection_reason()` provides server-side reason retrieval without client exposure.
- Existing route handlers already use shared JSON response style and can be normalized with low churn.

### Established Patterns
- Protected routes currently mix `400`, `401`, and empty-array fallback behavior; Phase 19 standardizes to strict `401`.
- User-scoped routes already call the identity helper; enforcement can remain centralized around helper output checks.

### Integration Points
- `jellyswipe/__init__.py` route handlers: `/room/swipe`, `/matches`, `/matches/delete`, `/undo`, `/watchlist/add`.
- Shared identity helper outputs from Phase 18 directly inform Phase 19 enforcement branches.

</code_context>

<specifics>
## Specific Ideas

- Keep client-facing unauthorized payload minimal and uniform.
- Apply enforcement immediately with no rollout toggles.
- Ensure `/matches` behavior aligns with other protected routes.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 19-route-authorization-enforcement*
*Context gathered: 2026-04-25*
