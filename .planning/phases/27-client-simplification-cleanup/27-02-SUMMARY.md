---
phase: 27-client-simplification-cleanup
plan: 02
subsystem: testing
tags: [integration-test, compliance, clnt-01, clnt-02, tdd]
dependency_graph:
  requires: [27-01-complete]
  provides: [phase-27-compliance-verified]
  affects: [tests/test_route_authorization.py]
tech_stack:
  added: []
  patterns: [compliance-testing, auth-lifecycle-test]
key_files:
  created: []
  modified:
    - tests/test_route_authorization.py
decisions:
  - Tests verify both server-side behavior and client-side cleanup via grep
  - auth lifecycle test covers full delegate login -> me -> logout -> 401 flow
  - SSE match test uses /room/{code}/status to verify enriched match data
metrics:
  duration: ~3 minutes
  completed: 2026-04-27
  tasks: 1
  files_modified: 1
  tests_added: 5
  total_tests: 141
---

# Phase 27 Plan 02: Integration Verification Tests Summary

Added comprehensive integration tests verifying Phase 27 (CLNT-01 and CLNT-02) compliance through 5 targeted tests covering auth lifecycle, swipe response shape, SSE match enrichment, solo endpoint, and active room tracking.

## What Was Done

### Task 1 (TDD): Integration verification tests for Phase 27 compliance
Added `TestPhase27Compliance` class with 5 tests:

1. **test_auth_lifecycle**: Delegate login → GET /me (200) → POST /auth/logout → GET /me (401). Verifies full session lifecycle.
2. **test_swipe_no_match_in_response**: Swipe returns exactly `{accepted: true}` with no match/title/thumb/solo fields (CLNT-02).
3. **test_sse_match_has_enriched_fields**: Two-player match via /room/{code}/status shows deep_link, rating, duration, year.
4. **test_solo_endpoint_not_go_solo**: POST /room/solo works (200), old go-solo route returns 404.
5. **test_me_returns_active_room**: GET /me tracks activeRoom: null → code → null after quit.

Also ran grep verification: zero localStorage and zero identity header references in client JS.

## Commits

| Hash | Message |
|------|---------|
| 0ce04ee | test(27-02): add Phase 27 compliance integration tests |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.
