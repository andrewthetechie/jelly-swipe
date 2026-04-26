# Context — Phase 21: Content Security Policy (CSP) Header

**Milestone:** v1.5 XSS Security Fix
**Phase:** 21 - CSP Header
**Date:** 2026-04-26

---

## Objective

Add a strict Content Security Policy (CSP) header to all HTTP responses from the Flask application to block inline scripts and restrict external resource loading to trusted domains, providing defense-in-depth against XSS attacks.

---

## Dependencies

**Phase 20 Complete:** Safe DOM rendering ensures all user-controlled content is rendered using safe DOM APIs. Phase 21 adds CSP as a third layer of defense, blocking inline scripts even if bugs slip through server validation and client-side rendering.

---

## Scope

**File to Modify:**
- `jellyswipe/__init__.py` - Add `@app.after_request` hook to set CSP header on all responses

**CSP Policy to Implement:**
```
Content-Security-Policy: default-src 'self'; script-src 'self'; object-src 'none'; img-src 'self' https://image.tmdb.org; frame-src https://www.youtube.com
```

**Policy Rationale:**
- `default-src 'self'`: Restrict all resources to same origin by default
- `script-src 'self'`: Allow only scripts from same origin (blocks inline scripts and external scripts)
- `object-src 'none'`: Block all plugins (Flash, Java, etc.) as they're obsolete security risks
- `img-src 'self' https://image.tmdb.org`: Allow images from same origin and TMDB (for movie posters)
- `frame-src https://www.youtube.com`: Allow YouTube embeds for trailers (trusted domain)

**Policy Exclusions (Critical for Security):**
- NO `'unsafe-inline'`: Blocks inline event handlers and `<script>` tags (critical for XSS defense)
- NO `'unsafe-eval'`: Blocks `eval()` and similar functions (prevents code injection)

---

## Technical Context

### Current Implementation

The Flask application in `jellyswipe/__init__.py` currently has no CSP header on responses. All responses are vulnerable to XSS if inline scripts are injected.

### Target Implementation

Add an `@app.after_request` hook that sets the CSP header on all HTTP responses:

```python
@app.after_request
def add_csp_header(response):
    csp_policy = (
        "default-src 'self'; "
        "script-src 'self'; "
        "object-src 'none'; "
        "img-src 'self' https://image.tmdb.org; "
        "frame-src https://www.youtube.com"
    )
    response.headers['Content-Security-Policy'] = csp_policy
    return response
```

### Placement in Code

The `@app.after_request` hook should be defined after the Flask app is instantiated (line 42) and before route definitions. A good location is after the `app.secret_key` assignment (line 46).

---

## Decisions

### D-01: CSP Policy String
Use the exact CSP policy specified in CSP-02: `default-src 'self'; script-src 'self'; object-src 'none'; img-src 'self' https://image.tmdb.org; frame-src https://www.youtube.com`

**Rationale:** This policy is strictly defined in requirements and success criteria. No deviation allowed.

### D-02: Implementation Pattern
Use Flask's `@app.after_request` decorator to set the CSP header on all responses.

**Rationale:** This is the standard Flask pattern for adding headers to all responses. It's simple, maintainable, and applies to all routes (including static files, templates, and API endpoints).

### D-03: Hook Placement
Place the `@app.after_request` hook after the Flask app instantiation and secret key assignment, before route definitions.

**Rationale:** This follows Flask conventions where middleware and hooks are defined near app configuration, before route handlers. The hook should be early in the file to ensure it applies to all routes.

### D-04: Policy Format
Store the CSP policy as a multi-line string for readability, then strip whitespace before setting the header.

**Rationale:** Multi-line strings are more readable and maintainable. Flattening at runtime ensures the header is properly formatted (no extra whitespace).

### D-05: No CSP Reporting
Do not implement CSP violation reporting (`report-uri` or `report-to`) in this phase.

**Rationale:** CSP reporting is explicitly out of scope for v1.5 (per REQUIREMENTS.md). It's a security monitoring enhancement that can be added in a future phase if needed.

---

## the agent's Discretion

The agent may:
- Choose between single-line or multi-line string format for the CSP policy (as long as the final header value is identical)
- Add comments explaining the CSP policy and its purpose
- Use string concatenation or f-strings for building the policy (as long as the final value is correct)
- Add the hook anywhere after app instantiation (placement is not critical for functionality)

---

## Success Criteria

From ROADMAP.md:

1. All HTTP responses from the Flask app include a Content-Security-Policy header
2. CSP policy allows scripts only from 'self' (no 'unsafe-inline' or 'unsafe-eval')
3. CSP policy restricts image sources to 'self' and https://image.tmdb.org
4. CSP policy restricts frame sources to https://www.youtube.com (for trailers)

---

## Security Context

This is the third and final layer of defense in the v1.5 XSS security fix:

1. **Layer 1 (Phase 19 - Complete):** Server-side validation ensures all metadata originates from trusted Jellyfin source
2. **Layer 2 (Phase 20 - Complete):** Safe DOM rendering prevents script injection in the frontend
3. **Layer 3 (Phase 21 - This Phase):** CSP header blocks inline scripts even if bugs slip through layers 1 and 2

The CSP policy is critical because:
- It provides defense-in-depth: even if validation or rendering has bugs, CSP blocks execution
- It enforces a secure default: all resources must come from trusted origins
- It blocks common XSS vectors: inline scripts, eval(), and untrusted external resources

---

## Verification

After implementation, verify:

1. **Header Presence:** All HTTP responses include `Content-Security-Policy` header
   ```bash
   curl -I http://localhost:5005/ | grep -i "content-security-policy"
   ```

2. **Policy Correctness:** The CSP header value matches the required policy exactly
   - Contains `default-src 'self'`
   - Contains `script-src 'self'` (no `unsafe-inline` or `unsafe-eval`)
   - Contains `object-src 'none'`
   - Contains `img-src 'self' https://image.tmdb.org`
   - Contains `frame-src https://www.youtube.com`

3. **No Unsafe Directives:** The policy does NOT contain:
   - `unsafe-inline` (in any directive)
   - `unsafe-eval` (in any directive)

4. **Functionality Check:** Verify the application still works correctly
   - Static assets (CSS, JS, images) load properly
   - TMDB images (movie posters) display correctly
   - YouTube trailers play in iframes
   - No console CSP errors in browser developer tools

---

## Risk Mitigation

### Risk: CSP Breaks Legitimate Functionality
**Mitigation:** The CSP policy is carefully designed to allow all required resources:
- Same-origin scripts, styles, images, fonts: `default-src 'self'`
- TMDB images: `img-src 'self' https://image.tmdb.org`
- YouTube trailers: `frame-src https://www.youtube.com`

### Risk: Inline Scripts in Templates
**Mitigation:** Phase 20 (Safe DOM Rendering) eliminated all inline scripts. The templates use only external scripts or safe DOM construction.

### Risk: Dynamic Script Loading
**Mitigation:** The application does not use dynamic script loading. All JavaScript is served from static files or inline (but Phase 20 eliminated unsafe inline scripts).

---

## Out of Scope

Explicitly excluded from Phase 21 (per REQUIREMENTS.md):

- Nonce-based CSP (higher complexity, not needed for v1.5)
- CSP violation reporting (`report-uri`, `report-to`)
- CSP for specific routes (policy applies to all responses)
- CSP level 3 features (e.g., `strict-dynamic`, `report-sample`)

---

*Context created: 2026-04-26*
