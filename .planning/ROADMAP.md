# Roadmap — Jelly Swipe

**Milestone:** v1.6 Plex Reference Cleanup
**Granularity:** Standard (5-8 phases)
**Current Phase:** 23 - Backend Source Cleanup (Not started)
**Last Updated:** 2026-04-26

---

## Overview

This roadmap removes all remaining Plex references from the source code so `rg -i 'plex'` returns only intentional historical references (README fork attribution). Purely a deletion milestone — no new features. Work spans four phases covering backend source files, the frontend template, configuration/deploy artifacts, and a final acceptance sweep.

**Phases:** 4
**Requirements:** 16 (SRC-01–03, FE-01–08, CFG-01–04, ACC-01)
**Starting Phase:** 23 (continuing from v1.5 Phase 22)

---

## Phases

- [ ] **Phase 23: Backend Source Cleanup** — Remove dead `/plex/server-info` route, stale `plex_id` comments from db.py, and fix base.py docstring to reference Jellyfin API path
- [x] **Phase 24: Frontend Plex Cleanup** — Strip all Plex CSS classes, JS functions, conditional branches, localStorage keys, URLs, and UI copy from templates/index.html (completed 2026-04-26)
- [ ] **Phase 25: Config & Deploy Cleanup** — Update manifest descriptions, delete dead data/index.html, clean Unraid template, and remove/strip requirements.txt
- [ ] **Phase 26: Acceptance Validation** — Run `rg -i 'plex'` and verify only intentional historical references remain

---

## Phase Details

### Phase 23: Backend Source Cleanup

**Goal:** All dead Plex route code and stale Plex references removed from backend Python source files.

**Depends on:** Nothing (first phase of v1.6)

**Requirements:** SRC-01, SRC-02, SRC-03

**Success Criteria** (what must be TRUE):
1. `/plex/server-info` route no longer exists in `jellyswipe/__init__.py` — requesting it returns 404
2. `jellyswipe/db.py` contains zero `plex_id` references in comments or code
3. `base.py` docstring references Jellyfin API path (`jellyfin/{id}/Primary`) instead of Plex `/library/metadata/`

**Plans:** 1 plan

Plans:
- [ ] 23-01-PLAN.md — Remove dead Plex route code and stale references from 3 backend Python files

---

### Phase 24: Frontend Plex Cleanup

**Goal:** All Plex-specific CSS, JavaScript, localStorage keys, URLs, and UI copy removed from the main template — leaving only Jellyfin code paths.

**Depends on:** Phase 23 (backend clean first, then frontend)

**Requirements:** FE-01, FE-02, FE-03, FE-04, FE-05, FE-06, FE-07, FE-08

**Success Criteria** (what must be TRUE):
1. No CSS classes containing "plex" exist in `jellyswipe/templates/index.html`
2. No JavaScript functions referencing Plex (`loginWithPlex`, `fetchPlexServerId`) exist in the template
3. No `mediaProvider === 'plex'` conditional branches remain in any frontend code
4. No Plex-related localStorage keys (`plex_token`, `plex_id`), HTTP headers (`X-Plex-Token`, `X-Plex-User-ID`), or literal Plex URLs exist in the codebase
5. No Plex UI copy ("Login with Plex", "OPEN IN PLEX") appears in the application interface

**Plans:** 2/2 plans complete

Plans:
- [x] 24-01-PLAN.md — Add Jellyfin server-info endpoint and rename Plex CSS classes
- [x] 24-02-PLAN.md — Remove all Plex JS functions, branches, localStorage, URLs, and UI copy

---

### Phase 25: Config & Deploy Cleanup

**Goal:** All deployment and configuration artifacts are free of Plex references and dead files are removed.

**Depends on:** Phase 24 (frontend clean, then sweep remaining config files)

**Requirements:** CFG-01, CFG-02, CFG-03, CFG-04

**Success Criteria** (what must be TRUE):
1. Both `manifest.json` files describe "Jellyfin" only — no "Plex or Jellyfin" text
2. `data/index.html` no longer exists on disk
3. `unraid_template/jelly-swipe.html` contains no Plex environment variables
4. `requirements.txt` is either deleted or contains no `plexapi` reference

**Plans:** 1 plan

Plans:
- [ ] 25-01-PLAN.md — Update manifest descriptions and delete dead config files

---

### Phase 26: Acceptance Validation

**Goal:** Verified that `rg -i 'plex'` against source returns only intentional historical references (README fork attribution), confirming the cleanup is complete.

**Depends on:** Phase 25 (all cleanup complete before final sweep)

**Requirements:** ACC-01

**Success Criteria** (what must be TRUE):
1. `rg -i 'plex'` returns only README fork attribution references — no hits in source, templates, config, or deploy files
2. All 16 v1.6 requirements pass individual verification
3. Application still starts and serves correctly with Jellyfin configuration after all deletions

**Plans:** TBD

---

## Progress

**Execution Order:**
Phases execute in numeric order: 23 → 24 → 25 → 26

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 23. Backend Source Cleanup | 0/1 | Not started | - |
| 24. Frontend Plex Cleanup | 2/2 | Complete    | 2026-04-26 |
| 25. Config & Deploy Cleanup | 0/1 | Not started | - |
| 26. Acceptance Validation | 0/? | Not started | - |

---

## Milestone Context

**Previous Milestones:**
- v1.0 (Jellyfin support): Phases 1–9 ✅
- v1.1 (Rename): No numbered phases ✅
- v1.2 (uv + Package Layout + Plex Removal): Phases 10–13 ✅
- v1.3 (Unit Tests): Phases 14–17 ✅
- v1.4 (Authorization Hardening): Phases 1–18 ✅
- v1.5 (XSS Security Fix): Phases 19–22 ✅

**Current Milestone:** v1.6 Plex Reference Cleanup — Phases 23–26
**Issue Reference:** https://github.com/andrewthetechie/jelly-swipe/issues/11

---

*Roadmap created: 2026-04-26*
*Last updated: 2026-04-26*
