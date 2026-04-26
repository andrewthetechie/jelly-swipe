# Requirements: Jelly Swipe

**Defined:** 2026-04-26
**Core Value:** Users can run a swipe session backed by Jellyfin, with library browsing and deck behavior equivalent to the original Plex path.

## v1.5 Requirements

Requirements for route test coverage milestone. Each maps to roadmap phases.

### App Factory

- [ ] **FACTORY-01**: Refactor `jellyswipe/__init__.py` into `create_app(test_config=None)` factory function with backwards-compatible global `app` instance

### Route Tests

- [x] **TEST-ROUTE-01
**: Add `tests/test_routes_auth.py` with authentication route tests (provider, server identity, login) including header-spoof tests for EPIC-01
- [x] **TEST-ROUTE-02
**: Add `tests/test_routes_xss.py` with XSS security tests (HTML tag escaping, javascript: URL rejection, script injection prevention) for EPIC-03
- [x] **TEST-ROUTE-03
**: Add `tests/test_routes_room.py` with room operation tests (create, join, swipe, match, quit, status, go-solo) covering happy paths and edge cases
- [x] **TEST-ROUTE-04
**: Add `tests/test_routes_proxy.py` with proxy route tests (valid/invalid paths, allowlist regex validation, content-type verification) for EPIC-04 SSRF prevention
- [ ] **TEST-ROUTE-05**: Add `tests/test_routes_sse.py` with SSE streaming tests (event streaming, invalid room handling, state change events, GeneratorExit handling)

### Coverage

- [ ] **COV-01**: Add `--cov-fail-under=70` to pytest configuration in pyproject.toml to enforce 70% coverage threshold for `jellyswipe/__init__.py`

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Coverage Reports

- **COV-02**: Add HTML coverage reports for local development
- **COV-03**: Add XML coverage reports for CI tools

### Advanced Testing

- **ADV-01**: Add parallel test execution with pytest-xdist
- **ADV-02**: Add property-based testing with Hypothesis
- **ADV-03**: Add end-to-end integration tests

### Deferred Product Features

- **ARC-02**: Plex regression matrix verification (partial in v1.0)
- **OPS-01**: Neutral DB column naming and multi-library selection
- **PRD-01**: Additional product features TBD

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| pytest-flask plugin | Flask's built-in test client is sufficient; unnecessary dependency |
| Framework-agnostic route tests | Route testing requires Flask test client; not framework-agnostic |
| Real Jellyfin/TMDB API calls in tests | Unit tests must be isolated from external dependencies |
| Edge case tests (concurrent operations) | Not required for 70% coverage target; defer to v2+ |
| Performance tests (load testing) | Not required for v1.5; defer to v2+ |
| Integration tests (end-to-end workflows) | Separate concern from unit/route testing; defer to v2+ |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FACTORY-01 | Phase 21 | Pending |
| TEST-ROUTE-01 | Phase 23 | Complete |
| TEST-ROUTE-02 | Phase 24 | Pending |
| TEST-ROUTE-03 | Phase 25 | Complete |
| TEST-ROUTE-04 | Phase 26 | Complete |
| TEST-ROUTE-05 | Phase 27 | Pending |
| COV-01 | Phase 28 | Pending |

**Coverage:**
- v1.5 requirements: 7 total
- Mapped to phases: 7/7 ✓
- Unmapped: 0

---
*Requirements defined: 2026-04-26*
*Last updated: 2026-04-26 after v1.5 roadmap creation*
