# Documentation Strategy — Self-Documenting API via OpenAPI and SSE Reference

## Problem Statement

The Jellyswipe API has no usable documentation for frontend developers. The FastAPI app passes no metadata to the OpenAPI spec — no title, no version, no description. Routes have no tags, no typed request or response models, and no declared error responses. The ReDoc page renders as a flat, unnamed list of endpoints with no schema information. A developer building a new frontend against this API would have to reverse-engineer every request body, response shape, error convention, and the entire SSE event protocol by reading Python source code.

The existing bundled frontend (`static/app.js`) is the only "documentation" for how the API behaves, and it conflates implementation details with the API contract.

## Solution

Make the API fully self-documenting using FastAPI's native OpenAPI tooling, and produce a standalone SSE event reference for the real-time streaming protocol that OpenAPI cannot represent.

Concretely:

1. Add Pydantic v2 request and response models for every frontend-facing endpoint, including a shared error response model. Wire these into route decorators via `response_model=` and `responses={}`.

2. Replace hand-rolled `await request.json()` + `isinstance()` validation in route handlers with Pydantic request body parameters. This deletes manual validation code while gaining automatic schema documentation.

3. Add app-level OpenAPI metadata (title, version from package metadata, rich markdown description covering the delegate auth model, error conventions, rate limiting, XSS-safe JSON escaping, and a pointer to the SSE docs).

4. Organize endpoints into 7 tagged groups in ReDoc: Authentication, Rooms, Swiping, Matches, Media, Proxy, Health.

5. Exclude static file routes and the deprecated `POST /room/solo` tombstone from the OpenAPI schema.

6. Document the `GET /proxy` endpoint with `image/*` response media type and JSON error responses.

7. Document the `GET /room/{code}/stream` SSE endpoint in OpenAPI with a rich description summarizing event types, and produce a standalone `docs/sse-events.md` reference specifying every event type, payload schema, cursor/replay semantics, and reconnection behavior.

8. Keep both `/docs` (Swagger UI) and `/redoc` (ReDoc) enabled.

## User Stories

1.  As a frontend developer building a new client, I want to open `/redoc` and see every endpoint grouped by domain area with full request and response schemas, so that I can build API calls without reading Python source code.
2.  As a frontend developer, I want to see the exact JSON shape of every response body in the docs, so that I can type my frontend models correctly.
3.  As a frontend developer, I want to see which fields are required vs. optional in request bodies, so that I know the minimum viable payload for each endpoint.
4.  As a frontend developer, I want to see the error response shape documented on every endpoint, so that I can build consistent error handling.
5.  As a frontend developer, I want to understand the delegate identity authentication model from the API docs, so that I know I'm authenticating via server identity — not per-user Jellyfin credentials.
6.  As a frontend developer, I want to know which endpoints require authentication and which are public, so that I can handle 401s correctly.
7.  As a frontend developer, I want to know which endpoints are rate-limited and what happens when I hit the limit, so that I can implement backoff logic.
8.  As a frontend developer, I want to understand the XSS-safe JSON escaping behavior (`\u003c`, `\u0026`) from the API docs, so that I don't write broken string-matching code against raw response bodies.
9.  As a frontend developer, I want a standalone SSE event reference document, so that I can implement the real-time session stream without reverse-engineering the Python generator.
10. As a frontend developer, I want to know every SSE event type (`session_bootstrap`, `session_reset`, `session_ready`, `session_closed`, `genre_changed`, `hide_watched_changed`, `match_found`) and its payload schema, so that I can build event handlers for each one.
11. As a frontend developer, I want to understand the SSE cursor/replay protocol (`Last-Event-ID`, `after_event_id`, replay boundary), so that I can implement robust reconnection without missing events.
12. As a frontend developer, I want to know how to construct image URLs using the proxy endpoint (`/proxy?path=jellyfin/{media_id}/Primary`), so that I can display artwork without needing Jellyfin credentials.
13. As a frontend developer, I want to see the card item schema (media_id, title, summary, thumb, year, media_type, rating, duration, season_count) documented in one place, so that I can build my card rendering component.
14. As a frontend developer, I want to see the match item schema documented, so that I can build my match list UI.
15. As a frontend developer using Swagger UI at `/docs`, I want to test endpoints interactively, so that I can experiment with the API during development.
16. As a frontend developer, I want the deprecated `POST /room/solo` endpoint excluded from the docs, so that I don't waste time trying to use a removed endpoint.
17. As a frontend developer, I want the static file routes (`GET /`, `/manifest.json`, etc.) excluded from the API docs, so that I only see the endpoints relevant to building a client.
18. As a frontend developer, I want the `GET /matches` `view` query parameter documented with its valid values (`history` or omitted), so that I know how to switch between active and historical match views.
19. As a frontend developer, I want to know that `POST /room` accepts `movies`, `tv_shows`, and `solo` as JSON booleans (not strings), so that I don't get unexpected 400 errors.
20. As an operator deploying Jellyswipe, I want the health check endpoints (`/healthz`, `/readyz`) tagged separately in the docs, so that I can find them without scrolling through the frontend API.
21. As a contributor to Jellyswipe, I want the Pydantic schemas to serve as the single source of truth for the API contract, so that response shapes can't silently drift from what the docs promise.

## Implementation Decisions

### Module structure

A new `jellyswipe/schemas/` package with per-domain modules:

- `common.py` — `ErrorResponse` model (error string + optional request_id), `CardItem` model (the card dict shape used by deck, genre-change, and watched-filter responses), `MatchItem` model (the match row shape). These are shared across routers.
- `auth.py` — Request/response models for the 4 auth endpoints: `LoginResponse`, `LogoutResponse`, `MeResponse`, `ServerInfoResponse`.
- `rooms.py` — Request/response models for room lifecycle and swiping: `CreateRoomRequest`, `CreateRoomResponse`, `JoinRoomResponse`, `SwipeRequest`, `SwipeResponse`, `UndoRequest`, `UndoResponse`, `QuitRoomResponse`, `SetGenreRequest`, `SetWatchedFilterRequest`, `DeckPageResponse` (or just `list[CardItem]`), `RoomStatusResponse`.
- `media.py` — `TrailerResponse`, `CastMember`, `CastResponse`, `WatchlistAddRequest`, `GenreListResponse`.
- `__init__.py` — Re-exports for convenience.

### App-level OpenAPI metadata

The `FastAPI()` constructor will receive:

- `title`: `"Jellyswipe API"`
- `version`: Pulled from `importlib.metadata.version("jellyswipe")` with `"0.0.0-dev"` fallback (same pattern already used in `health.py`).
- `description`: Rich markdown covering the delegate auth model, session cookie requirement, error response convention, rate-limited endpoints, XSS-safe JSON escaping caveat, and a link to the SSE event docs.
- `license_info`: MIT, linking to the LICENSE file.

### Tag definitions

Seven tags defined via `openapi_tags` on the `FastAPI()` constructor, each with a description paragraph:

| Tag            | Description                                                                    |
| -------------- | ------------------------------------------------------------------------------ |
| Authentication | Session lifecycle and user identity via Jellyfin delegate auth                 |
| Rooms          | Room creation, joining, lifecycle, and real-time events                        |
| Swiping        | Deck navigation, swiping, undo, and filtering                                  |
| Matches        | Match retrieval and history management                                         |
| Media          | Metadata enrichment from TMDB and Jellyfin (trailers, cast, genres, watchlist) |
| Proxy          | Image proxying for Jellyfin artwork                                            |
| Health         | Operational liveness and readiness probes                                      |

### Route decorator changes

Every frontend-facing route gets:

- `tags=[...]` — one of the 7 tags above
- `response_model=` — the Pydantic response model
- `responses={...}` — error status codes with the `ErrorResponse` model
- `summary=` — short one-line summary
- Enriched docstring — multi-line description for ReDoc

### Request body migration

Routes that currently do `await request.json()` followed by manual field extraction and type-checking will be migrated to Pydantic body parameters. This deletes the hand-rolled validation code in:

- `POST /room` (boolean type checks for `movies`, `tv_shows`, `solo`)
- `POST /room/{code}/swipe` (media_id required check)
- `POST /room/{code}/undo` (media_id required check)
- `POST /room/{code}/genre` (genre required check)
- `POST /room/{code}/watched-filter` (hide_watched required + boolean check)
- `POST /matches/delete` (media_id required check)
- `POST /watchlist/add` (media_id required check)

### Schema exclusions

- All 4 static routes (`GET /`, `/manifest.json`, `/sw.js`, `/favicon.ico`) get `include_in_schema=False`.
- The deprecated `POST /room/solo` tombstone gets `include_in_schema=False`.

### Proxy response documentation

`GET /proxy` declares `responses=` with:

- 200: `content={"image/*": {}}` media type
- 403, 404, 502: `ErrorResponse` model

### SSE documentation

The `GET /room/{code}/stream` route gets a rich docstring covering the event types, reconnection protocol, and a pointer to `docs/sse-events.md`.

A standalone `docs/sse-events.md` documents:

- Connection setup and the `session_bootstrap` handshake
- All 7 event types with payload schemas
- The cursor/replay protocol (`Last-Event-ID`, `after_event_id`, `replay_boundary`)
- Reconnection behavior (stale cursor → `session_reset`)
- Keep-alive pings (comment-only SSE frames every 15s)
- Terminal events (`session_closed`, `session_reset`)

## Testing Decisions

### What makes a good test here

API documentation changes are primarily structural — they change the OpenAPI spec output and the request validation behavior, not the business logic. Good tests verify external behavior: "does the endpoint accept this input and return this shape?" They should not assert internal details like which Pydantic model class is used.

### What to test

- **Request validation via Pydantic** — The migration from hand-rolled validation to Pydantic models changes error behavior (Pydantic returns 422 with detailed validation errors instead of the hand-crafted 400s). Existing tests that assert specific 400 error messages for malformed input may need updating to expect 422s with Pydantic's validation error shape. This is the primary regression risk.
- **OpenAPI schema correctness** — A single test can hit `/openapi.json` and assert that all expected endpoints, tags, and response schemas are present. This catches regressions if someone adds a route without models.
- **Existing integration tests** — The full test suite (`uv run pytest tests/`) should pass unchanged (or with minor status-code adjustments for the 400→422 migration). No new business logic is introduced.

### Prior art

The existing test suite in `tests/` uses `@pytest.mark.anyio`, the `client_real_auth` fixture for authenticated HTTP testing, and `FakeProvider` for Jellyfin mocking. The Pydantic migration should not require new test patterns — existing route tests already send JSON bodies and assert response shapes.

## Out of Scope

- **Pydantic models for SSE event payloads as runtime types** — The SSE events are emitted by the session event stream generator using plain dicts and `json.dumps`. Converting them to Pydantic models would touch the event ledger and mutation services. The SSE payloads are documented in `docs/sse-events.md` but not enforced by Pydantic at runtime.
- **Authentication scheme declaration in OpenAPI** — FastAPI supports declaring security schemes (e.g., `HTTPBearer`, `APIKeyCookie`). The delegate identity model uses session cookies, which could be declared as an `APIKeyCookie` security scheme. This is a follow-up concern — the current work documents the auth flow in prose but doesn't wire up OpenAPI security scheme metadata.
- **API versioning** — No `/v1/` prefix or versioning strategy is introduced. The API is still v0/unstable.
- **Client SDK generation** — The improved OpenAPI spec could feed `openapi-generator` or similar tools to produce typed client libraries. This is a downstream benefit but not in scope here.
- **Changing the deprecated** `POST /room/solo` **behavior** — It stays as a 404 tombstone; we only hide it from the schema.

## Further Notes

- The 400→422 status code change for request validation is the only behavioral change in this PRD. Pydantic returns 422 Unprocessable Entity for validation failures, not 400 Bad Request. Any frontend currently relying on 400 status codes for input validation errors will need to handle 422 as well. The error body shape also changes from `{"error": "..."}` to FastAPI's standard `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` for validation errors.
- The `ErrorResponse` model covers application-level errors (room not found, rate limit exceeded, etc.). Pydantic validation errors (422) use FastAPI's built-in `RequestValidationError` shape and are a separate concern.
- The card dict shape documented in `CONTEXT.md` uses `id` internally but the API exposes `media_id`. The Pydantic `CardItem` model uses `media_id` since it represents the API contract, not the internal storage format.
