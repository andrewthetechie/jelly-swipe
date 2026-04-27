# Phase 25: RESTful Routes + Deck Ownership - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-26
**Phase:** 25-restful-routes-deck-ownership
**Areas discussed:** Route Migration, Deck Order Persistence, Cursor Tracking

---

## Route Migration

| Option | Description | Selected |
|--------|-------------|----------|
| Big switch | Migrate all routes at once, old removed | ✓ |
| Gradual compat | Support both old and new temporarily | |

**User's choice:** Big switch
**Notes:** Client must update in Phase 27. Clean break.

---

## Deck Order Persistence

| Option | Description | Selected |
|--------|-------------|----------|
| Keep full JSON | Shuffled deck JSON in movie_data (existing pattern) | ✓ |
| Store seed | Store seed, regenerate deterministically | |

**User's choice:** Keep full JSON
**Notes:** Simple, works with existing pattern. Server generates once at room creation.

---

## Cursor Tracking

| Option | Description | Selected |
|--------|-------------|----------|
| Per-user JSON map | {user_id: index} in deck_position column | ✓ |
| Last-swiped ID | Track last movie swiped, find position in deck | |

**User's choice:** Per-user JSON map
**Notes:** On reconnect, user resumes at stored index. Cursor advances on swipe, not view.

---

## the agent's Discretion

- Genre change endpoint design (query param vs body)
- Deck endpoint pagination
- Stale cursor handling

## Deferred Ideas

None — discussion stayed within phase scope.
