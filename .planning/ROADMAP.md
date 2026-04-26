# ROADMAP — Jelly Swipe v1.5

**Milestone:** Route Test Coverage
**Granularity:** Standard
**Requirements:** 7 total (FACTORY-01, TEST-ROUTE-01..05, COV-01)

## Phases

- [ ] **Phase 21: App Factory Refactor** - Refactor Flask app into factory pattern for test isolation
- [ ] **Phase 22: Test Infrastructure Setup** - Add app and client fixtures to conftest.py
- [ ] **Phase 23: Auth Route Tests** - Add authentication route tests with header-spoof protection
- [ ] **Phase 24: XSS Security Tests** - Add XSS blocking tests for input validation
- [ ] **Phase 25: Room Operation Tests** - Add room lifecycle tests (create/join/swipe/match/quit)
- [ ] **Phase 26: Proxy Route Tests** - Add proxy route tests for SSRF prevention
- [ ] **Phase 27: SSE Streaming Tests** - Add SSE event streaming and shutdown tests
- [ ] **Phase 28: Coverage Enforcement** - Add 70% coverage threshold enforcement to CI

## Phase Details

### Phase 21: App Factory Refactor
**Goal**: Flask app uses factory pattern for test isolation
**Depends on**: Nothing (first phase)
**Requirements**: FACTORY-01
**Success Criteria** (what must be TRUE):
  1. Application creates via `create_app(test_config=None)` factory function
  2. Global `app` instance exists for backwards compatibility
  3. Factory accepts test_config parameter for test overrides
  4. Application runs with existing configuration (no breaking changes)
**Plans**: TBD

### Phase 22: Test Infrastructure Setup
**Goal**: Route tests have app and client fixtures available
**Depends on**: Phase 21
**Requirements**: None (infrastructure phase)
**Success Criteria** (what must be TRUE):
  1. `app` fixture creates fresh Flask app instance for each test
  2. `client` fixture provides Flask test client for HTTP requests
  3. Fixtures use function-scoped isolation (no state leakage between tests)
  4. Fixtures work with existing conftest.py patterns (db_connection, mock_env_vars)
**Plans**: TBD

### Phase 23: Auth Route Tests
**Goal**: Authentication routes have comprehensive test coverage
**Depends on**: Phase 22
**Requirements**: TEST-ROUTE-01
**Success Criteria** (what must be TRUE):
  1. `/auth/provider` returns correct provider for MEDIA_PROVIDER env
  2. `/auth/jellyfin-use-server-identity` handles valid and invalid tokens
  3. `/auth/jellyfin-login` authenticates with valid credentials
  4. Header-spoof tests verify EPIC-01 protection (client identity rejected)
**Plans**: TBD

### Phase 24: XSS Security Tests
**Goal**: XSS vulnerabilities are prevented and tested
**Depends on**: Phase 22
**Requirements**: TEST-ROUTE-02
**Success Criteria** (what must be TRUE):
  1. HTML tags in user input are escaped in responses
  2. `javascript:` URLs are rejected with 400 error
  3. Script injection attempts are blocked (EPIC-03)
  4. All user-controlled content is sanitized before rendering
**Plans**: TBD

### Phase 25: Room Operation Tests
**Goal**: Room lifecycle operations have comprehensive test coverage
**Depends on**: Phase 22
**Requirements**: TEST-ROUTE-03
**Success Criteria** (what must be TRUE):
  1. `/room/create` creates new room and returns room code
  2. `/room/join` adds user to existing room
  3. `/room/swipe` records swipe and updates match state
  4. `/room/quit` removes user from room
  5. `/room/status` returns current room state
  6. `/room/go-solo` converts shared room to solo room
**Plans**: TBD

### Phase 26: Proxy Route Tests
**Goal**: Proxy route prevents SSRF attacks with allowlist validation
**Depends on**: Phase 22
**Requirements**: TEST-ROUTE-04
**Success Criteria** (what must be TRUE):
  1. `/proxy` serves valid Jellyfin image paths
  2. Invalid paths are rejected with 403 error
  3. Allowlist regex blocks non-whitelisted paths (EPIC-04)
  4. Content-type verification returns correct image types
**Plans**: TBD

### Phase 27: SSE Streaming Tests
**Goal**: SSE streaming works correctly and handles edge cases
**Depends on**: Phase 22
**Requirements**: TEST-ROUTE-05
**Success Criteria** (what must be TRUE):
  1. `/room/stream` sends SSE events for state changes
  2. Invalid room code returns 404 error
  3. GeneratorExit is handled gracefully on client disconnect
  4. Stream includes correct event format (data, event, id)
**Plans**: TBD

### Phase 28: Coverage Enforcement
**Goal**: CI enforces 70% coverage threshold for jellyswipe/__init__.py
**Depends on**: Phase 27
**Requirements**: COV-01
**Success Criteria** (what must be TRUE):
  1. pytest configuration includes `--cov-fail-under=70` option
  2. CI workflow fails if coverage drops below 70%
  3. Terminal coverage report shows jellyswipe/__init__.py percentage
  4. All route tests contribute to coverage threshold
**Plans**: TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 21. App Factory Refactor | 0/0 | Not started | - |
| 22. Test Infrastructure Setup | 0/0 | Not started | - |
| 23. Auth Route Tests | 0/0 | Not started | - |
| 24. XSS Security Tests | 0/0 | Not started | - |
| 25. Room Operation Tests | 0/0 | Not started | - |
| 26. Proxy Route Tests | 0/0 | Not started | - |
| 27. SSE Streaming Tests | 0/0 | Not started | - |
| 28. Coverage Enforcement | 0/0 | Not started | - |

---

*Roadmap created: 2026-04-26*
*Next: `/gsd-plan-phase 21`*
