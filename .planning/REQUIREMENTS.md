# Requirements: Jelly Swipe — v1.1 project rename

**Defined:** 2026-04-24  
**Core value:** Same as v1.0 — Plex or Jellyfin-backed swipe sessions — under the **Jelly Swipe** product name and **AndrewTheTechie** maintainer identity.

## v1.1 Requirements

### Branding and packaging

- [x] **BRAND-01**: User-visible page titles and PWA manifest fields use **Jelly-Swipe** / **Jelly Swipe** naming (replacing Kino-Swipe).
- [x] **BRAND-02**: `README.md` reflects the new name, Docker image coordinates (`andrewthetechie/jelly-swipe`), and a single prominent **fork** line pointing at `https://github.com/Bergasha/kino-swipe`; other maintainer references use **AndrewTheTechie** (no Bergasha attribution except that fork line).
- [x] **BRAND-03**: Unraid community template is updated and renamed to `unraid_template/jelly-swipe.html` with repository/support/project URLs under `AndrewTheTechie/jelly-swipe`.
- [x] **BRAND-04**: Default SQLite filename and ignore rules use `jellyswipe.db`; `docker-compose.yml` and GitHub Actions publish workflow use the new image name; Plex client identifier string updated (operators may need to re-link Plex.tv after upgrade).

## Out of scope (v1.1)

- Renaming the local git checkout directory (still `kino-swipe` on disk until you rename it).
- Rewriting archived milestone markdown under `.planning/milestones/v1.0-phases/` (historical snapshot).

## Traceability

| Requirement | Phase | Status |
|---------------|-------|--------|
| BRAND-01 | 10 | Done |
| BRAND-02 | 10 | Done |
| BRAND-03 | 10 | Done |
| BRAND-04 | 10 | Done |

---
*Last updated: 2026-04-24 — v1.1 rename milestone*
