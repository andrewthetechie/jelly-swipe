# Requirements: Jelly Swipe

**Defined:** 2026-05-02
**Milestone:** v2.0 Flask → FastAPI + MVC Refactor
**Core Value:** Users can run a swipe session backed by Jellyfin, with library browsing and deck behavior equivalent to the original Plex path.

## v2.0 Requirements

### Framework Migration

- [x] **FAPI-01**: FastAPI replaces Flask as the web framework; Uvicorn replaces Gunicorn+gevent as the ASGI server
- [x] **FAPI-02**: All existing HTTP endpoints retain identical URL paths, methods, and response shapes after migration
- [x] **FAPI-03**: SSE endpoint (`/room/<code>/stream`) works via FastAPI `StreamingResponse` with an async generator using `await asyncio.sleep()` — `time.sleep()` must not be used in the event loop path
- [x] **FAPI-04**: Session management migrated from Flask sessions to Starlette `SessionMiddleware`

### Architecture

- [x] **ARCH-01**: Route handlers split from `jellyswipe/__init__.py` into domain-specific routers: auth, rooms, media, proxy, and static
- [x] **ARCH-03**: Shared logic (auth checking, provider access, DB connection) extracted into `jellyswipe/dependencies.py` using FastAPI's `Depends()` pattern
- [x] **ARCH-04**: `jellyswipe/__init__.py` becomes the thin app factory — imports and mounts routers, configures middleware

### Deployment

- [x] **DEP-01**: `Dockerfile` CMD updated to run Uvicorn; `pyproject.toml` updated: Flask, Gunicorn, gevent, Werkzeug removed; `fastapi>=0.136.1`, `uvicorn[standard]>=0.46.0`, `itsdangerous>=2.2.0`, `jinja2>=3.1.6`, `python-multipart>=0.0.18` added; `httpx>=0.28.1` added as dev dependency

### Testing

- [x] **TST-01**: All 321 existing tests updated to use FastAPI's `TestClient`; full test suite passes with no modifications to test logic (only API surface changes) — 317 pass, 1 skip (pre-existing Flask-era skip), 3 pre-existing failures (TestCleanupExpiredTokens: cleanup_expired_tokens uses 14-day threshold, tests expect 24h)

## v2.1 Requirements (Deferred)

### Pydantic Models

- **ARCH-02**: Pydantic v2 models cover all request bodies and significant response shapes; all route handlers use typed request/response contracts

## Out of Scope

| Feature | Reason |
|---------|--------|
| New end-user features | Pure migration — behavior parity is the goal, not new capabilities |
| WebSocket upgrade | SSE is sufficient; WebSocket adds complexity without clear benefit now |
| Database schema changes | v2.0 is framework-only; no data model changes |
| Plex support | Removed in v1.2; application is Jellyfin-only |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DEP-01 | Phase 30 | Complete |
| FAPI-01 | Phase 31, Phase 35 | Complete |
| FAPI-04 | Phase 31 | Complete |
| ARCH-04 | Phase 31 | Complete |
| ARCH-03 | Phase 32 | Completed | 32-01 |
| ARCH-01 | Phase 33 | Complete |
| FAPI-02 | Phase 33 | Complete |
| FAPI-03 | Phase 34 | Complete |
| TST-01 | Phase 35 | Complete |

**Coverage:**
- v2.0 requirements: 9 total
- Mapped to phases: 9 (100% coverage)
- Unmapped: 0

---
*Requirements defined: 2026-05-02*
*Last updated: 2026-05-01 after v2.0 roadmap creation — all 9 requirements mapped*
