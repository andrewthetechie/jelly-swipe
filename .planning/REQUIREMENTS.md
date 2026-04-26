# Requirements: Jelly Swipe

**Defined:** 2026-04-26
**Milestone:** v1.6 Plex Reference Cleanup
**Core Value:** Users can run a swipe session backed by Jellyfin, with library browsing and deck behavior equivalent to the original Plex path.

## v1.6 Requirements

Requirements for this milestone are scoped to Issue #11 (EPIC-08) — remove all remaining Plex references from the source code. Purely deletion; no new features.

### Source Cleanup (SRC)

- [ ] **SRC-01**: `/plex/server-info` route deleted from `jellyswipe/__init__.py` (lines 337–341).
- [ ] **SRC-02**: `plex_id` references removed from `jellyswipe/db.py` comments (lines :35, :41).
- [ ] **SRC-03**: `base.py` docstring at :42 updated to reference Jellyfin API path (`jellyfin/{id}/Primary`) instead of Plex `/library/metadata/`.

### Frontend Cleanup (FE)

- [x] **FE-01**: `.plex-yellow` and `.plex-open-btn` CSS classes renamed to neutral names in `jellyswipe/templates/index.html`.
- [x] **FE-02**: `loginWithPlex` and `fetchPlexServerId` JS functions removed from `jellyswipe/templates/index.html`.
- [x] **FE-03**: All `mediaProvider === 'plex'` conditional branches removed from `jellyswipe/templates/index.html`.
- [x] **FE-04**: Plex-related localStorage keys (`plex_token`, `plex_id`) and Plex HTTP headers (`X-Plex-Token`, `X-Plex-User-ID`) removed.
- [x] **FE-05**: Literal Plex URLs removed (`plex.tv/api/v2/user`, `app.plex.tv/desktop`).
- [x] **FE-06**: `plexServerId` variable and `plex_id` references removed from `/room/swipe` body handler.
- [x] **FE-07**: Plex auth PIN flow removed (`/auth/check-returned-pin`, `/auth/plex-url` route calls).
- [x] **FE-08**: Plex UI copy removed ("Login with Plex", "OPEN IN PLEX").

### Config & Deploy Cleanup (CFG)

- [ ] **CFG-01**: Manifest descriptions updated from "Plex or Jellyfin" to "Jellyfin" in both `jellyswipe/static/manifest.json` and `data/manifest.json`.
- [ ] **CFG-02**: Dead `data/index.html` deleted (never-fetched PWA shell).
- [ ] **CFG-03**: Plex env block removed from `unraid_template/jelly-swipe.html`.
- [ ] **CFG-04**: `requirements.txt` deleted or stripped of plexapi (file is deprecated; Docker uses uv).

### Acceptance Validation (ACC)

- [ ] **ACC-01**: `rg -i 'plex'` against source returns only intentional historical references (README fork attribution).

## v2 Requirements

Deferred to future milestones.

### Existing Deferred Candidates

- **ARC-02**: Formal Plex regression matrix closure in archived v1.0 verification artifacts.
- **OPS-01 / PRD-01**: Neutral DB column naming and multi-library selection.
- **ADV-01**: Coverage thresholds enforced in CI to prevent regression.
- **ADV-02**: Multiple coverage reports (HTML for local, XML for CI).

## Out of Scope

Explicitly excluded from v1.6.

| Feature | Reason |
|---------|--------|
| Renaming DB columns from plex_id | v1.2 already migrated schema; only stale comments remain |
| Adding new features | This is purely a cleanup milestone |
| Updating README fork attribution | Intentional historical reference; must be preserved |
| Refactoring frontend architecture | Only removing Plex dead code; no structural changes |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SRC-01 | Phase 23 | Pending |
| SRC-02 | Phase 23 | Pending |
| SRC-03 | Phase 23 | Pending |
| FE-01 | Phase 24 | Complete |
| FE-02 | Phase 24 | Complete |
| FE-03 | Phase 24 | Complete |
| FE-04 | Phase 24 | Complete |
| FE-05 | Phase 24 | Complete |
| FE-06 | Phase 24 | Complete |
| FE-07 | Phase 24 | Complete |
| FE-08 | Phase 24 | Complete |
| CFG-01 | Phase 25 | Pending |
| CFG-02 | Phase 25 | Pending |
| CFG-03 | Phase 25 | Pending |
| CFG-04 | Phase 25 | Pending |
| ACC-01 | Phase 26 | Pending |

**Coverage:**
- v1.6 requirements: 16 total
- Mapped to phases: 16
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-26*
*Last updated: 2026-04-26 after v1.6 definition*
