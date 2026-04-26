# Requirements: Jelly Swipe (v1.4 — Clean up Unraid template)

**Defined:** 2026-04-25
**Core Value:** Users can run a swipe session backed by Jellyfin, with library browsing and deck behavior equivalent to the original Plex path.

## v1.4 Requirements

Requirements for Unraid template cleanup milestone. Each maps to roadmap phases.

### Template Variables

- [ ] **TEMP-01**: Unraid template uses JELLYFIN_URL instead of PLEX_URL
- [ ] **TEMP-02**: Unraid template uses JELLYFIN_API_KEY or JELLYFIN_USERNAME/JELLYFIN_PASSWORD instead of PLEX_TOKEN
- [ ] **TEMP-03**: Unraid template includes TMDB_API_KEY masked variable
- [ ] **TEMP-04**: Unraid template includes FLASK_SECRET masked variable

### Template UX

- [ ] **UX-01**: Unraid template masked fields have no fake placeholder values (blank by default)

### CI Validation

- [ ] **CI-01**: CI workflow lints Unraid template to verify variables are a strict subset of recognized app env vars

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Advanced Testing (from v1.3 Active candidates)

- **ADV-01**: Coverage thresholds enforced in CI to prevent regression
- **ADV-02**: Multiple coverage reports (HTML for local, XML for CI)
- **ADV-03**: pytest-mock integration for cleaner mock API
- **ADV-04**: Parametrized fixtures for comprehensive scenario coverage
- **ADV-05**: Module-scoped fixtures for test performance optimization

### Future Enhancements

- **ARC-02 closure**: Formal Plex regression matrix verification (partial in v1.0)
- **OPS-01 / PRD-01**: Neutral DB column naming and multi-library selection

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Plex support in template | Product is Jellyfin-only since v1.2 |
| Unraid template UI redesign | Out of scope for this cleanup issue |
| Additional Unraid features | Focus on fixing broken deployment only |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| TEMP-01 | Phase 18 | Pending |
| TEMP-02 | Phase 18 | Pending |
| TEMP-03 | Phase 18 | Pending |
| TEMP-04 | Phase 18 | Pending |
| UX-01 | Phase 18 | Pending |
| CI-01 | Phase 18 | Pending |

**Coverage:**
- v1.4 requirements: 6 total
- Mapped to phases: 6
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-25*
*Last updated: 2026-04-25 after initial definition*
