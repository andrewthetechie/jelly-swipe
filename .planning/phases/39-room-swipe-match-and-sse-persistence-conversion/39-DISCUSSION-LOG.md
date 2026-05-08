# Phase 39: Room, Swipe, Match, and SSE Persistence Conversion - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-06
**Phase:** 39-Room, Swipe, Match, and SSE Persistence Conversion
**Areas discussed:** Room identity and lifecycle, Swipe/match transaction semantics, SSE stream behavior, Service/repository slicing

---

## Room identity and lifecycle

### Question 1

| Option | Description | Selected |
|--------|-------------|----------|
| Keep current browser/session identity | Use the current browser/session identity as the persisted participant key everywhere | ✓ |
| New persisted participant id | Introduce a new participant identity layer in this phase | |
| Mixed identity model | Keep session identity for some flows and add a new id for others | |

**User's choice:** Keep current browser/session identity
**Notes:** The user kept the current session-backed participant identity model for all persisted room and swipe flows.

### Question 2

| Option | Description | Selected |
|--------|-------------|----------|
| Eager cleanup | Clear local room state immediately when `active_room` points to a missing room | ✓ |
| Soft preserve | Keep local room state until explicit leave or refresh | |
| Recreate or rejoin | Attempt recovery before clearing | |

**User's choice:** Eager cleanup
**Notes:** Missing or stale rooms should clear local room state immediately.

### Question 3

| Option | Description | Selected |
|--------|-------------|----------|
| Shared path with `solo_mode` | Use the same persistence and service path for solo and multiplayer rooms | ✓ |
| Separate solo path | Build a solo-specific persistence and service path | |
| Shared room path, separate swipe path | Share room persistence but split swipe and match behavior | |

**User's choice:** Shared path with `solo_mode`
**Notes:** The user wanted solo mode to stay a variation of the same room domain, not a forked subsystem.

### Question 4

| Option | Description | Selected |
|--------|-------------|----------|
| Immediate hard cleanup | Delete room state as soon as the room is closed or emptied | ✓ |
| Brief recovery window | Keep room and swipe state for reconnect or rejoin recovery | |
| Keep room metadata only | Retain room metadata but clear swipes and matches | |

**User's choice:** Immediate hard cleanup
**Notes:** No reconnect-recovery retention is required in this phase.

---

## Swipe/match transaction semantics

### Question 1

| Option | Description | Selected |
|--------|-------------|----------|
| One atomic swipe mutation | Keep swipe write, cursor advance, match detection, and `last_match` update together | ✓ |
| Split match detection | Separate swipe write/cursor advance from match detection | |
| Split everything | Break the mutation into smaller independent persistence calls | |

**User's choice:** One atomic swipe mutation
**Notes:** The user wanted parity with the current transaction semantics.

### Question 2

| Option | Description | Selected |
|--------|-------------|----------|
| Preserve serialized room mutation behavior | Keep race protection equivalent to `BEGIN IMMEDIATE` | ✓ |
| Per-user serialization only | Relax locking to user-local conflicts | |
| Optimistic retry | Use optimistic conflict handling instead of strict serialization | |

**User's choice:** Preserve serialized room mutation behavior
**Notes:** The user explicitly kept the current strict room-level race protection model.

### Question 3

| Option | Description | Selected |
|--------|-------------|----------|
| Immediate recompute | Undo/delete updates visible match and history state right away | ✓ |
| Local-only first | Update the caller-visible state first and let shared state catch up | |
| Defer recompute | Delay match-state recomputation until a later refresh | |

**User's choice:** Immediate recompute
**Notes:** Undo and delete should preserve immediate visible parity rather than eventual consistency.

### Question 4

| Option | Description | Selected |
|--------|-------------|----------|
| Match history plus `last_match` sentinel | Keep the current fast-path parity model | ✓ |
| Match history only | Derive the latest match on demand | |
| Dedicated event record | Add an outbox-style notification record | |

**User's choice:** Match history plus `last_match` sentinel
**Notes:** The user kept the persisted fast-path room-state model and rejected turning this into an eventing redesign.

---

## SSE stream behavior

### Question 1

| Option | Description | Selected |
|--------|-------------|----------|
| Immediate snapshot on connect | Send the latest room snapshot right away when available | ✓ |
| Minimal ack only | Connect without room state and require a separate fetch | |
| Multiplayer-only snapshot | Send snapshot on connect only for multiplayer rooms | |

**User's choice:** Immediate snapshot on connect
**Notes:** Current stream behavior stays intact on initial connect.

### Question 2

| Option | Description | Selected |
|--------|-------------|----------|
| Post-commit emission only | Emit SSE only after room or swipe state commits | ✓ |
| Pre-commit allowed | Emit when in-memory state changes before commit | |
| Mixed durability | Use both post-commit and best-effort pre-commit events | |

**User's choice:** Post-commit emission only
**Notes:** Stream state must reflect committed persistence state only.

### Question 3

| Option | Description | Selected |
|--------|-------------|----------|
| No replay queue | Reconnect clients resubscribe and refresh from current room state | ✓ |
| Short replay buffer | Keep a recent per-room replay window | |
| Durable resume log | Add durable events and resume tokens | |

**User's choice:** No replay queue
**Notes:** The user kept the current snapshot-plus-resubscribe recovery model.

### Question 4

| Option | Description | Selected |
|--------|-------------|----------|
| Keep app-local broadcaster semantics | Preserve the current local stream behavior in this phase | ✓ |
| Persistence-backed broadcaster | Introduce outbox or persistence-backed fanout now | |
| Hybrid local plus recorded events | Keep local fanout but add explicit event records | |

**User's choice:** Keep app-local broadcaster semantics
**Notes:** The user kept Phase 39 focused on persistence conversion, not distributed eventing.

---

## Service/repository slicing

### Question 1

| Option | Description | Selected |
|--------|-------------|----------|
| Repositories by aggregate concern | Split room, swipe, and match persistence while coordinating in services | ✓ |
| One combined room-state repository | Centralize all room, swipe, and match persistence in one repository | |
| Services with thin helper queries | Keep most persistence logic in services | |

**User's choice:** Repositories by aggregate concern
**Notes:** The user wanted a real repository split rather than another large persistence blob.

### Question 2

| Option | Description | Selected |
|--------|-------------|----------|
| Room lifecycle service plus swipe/match service | Separate room orchestration from mutation-heavy swipe and match logic | ✓ |
| One unified room service | Put all room, swipe, match, and SSE logic into one service | |
| Many fine-grained services | Split services by endpoint or action | |

**User's choice:** Room lifecycle service plus swipe/match service
**Notes:** This keeps mutation complexity isolated without exploding the service count.

### Question 3

| Option | Description | Selected |
|--------|-------------|----------|
| Vertical-slice router migration | Convert endpoints incrementally while keeping response contracts unchanged | ✓ |
| Persistence-first cutover | Convert low-level persistence first and flip routers later | |
| Mixed legacy retention | Leave some working endpoints on sync helpers | |

**User's choice:** Vertical-slice router migration
**Notes:** The user preferred visible contract stability during incremental conversion.

### Question 4

| Option | Description | Selected |
|--------|-------------|----------|
| Keep route tests and add lower-level tests | Preserve parity tests and add focused service/repository coverage | ✓ |
| Shift mostly to service tests | Reduce route-level assertions after the conversion | |
| End-to-end only | Avoid adding lower-level tests | |

**User's choice:** Keep route tests and add lower-level tests
**Notes:** The user kept route tests as the behavior contract while asking for deeper domain coverage underneath.

---

## the agent's Discretion

None.

## Deferred Ideas

None.
