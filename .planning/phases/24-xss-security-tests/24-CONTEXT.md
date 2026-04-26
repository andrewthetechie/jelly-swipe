# Phase 24: XSS Security Tests - Context

**Gathered:** 2026-04-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Add XSS security tests in `tests/test_routes_xss.py` that verify malicious input is properly handled across all routes accepting user-controlled data. Tests cover stored XSS (title/thumb stored via swipe, returned via matches), reflected XSS (error responses echoing input), path injection (proxy route), and `javascript:` URL rejection. Validates EPIC-03 security hardening.

Input vectors in scope:
- `POST /room/swipe` — `title`, `thumb`, `movie_id` fields (stored in DB, returned in match responses)
- `GET /matches` — Returns stored title/thumb from DB (stored XSS read path)
- `GET /proxy?path=` — External path parameter with allowlist regex
- `POST /auth/jellyfin-login` — `username`, `password` fields
- `POST /room/join` — `code` field

</domain>

<decisions>
## Implementation Decisions

### Test Structure
- **D-01:** Create `tests/test_routes_xss.py` — single file for all XSS security tests
- **D-02:** Use shared `client` fixture from conftest.py — no local fixture overrides needed
- **D-03:** Define XSS payload constants at module level for reuse across tests

### XSS Payloads to Test
- **D-04:** HTML tags: `<script>alert('xss')</script>`, `<img src=x onerror=alert(1)>`, `<svg onload=alert(1)>`
- **D-05:** `javascript:` URLs: `javascript:alert(1)`, `javascript:void(0)`
- **D-06:** Event handlers in attributes: `" onmouseover="alert(1)`, `' onload='alert(1)`
- **D-07:** Encoded variants: `&lt;script&gt;`, `%3Cscript%3E`, `&#x3C;script&#x3E;`

### Stored XSS Tests (via /room/swipe → /matches)
- **D-08:** Swipe with `<script>` in title — verify match response escapes it (Flask jsonify auto-escapes HTML entities in JSON)
- **D-09:** Swipe with `<script>` in thumb — verify match response escapes it
- **D-10:** Swipe with XSS title, then fetch `/matches` — verify stored payload is escaped in output
- **D-11:** Swipe with XSS title, verify SSE stream data is escaped (if testable without streaming complexity — defer to Phase 27 if complex)

### Proxy Route XSS Tests
- **D-12:** `javascript:` URL in path parameter — verify rejected with 403 (allowlist regex blocks it)
- **D-13:** `../` path traversal in path parameter — verify rejected with 403
- **D-14:** HTML/script content in path parameter — verify rejected with 403
- **D-15:** Verify only valid `jellyfin/{uuid}/Primary` patterns are accepted (existing regex)

### Input Validation Tests
- **D-16:** Login with XSS payload in username — verify response doesn't echo the payload unescaped
- **D-17:** Join room with XSS payload in code — verify response doesn't echo unescaped

### Assertion Patterns
- **D-18:** For JSON responses: verify `response.get_json()` values don't contain unescaped `<script>` or `javascript:` strings
- **D-19:** Flask's `jsonify()` encodes `<` as `\u003c` and `>` as `\u003e` in JSON — test for the escaped form, not the raw form
- **D-20:** For 403 responses: verify error response format, not content echoing

### the agent's Discretion
- Exact set of XSS payloads (can add more beyond minimum listed)
- Whether to parametrize payloads or write individual tests
- Whether to add a helper function for common XSS assertion patterns

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Test Infrastructure (Phase 22)
- `tests/conftest.py` — Shared fixtures: `app`, `client`, `FakeProvider`, `db_connection`
- `.planning/phases/22-test-infrastructure-setup/22-CONTEXT.md` — Fixture design decisions

### XSS-Related Routes
- `jellyswipe/__init__.py:317-363` — `/room/swipe` handler (stores title/thumb in DB)
- `jellyswipe/__init__.py:365-378` — `/matches` handler (returns stored title/thumb)
- `jellyswipe/__init__.py:511-524` — `/proxy` handler (path allowlist regex)
- `jellyswipe/__init__.py:269-280` — `/auth/jellyfin-login` handler (username input)

### Existing Test Patterns
- `tests/test_routes_auth.py` — Auth route test patterns from Phase 23 (client fixture usage, monkeypatch for failure cases)
- `tests/test_route_authorization.py` — Security testing patterns (parametrized spoof headers, session setup)

### Research
- `.planning/research/SUMMARY.md` — Testing pitfalls: avoid over-mocking, test behavior not implementation

### Flask XSS Documentation
- `https://flask.palletsprojects.com/en/stable/security/` — Flask auto-escaping in templates, jsonify behavior

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tests/conftest.py:client` fixture — Function-scoped Flask test client
- `tests/conftest.py:FakeProvider` — Mock provider with `fetch_library_image` returning `(b"", "image/jpeg")`
- `tests/test_routes_auth.py` — Pattern for organizing route tests by endpoint with clear section headers

### Established Patterns
- **Flask jsonify escaping**: `<` becomes `\u003c`, `>` becomes `\u003e`, `&` becomes `\u0026` in JSON responses — test for escaped forms
- **Proxy allowlist regex**: `^jellyfin/(?:[0-9a-fA-F]{32}|[0-9a-fA-F-]{36})/Primary$` — only valid image paths accepted
- **Session setup**: `client.session_transaction()` to set active_room and user_id before swipe tests

### Integration Points
- **Swipe → Match flow**: `/room/swipe` stores title/thumb → `/matches` returns them — stored XSS read path
- **Proxy path validation**: `request.args.get('path')` validated against regex → 403 on mismatch
- **Error responses**: `jsonify({"error": str(e)})` — `str(e)` could contain user input in some paths

### Key Security Note
Flask's `jsonify()` auto-escapes HTML entities in JSON strings. The primary XSS risk is if user input reaches non-JSON output (templates, SSE stream, proxy responses). Tests should verify jsonify escaping works AND that non-JSON paths (proxy, SSE) are also protected.

</code_context>

<specifics>
## Specific Ideas

No specific requirements — standard XSS security testing following OWASP patterns.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---
*Phase: 24-xss-security-tests*
*Context gathered: 2026-04-26*
