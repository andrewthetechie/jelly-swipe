# Requirements: Jelly Swipe

**Defined:** 2026-04-25
**Milestone:** v1.5 XSS Security Fix
**Core Value:** Users can run a swipe session backed by Jellyfin, with library browsing and deck behavior equivalent to the original Plex path.

## v1.5 Requirements

Requirements for this milestone are scoped to Issue #6 (`EPIC-03`) XSS vulnerability elimination.

### Server-Side Validation

- [ ] **SSV-01**: `/room/swipe` endpoint does not accept `title` or `thumb` parameters from the client request body.
- [ ] **SSV-02**: `/room/swipe` resolves movie metadata (title, thumb) server-side from `movie_id` via `JellyfinLibraryProvider.resolve_item_for_tmdb()`.
- [ ] **SSV-03**: Server handles case where `resolve_item_for_tmdb()` fails gracefully (does not insert malformed match data).

### Safe DOM Rendering

- [ ] **DOM-01**: Template `jellyswipe/templates/index.html` replaces `innerHTML` with `textContent` for all user-controlled text content (title, summary, actor names).
- [ ] **DOM-02**: Template uses safe DOM construction methods (`document.createElement()`, `setAttribute()`) for structured HTML containing user data.
- [ ] **DOM-03**: Template removes or refactors unsafe innerHTML usages for `m.title`, `m.summary`, `m.thumb`, `m.movie_id`, `actor.name`, `actor.character`.

### Content Security Policy

- [ ] **CSP-01**: Flask app sets `Content-Security-Policy` header on all responses via `@app.after_request` hook.
- [ ] **CSP-02**: CSP policy includes `default-src 'self'; script-src 'self'; object-src 'none'; img-src 'self' https://image.tmdb.org; frame-src https://www.youtube.com`.
- [ ] **CSP-03**: CSP policy does not include `'unsafe-inline'` or `'unsafe-eval'` directives.

### XSS Testing

- [ ] **XSS-01**: Test file `tests/test_routes_xss.py` exists with smoke test proving XSS is blocked.
- [ ] **XSS-02**: Test verifies that swipe with `title: "<script>...</script>"` renders as literal text, not executed.
- [ ] **XSS-03**: Test verifies that CSP header is present on all HTTP responses.
- [ ] **XSS-04**: Test verifies that server rejects client-supplied `title`/`thumb` parameters.

## v2 Requirements

Deferred to future milestones.

### Existing Deferred Candidates

- **ARC-02**: Formal Plex regression matrix closure in archived v1.0 verification artifacts.
- **OPS-01 / PRD-01**: Neutral DB column naming and multi-library selection.
- **ADV-01**: Coverage thresholds enforced in CI to prevent regression.
- **ADV-02**: Multiple coverage reports (HTML for local, XML for CI).
- **SEC-01–05**: Authorization hardening requirements (v1.4) — deferred pending v1.5 completion.

## Out of Scope

Explicitly excluded from v1.5.

| Feature | Reason |
|---------|--------|
| Nonce-based CSP | Higher complexity; basic CSP sufficient for v1.5, can upgrade in v1.5.1 |
| CSP violation reporting | Security monitoring enhancement, not required to close XSS vulnerability |
| Comprehensive escape helper utility | Direct textContent/DOM API usage is simpler for this scope |
| Trusted Types API | Browser support and complexity; defer to future security enhancements |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SSV-01 | Pending | |
| SSV-02 | Pending | |
| SSV-03 | Pending | |
| DOM-01 | Pending | |
| DOM-02 | Pending | |
| DOM-03 | Pending | |
| CSP-01 | Pending | |
| CSP-02 | Pending | |
| CSP-03 | Pending | |
| XSS-01 | Pending | |
| XSS-02 | Pending | |
| XSS-03 | Pending | |
| XSS-04 | Pending | |

**Coverage:**
- v1.5 requirements: 13 total
- Mapped to phases: 0 (roadmap not yet created)
- Unmapped: 13 ⚠️

---
*Requirements defined: 2026-04-25*
*Last updated: 2026-04-25 after v1.5 milestone initialization*
