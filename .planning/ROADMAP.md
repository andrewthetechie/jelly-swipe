# Roadmap — Jelly Swipe

**Milestone:** v2.0 Architecture Tier Fix
**Granularity:** Standard (5-8 phases)
**Current Phase:** 23 - Database Schema + Token Vault
**Last Updated:** 2026-04-26

---

## Milestones

- ✅ **v1.0 MVP** - Phases 1-9 (shipped 2026-04-24)
- ✅ **v1.1 Rename** - Phases 10 (shipped 2026-04-24)
- ✅ **v1.2 uv + Package** - Phases 11-13 (shipped 2026-04-25)
- ✅ **v1.3 Unit Tests** - Phases 14-17 (shipped 2026-04-25)
- ✅ **v1.4 Auth Hardening** - Phases 18 (shipped)
- ✅ **v1.5 XSS Fix** - Phases 19-22 (shipped 2026-04-26)
- 🚧 **v2.0 Architecture Tier Fix** - Phases 23-28 (in progress)

---

## Overview

This roadmap eliminates tier responsibility violations between server and client. The server takes ownership of identity resolution, token storage, deck composition, match decision logic, and deep link generation. The client is simplified to animation and optimistic UI only. The migration is sequenced so additive schema changes come first, auth logic builds on the new schema, routes and deck ownership come next, match/notification logic follows, client cleanup is purely subtractive, and deployment validation confirms everything works end-to-end.

**Status:** 🚧 **In Progress**
**Phases:** 6 (Phases 23-28)
**Requirements:** 14
**Starting Phase:** 23 (continuing from v1.5 Phase 22)

---

## Phases

**Phase Numbering:**
- Integer phases (23, 24, 25...): Planned milestone work
- Decimal phases (23.1, 24.1...): Urgent insertions (marked with INSERTED)

- [ ] **Phase 23: Database Schema + Token Vault** - Additive-only schema migration: user_tokens table, deck state columns, expired token cleanup
- [ ] **Phase 24: Auth Module + Server-Owned Identity** - Token vault CRUD, @login_required decorator, session cookie auth, identity unification
- [ ] **Phase 25: RESTful Routes + Deck Ownership** - POST /room/{code}/swipe, server-owned deck composition/order/cursor
- [ ] **Phase 26: Match Notification + Deep Links + Metadata** - SSE-only match delivery, enriched match metadata, Jellyfin deep links, /me, /room/solo
- [ ] **Phase 27: Client Simplification + Cleanup** - Remove localStorage tokens, identity headers, client-side match detection, URL construction
- [ ] **Phase 28: Deployment Validation** - Docker volume mounts, ProxyFix verification, end-to-end flow validation

---

## Phase Details

### Phase 23: Database Schema + Token Vault

**Goal:** Foundation exists for server-side token storage — database has the tables and columns needed by all subsequent phases.

**Depends on:** Nothing (first phase of v2.0, additive-only)

**Requirements:** AUTH-02, AUTH-03

**Success Criteria** (what must be TRUE):
  1. `user_tokens` table exists in SQLite with columns: session_id (PK), jellyfin_token, jellyfin_user_id, created_at
  2. Existing rooms and matches tables have new columns alongside existing ones — no data loss from additive-only migration
  3. Rows in `user_tokens` older than 24 hours are automatically cleaned up when `cleanup_expired_tokens()` is called
  4. Existing tests continue passing after schema migration (backward compatibility preserved)

**Plans:** TBD

Plans:
- [ ] 23-01: Add user_tokens table and deck/match schema columns
- [ ] 23-02: Implement expired token cleanup function

---

### Phase 24: Auth Module + Server-Owned Identity

**Goal:** Server resolves user identity from session cookie alone — no client-supplied headers for user_id or identity.

**Depends on:** Phase 23 (user_tokens table exists)

**Requirements:** AUTH-01

**Success Criteria** (what must be TRUE):
  1. User authenticates via Jellyfin credentials, and the server stores the Jellyfin token in `user_tokens` keyed by session_id — client never sees the token
  2. All authenticated endpoints resolve user_id from session cookie + token vault lookup — no client-supplied user_id or identity headers are read
  3. Client receives an HttpOnly session cookie containing only session_id; browser DevTools show no token in localStorage or JavaScript-accessible cookies
  4. `@login_required` decorator populates `g.user_id` and `g.jf_token` for every authenticated request; unauthenticated requests get a clear error

**Plans:** TBD

Plans:
- [ ] 24-01: Create auth.py with token vault CRUD and @login_required decorator
- [ ] 24-02: Refactor login and delegate routes to use token vault + session cookie

---

### Phase 25: RESTful Routes + Deck Ownership

**Goal:** Routes follow RESTful patterns with room code in URL path, and the server is the sole source of deck composition, order, and cursor position.

**Depends on:** Phase 24 (stable server-owned identity via g.user_id)

**Requirements:** API-01, DECK-01, DECK-02

**Success Criteria** (what must be TRUE):
  1. Swipe endpoint accepts `POST /room/{code}/swipe` with body `{movie_id, direction}` only — no title, thumb, or metadata parameters accepted
  2. Deck composition and shuffle order are generated server-side; client receives cards from server without re-fetching or re-shuffling
  3. Server tracks each user's cursor position in the deck; a user who reloads the page resumes where they left off in the same deck order
  4. Existing route patterns that depend on client-supplied identity or deck state are replaced by server-resolved equivalents

**Plans:** TBD

Plans:
- [ ] 25-01: Restructure swipe endpoint to POST /room/{code}/swipe
- [ ] 25-02: Implement server-owned deck composition, shuffle, and cursor tracking

---

### Phase 26: Match Notification + Deep Links + Metadata

**Goal:** Match logic is fully server-owned with enriched match data, correct Jellyfin deep links, and new identity/solo endpoints.

**Depends on:** Phase 25 (RESTful routes and server-owned identity in place)

**Requirements:** MTCH-01, MTCH-02, MTCH-03, API-02, API-03, API-04

**Success Criteria** (what must be TRUE):
  1. Swipe HTTP response returns `{accepted: true}` only; match notifications appear exclusively via SSE stream event, never in the swipe response payload
  2. Match SSE events include rating, duration, year, and deep_link — client receives complete match data without additional API calls
  3. Server generates Jellyfin deep links as `{JELLYFIN_URL}/web/#/details?id={itemId}` — no Plex URL construction patterns remain
  4. `GET /me` returns verified user id, display name, and server info from server-side session
  5. `POST /room/solo` creates a solo swipe session without the two-player room lifecycle
  6. Match check-and-insert is wrapped in SQLite `BEGIN IMMEDIATE` transaction — concurrent right-swipes on the same movie produce exactly one match

**Plans:** TBD

Plans:
- [ ] 26-01: SSE-only match delivery with enriched metadata
- [ ] 26-02: Jellyfin deep link generation, /me endpoint, /room/solo endpoint
- [ ] 26-03: BEGIN IMMEDIATE transaction for swipe+match atomicity

---

### Phase 27: Client Simplification + Cleanup

**Goal:** Client JavaScript is stripped of all server-responsibility code — token storage, identity headers, match detection, and URL construction are removed.

**Depends on:** Phase 26 (all server-side endpoints stable and producing correct responses)

**Requirements:** CLNT-01, CLNT-02

**Success Criteria** (what must be TRUE):
  1. No JavaScript code reads `provider_token` or `plex_token` from localStorage — all auth flows use session cookies exclusively
  2. Client-side match detection logic is removed; match popup renders only when an SSE event arrives, never from the swipe HTTP response
  3. Client never constructs media URLs — all deep links come from server match responses
  4. Client sends no identity headers (no X-User-Id, X-Provider-Token, or similar); server resolves identity from session cookie alone

**Plans:** TBD

**UI hint**: yes

Plans:
- [ ] 27-01: Remove localStorage token reads and identity header sends
- [ ] 27-02: Remove client-side match detection; wire popup to SSE events only

---

### Phase 28: Deployment Validation

**Goal:** The refactored application works correctly in Docker deployment with proper cookie security and proxy headers.

**Depends on:** Phase 27 (all code changes complete)

**Requirements:** (validation phase — no new requirements; validates all 14 v2.0 requirements end-to-end)

**Success Criteria** (what must be TRUE):
  1. Docker container starts and the application serves requests correctly with gunicorn + gevent workers
  2. Session cookies are properly configured for reverse proxy deployment — ProxyFix sets correct X-Forwarded headers and cookies respect HTTPS behind a proxy
  3. Full end-to-end flow works in Docker: authenticate → create/join room → swipe → receive match via SSE → open Jellyfin deep link

**Plans:** TBD

Plans:
- [ ] 28-01: Docker build verification and ProxyFix configuration
- [ ] 28-02: End-to-end flow validation in Docker environment

---

## Progress

**Execution Order:**
Phases execute in numeric order: 23 → 24 → 25 → 26 → 27 → 28

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 23. Database Schema + Token Vault | 0/2 | Not started | - |
| 24. Auth Module + Server-Owned Identity | 0/2 | Not started | - |
| 25. RESTful Routes + Deck Ownership | 0/2 | Not started | - |
| 26. Match Notification + Deep Links + Metadata | 0/3 | Not started | - |
| 27. Client Simplification + Cleanup | 0/2 | Not started | - |
| 28. Deployment Validation | 0/2 | Not started | - |
| **Total** | **0/13** | **In Progress** | - |

---

## Milestone Context

**Previous Milestone:** v1.5 (XSS Security Fix) — Phases 19-22 completed
**Current Milestone:** v2.0 (Architecture Tier Fix) — Phases 23-28
**Issue Reference:** https://github.com/andrewthetechie/jelly-swipe/issues/8
**Status:** 🚧 In Progress

**Architecture Goal:**
Eliminate tier responsibility violations — server owns identity, deck, match logic, and deep links; client owns animation and optimistic UI only.

**Research Flags (phases needing deeper investigation during planning):**
- **Phase 24:** Delegate mode identity disambiguation — two browsers with same Jellyfin account need session_id-based disambiguator
- **Phase 25:** Deck cursor resume-on-reconnect behavior — user reloads mid-session must resume from server-tracked position
- **Phase 26:** `BEGIN IMMEDIATE` pattern with gevent cooperative I/O — verify compatibility with existing `get_db()` connection-per-request

---

*Roadmap created: 2026-04-26*
*Last updated: 2026-04-26*
