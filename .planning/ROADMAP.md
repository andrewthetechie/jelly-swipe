# Roadmap: Jelly Swipe

## Overview

v1.3 adds a comprehensive unit test suite for the existing Jelly Swipe codebase. The milestone follows a dependency-driven approach: establish test infrastructure first, then test core modules (database and Jellyfin provider), and finally integrate coverage reporting and CI. This framework-agnostic approach tests Python modules directly without coupling to Flask's request/response cycle, improving reliability when making changes.

## Milestones

- ✅ **v1.0 Jellyfin Support** - Phases 1-5 (shipped 2026-04-24)
- ✅ **v1.1 Jelly Swipe Rename** - Branding and identity (shipped 2026-04-24)
- ✅ **v1.2 uv + Package Layout + Plex Removal** - Phases 10-13 (shipped 2026-04-25)
- 🚧 **v1.3 Unit Tests** - Phases 14-17 (in progress)
- 📋 **v2.0 Advanced Features** - Future work (ARC-02 closure, OPS-01/PRD-01)

## Phases

<details>
<summary>✅ v1.0 Jellyfin Support (Phases 1-9) - SHIPPED 2026-04-24</summary>

### Phase 1: Project Setup
**Goal**: Initialize project scaffolding and development environment
**Plans**: 3 plans

Plans:
- [x] 01-01: Initialize Git repository and directory structure
- [x] 01-02: Set up Flask application skeleton
- [x] 01-03: Configure basic logging and error handling

### Phase 2: Database Schema
**Goal**: Design and implement SQLite database schema for rooms, swipes, and matches
**Plans**: 2 plans

Plans:
- [x] 02-01: Design database schema and create migrations
- [x] 02-02: Implement database connection and query functions

### Phase 3: Media Provider Abstraction
**Goal**: Create abstract base class for media provider with Plex implementation
**Plans**: 2 plans

Plans:
- [x] 03-01: Define LibraryMediaProvider abstract interface
- [x] 03-02: Implement PlexLibraryProvider with auth and library browsing

### Phase 4: Jellyfin Integration
**Goal**: Implement Jellyfin as alternative media backend
**Plans**: 3 plans

Plans:
- [x] 04-01: Implement JellyfinLibraryProvider with server authentication
- [x] 04-02: Build Jellyfin library browsing and deck fetching
- [x] 04-03: Add genre filtering and "Recently Added" sorting

### Phase 5: Verification & Validation
**Goal**: Verify Jellyfin parity and validate implementation
**Plans**: 3 plans

Plans:
- [x] 05-01: Verify Jellyfin authentication and token handling
- [x] 05-02: Validate library browsing and card transformation
- [x] 05-03: Test user-scoped features (matches, history, watchlist)

### Phase 6: Infrastructure Validation
**Goal**: Validate deployment infrastructure and Docker setup
**Plans**: 2 plans

Plans:
- [x] 06-01: Validate Docker image builds and runs correctly
- [x] 06-02: Test environment configuration and port binding

### Phase 7: Data Layer Validation
**Goal**: Validate database operations and data integrity
**Plans**: 2 plans

Plans:
- [x] 07-01: Validate database schema and migrations
- [x] 07-02: Test CRUD operations and data consistency

### Phase 8: E2E Validation
**Goal**: End-to-end validation of complete user workflows
**Plans**: 3 plans

Plans:
- [x] 08-01: Test complete room creation and guest join flow
- [x] 08-02: Verify swiping, matching, and notification behavior
- [x] 08-03: Validate operator deployment and configuration

### Phase 9: UI Enhancements
**Goal**: Enhance UI for Jellyfin delegate auth and poster display
**Plans**: 2 plans

Plans:
- [x] 09-01: Implement Jellyfin browser delegate auth
- [x] 09-02: Fix poster containment with object-fit: contain

</details>

<details>
<summary>✅ v1.1 Jelly Swipe Rename (No numbered phases) - SHIPPED 2026-04-24</summary>

No numbered phases - branding updates completed as single milestone.

</details>

<details>
<summary>✅ v1.2 uv + Package Layout + Plex Removal (Phases 10-13) - SHIPPED 2026-04-25</summary>

### Phase 10: uv Dependency Management
**Goal**: Migrate from requirements.txt to uv-based dependency management with Python 3.13
**Plans**: 2 plans

Plans:
- [x] 10-01: Create pyproject.toml with Python 3.13 requirements
- [x] 10-02: Generate uv.lock and update Docker/CI workflows

### Phase 11: Package Layout
**Goal**: Refactor code into jellyswipe/ package structure
**Plans**: 2 plans

Plans:
- [x] 11-01: Create jellyswipe/ package with __init__.py, db.py, jellyfin_library.py
- [x] 11-02: Update Gunicorn and local run commands to use jellyswipe:app

### Phase 12: Docker Multi-Stage Build
**Goal**: Implement multi-stage Docker build using uv for smaller, reproducible images
**Plans**: 2 plans

Plans:
- [x] 12-01: Create multi-stage Dockerfile with uv sync
- [x] 12-02: Update maintainer documentation for uv-based setup

### Phase 13: Plex Removal
**Goal**: Remove all Plex support to make application Jellyfin-only
**Plans**: 3 plans

Plans:
- [x] 13-01: Remove Plex implementation code (plex_library.py, factory.py)
- [x] 13-02: Remove plexapi dependency and update database schema
- [x] 13-03: Verify application works with Jellyfin-only configuration

</details>

### 🚧 v1.3 Unit Tests (In Progress)

**Milestone Goal:** Add unit tests that improve reliability when making changes to this software

#### Phase 14: Test Infrastructure Setup
**Goal**: Configure pytest environment and establish shared fixtures for isolated testing
**Depends on**: Phase 13
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04
**Success Criteria** (what must be TRUE):
  1. pytest discovers and executes tests from tests/ directory
  2. tests/conftest.py provides database, mock, and test data fixtures
  3. Tests import and execute modules directly without Flask app initialization
  4. pytest configuration in pyproject.toml enables appropriate test discovery and output
**Plans**: 3 plans

Plans:
- [ ] 14-01-PLAN.md — Add pytest dependencies to pyproject.toml and regenerate uv.lock
- [ ] 14-02-PLAN.md — Create tests/conftest.py with environment fixtures
- [ ] 14-03-PLAN.md — Create smoke tests and verify pytest setup

#### Phase 15: Database Module Tests
**Goal**: Test database operations with in-memory SQLite for complete isolation
**Depends on**: Phase 14
**Requirements**: DB-01, DB-02, DB-03
**Success Criteria** (what must be TRUE):
  1. Database tests create in-memory SQLite databases for each test
  2. Tests verify schema initialization, migrations, and CRUD operations
  3. Database state does not leak between tests (each test starts fresh)
**Plans**: 1 plan

Plans:
- [x] 15-01-PLAN.md — Create database fixtures and comprehensive tests for db.py module (completed 2026-04-25)

#### Phase 16: Jellyfin Provider Tests
**Goal**: Test Jellyfin library provider with mocked external API calls
**Depends on**: Phase 14
**Requirements**: API-01, API-02, API-03, API-04
**Success Criteria** (what must be TRUE):
  1. Tests mock HTTP requests to prevent real Jellyfin/TMDB API calls
  2. Tests verify authentication, token caching, and user ID resolution
  3. Tests cover library discovery, genre listing, and deck fetching
  4. Tests verify item-to-card transformation and TMDB resolution
**Plans**: 4 plans

Plans:
- [ ] 16-01-PLAN.md — Authentication tests (API key, username/password, 401 retry, token caching, user ID resolution)
- [ ] 16-02-PLAN.md — Library discovery tests (library ID resolution, genre listing, genre mapping, genre cache)
- [ ] 16-03-PLAN.md — Deck fetching and transformation tests (deck retrieval, item-to-card, TMDB resolution, genre filtering)
- [ ] 16-04-PLAN.md — Error and edge case tests (network failures, empty responses, missing fields, HTTP errors)

#### Phase 17: Coverage & CI Integration
**Goal**: Configure coverage reporting and GitHub Actions workflow
**Depends on**: Phase 15, Phase 16
**Requirements**: COV-01, COV-02
**Success Criteria** (what must be TRUE):
  1. pytest-cov generates coverage reports in terminal output
  2. GitHub Actions workflow runs tests on every push and pull request
**Plans**: TBD

### 📋 v2.0 Advanced Features (Planned)

**Milestone Goal:** Close ARC-02 regression matrix and implement multi-library selection

No phases defined yet - requirements are active candidates.

## Progress

**Execution Order:**
Phases execute in numeric order: 14 → 15 → 16 → 17

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Project Setup | v1.0 | 3/3 | Complete | 2026-04-24 |
| 2. Database Schema | v1.0 | 2/2 | Complete | 2026-04-24 |
| 3. Media Provider Abstraction | v1.0 | 2/2 | Complete | 2026-04-24 |
| 4. Jellyfin Integration | v1.0 | 3/3 | Complete | 2026-04-24 |
| 5. Verification & Validation | v1.0 | 3/3 | Complete | 2026-04-24 |
| 6. Infrastructure Validation | v1.0 | 2/2 | Complete | 2026-04-24 |
| 7. Data Layer Validation | v1.0 | 2/2 | Complete | 2026-04-24 |
| 8. E2E Validation | v1.0 | 3/3 | Complete | 2026-04-24 |
| 9. UI Enhancements | v1.0 | 2/2 | Complete | 2026-04-24 |
| 10. uv Dependency Management | v1.2 | 2/2 | Complete | 2026-04-25 |
| 11. Package Layout | v1.2 | 2/2 | Complete | 2026-04-25 |
| 12. Docker Multi-Stage Build | v1.2 | 2/2 | Complete | 2026-04-25 |
| 13. Plex Removal | v1.2 | 3/3 | Complete | 2026-04-25 |
| 14. Test Infrastructure Setup | v1.3 | 0/3 | Ready to execute | - |
| 15. Database Module Tests | v1.3 | 0/1 | Ready to execute | - |
| 16. Jellyfin Provider Tests | v1.3 | 0/4 | Ready to execute | - |
| 17. Coverage & CI Integration | v1.3 | 0/0 | Not started | - |
