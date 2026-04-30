# Requirements: Jelly Swipe

**Defined:** 2026-04-29
**Milestone:** v1.7 SSE/SQLite Architecture Fix
**Core Value:** Users can run a swipe session backed by Jellyfin, with library browsing and deck behavior equivalent to the original Plex path.

## v1.7 Requirements

Fix the SQLite contention and SSE reliability problems that collapse the app under load when multiple rooms have connected browsers.

### SQLite Performance (DB)

- [x] **DB-01**: SQLite runs in WAL mode with `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL` set at database initialization
- [x] **DB-02**: SSE generator holds one SQLite connection per client session instead of opening and closing a connection every 1.5-second poll cycle

### SSE Reliability (SSE)

- [x] **SSE-01**: Poll interval includes random jitter (0–0.5s) to desynchronize concurrent thundering-herd queries
- [x] **SSE-02**: SSE stream sends heartbeat comment (`: ping\n\n`) every ~15 seconds to prevent reverse proxy connection reaping
- [x] **SSE-03**: SSE stream handles room disappearance gracefully — exits immediately when the room record is gone, rather than waiting for the next poll tick

### Acceptance (ACC)

- [ ] **ACC-01**: All existing tests (48+) continue to pass after all architecture changes

## v2 Requirements

Deferred to future milestones.

### Existing Deferred Candidates

- **ARC-02**: Formal Plex regression matrix closure in archived v1.0 verification artifacts.
- **OPS-01 / PRD-01**: Neutral DB column naming and multi-library selection.
- **ADV-01**: Coverage thresholds enforced in CI to prevent regression.
- **ADV-02**: Multiple coverage reports (HTML for local, XML for CI).

### Architecture Improvements (Future)

- **ARCH-01**: Replace room-state-as-message-bus pattern with a proper event notification mechanism (e.g., server-sent events triggered by writes, or a pub/sub layer) to prevent `last_match_data` overwrites when multiple matches occur within one poll cycle.
- **ARCH-02**: Migrate `/movies` endpoint to serve movie data from a cached/optimized path instead of reading a multi-KB blob from SQLite on every room join.

## Out of Scope

Explicitly excluded from v1.7.

| Feature | Reason |
|---------|--------|
| WebSocket migration | SSE works — this milestone fixes the existing pattern, not replaces it |
| Postgres/Redis data store | SQLite is appropriate for the app's scale; WAL fixes the contention |
| Message bus architecture | Out of scope for this fix; `last_match_data` overwrite is a known limitation to address later |
| Rate limiting on SSE endpoint | Not the root cause; may be added later |
| Replacing gevent workers | gevent is appropriate for SSE; the problem is SQLite access patterns |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DB-01 | Phase 27 | Complete |
| DB-02 | Phase 27 | Complete |
| SSE-01 | Phase 28 | Complete |
| SSE-02 | Phase 28 | Complete |
| SSE-03 | Phase 28 | Complete |
| ACC-01 | Phase 29 | Pending |

**Coverage:**
- v1.7 requirements: 6 total
- Mapped to phases: 6
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-29*
*Last updated: 2026-04-29 after roadmap creation (Phases 27–29)*