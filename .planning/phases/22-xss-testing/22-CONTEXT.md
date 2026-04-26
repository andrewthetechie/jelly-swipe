# Phase 22: XSS Testing

**Created:** 2026-04-26
**Status:** Planning

---

## Phase Goal

Comprehensive tests verify that XSS is blocked on all three security layers and the vulnerability is closed.

---

## Depends On

- Phase 19: Server-Side Validation (complete)
- Phase 20: Safe DOM Rendering (complete)
- Phase 21: CSP Header (complete)

All three security defense layers must be in place before testing.

---

## Requirements

This phase addresses the following requirements from REQUIREMENTS.md:

- **XSS-01**: Test file `tests/test_routes_xss.py` exists with smoke test proving XSS is blocked
- **XSS-02**: Test verifies that swipe with `title: "<script>...</script>"` renders as literal text, not executed
- **XSS-03**: Test verifies that CSP header is present on all HTTP responses
- **XSS-04**: Test verifies that server rejects client-supplied `title`/`thumb` parameters

---

## Success Criteria

From ROADMAP.md, the following must be TRUE when this phase is complete:

1. Test file `tests/test_routes_xss.py` exists and passes all XSS smoke tests
2. Test proves that a swipe with malicious script in title renders as literal text (not executed)
3. Test verifies that CSP header is present on all HTTP responses with correct directives
4. Test verifies that server rejects client-supplied title/thumb parameters with appropriate error

---

## Context from Prior Phases

### Phase 19: Server-Side Validation (Complete)

**Implementation Summary:**
- `/room/swipe` endpoint now ignores any `title` or `thumb` parameters sent by client
- Server resolves title and thumb from Jellyfin using `JellyfinLibraryProvider.resolve_item_for_tmdb(movie_id)`
- Security logging in place: when client sends title/thumb, a warning is logged
- Graceful degradation: if metadata resolution fails, swipe completes but match creation is skipped

**Key File Modified:**
- `jellyswipe/__init__.py` - Modified `/room/swipe` endpoint (lines 253-312)
  - Security logging at lines 266-271
  - Server-side metadata resolution at lines 273-284
  - Match creation conditional on successful resolution at line 292

**Testing Requirements (XSS-04):**
- Verify that when client sends title/thumb parameters, they are ignored
- Verify security warning is logged
- Verify server resolves from Jellyfin instead

### Phase 20: Safe DOM Rendering (Complete)

**Implementation Summary:**
- Replaced all innerHTML usage with textContent for user-controlled text
- Replaced innerHTML-based DOM construction with createElement() and appendChild()
- Applied to both templates: `jellyswipe/templates/index.html` and `data/index.html`

**Functions Refactored:**
- `openMatches()` - Match card rendering
- `createCard()` - Movie card rendering
- Cast loading - Actor names using textContent
- `watchTrailer()` - iframe using property assignment

**Testing Requirements (XSS-02):**
- Verify that malicious script in title renders as literal text
- This is difficult to test programmatically in backend tests
- Focus on verifying the code uses textContent instead of innerHTML
- Manual verification may be needed for actual browser rendering

### Phase 21: CSP Header (Complete)

**Implementation Summary:**
- Added `@app.after_request` hook to set Content Security Policy header
- CSP policy: `default-src 'self'; script-src 'self'; object-src 'none'; img-src 'self' https://image.tmdb.org; frame-src https://www.youtube.com`

**Key File Modified:**
- `jellyswipe/__init__.py` - Added CSP hook at lines 48-59

**CSP Directives:**
- `default-src 'self'` - Default to same-origin only
- `script-src 'self'` - No `unsafe-inline`, no `unsafe-eval`
- `object-src 'none'` - Block all plugins
- `img-src 'self' https://image.tmdb.org` - Allow TMDB images
- `frame-src https://www.youtube.com` - Allow YouTube trailers

**Testing Requirements (XSS-03):**
- Verify CSP header is present on all HTTP responses
- Verify CSP policy has correct directives
- Verify no `unsafe-inline` or `unsafe-eval`

---

## Testing Approach

### Test Framework

- **Framework:** pytest (already in use, see tests/conftest.py)
- **Test Client:** Flask `app.test_client()` for HTTP endpoint testing
- **Fixtures:** Use existing fixtures from conftest.py (db_connection, db_path, etc.)

### Test File Structure

Create `tests/test_routes_xss.py` with the following test functions:

1. **Test Layer 1 (Server-Side Validation):**
   - `test_swipe_ignores_client_supplied_title_thumb()` - Verify client title/thumb are ignored
   - `test_swipe_logs_security_warning_for_client_params()` - Verify security logging

2. **Test Layer 2 (Safe DOM Rendering):**
   - `test_dom_rendering_uses_textcontent()` - Verify textContent usage in templates (code inspection test)
   - Note: Actual rendering verification may require manual browser testing or headless browser automation (out of scope for v1.5)

3. **Test Layer 3 (CSP Header):**
   - `test_csp_header_present_on_responses()` - Verify CSP header on all responses
   - `test_csp_policy_directives_correct()` - Verify CSP policy has correct values

4. **End-to-End XSS Block Verification:**
   - `test_xss_blocked_three_layer_defense()` - Comprehensive test proving XSS is blocked

### Mocking Strategy

- **Mock JellyfinLibraryProvider:** Since we're testing security, don't call real Jellyfin API
- **Mock session:** Set up fake session with room code and user ID
- **Mock database:** Use db_connection fixture for fresh database per test

---

## File to Create

- `tests/test_routes_xss.py` - New test file with XSS smoke tests

---

## Discovery Level

**Level 0 (Skip)** - Pure internal work, existing patterns only:
- Test framework (pytest) already in use
- Test fixtures already established in conftest.py
- Flask test client pattern standard
- No new external dependencies

---

## Security Context

This is the validation phase for the three-layer XSS defense:

1. **Layer 1: Server-side validation** (Phase 19)
   - Client cannot inject malicious content via title/thumb parameters
   - All movie metadata resolved server-side from trusted Jellyfin source

2. **Layer 2: Safe DOM rendering** (Phase 20)
   - All user-controlled content rendered using safe DOM APIs
   - No innerHTML with user data

3. **Layer 3: CSP header** (Phase 21)
   - Browser-enforced policy blocks inline scripts
   - Restricts external resources to trusted domains

**Testing must verify each layer independently and together.**

---

## Known Constraints

### From TESTING.md (Codebase Conventions)

- Use Flask `app.test_client()` against `app` from `jellyswipe/__init__.py`
- Mock `JellyfinLibraryProvider` for tests (don't call real API)
- Use temporary database via db_connection fixture
- Prefer pytest with framework-agnostic imports

### From CONVENTIONS.md (Codebase Conventions)

- Test files: `tests/test_<feature>.py`
- Use snake_case for function names
- Error handling: wrap external IO in try/except

---

## Open Questions / Gray Areas

None identified - this is a straightforward testing phase with clear success criteria and established patterns.

---

*Context created: 2026-04-26*
