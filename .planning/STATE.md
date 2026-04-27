---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Architecture Tier Fix
status: planning
last_updated: "2026-04-27T17:44:00.416Z"
last_activity: 2026-04-27
progress:
  total_phases: 6
  completed_phases: 2
  total_plans: 6
  completed_plans: 4
  percent: 67
---

# State — Jelly Swipe

**Milestone:** v2.0 Architecture Tier Fix
**Phase:** 25
**Status:** Ready to plan
**Progress:** [██████████] 100%

---

## Project Reference

**What This Is:**
Jelly Swipe is a small Flask app for shared "Tinder for movies" sessions: a host creates a room, guests join, everyone swipes on a deck pulled from a home media server, and matches surface when two people swipe right on the same title. Trailers and cast come from TMDB.

**Core Value:**
Users can run a swipe session backed by Jellyfin, with library browsing and deck behavior equivalent to the original Plex path.

**Current Focus:** Phase --phase — 24

---

## Current Position

Phase: --phase (24) — EXECUTING
Plan: Not started
Status: Executing Phase --phase
Last activity: 2026-04-27

---

## Accumulated Context

### Decisions Made

**v2.0 Architecture Strategy (Current Milestone):**

- Server owns identity (session → Jellyfin token → user_id) — AUTH-01
- Token vault is custom SQLite `user_tokens` table (not Flask-Session) — AUTH-02
- Expired tokens auto-cleaned after 24 hours — AUTH-03
- Server owns deck composition and order — DECK-01
- Server tracks per-user deck cursor for reconnect — DECK-02
- Match notification via SSE only (no HTTP response payload) — MTCH-01
- Match metadata enriched server-side (rating, duration, year) — MTCH-02
- Swipe+match wrapped in BEGIN IMMEDIATE transaction — MTCH-03
- RESTful swipe endpoint: POST /room/{code}/swipe — API-01
- Server generates Jellyfin deep links — API-02
- GET /me returns verified identity from session — API-03
- POST /room/solo for dedicated solo sessions — API-04
- Client removes localStorage tokens and identity headers — CLNT-01
- Client removes match detection from swipe response — CLNT-02
- Flask-Session rejected in favor of custom SQLite token vault (simpler, consistent)
- ADR as shipped artifact deferred — decisions documented in PROJECT.md and code

**Phase Ordering Rationale:**

1. Schema first (additive-only, zero breakage risk)
2. Auth module second (populates schema, unblocks all downstream)
3. Routes + deck third (identity-dependent route restructuring)
4. Match + metadata fourth (depends on new routes and identity)
5. Client cleanup fifth (subtractive, must come after server is stable)
6. Deployment validation last (end-to-end Docker verification)
- Used ISO 8601 string comparison for TTL-based token cleanup — avoids SQLite date functions
- Proactively added all v2.0 columns in one migration pass (per D-04) — reduces migration churn

### Active Todos

None yet.

### Known Blockers

None.

### Risks and Concerns

- **SSE generator session context loss** — Flask warns against reading `session` inside streaming generators; all values must be captured by closure in view functions
- **Dual identity migration** — Current code uses `host_`/`guest_` synthetic IDs; switching to Jellyfin-only IDs could orphan existing swipes
- **Session cookie last-write-wins** — Flask signed-cookie is a single blob; concurrent requests can silently overwrite changes
- **Delegate mode disambiguation** — Two browsers with same Jellyfin account need reliable session_id-based disambiguation

---

## Session Continuity

**Last Session:**
--stopped-at

- v2.0 roadmap created with 6 phases (23-28)
- 14/14 requirements mapped to phases
- Phase ordering follows research recommendations
- Next step: `/gsd-plan-phase 23`

---

## Quick Reference

**Key Files:**

- Project context: `.planning/PROJECT.md`
- Requirements: `.planning/REQUIREMENTS.md`
- Roadmap: `.planning/ROADMAP.md`
- Milestones: `.planning/MILESTONES.md`
- State: `.planning/STATE.md` (this file)
- Research: `.planning/research/SUMMARY.md`

**Important Commands:**

- `/gsd-plan-phase 23` — Begin planning Phase 23
- `/gsd-transition` — Mark phase complete and move to next
- `/gsd-progress` — View current progress

**Issue Reference:**

- Architecture tier violations: https://github.com/andrewthetechie/jelly-swipe/issues/8

---
*State created: 2026-04-26*
*Last updated: 2026-04-26 (roadmap created)*

**Planned Phase:** 25 (RESTful Routes + Deck Ownership) — 2 plans — 2026-04-27T17:44:00.413Z
