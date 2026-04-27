# Phase 25: RESTful Routes + Deck Ownership - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-27 (updated)
**Phase:** 25-restful-routes-deck-ownership
**Areas discussed:** Route Migration, Deck Order Persistence, Cursor Tracking, Deck Delivery, End-of-Deck Behavior, SSE Stream Auth, Genre Change Endpoint, Route Transition Strategy

---

## Route Migration

| Option | Description | Selected |
|--------|-------------|----------|
| Big switch | Migrate all routes at once, old removed | ✓ |
| Gradual compat | Support both old and new temporarily | |

**User's choice:** Big switch
**Notes:** Client must update in Phase 27. Clean break. Acceptable that app is broken between Phase 25 and 27 — no active users during development.

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

## Deck Delivery

| Option | Description | Selected |
|--------|-------------|----------|
| Paginated (20/page) | Return N cards per request from cursor position | ✓ |
| Full remaining deck | Return all unswiped cards at once | |

**User's choice:** Paginated, 20 cards per page
**Notes:** Decks may grow large over time. Pagination-ready now prevents future migration. Page size of 20 balances payload size with round-trips.

---

## End-of-Deck Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Empty array [] | Client shows "no more cards" state | ✓ |
| Loop back to start | Reshuffle and start over | |
| Auto-fetch fresh deck | Trigger new Jellyfin fetch | |

**User's choice:** Empty array
**Notes:** Clean and simple. Client shows end-of-deck state.

---

## SSE Stream Authentication

| Option | Description | Selected |
|--------|-------------|----------|
| No auth | Room code in URL is access control, generator context-free | ✓ |
| Require @login_required | Gate behind vault identity | |

**User's choice:** No auth
**Notes:** SSE polls every 1.5s — repeated vault lookups add latency for no security gain. Room code is the access token. Generator stays context-free per Phase 24 D-12.

---

## Genre Change Endpoint

| Option | Description | Selected |
|--------|-------------|----------|
| JSON body | POST /room/{code}/genre with {"genre": "Action"} | ✓ |
| Query param | POST /room/{code}/genre?genre=Action | |

**User's choice:** JSON body
**Notes:** Consistent with other POST endpoints that accept JSON payloads.

---

## Route Transition Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Big switch (original D-01) | Old routes removed immediately | ✓ |
| Keep both during Phases 25-27 | Old routes continue, new added alongside | |

**User's choice:** Big switch (confirmed)
**Notes:** Revisited due to 3-phase gap before client updates. User confirmed big switch is fine — no one is actively using the app during development.

---

## the agent's Discretion

- Pagination query param format (?page=2 vs ?offset=20 vs ?cursor=movie_id)
- Response envelope shape for paginated deck
- Whether to include total card count in deck response

## Deferred Ideas

None — discussion stayed within phase scope.
