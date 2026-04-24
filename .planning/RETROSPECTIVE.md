# Retrospective — Kino Swipe

Cross-milestone trends accumulate at the bottom of this file.

---

## Milestone: v1.0 — Jellyfin support

**Shipped:** 2026-04-24  
**Phases:** 1–9 | **Theme:** Either/or Plex/Jellyfin backend with verification closure and operator E2E narrative.

### What was built

- Provider abstraction with Jellyfin REST client, env auth, deck/genre/proxy/TMDB parity routes.
- Verification and validation artifacts for configuration through user parity (`01`–`05`, `06`–`07`, `08`).
- Phase 9: Flask session delegate identity for Jellyfin browser UX + poster letterboxing in dual HTML surfaces.

### What worked

- Phased verification closure (6–7) separated “evidence debt” from feature delivery.
- Either-or deployment model kept configuration and security review tractable.

### What was inefficient

- `gsd-sdk query milestone.complete` failed in this environment (`version required for phases archive`); milestone close was finished manually with the same artifacts the CLI would have produced.

### Patterns established

- Native per-phase `*-VERIFICATION.md` plus milestone audit file for re-audit readiness.
- Mirrored `templates/index.html` and `data/index.html` for PWA-facing changes.

### Key lessons

- Ship UI polish (Phase 9) after auth/library parity so delegate flows sit on a stable provider stack.
- Keep Plex parity (ARC-02) on the checklist until operator matrix in `02-VERIFICATION.md` is fully green.

### Cost observations

Not tracked in-repo; add session/token notes here if you adopt cost logging next milestone.

---

## Cross-Milestone Trends

| Milestone | Verification style | Open parity gaps |
|-----------|---------------------|------------------|
| v1.0 | Native phase VERIFICATION + VALIDATION + audit | ARC-02 (Plex), partial J\* traceability rows |
