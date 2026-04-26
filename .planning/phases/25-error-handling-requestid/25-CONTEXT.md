# Phase 25: Error Handling & RequestId - Context

**Gathered:** 2026-04-27
**Status:** Ready for planning
**Source:** ROADMAP Phase 25 specification + M04-REQUIREMENTS.md

<domain>
## Phase Boundary

Implement structured error handling with RequestId tracing across all Flask routes. Clients receive generic error messages + RequestId; operators get full exception details + RequestId in server logs. Remove all `str(e)` leakage in client responses.

**In scope:**
- RequestId generation per incoming HTTP request (format: `req_<timestamp>_<random>`)
- Flask `before_request` hook to inject RequestId into request context
- Structured error logging with full exception details + RequestId
- Sanitized error responses: generic message + RequestId to clients
- Consistent error response format across all routes
- Unit tests for RequestId propagation and error sanitization

**Out of scope:**
- Rate limiting (Phase 26)
- SSRF protection (Phase 27)
- HTTP client helper changes (Phase 23, complete)
- TMDB auth changes (Phase 24, complete)
</domain>

<decisions>
## Implementation Decisions

### D-01: RequestId Format
- Format: `req_<unix_timestamp>_<8-char-hex>` (e.g., `req_1714123456_abc12340`)
- Generated using `time.time()` for timestamp + `secrets.token_hex(4)` for random component
- Stored in Flask's `request.environ` for server-side access and included in all log entries

### D-02: RequestId Injection Mechanism
- Use Flask `@app.before_request` hook to generate and attach RequestId
- Store as `request.request_id` via Werkzeug's `request.environ` dict
- Add RequestId to response headers as `X-Request-Id` for client-side debugging

### D-03: Error Response Format
- 4xx responses: `{"error": "<specific client-safe message>", "request_id": "req_..."}`
- 5xx responses: `{"error": "Internal server error", "request_id": "req_..."}`
- All error responses include appropriate HTTP status code and `Content-Type: application/json`

### D-04: Structured Error Logging
- All exception handlers log: timestamp, request_id, route, method, exception_type, exception_message, stack_trace
- Use `app.logger.error()` for 5xx exceptions, `app.logger.warning()` for 4xx errors
- Log entries use `extra={}` dict for structured fields (consistent with http_client.py pattern)

### D-05: No New Dependencies
- Zero new pip dependencies for error handling
- Use stdlib: `time`, `secrets`, `traceback`, `logging`
- RequestId generation and error formatting implemented inline

### D-06: Generic Error Helper Function
- Create `make_error_response()` helper that returns properly formatted error responses
- Accept: message, status_code, request_id, include_stack_trace (bool, server-side only)
- Replace all `jsonify({'error': str(e)})` patterns with this helper

### the agent's Discretion
- Exact variable naming for helper functions
- Whether to create a separate error handling module or add to `__init__.py`
- Test file organization and naming conventions
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Core Application
- `jellyswipe/__init__.py` — Main Flask app with all route handlers (contains all `str(e)` patterns to fix)
- `jellyswipe/http_client.py` — Existing HTTP client helper (established logging pattern to follow)

### Test Infrastructure
- `tests/conftest.py` — Test fixtures including Flask test client setup
- `tests/test_http_client.py` — Example test patterns for structured logging assertions

### Milestone Context
- `.planning/milestones/M04-REQUIREMENTS.md` — Full requirements (ERR-01 through ERR-04, TEST-02)
- `.planning/milestones/M04-CONTEXT.md` — Milestone problem analysis (Problem 3: Raw Exception Message Leak)

### Codebase Conventions
- `.planning/codebase/CONVENTIONS.md` — Error handling patterns and logging conventions
- `.planning/codebase/TESTING.md` — Test framework patterns
</canonical_refs>

<specifics>
## Specific Requirements

### ERR-01: RequestId Generation
- RequestId generation function exists
- RequestId stored in Flask request context (`request.request_id`)
- RequestId included in all server-side log entries
- RequestId format: `req_<timestamp>_<random>`

### ERR-02: Structured Error Logging
- All exception handlers log full details with RequestId
- Log includes: timestamp, request_id, route, method, exception_type, exception_message, stack_trace
- Log level is ERROR for 5xx, WARNING for 4xx

### ERR-03: No str(e) in Client Responses
- No `return jsonify({'error': str(e)})` patterns remain
- No `str(e)` in any JSON response body
- All error responses use generic messages + RequestId

### ERR-04: Error Response Consistency
- All 4xx responses: `{"error": "<specific message>", "request_id": "..."}`
- All 5xx responses: `{"error": "Internal server error", "request_id": "..."}`
- All error responses include appropriate HTTP status code and RequestId

### TEST-02: Error Handling Tests
- Test RequestId generation and propagation
- Test error logging with RequestId
- Test client error responses contain RequestId
- Test no exception details in client responses
- Test all error paths in main routes
</specifics>

<deferred>
## Deferred Ideas

None — all ERR requirements are in scope for this phase.
</deferred>

---

*Phase: 25-error-handling-requestid*
*Context gathered: 2026-04-27*
