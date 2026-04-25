---
status: partial
phase: 11-jellyswipe-package-layout
source: [11-VERIFICATION.md]
started: 2026-04-25T01:35:00Z
updated: 2026-04-25T01:35:00Z
---

## Current Test

Awaiting human testing

## Tests

### 1. Verify application runs with Gunicorn entry point jellyswipe:app
expected: Gunicorn starts without errors, logs show "Listening at: http://0.0.0.0:5005"
result: [pending]

### 2. Verify templates render correctly in browser
expected: UI renders with correct styling, icons, layout, and media_provider context
result: [pending]

### 3. Verify static files (icons, manifest) load correctly
expected: icon-192.png, icon-512.png, logo.png, manifest.json all load with 200 status codes
result: [pending]

### 4. Verify environment validation works correctly
expected: Gunicorn fails to start with clear "Missing env vars" error message
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps

### Gap 1: SSE stream fails with Gunicorn sync workers
**Status:** failed
**Issue:** /room/stream SSE generator fails with `SystemExit: 1` during `time.sleep(POLL)`
**Root Cause:** Gunicorn sync workers incompatible with long-lived SSE connections
**Test Case:** Joining a room hangs for several seconds, then errors, then repeats
**Proposed Solutions:**
1. Use Gunicorn with gevent workers (quickest fix)
2. Switch to Uvicorn with Flask ASGI adapter (better long-term)
3. Switch to Quart (Flask-compatible ASGI) — more work
**Priority:** High — blocking core functionality
