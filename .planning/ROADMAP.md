# Roadmap: Jellyfin support

**Milestone:** Jellyfin as alternative media backend  
**Granularity:** Standard (GSD config)  
**Defined:** 2026-04-22

## Phase overview

| # | Phase | Goal | Requirements | Success criteria |
|---|--------|------|--------------|------------------|
| 1 | Configuration & startup | Either/or provider selection and env validation | CFG-01 — CFG-03 | 3 |
| 2 | Media provider abstraction | Plex behind a stable provider API | ARC-01 — ARC-03 | 3 |
| 3 | Jellyfin auth & client | Logged-in server session for API calls | JAUTH-01 — JAUTH-03 | 3 |
| 4 | Jellyfin library & media | Deck, genres, images, TMDB chain, server info | JLIB-01 — JLIB-05 | 5 |
| 5 | User parity & packaging | Per-user rows, watchlist/favorites, UI auth path, deps | JUSR-01 — JUSR-04 | 4 |

**UI hint:** Phase 5 — yes (front-end auth and headers per provider).

---

## Backlog

### Phase 999.1: Follow-up — Phase 1 incomplete plans (BACKLOG)

**Goal:** Resolve plans that ran without producing summaries during Phase 1 execution  
**Source phase:** 1  
**Deferred at:** 2026-04-23 during /gsd-next advancement to Phase 5
**Plans:**
- [ ] 1-01: configuration-startup plan 1 (ran, no SUMMARY.md)
- [ ] 1-02: configuration-startup plan 2 (ran, no SUMMARY.md)

### Phase 999.2: Follow-up — Phase 3 missing planning artifacts (BACKLOG)

**Goal:** Create and execute missing plans for Phase 3 after context was gathered  
**Source phase:** 3  
**Deferred at:** 2026-04-23 during /gsd-next advancement to Phase 5
**Plans:**
- [ ] 3-01: create PLAN.md artifacts for auth/http client scope (context exists, no plans)

### Phase 999.3: Follow-up — Phase 4 missing planning artifacts (BACKLOG)

**Goal:** Create and execute missing plans for Phase 4 after context was gathered  
**Source phase:** 4  
**Deferred at:** 2026-04-23 during /gsd-next advancement to Phase 5
**Plans:**
- [ ] 4-01: create PLAN.md artifacts for library/media scope (context exists, no plans)

## Phase 1: Configuration & startup

**Goal:** One deployment runs either Plex or Jellyfin; startup and docs match that contract.

**Requirements:** CFG-01, CFG-02, CFG-03

**Success criteria:**

1. Setting provider to `jellyfin` allows the process to start without Plex env vars present.  
2. Setting provider to `plex` preserves existing required-variable behavior.  
3. README describes both modes and the two-instance note for operators who want both backends.

---

## Phase 2: Media provider abstraction

**Goal:** All library operations go through an abstraction; Plex behavior is unchanged when selected.

**Requirements:** ARC-01, ARC-02, ARC-03

**Success criteria:**

1. Genres, deck fetch, item fetch for TMDB, server info, and poster fetch are reachable through the provider interface.  
2. Manual or automated check: Plex mode room create + swipe + trailer + proxy image matches pre-refactor behavior.  
3. In `jellyfin` mode before Phases 3–4 are complete, startup must fail fast with a clear message (no partial routes); Plex mode must remain fully functional behind the abstraction.

---

## Phase 3: Jellyfin authentication & HTTP client

**Goal:** Server-side Jellyfin session (token) with safe handling and reconnect behavior.

**Requirements:** JAUTH-01, JAUTH-02, JAUTH-03

**Success criteria:**

1. From configured credentials, the app obtains an access token usable for authenticated `/Items` calls.  
2. Forced invalidation (wrong password, revoked key) surfaces a clear error without leaking secrets.  
3. Token refresh or re-login path is defined and exercised once in manual test notes.

---

## Phase 4: Jellyfin library & media

**Goal:** Same card JSON and routes as Plex for the core swipe experience, including images and TMDB.

**Requirements:** JLIB-01, JLIB-02, JLIB-03, JLIB-04, JLIB-05

**Success criteria:**

1. Creating a room in Jellyfin mode loads a shuffled deck with populated thumbs in the browser.  
2. Genre changes refetch and update the room deck analogous to Plex.  
3. Trailer and cast endpoints return data for a Jellyfin-backed `movie_id`.  
4. Server info endpoint returns name + stable id string for display.  
5. Image proxy (or parallel route) rejects malicious paths.

---

## Phase 5: User parity & packaging

**Status:** Complete — 2026-04-23

**Goal:** Per-user match/history/undo and list-add work in Jellyfin mode; dependencies and compose are complete.

**Requirements:** JUSR-01, JUSR-02, JUSR-03, JUSR-04

**Success criteria:**

1. Two browser identities in Jellyfin mode do not corrupt each other’s match rows (same test spirit as dual `plex_id`).  
2. User can add a matched title to their Jellyfin-side list when authenticated.  
3. Front end does not send Plex-only headers in Jellyfin mode (or server accepts both naming schemes — document the contract).  
4. `docker build` / CI succeeds with new dependencies.

**Next:** Backlog follow-ups live under **Phase 999.x** (planning-debt cleanup), starting with **Phase 999.1**.

---

## Requirement coverage checklist

- [x] CFG-01 — Phase 1  
- [x] CFG-02 — Phase 1  
- [x] CFG-03 — Phase 1  
- [x] ARC-01 — Phase 2  
- [x] ARC-02 — Phase 2  
- [x] ARC-03 — Phase 2  
- [x] JAUTH-01 — Phase 3  
- [x] JAUTH-02 — Phase 3  
- [x] JAUTH-03 — Phase 3  
- [x] JLIB-01 — Phase 4  
- [x] JLIB-02 — Phase 4  
- [x] JLIB-03 — Phase 4  
- [x] JLIB-04 — Phase 4  
- [x] JLIB-05 — Phase 4  
- [x] JUSR-01 — Phase 5  
- [x] JUSR-02 — Phase 5  
- [x] JUSR-03 — Phase 5  
- [x] JUSR-04 — Phase 5  

---
*Roadmap created: 2026-04-22*
