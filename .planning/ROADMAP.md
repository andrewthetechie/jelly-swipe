# Roadmap — Jelly Swipe

**Milestone:** v1.7 SSE/SQLite Architecture Fix
**Granularity:** Standard (5-8 phases)
**Current Phase:** 27 - Database Architecture (Not started)
**Last Updated:** 2026-04-29

---

## Overview

This roadmap fixes the SQLite contention and SSE reliability problems that collapse the app under load when multiple rooms have connected browsers. Three surgical phases: enable WAL mode and persistent connections, add SSE reliability features (jitter, heartbeat, graceful exit), and validate nothing broke.

**Phases:** 3
**Requirements:** 6 (DB-01, DB-02, SSE-01, SSE-02, SSE-03, ACC-01)
**Starting Phase:** 27 (continuing from v1.6 Phase 26)

---

## Phases

- [ ] **Phase 27: Database Architecture** — Enable WAL mode, set synchronous=NORMAL, and refactor SSE generator to hold one SQLite connection per client session
- [ ] **Phase 28: SSE Reliability** — Add poll jitter, heartbeat comments, and graceful room-disappearance exit to the SSE stream
- [ ] **Phase 29: Acceptance Validation** — Verify all 48 existing tests still pass after all architecture changes

---

## Phase Details

### Phase 27: Database Architecture

**Goal:** SQLite no longer bottlenecks under concurrent SSE load — WAL mode eliminates file-lock contention and the SSE generator holds a single persistent connection per client.

**Depends on:** Nothing (first phase of v1.7)

**Requirements:** DB-01, DB-02

**Success Criteria** (what must be TRUE):
  1. `init_db()` executes `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL` at startup, and the WAL mode persists across connection reopens
  2. SSE generator opens one SQLite connection at stream start and reuses it across all poll cycles, closing only at generator exit
  3. `get_db()` continues to work for non-SSE code paths (one-off queries create connections as before)

**Plans:** 1 plan

Plans:
- [ ] 27-01-PLAN.md — Enable WAL mode, add persistent SSE connection, verify no regressions

---

### Phase 28: SSE Reliability

**Goal:** SSE streams stay connected and healthy under concurrent load — no thundering-herd queries, no proxy connection reaping, no silent hangs on room disappearance.

**Depends on:** Phase 27 (SSE changes build on the persistent connection from DB-02)

**Requirements:** SSE-01, SSE-02, SSE-03

**Success Criteria** (what must be TRUE):
  1. SSE poll interval varies by 0–0.5s random jitter per cycle, preventing synchronized thundering-herd database queries
  2. SSE stream sends `: ping\n\n` heartbeat at approximately 15-second intervals when no data events are emitted
  3. SSE generator exits immediately when the queried room record disappears from the database (no waiting for next poll tick)
  4. Existing SSE event formats (match notifications, room full, etc.) remain unchanged and functional

**Plans:** TBD

Plans:
- [ ] 28-01: SSE jitter, heartbeat, and graceful exit

---

### Phase 29: Acceptance Validation

**Goal:** The architecture fixes are transparent — all existing tests pass without modification and the application still works correctly.

**Depends on:** Phase 28 (all code changes complete before validation)

**Requirements:** ACC-01

**Success Criteria** (what must be TRUE):
  1. All 48 existing tests pass with no modifications to test code
  2. Application starts correctly and serves the root page after all architecture changes
  3. No regression in SSE stream behavior for normal single-room, single-client usage

**Plans:** TBD

Plans:
- [ ] 29-01: Run full test suite and verify application startup

---

## Progress

**Execution Order:**
Phases execute in numeric order: 27 → 28 → 29

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 27. Database Architecture | 0/1 | Planned | - |
| 28. SSE Reliability | 0/1 | Not started | - |
| 29. Acceptance Validation | 0/1 | Not started | - |

---

## Milestone Context

**Previous Milestones:**
- v1.0 (Jellyfin support): Phases 1–9 ✅
- v1.1 (Rename): No numbered phases ✅
- v1.2 (uv + Package Layout + Plex Removal): Phases 10–13 ✅
- v1.3 (Unit Tests): Phases 14–17 ✅
- v1.4 (Authorization Hardening): Phases 1–18 ✅
- v1.5 (XSS Security Fix): Phases 19–22 ✅
- v1.6 (Plex Reference Cleanup): Phases 23–26 ✅

**Current Milestone:** v1.7 SSE/SQLite Architecture Fix — Phases 27–29

---

*Roadmap created: 2026-04-29*
*Last updated: 2026-04-29 (Phase 27 planned)*