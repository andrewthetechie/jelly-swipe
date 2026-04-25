# Roadmap: Jelly Swipe

**Planning root:** No active milestone — **v1.2** is shipped. **v1.0** / **v1.1** / **v1.2** are archived — see [MILESTONES.md](MILESTONES.md) and [milestones/](milestones/).

## Milestones

- ✅ **v1.0 — Jellyfin as alternative backend** — Phases 1–9 — 2026-04-24 — [Roadmap archive](milestones/v1.0-ROADMAP.md) · [Requirements](milestones/v1.0-REQUIREMENTS.md)
- ✅ **v1.1 — Jelly Swipe rename** — Branding & maintainer identity — 2026-04-24 — [Roadmap archive](milestones/v1.1-ROADMAP.md) · [Requirements](milestones/v1.1-REQUIREMENTS.md)
- ✅ **v1.2 — uv + `jellyswipe` package + Docker-only + Plex removal** — Phases 10–13 — 2026-04-25 — [Roadmap archive](milestones/v1.2-ROADMAP.md) · [Requirements](milestones/v1.2-REQUIREMENTS.md) · [Milestone audit](milestones/v1.2-MILESTONE-AUDIT.md)

**Phase history:** [v1.0-phases/](milestones/v1.0-phases/) (Phases 1–9), [v1.2-phases/](milestones/v1.2-phases/) (Phases 10–13). **v1.1** had no new numbered phase directories.

---

## v1.2 — Phase overview (archived)

| # | Phase | Goal | Status | Completion |
|---|--------|------|--------|------------|
| 10 | uv & Python 3.13 lockfile | Introduce `pyproject.toml`, `uv.lock`, and 3.13-aligned pins | ✅ Complete | 2026-04-24 |
| 11 | `jellyswipe/` package | Move Flask app and `media_provider` under `jellyswipe/` | ✅ Complete | 2026-04-25 |
| 12 | Docker & docs | Image uses uv; README and distribution story match Docker-only | ✅ Complete | 2026-04-25 |
| 13 | Remove Plex support | Remove all Plex code, dependencies, and references | ✅ Complete | 2026-04-25 |

**v1.2 Details:** See [v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md) for complete phase details, plans, and success criteria.

---

## Backlog

### Phase 999.1: Follow-up — Phase 1 incomplete plans (BACKLOG)

**Goal:** Resolve plans that ran without producing summaries during Phase 1 execution  
**Source phase:** 1  
**Deferred at:** 2026-04-23 during /gsd-next advancement to Phase 5  
**Plans:**

- [x] 1-01: configuration-startup plan 1 (ran, no SUMMARY.md)
- [x] 1-02: configuration-startup plan 2 (ran, no SUMMARY.md)

### Phase 999.2: Follow-up — Phase 3 missing planning artifacts (BACKLOG)

**Goal:** Create and execute missing plans for Phase 3 after context was gathered  
**Source phase:** 3  
**Deferred at:** 2026-04-23 during /gsd-next advancement to Phase 5  
**Plans:**

- [x] 3-01: create PLAN.md artifacts for auth/http client scope (context exists, no plans)

### Phase 999.3: Follow-up — Phase 4 missing planning artifacts (BACKLOG)

**Goal:** Create and execute missing plans for Phase 4 after context was gathered  
**Source phase:** 4  
**Deferred at:** 2026-04-23 during /gsd-next advancement to Phase 5  
**Plans:**

- [x] 4-01: create PLAN.md artifacts for library/media scope (context exists, no plans)
