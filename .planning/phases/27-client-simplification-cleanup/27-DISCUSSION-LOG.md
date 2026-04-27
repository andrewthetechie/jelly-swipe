# Phase 27: Client Simplification + Cleanup - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-26
**Phase:** 27-client-simplification-cleanup
**Areas discussed:** Login UX Flow, Match Popup Trigger

---

## Login UX Flow

| Option | Description | Selected |
|--------|-------------|----------|
| Form + delegate fallback | Username/password form, /me check on load | |
| Auto-delegate | Always try delegate first, fall back to form | ✓ |

**User's choice:** Auto-delegate
**Notes:** Preserves current UX where env-credential users skip login. Falls back to form if delegate unavailable.

---

## Match Popup Trigger

| Option | Description | Selected |
|--------|-------------|----------|
| SSE listener (decided) | Existing EventSource already receives last_match — just render from SSE | ✓ |

**User's choice:** SSE listener
**Notes:** Architecture already decided. No new code path needed.

---

## the agent's Discretion

- Login/delegate UI layout
- Error handling for failed login/delegate
- Loading state transitions

## Deferred Ideas

None — discussion stayed within phase scope.
