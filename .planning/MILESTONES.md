# Milestones — Kino Swipe

Living log of shipped versions. For current planning, see `.planning/ROADMAP.md`.

---

## v1.0 — Jellyfin support

**Shipped:** 2026-04-24  
**Name:** Jellyfin as alternative media backend (either/or `MEDIA_PROVIDER` per deployment)  
**Phases:** 1–9 (implementation 1–5, verification closure 6–7, E2E/validation 8, UI 9)

**Archives:**

- [v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md) — full phase roadmap snapshot  
- [v1.0-REQUIREMENTS.md](milestones/v1.0-REQUIREMENTS.md) — requirement list and traceability at close  
- [v1.0-MILESTONE-AUDIT.md](milestones/v1.0-MILESTONE-AUDIT.md) — pre-close audit (`ready_for_reaudit`)  
- [v1.0-phases/](milestones/v1.0-phases/) — phase execution directories (Phases 1–9) after `/gsd-cleanup`

### What shipped (high level)

1. **Configuration** — Single active provider (`plex` or `jellyfin`), env validation, README / compose notes.  
2. **Abstraction** — `LibraryMediaProvider` with Plex and Jellyfin implementations.  
3. **Jellyfin core** — Server auth, deck/genres/images, TMDB chain, `/plex/server-info` parity, user-scoped rows and watchlist.  
4. **Verification** — Native `*-VERIFICATION.md` / `*-VALIDATION.md` closure for foundation and Jellyfin parity.  
5. **Operator narrative** — `08-E2E.md` and validation tables for re-audit.  
6. **UI (Phase 9)** — Server-delegated Jellyfin browser session (no env-token JSON leakage) and poster `object-fit: contain` in `templates/index.html` and `data/index.html`.

### Known gaps at close

Documented in the milestone audit; not blocking the **v1.0** tag as shipped product direction.

| ID | Gap | Pointer |
|----|-----|---------|
| ARC-02 | Plex baseline parity checklist remains **partial** | `milestones/v1.0-phases/02-media-provider-abstraction/02-VERIFICATION.md` |
| Traceability | Several J\* rows **Partial** in archived requirements | Native `03-` / `04-` / `05-VERIFICATION.md` under `v1.0-phases/` |
| E2E | `08-E2E.md` operator date tables still **draft** until live runs | `milestones/v1.0-phases/08-e2e-validation-hardening/08-E2E.md` |

### Deferred items at milestone close

`gsd-tools.cjs audit-open` reported **all artifact types clear** (no blocking open debug/UAT items).
