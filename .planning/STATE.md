---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Architecture Tier Fix
status: defining_requirements
last_updated: "2026-04-26T17:00:00.000Z"
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# State — Jelly Swipe

**Milestone:** v2.0 Architecture Tier Fix
**Phase:** Not started (defining requirements)
**Status:** Defining requirements
**Progress:** [░░░░░░░░░░] 0%

---

## Project Reference

**What This Is:**
Jelly Swipe is a small Flask app for shared "Tinder for movies" sessions: a host creates a room, guests join, everyone swipes on a deck pulled from a home media server, and matches surface when two people swipe right on the same title. Trailers and cast come from TMDB.

**Core Value:**
Users can run a swipe session backed by Jellyfin, with library browsing and deck behavior equivalent to the original Plex path.

**Current Focus:** Defining requirements for v2.0 Architecture Tier Fix

---

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-04-26 — Milestone v2.0 started

---

## Accumulated Context

### Decisions Made

**v2.0 Architecture Strategy (Current Milestone):**

- Server owns identity (session → Jellyfin token → user_id)
- Server owns deck composition and order
- Server owns match decision and notification (SSE only)
- Server generates deep links from JELLYFIN_URL
- Client owns animation and optimistic UI only
- Token storage moves to server-side session with HttpOnly cookie
- ADR will document tier responsibilities

**Previous Milestone Decisions:**

- v1.5: Three-layer XSS defense (server validation + safe DOM + CSP)
- v1.4: Authorization hardening
- v1.3: pytest with framework-agnostic imports, terminal-only coverage
- v1.2: uv dependency management, jellyswipe/ package layout, Plex removal
- v1.1: Jelly Swipe rename, AndrewTheTechie branding
- v1.0: Jellyfin as alternative backend, provider abstraction

### Active Todos

None yet — requirements being defined.

### Known Blockers

None.

### Risks and Concerns

- Significant refactor touching routes and client JS simultaneously
- Must maintain existing functionality while restructuring
- Session/cookie changes affect all authenticated flows
- Need to ensure SSE channel is the sole match notification path

---

## Session Continuity

**Last Session:**
2026-04-26T17:00:00.000Z

- v2.0 milestone initiated from Issue #8
- PROJECT.md updated with v2.0 goals
- STATE.md reset for new milestone
- Next step: Research decision, then define requirements

---

## Quick Reference

**Key Files:**

- Project context: `.planning/PROJECT.md`
- Requirements: `.planning/REQUIREMENTS.md`
- Roadmap: `.planning/ROADMAP.md`
- Milestones: `.planning/MILESTONES.md`
- State: `.planning/STATE.md` (this file)

**Important Commands:**

- `/gsd-plan-phase N` — Begin planning phase N
- `/gsd-transition` — Mark phase complete and move to next
- `/gsd-complete-milestone` — Close current milestone
- `/gsd-progress` — View current progress

**Issue Reference:**

- Architecture tier violations: https://github.com/andrewthetechie/jelly-swipe/issues/8

---

*State created: 2026-04-26*
*Last updated: 2026-04-26 (v2.0 milestone started)*
