# PRD: Architecture Deepening — Module Extraction and Responsibility Consolidation

## Problem Statement

The Jelly Swipe codebase has grown organically through several feature additions (TV show support, Watched Filter, SSE stream revamp) and now exhibits architectural friction that slows feature development and makes testing harder than it needs to be.

The core issues, from a developer's perspective:

1. **The Jellyfin provider is two modules in one.** `JellyfinLibraryProvider` (673 lines) mixes library I/O (fetching Swipe Decks, Media Candidates, genres) with user-session management (credential exchange, token resolution, favorites). These responsibilities have different callers, different error modes, and different change reasons, but they share a single file and a single singleton. When debugging a user login failure, you're wading through deck-fetching code. When testing auth flows, you're coupled to the entire library provider.

2. **Swipe Deck building logic is duplicated and scattered.** The 7-step pipeline for building a Swipe Deck — determine Media Type Filter, fetch from provider, apply Balanced Interleaving, exclude swiped candidates, validate non-empty, persist, convert to Media Payload format — is split between `create_room` and `_rebuild_deck`, with the Balanced Interleaving logic copy-pasted identically in both methods. The `id` → `media_id` field translation also happens in multiple places. Understanding how a Swipe Deck gets built requires reading three methods and mentally stitching together which steps each one owns.

3. **TMDB enrichment is inlined in route handlers.** The trailer and cast lookup routes contain multi-step TMDB orchestration (resolve Jellyfin item → search TMDB → fetch videos/cast) directly in the HTTP handler. The route handler IS the implementation — a classic shallow module where the interface is as complex as the code behind it. This makes TMDB logic untestable without the full HTTP stack, and every lookup makes 2-3 external HTTP calls with no caching, meaning duplicate lookups for the same Media Candidate are common.

4. **The Session Event Stream generator is a 120-line function inlined in a route handler.** Bootstrap, Session Event Cursor validation, Session Event Ledger replay, heartbeat pings, live event subscription, and disconnect detection all live inside a single `generate()` async generator nested in the route. Testing this behavior requires HTTP-level interactions with mocked requests, mocked notifiers, and mocked time — confirmed by the 580-line `test_routes_sse.py` that exists precisely because the test surface is so awkward.

5. **The `LibraryMediaProvider` ABC claims a seam that doesn't exist.** It has one adapter, zero polymorphism, and tests don't use it (the `FakeProvider` in conftest is duck-typed). Meanwhile, a `DeckProvider` Protocol already exists in the services layer as a narrower, more honest contract for the one seam that's actually exercised.

6. **Router helper functions are copy-pasted across three files.** `make_error_response` and `log_exception` are identically implemented in the auth, media, and rooms routers.

## Solution

Extract deep modules with small interfaces and high leverage, consolidating scattered logic and eliminating duplication. Each extraction creates a module that can be tested through its own interface without requiring the full HTTP or database apparatus.

The extractions are ordered to minimize churn:

1. Delete the unused ABC
2. Split the provider into library I/O and user-session modules
3. Unify Swipe Deck building into a single pipeline module
4. Extract TMDB enrichment as a pure module with DB-backed caching at the orchestration layer
5. Extract the Session Event Stream generator into its own module with injectable dependencies
6. Deduplicate router helpers

## User Stories

1. As a developer debugging a user login failure, I want user-session logic isolated from library I/O, so that I can read and reason about auth code without navigating 673 lines of deck-fetching machinery.
2. As a developer adding a new Jellyfin user-facing action, I want a dedicated user-session module with a clear interface, so that I know exactly where to add the method and how to test it.
3. As a developer writing tests for auth flows, I want to mock the user-session module independently from the library provider, so that my test setup doesn't require a full `FakeProvider` that also pretends to fetch decks.
4. As a developer fixing a Balanced Interleaving bug, I want interleaving logic to exist in exactly one place, so that a single fix resolves the issue everywhere.
5. As a developer adding a new filter type (e.g., a rating filter), I want one pipeline module that handles all Swipe Deck building steps, so that I add the filter in one place rather than patching it into `create_room` and `_rebuild_deck` separately.
6. As a developer changing how the `id` → `media_id` Media Payload conversion works, I want that conversion to live in one location, so that I don't miss one of the multiple places it currently happens.
7. As a developer testing Swipe Deck building, I want to exercise the full pipeline (fetch → interleave → exclude → validate → persist) through a single function call, so that I can write focused tests without HTTP or session setup.
8. As a developer testing TMDB trailer lookups, I want to call a pure function with `(title, year)` and get back a YouTube key or `None`, so that my tests don't require a running FastAPI app, a fake Jellyfin provider, or HTTP mocking.
9. As a developer changing the TMDB API version or auth scheme, I want all TMDB-specific code in one module, so that the change is localized.
10. As a user viewing a popular Media Candidate's detail card, I want trailer and cast data to be served from a local cache when available, so that the app responds faster and doesn't make redundant external API calls.
11. As a developer testing Session Event Stream behavior (bootstrap, replay, cursor validation, heartbeat), I want to call the stream generator directly with fake dependencies, so that I don't need to mock HTTP requests, parse SSE output, or manipulate time.
12. As a developer modifying heartbeat timing or cursor validation logic, I want that logic concentrated in one module, so that I know exactly what to change and what tests cover it.
13. As a developer adding a new Session Event Stream feature (e.g., a new event type or delivery rule), I want the stream delivery module to have an obvious home for the change, separate from SSE formatting and HTTP concerns.
14. As a developer reading the codebase for the first time, I want the ABC to reflect reality — either a real seam with multiple adapters or no ABC at all — so that I don't waste time understanding a contract that nothing enforces.
15. As a developer modifying error response format, I want to change it in one place instead of three identical copies across routers.
16. As a developer onboarding to the project, I want each module to have a single clear responsibility, so that I can build a mental model of the system without cross-referencing scattered implementations.

## Implementation Decisions

### 1. Delete the `LibraryMediaProvider` ABC

- Remove the ABC file entirely. Remove inheritance from the Jellyfin provider class.
- The `DeckProvider` Protocol (already defined in the services layer) remains as the only seam contract — it's narrow, honest, and actually exercised by tests.
- No replacement ABC is introduced. Future seams use Protocols at the point of need.

### 2. Split the Jellyfin provider into two modules

**Library I/O module** (existing file, trimmed):

- Keeps the server-level auth bootstrap (`ensure_authenticated`, `_login_from_env`, `_api` with 401-retry)
- Keeps all library query methods: `fetch_deck`, `list_genres`, `resolve_item_for_tmdb`, `server_info`, `fetch_library_image`
- Keeps delegate accessor methods (`server_access_token_for_delegate`, `server_primary_user_id_for_delegate`) because they depend on server-level auth state
- Keeps all internal helpers: `_user_id`, `_library_ids_for_type`, `_item_to_card`, `_series_to_card`, etc.

**User-session module** (new file):

- `authenticate_user_session(username, password) → {token, user_id}` — exchanges user credentials for a Jellyfin session
- `resolve_user_id_from_token(user_token) → str` — resolves a user-supplied token to a Jellyfin user ID
- `add_to_user_favorites(user_token, movie_id) → None` — adds a Media Candidate to user favorites
- `extract_media_browser_token()` and `user_auth_header(token)` — static HTTP header utilities
- Gets its own `requests.Session` and base URL from the same `JELLYFIN_URL` env var. Does NOT share the library module's connection pool or auth state — the coupling between them was only `self._base` and `self._session`, and user-session calls don't use the server-level `_access_token` or `_auth_headers()`.

**Dependency injection:**

- A new `get_jellyfin_user_session()` function is added to the dependencies module, following the same singleton pattern as `get_provider()`.
- Auth router calls `get_jellyfin_user_session()` for login. Media router calls it for watchlist. The dependency resolution layer calls it for token validation.

### 3. Unify Swipe Deck building into a single pipeline

**New module** in the services layer.

Interface: a single async function that takes explicit config (provider, unit-of-work, room code, media types, genre, hide_watched flag) and returns an API-format deck.

Internally the function:

1. Calls the provider (via `DeckProvider` Protocol) with media types, genre, and hide_watched
2. Applies Balanced Interleaving when both media types are present (one implementation, not two)
3. Reads swiped Media Candidate IDs from the unit-of-work and excludes them
4. Validates the resulting deck is non-empty (raises on empty)
5. Persists the deck in internal format via the unit-of-work
6. Converts `id` → `media_id` for the Media Payload API shape and returns it

The `DeckProvider` Protocol moves from the room lifecycle service to this new module.

**Callers:**

- `create_room` calls the pipeline after creating the room row (so the room exists for persistence)
- `set_genre` and `set_watched_filter` call the pipeline with the override value
- `_rebuild_deck` is eliminated — replaced entirely by the pipeline function

The pipeline receives explicit config rather than reading it from the room, so `create_room` can pass the config it's about to persist without a chicken-and-egg problem.

### 4. Extract TMDB enrichment with DB-backed caching

**New pure module** for TMDB lookups:

- `lookup_trailer(title, year) → str | None` — searches TMDB, returns YouTube key. All failures (network, not found, bad response) return `None`. Best-effort enrichment.
- `lookup_cast(title, year) → list[dict]` — searches TMDB, returns up to 8 cast members. All failures return `[]`.
- Owns `TMDB_AUTH_HEADERS`, URL construction, and response parsing. Uses `make_http_request` for actual calls.
- Zero external dependencies — no provider, no DB, no FastAPI. Testable with HTTP mocking alone.

**New DB table** (`tmdb_cache`) via Alembic migration:

- Schema: `media_id TEXT, lookup_type TEXT, result_json TEXT, fetched_at TEXT`
- Primary key: `(media_id, lookup_type)`
- `lookup_type` is `"trailer"` or `"cast"`
- `fetched_at` stores ISO timestamp for TTL-based expiry

**New repository** for cache operations:

- `get(media_id, lookup_type, max_age_days=7) → dict | None` — returns cached result if fresh, else `None`
- `put(media_id, lookup_type, result_json) → None` — upserts cache entry with current timestamp

**Caching lives at the orchestration layer** (route handlers), not inside the TMDB module:

1. Check cache by `media_id` + lookup type
2. On hit: return cached result
3. On miss: resolve item via library provider (title + year), call TMDB pure function, store result in cache, return

This keeps the TMDB module maximally testable (pure functions with zero dependencies) while still avoiding duplicate external lookups.

### 5. Extract Session Event Stream generator

**New module** containing the async generator function.

Parameters (all injected, no global imports):

- `code` — room pairing code
- `instance_id` — Session Instance identity
- `room` — current room state (for bootstrap data)
- `cursor` — optional Session Event Cursor (from `Last-Event-ID` header)
- `sessionmaker_factory` — callable returning async DB sessions
- `notifier` — pub/sub notifier for live event wakeups
- `is_disconnected` — async callable returning bool (abstracts `request.is_disconnected()`)

Returns an async generator yielding dicts with `id`, `data`, and/or `comment` keys — the same shape `EventSourceResponse` already consumes.

The generator owns:

- Session Bootstrap Event construction (first-attach path)
- Session Event Cursor validation and stale-cursor detection
- Session Event Ledger replay (missed events)
- Heartbeat ping timing
- Live event subscription loop (notifier subscribe → DB read → yield)
- `session_closed` event detection and stream termination

The route handler shrinks to: resolve instance + room, parse cursor from headers, call the generator, wrap in `EventSourceResponse` with cache headers. ~15 lines.

### 6. Deduplicate router helpers

Extract `make_error_response` and `log_exception` into a shared routers helper module. All three routers import from there. Identical implementations today, so this is a pure deduplication — no behavior change.

## Testing Decisions

### What makes a good test

Tests should exercise external behavior through the module's interface, not implementation details. A test that breaks because an internal method was renamed or a private helper was refactored is a bad test. Tests should be:

- **Interface-focused**: call the public function/method, assert on the return value or observable side effects
- **Dependency-injected**: pass fakes for external dependencies (provider, DB, notifier) rather than monkeypatching globals
- **Isolated**: each test runs against its own DB state, doesn't share mutable singletons across tests

### Modules to test

**User-session module** — test credential exchange, token resolution, favorites. Mock HTTP responses from Jellyfin. Prior art: the existing user-session tests in `test_jellyfin_library.py` (lines ~1046+) which will move to a new test file with the same patterns but simpler setup (no library provider needed).

**Deck pipeline** — test the full pipeline: fetch → interleave → exclude swiped → validate → persist → return. Use `FakeProvider` (or a simple lambda) for deck fetching. Use a real in-memory DB for persistence. Test cases should cover: single media type, both media types (Balanced Interleaving), genre filter, Watched Filter, swiped exclusion, empty deck rejection. Prior art: `test_room_lifecycle.py` (824 lines) already tests some of this through the service layer, but the new tests will be more focused.

**TMDB pure module** — test `lookup_trailer` and `lookup_cast` with mocked HTTP responses. Test cases: successful lookup, no TMDB match, network failure returns `None`/`[]`, malformed response returns `None`/`[]`. No DB or provider needed. Prior art: `test_http_client.py` (266 lines) for HTTP mocking patterns.

**TMDB cache repository** — test `get` and `put` with a real in-memory DB. Test TTL expiry. Prior art: `test_session_event_repos.py` (398 lines) and `test_repositories.py` (449 lines) for repository test patterns.

**Session Event Stream generator** — test directly by calling the generator with: a fake notifier that fires on demand, a fake `is_disconnected` that returns `True` after N events, and a real in-memory DB session. Test cases: first attach (bootstrap), reconnect with cursor (replay), stale cursor (session_reset), heartbeat timing, session_closed termination. Prior art: `test_routes_sse.py` (580 lines) — many of its test scenarios will move here with dramatically simpler setup. The existing `test_routes_sse.py` shrinks to verifying SSE headers, content-type, and the thin route wiring.

### Modules NOT getting new tests

- The library I/O provider (already well-tested in `test_jellyfin_library.py`)
- Route handlers that become thin wrappers (tested adequately by existing integration tests)
- The deduplicated router helpers (trivial, tested indirectly by every route test)

## Out of Scope

- **New features**: This PRD is purely structural. No new user-facing behavior is added (TMDB caching improves performance but doesn't change what users see).
- **Frontend changes**: The HTML/JS client is untouched.
- **Auth model changes**: The identity flow (server-delegated vs. per-user token) is not redesigned — the user-session module preserves the existing behavior.
- **Multi-process / horizontal scaling**: The architecture remains single-process with SQLite.
- **Provider abstraction for multiple backends**: No new providers (e.g., Emby) are introduced. The ABC is deleted, not replaced.
- **Route path renames**: API routes keep their current paths.
- **SSE protocol changes**: The Session Event Stream wire format doesn't change — clients see the same events.

## Further Notes

- **Execution order matters.** The ABC deletion (step 1) should land first because it unblocks the provider split. The provider split (step 2) should land before the deck pipeline extraction (step 3) because step 3 depends on the provider's shape being stable. Steps 4 (TMDB) and 5 (SSE) are independent of each other and can be done in either order. Step 6 (helper dedup) is cleanup that can land anytime.
- **Migration required.** The TMDB cache table requires an Alembic migration (next in sequence after the existing `0004_session_event_ledger`).
- **CONTEXT.md vocabulary.** All domain terms used in this PRD (Swipe Deck, Media Candidate, Balanced Interleaving, Watched Filter, Genre Filter, Media Type Filter, Media Payload, Session Event Stream, Session Event Cursor, Session Event Ledger, Session Bootstrap Event, Session Instance) are already defined in the project glossary. No new domain terms are introduced — these extractions are structural, not conceptual.
- **The `DeckProvider` Protocol is the only surviving seam contract.** It moves from `room_lifecycle.py` to the new deck pipeline module. Future seams should follow the same pattern: define a Protocol at the point of use, not a monolithic ABC in a separate file.
