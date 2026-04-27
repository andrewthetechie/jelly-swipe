# Requirements: Jelly Swipe

**Defined:** 2026-04-26
**Milestone:** v2.0 Architecture Tier Fix
**Core Value:** Users can run a swipe session backed by Jellyfin, with library browsing and deck behavior equivalent to the original Plex path.

## v2.0 Requirements

Requirements for this milestone are scoped to Issue #8 — eliminating 7 tier responsibility violations between server and client.

### Identity & Auth

- [x] **AUTH-01**: Server resolves user identity from session cookie alone — no client-supplied headers for user_id or identity
- [x] **AUTH-02
**: Jellyfin API token stored in server-side `user_tokens` SQLite table, keyed by session_id; never exposed to client JavaScript
- [x] **AUTH-03
**: Expired `user_tokens` rows are cleaned up automatically (rows older than 24 hours deleted)

### Deck Management

- [ ] **DECK-01**: Server is sole source of deck composition and shuffle order; client never re-fetches or re-shuffles
- [ ] **DECK-02**: Server tracks each user's cursor position in the deck for reconnect support

### Match & Notification

- [ ] **MTCH-01**: Match notification delivered exclusively via SSE stream — swipe HTTP response returns `{accepted: true}` only, no match payload
- [ ] **MTCH-02**: Match responses enriched with rating, duration, and year via server-side join through movies table
- [ ] **MTCH-03**: Match check-and-insert wrapped in SQLite `BEGIN IMMEDIATE` transaction to prevent TOCTOU race

### RESTful API

- [ ] **API-01**: Swipe endpoint restructured as `POST /room/{code}/swipe` accepting `{movie_id, direction}` only
- [ ] **API-02**: Server generates Jellyfin deep links as `{JELLYFIN_URL}/web/#/details?id={itemId}` — client never constructs media URLs
- [ ] **API-03**: `GET /me` endpoint returns verified user id, display name, and server info from server-side session
- [ ] **API-04**: Dedicated `POST /room/solo` endpoint creates a solo session without the two-player room lifecycle

### Client Cleanup

- [ ] **CLNT-01**: Front-end never reads `provider_token` or `plex_token` from localStorage — all auth is session-cookie based
- [ ] **CLNT-02**: Client-side match detection logic removed — match popup triggered only by SSE events, never by swipe HTTP response

## v2 Requirements

Deferred to future milestones.

### Existing Deferred Candidates

- **ARC-02**: Formal Plex regression matrix closure in archived v1.0 verification artifacts.
- **OPS-01 / PRD-01**: Neutral DB column naming and multi-library selection.
- **ADV-01**: Coverage thresholds enforced in CI to prevent regression.
- **ADV-02**: Multiple coverage reports (HTML for local, XML for CI).

## Out of Scope

Explicitly excluded from v2.0.

| Feature | Reason |
|---------|--------|
| Dual-read migration bridge | Accept breaking change during upgrade; no backward-compatible localStorage path |
| Flask-Session extension | Custom SQLite token vault is simpler and consistent with existing patterns |
| Delegate mode disambiguation | Same-account multi-user is not a supported use case in v2.0 |
| Redis or external session store | Single-server Docker deployment; filesystem/SQLite sufficient |
| ADR as a shipped artifact | Decision documented in PROJECT.md and code; formal ADR is documentation overhead for this scale |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 | Phase 24 | Complete |
| AUTH-02 | Phase 23 | Pending |
| AUTH-03 | Phase 23 | Pending |
| DECK-01 | Phase 25 | Pending |
| DECK-02 | Phase 25 | Pending |
| MTCH-01 | Phase 26 | Pending |
| MTCH-02 | Phase 26 | Pending |
| MTCH-03 | Phase 26 | Pending |
| API-01 | Phase 25 | Pending |
| API-02 | Phase 26 | Pending |
| API-03 | Phase 26 | Pending |
| API-04 | Phase 26 | Pending |
| CLNT-01 | Phase 27 | Pending |
| CLNT-02 | Phase 27 | Pending |

**Coverage:**
- v2.0 requirements: 14 total
- Mapped to phases: 14 ✓
- Unmapped: 0

---
*Requirements defined: 2026-04-26*
*Last updated: 2026-04-26 after roadmap creation (traceability mapped to Phases 23-28)*
