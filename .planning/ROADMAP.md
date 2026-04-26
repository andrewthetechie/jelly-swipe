# Roadmap: Jelly Swipe

## Overview

Jelly Swipe is a small Flask app for shared "Tinder for movies" sessions: a host creates a room, guests join, everyone swipes on a deck pulled from a home media server, and matches surface when two people swipe right on the same title. Trailers and cast come from TMDB. **v1.3 shipped** comprehensive unit tests for the Jellyfin backend with framework-agnostic pytest approach.

## Milestones

- ✅ **v1.0 Jellyfin Support** - Phases 1-5 (shipped 2026-04-24)
- ✅ **v1.1 Jelly Swipe Rename** - Branding and identity (shipped 2026-04-24)
- ✅ **v1.2 uv + Package Layout + Plex Removal** - Phases 10-13 (shipped 2026-04-25)
- ✅ **v1.3 Unit Tests** - Phases 14-17 (shipped 2026-04-25)
- 📋 **v1.4 Clean up Unraid Template** - Phase 18 (in progress)
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
<summary>✅ v1.1 Jelly Swipe Rename - SHIPPED 2026-04-24</summary>

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

<details>
<summary>✅ v1.3 Unit Tests (Phases 14-17) - SHIPPED 2026-04-25</summary>

### Phase 14: Test Infrastructure Setup
**Goal**: Configure pytest environment and establish shared fixtures for isolated testing
**Plans**: 3 plans

Plans:
- [x] 14-01: Add pytest dependencies to pyproject.toml and regenerate uv.lock
- [x] 14-02: Create tests/conftest.py with environment fixtures
- [x] 14-03: Create smoke tests and verify pytest setup

### Phase 15: Database Module Tests
**Goal**: Test database operations with in-memory SQLite for complete isolation
**Plans**: 1 plan

Plans:
- [x] 15-01: Create database fixtures and comprehensive tests for db.py module

### Phase 16: Jellyfin Provider Tests
**Goal**: Test Jellyfin library provider with mocked external API calls
**Plans**: 4 plans

Plans:
- [x] 16-01: Authentication tests (API key, username/password, 401 retry, token caching, user ID resolution)
- [x] 16-02: Library discovery tests (library ID resolution, genre listing, genre mapping, genre cache)
- [x] 16-03: Deck fetching and transformation tests (deck retrieval, item-to-card, TMDB resolution, genre filtering)
- [x] 16-04: Error and edge case tests (network failures, empty responses, missing fields, HTTP errors)

### Phase 17: Coverage & CI Integration
**Goal**: Configure coverage reporting and GitHub Actions workflow
**Plans**: 1 plan

Plans:
- [x] 17-01: Add pytest-cov configuration and create GitHub Actions test workflow

</details>

### 📋 v1.4 — Clean up Unraid Template

**Milestone Goal:** Fix the Unraid template to use Jellyfin environment variables instead of removed Plex variables, ensuring users can successfully deploy the application

**Phases defined:** 1 phase (18)

### Phase 18: Unraid Template Cleanup
**Goal**: Update Unraid template variables and add CI validation
**Plans**: 3 plans

Plans:
- [ ] 18-01: Update Unraid template with Jellyfin environment variables and blank placeholders
- [ ] 18-02: Create CI lint workflow to validate Unraid template variables
- [ ] 18-03: Document Unraid template and CI validation in README

### 📋 v2.0 Advanced Features (Planned)

**Milestone Goal:** Close ARC-02 regression matrix and implement multi-library selection

No phases defined yet - requirements are active candidates.

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 17 → 18

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
| 14. Test Infrastructure Setup | v1.3 | 3/3 | Complete | 2026-04-25 |
| 15. Database Module Tests | v1.3 | 1/1 | Complete | 2026-04-25 |
| 16. Jellyfin Provider Tests | v1.3 | 4/4 | Complete | 2026-04-25 |
| 17. Coverage & CI Integration | v1.3 | 1/1 | Complete | 2026-04-25 |
| 18. Unraid Template Cleanup | v1.4 | 0/3 | Not started | — |
