# Feature Landscape: XSS Security Fixes for Jelly Swipe

**Domain:** Flask Web Application Security
**Researched:** 2026-04-25
**Overall confidence:** HIGH

## Executive Summary

Jelly Swipe v1.5 requires XSS security fixes to address a stored XSS vulnerability where client-supplied `title` and `thumb` parameters are rendered unsafely using `innerHTML` in the template. Research indicates three primary defensive layers are needed: **Content Security Policy (CSP) headers**, **safe HTML escaping patterns** (textContent/DOM construction), and **server-side input validation**. The vulnerability manifests in `jellyswipe/templates/index.html` at lines 644-661 and 565-585 where user-controlled data is injected directly into the DOM without sanitization.

**Recommended approach:** Implement CSP as a defense-in-depth layer while fixing the root cause by replacing `innerHTML` with safe DOM APIs and removing client-controlled title/thumb from the API contract.

## Table Stakes

Features users expect in a secure web application. Missing these = product feels insecure and vulnerable.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Content Security Policy (CSP) Header** | Security-conscious users expect CSP headers on all modern web apps; absence indicates poor security posture | LOW | Set via Flask `@app.after_request` hook; recommended policy: `default-src 'self'; script-src 'self'; object-src 'none'; img-src 'self' https://image.tmdb.org; frame-src https://www.youtube.com` |
| **HTML Entity Escaping for User Data** | Basic XSS prevention requirement; without it, any user input can execute JavaScript | LOW | Replace `innerHTML` with `textContent` for text content; use `document.createElement()` for structured HTML; or implement strict escape helper |
| **Server-Side Input Validation** | Never trust client data; validate and sanitize all inputs before storage or processing | MEDIUM | Reject title/thumb from client; resolve from `movie_id` via `JellyfinLibraryProvider.resolve_item_for_tmdb()`; validate JSON structure |
| **XSS Smoke Tests** | Automated verification that XSS is blocked; required for security regression testing | LOW | Add test file `tests/test_routes_xss.py` with tests proving script tags render as literal text, not executed |

## Differentiators

Features that set the security posture apart. Not expected, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Nonce-Based Strict CSP** | Provides strongest XSS protection by only allowing scripts with server-generated nonces; exceeds standard CSP implementations | HIGH | Generate cryptographically random nonce per response (128+ bits, Base64); inject into CSP header and all `<script nonce="...">` tags; requires template refactoring |
| **Comprehensive Escape Helper** | Reusable utility for safe HTML rendering; reduces developer error surface area | MEDIUM | Implement JavaScript escape function using textContent or manual HTML entity encoding (`&` → `&amp;`, `<` → `&lt;`, etc.); document safe sinks vs unsafe sinks |
| **CSP Violation Reporting** | Detects attempted XSS attacks in production; provides security monitoring | MEDIUM | Add `Content-Security-Policy-Report-Only` header during development; integrate reporting endpoint for production monitoring |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **`'unsafe-inline'` in CSP** | Defeats the purpose of CSP by allowing inline scripts; common anti-pattern that creates false sense of security | Use nonce-based CSP or refactor to external scripts |
| **`eval()` or `setTimeout(string)`** | Dangerous JavaScript patterns that execute arbitrary strings; blocked by strict CSP | Use `JSON.parse()` for JSON, pass functions to `setTimeout` |
| **Client-Side Title/Thumb Parameters** | Original vulnerability source; allows attacker to inject malicious content | Resolve all metadata server-side from `movie_id` using `JellyfinLibraryProvider.resolve_item_for_tmdb()` |
| **`dangerouslySetInnerHTML` Pattern** | Explicitly marks content as unsafe; exactly what we're trying to prevent | Use textContent, createElement, or DOMPurify if HTML is absolutely required |

## Feature Dependencies

```
[Server-Side Validation]
    └──requires──> [Remove Client Title/Thumb from API]
                       └──requires──> [Refactor /room/swipe Endpoint]

[Safe DOM Rendering]
    └──requires──> [Replace innerHTML with textContent]
                       └──requires──> [Template Refactoring]

[CSP Header]
    └──enhances──> [All Other Features]

[XSS Smoke Tests]
    └──requires──> [All Security Fixes Implemented]
```

### Dependency Notes

- **Server-Side Validation requires Remove Client Title/Thumb from API:** The `/room/swipe` endpoint currently accepts `title` and `thumb` from the client (line 244 of `jellyswipe/__init__.py`). These must be removed and resolved server-side via `JellyfinLibraryProvider.resolve_item_for_tmdb(movie_id)` to prevent malicious data from entering the system.

- **Safe DOM Rendering requires Replace innerHTML with textContent:** Lines 644-661 and 565-585 of `index.html` use `innerHTML` with template literals containing user data (`${m.title}`, `${m.thumb}`). These must be refactored to use `textContent` or DOM construction methods to prevent script execution.

- **CSP Header enhances All Other Features:** CSP provides defense-in-depth but is not a substitute for proper escaping and validation. It should be implemented alongside, not instead of, the other security features.

- **XSS Smoke Tests requires All Security Fixes Implemented:** Tests should verify the complete fix chain: server rejects bad input, client renders safely, CSP blocks any remaining injection attempts.

## MVP Definition

### Launch With (v1.5)

Minimum viable security fixes — what's needed to close the XSS vulnerability.

- [x] **Server-Side Input Validation** — Remove title/thumb from client API; resolve from movie_id via JellyfinLibraryProvider
- [x] **Safe DOM Rendering** — Replace all `innerHTML` with `textContent` or DOM construction for user-controlled data
- [x] **Basic CSP Header** — Set `Content-Security-Policy: default-src 'self'; script-src 'self'; object-src 'none'; img-src 'self' https://image.tmdb.org; frame-src https://www.youtube.com`
- [x] **XSS Smoke Tests** — Add `tests/test_routes_xss.py` proving XSS is blocked

### Add After Validation (v1.5.1)

Features to add once core security is verified.

- [ ] **Nonce-Based Strict CSP** — Upgrade to nonce-based CSP for stronger protection
- [ ] **CSP Violation Reporting** — Add reporting endpoint for security monitoring
- [ ] **Comprehensive Escape Helper** — Reusable utility function for safe HTML rendering

### Future Consideration (v2+)

Features to defer until security posture is stable.

- [ ] **Trusted Types API** — Browser-native API for preventing DOM-based XSS (requires modern browser support)
- [ ] **HTML Sanitization (DOMPurify)** — If user-generated HTML is ever needed, integrate DOMPurify library
- [ ] **Subresource Integrity (SRI)** — Add integrity hashes for external scripts

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Server-Side Input Validation | CRITICAL (closes vulnerability) | MEDIUM | P1 |
| Safe DOM Rendering | CRITICAL (closes vulnerability) | MEDIUM | P1 |
| Basic CSP Header | HIGH (defense-in-depth) | LOW | P1 |
| XSS Smoke Tests | HIGH (regression prevention) | LOW | P1 |
| Nonce-Based Strict CSP | MEDIUM (enhanced protection) | HIGH | P2 |
| CSP Violation Reporting | MEDIUM (security monitoring) | MEDIUM | P2 |
| Comprehensive Escape Helper | LOW (developer convenience) | MEDIUM | P3 |
| Trusted Types API | LOW (future-proofing) | HIGH | P3 |

**Priority key:**
- P1: Must have for v1.5 (closes XSS vulnerability)
- P2: Should have, add in v1.5.1 (enhanced protection)
- P3: Nice to have, future consideration (v2+)

## Competitor Feature Analysis

| Feature | Standard Flask Apps | OWASP Recommendations | Our Approach |
|---------|---------------------|----------------------|--------------|
| CSP Header | Often missing or too permissive | Strict nonce-based CSP recommended | Start with basic CSP, upgrade to nonce-based in v1.5.1 |
| HTML Escaping | Depends on template engine (Jinja2 autoescapes by default) | Output encoding for all contexts | Replace innerHTML with textContent (client-side) + Jinja2 autoescaping (server-side) |
| Input Validation | Varies; often client-side only | Validate on server, whitelist approach | Server-side resolution from trusted source (Jellyfin/TMDB) |
| XSS Testing | Rarely comprehensive | Unit tests + security testing | Add dedicated XSS smoke test suite |

## Complexity Notes

### Server-Side Validation (MEDIUM)
- Requires refactoring `/room/swipe` endpoint to ignore client `title`/`thumb`
- Must handle case where `JellyfinLibraryProvider.resolve_item_for_tmdb()` fails (graceful degradation)
- Existing code already has `resolve_item_for_tmdb()` method for TMDB integration (lines 117-130)
- **Dependency:** Requires understanding of movie_id to Jellyfin item mapping

### Safe DOM Rendering (MEDIUM)
- Template has 11+ `innerHTML` usages (found via grep)
- Must identify which contain user data vs static HTML
- Static HTML can remain with `innerHTML` if no user data (e.g., trailer iframe at line 709)
- **Pattern:** Replace `c.innerHTML = \`${m.title}\`` with `c.textContent = m.title` or use DOM creation API
- **Safe sinks:** `textContent`, `insertAdjacentText`, `setAttribute`, `value`, `className` (per OWASP)
- **Unsafe sinks:** `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write` (must avoid)

### Basic CSP Header (LOW)
- Single `@app.after_request` hook in `jellyswipe/__init__.py`
- Policy format validated by MDN and web.dev sources
- Must allow `https://image.tmdb.org` for images (TMDB integration requirement)
- Must allow `https://www.youtube.com` for trailer embeds (existing feature)
- **Implementation:**
```python
@app.after_request
def add_security_headers(response):
    csp = "default-src 'self'; script-src 'self'; object-src 'none'; img-src 'self' https://image.tmdb.org; frame-src https://www.youtube.com"
    response.headers['Content-Security-Policy'] = csp
    return response
```

### XSS Smoke Tests (LOW)
- Create `tests/test_routes_xss.py`
- Test 1: Send malicious payload in swipe endpoint, verify it's not rendered as executable script
- Test 2: Verify CSP header is present on all responses
- Test 3: Verify server rejects title/thumb from client
- **Framework:** Use existing pytest setup with mock responses (follows pattern of `test_db.py`)

### Nonce-Based Strict CSP (HIGH)
- Requires generating random nonce per response: `secrets.token_urlsafe(16)` or `os.urandom(16).base64()`
- Must inject nonce into all `<script>` tags via template variable
- Template currently has inline scripts; must be refactored to accept nonce parameter
- **Implementation complexity:** HIGH because all scripts need nonce attribute, including any dynamically created scripts
- **Browser support:** Chrome 52+, Edge 79+, Firefox 52+, Safari 15.4+ (per web.dev sources)

## Sources

**Context7 Documentation (HIGH confidence):**
- Flask web security: CSP header configuration, after_request pattern
- Jinja2 autoescaping: Automatic HTML escaping enabled by default
- Flask input handling: `request.json`, `get_json()`, HTML escaping with `markupsafe.escape`

**MDN Web Docs (HIGH confidence):**
- Content Security Policy guide: https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CSP
- CSP header reference: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy

**web.dev Articles (HIGH confidence):**
- Strict CSP guide: https://web.dev/articles/strict-csp
- Nonce-based CSP implementation patterns and browser support

**OWASP Cheat Sheet Series (HIGH confidence):**
- XSS Prevention Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html
- Safe sinks (textContent, insertAdjacentText) vs unsafe sinks (innerHTML)
- Output encoding rules for HTML, JavaScript, CSS, URL contexts

**Code Analysis (HIGH confidence):**
- Vulnerable locations: `jellyswipe/templates/index.html` lines 644-661, 565-585
- Server endpoint: `jellyswipe/__init__.py` line 244 (`/room/swipe` accepts title/thumb from client)
- Existing method: `JellyfinLibraryProvider.resolve_item_for_tmdb()` can be leveraged for server-side resolution

**Confidence Level Rationale:**
- **HIGH confidence** for all sources: All information from official documentation (Flask, MDN, OWASP) or direct code analysis
- **Verified through multiple sources:** CSP patterns cross-referenced between Context7, MDN, and web.dev
- **No LOW confidence findings:** All claims backed by authoritative sources or direct code inspection

---
*Feature research for: XSS Security Fixes in Jelly Swipe Flask App*
*Researched: 2026-04-25*
