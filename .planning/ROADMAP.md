# Roadmap — Jelly Swipe

**Milestone:** v1.5 XSS Security Fix
**Granularity:** Standard (5-8 phases)
**Current Phase:** Not started
**Last Updated:** 2026-04-25

---

## Overview

This roadmap eliminates the stored XSS vulnerability (Issue #6) where client-supplied title/thumb parameters are rendered unsafely, allowing JavaScript injection. The fix operates on three layers: server-side validation, safe DOM rendering, and Content Security Policy enforcement, with comprehensive testing to verify the vulnerability is closed.

**Phases:** 4
**Requirements:** 13
**Starting Phase:** 19 (continuing from v1.4)

---

## Phases

- [ ] **Phase 19: Server-Side Validation** - Remove client-supplied title/thumb parameters and resolve metadata server-side from movie_id
- [ ] **Phase 20: Safe DOM Rendering** - Replace innerHTML with textContent/DOM construction for all user-controlled content
- [ ] **Phase 21: CSP Header** - Add strict Content-Security-Policy header via Flask after_request hook
- [ ] **Phase 22: XSS Testing** - Add smoke tests proving XSS is blocked and CSP is enforced

---

## Phase Details

### Phase 19: Server-Side Validation

**Goal:** Client cannot inject malicious content via title/thumb parameters; all movie metadata is resolved server-side from trusted Jellyfin source.

**Depends on:** Nothing (first phase of v1.5)

**Requirements:** SSV-01, SSV-02, SSV-03

**Success Criteria** (what must be TRUE):
1. `/room/swipe` endpoint ignores any `title` or `thumb` parameters sent by client
2. When a user swipes on a movie, the server resolves title and thumb from Jellyfin using only the movie_id
3. If Jellyfin metadata resolution fails, the server returns an error instead of storing incomplete/invalid data
4. Match records in database contain only server-resolved title and thumb values (no client-provided data)

**Plans:** TBD

---

### Phase 20: Safe DOM Rendering

**Goal:** All user-controlled content in the frontend is rendered using safe DOM APIs that prevent script injection.

**Depends on:** Phase 19 (server no longer accepts client-supplied metadata)

**Requirements:** DOM-01, DOM-02, DOM-03

**Success Criteria** (what must be TRUE):
1. Movie titles, summaries, actor names, and character names are rendered using textContent (not innerHTML)
2. Image sources and movie IDs are set using setAttribute() or DOM property assignment (not innerHTML)
3. All innerHTML usages for user-controlled content have been removed or refactored to safe DOM construction
4. Malicious script tags in movie data render as literal text in the browser (not executed)

**Plans:** TBD

**UI hint**: yes

---

### Phase 21: CSP Header

**Goal:** Content Security Policy header blocks inline scripts and restricts external resource loading to trusted domains.

**Depends on:** Phase 20 (safe DOM rendering in place as defense-in-depth)

**Requirements:** CSP-01, CSP-02, CSP-03

**Success Criteria** (what must be TRUE):
1. All HTTP responses from the Flask app include a Content-Security-Policy header
2. CSP policy allows scripts only from 'self' (no 'unsafe-inline' or 'unsafe-eval')
3. CSP policy restricts image sources to 'self' and https://image.tmdb.org
4. CSP policy restricts frame sources to https://www.youtube.com (for trailers)

**Plans:** TBD

---

### Phase 22: XSS Testing

**Goal:** Comprehensive tests verify that XSS is blocked on all three security layers and the vulnerability is closed.

**Depends on:** Phase 21 (all security defenses in place)

**Requirements:** XSS-01, XSS-02, XSS-03, XSS-04

**Success Criteria** (what must be TRUE):
1. Test file `tests/test_routes_xss.py` exists and passes all XSS smoke tests
2. Test proves that a swipe with malicious script in title renders as literal text (not executed)
3. Test verifies that CSP header is present on all HTTP responses with correct directives
4. Test verifies that server rejects client-supplied title/thumb parameters with appropriate error

**Plans:** TBD

---

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 19. Server-Side Validation | 0/0 | Not started | - |
| 20. Safe DOM Rendering | 0/0 | Not started | - |
| 21. CSP Header | 0/0 | Not started | - |
| 22. XSS Testing | 0/0 | Not started | - |

---

## Milestone Context

**Previous Milestone:** v1.4 (Authorization Hardening) — Phases 1-18 completed
**Current Milestone:** v1.5 (XSS Security Fix) — Phases 19-22 planned
**Issue Reference:** https://github.com/andrewthetechie/jelly-swipe/issues/6

**Vulnerability Description:**
The `/room/swipe` endpoint currently accepts `title` and `thumb` parameters from the client request body and stores them directly in the database. When matches are rendered, this unsanitized content is inserted into the DOM using `innerHTML`, allowing attackers to inject JavaScript that executes when other users view the match.

**Fix Strategy:**
Three-layer defense:
1. **Server-side:** Never trust client data; resolve all metadata server-side from trusted Jellyfin API
2. **Client-side:** Use safe DOM APIs (textContent, createElement, setAttribute) instead of innerHTML
3. **Headers:** Enforce strict CSP to block inline scripts even if bugs slip through

---

*Roadmap created: 2026-04-25*
*Last updated: 2026-04-25*
