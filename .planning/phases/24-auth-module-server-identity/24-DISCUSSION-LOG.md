# Phase 24: Auth Module + Server-Owned Identity - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-26
**Phase:** 24-auth-module-server-identity
**Areas discussed:** Login Response, Delegate Mode, Identity Unification, Auth Scope

---

## Login Response

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal | {userId, displayName} only, token in vault | ✓ |
| Same shape + vault | Keep returning token, also store, remove later | |

**User's choice:** Minimal
**Notes:** Token never exposed to client JavaScript.

---

## Delegate Mode

| Option | Description | Selected |
|--------|-------------|----------|
| Unify | Delegate login stores server token in vault like regular login | ✓ |
| Keep separate | Delegate stays as-is, two code paths | |

**User's choice:** Unify
**Notes:** Both login paths produce same g.user_id + g.jf_token via @login_required.

---

## Identity Unification

| Option | Description | Selected |
|--------|-------------|----------|
| Jellyfin UUID | Jellyfin UUID everywhere, eliminate host_/guest_ IDs | ✓ |
| Session-derived | Keep session-derived IDs from vault | |

**User's choice:** Jellyfin UUID
**Notes:** Existing swipes with old IDs become orphaned (acceptable for self-hosted app).

---

## Auth Scope

| Option | Description | Selected |
|--------|-------------|----------|
| All mutations | All POST/DELETE endpoints require @login_required | ✓ |
| Room-scoped only | Only room data endpoints require auth | |

**User's choice:** All mutations
**Notes:** Public GET endpoints (genres, server-info, static) remain open.

---

## the agent's Discretion

- @login_required implementation (before_request vs per-route decorator)
- Missing vault entry handling (redirect vs 401 JSON)
- Session ID generation format

## Deferred Ideas

None — discussion stayed within phase scope.
