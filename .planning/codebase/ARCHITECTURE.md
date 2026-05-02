<!-- refreshed: 2026-05-01 -->
# Architecture

**Analysis Date:** 2026-05-01

## System Overview

```text
┌─────────────────────────────────────────────────────────────────────┐
│                    Browser (SPA — app.js)                           │
│  Login → Host/Join Room → Swipe Deck → SSE Event Stream             │
└────────┬──────────────────────────────────────────┬────────────────┘
         │ HTTP + session cookie                     │ EventSource SSE
         ▼                                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│             Flask Application  (jellyswipe/__init__.py)             │
│                                                                     │
│  ┌───────────────┐  ┌───────────────┐  ┌──────────────────────┐   │
│  │ Auth Routes   │  │  Room Routes  │  │  Media/Proxy Routes  │   │
│  │ /auth/*  /me  │  │ /room/<code>  │  │  /proxy  /get-trailer │   │
│  └──────┬────────┘  └──────┬────────┘  │  /cast  /genres       │   │
│         │                  │           └──────────┬────────────┘   │
│         │   @login_required (jellyswipe/auth.py)  │               │
│         ▼                  ▼                      │               │
│  ┌────────────────────────────────────────────┐  │               │
│  │      Token Vault  (jellyswipe/db.py)        │  │               │
│  │  user_tokens · rooms · swipes · matches     │  │               │
│  └────────────────────────────────────────────┘  │               │
└──────────────────────────────────────────────────┼───────────────┘
                                                    │
         ┌──────────────────────────────────────────┤
         ▼                                          ▼
┌──────────────────────┐           ┌─────────────────────────────┐
│  JellyfinLibrary     │           │  TMDB API (external)        │
│  Provider            │           │  /3/search/movie            │
│  (jellyfin_library.py│           │  /3/movie/{id}/videos       │
│  implements base.py) │           │  /3/movie/{id}/credits      │
└──────────────────────┘           └─────────────────────────────┘
         │
         ▼
┌──────────────────────┐
│  Jellyfin Server     │
│  REST API (upstream) │
└──────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Flask app factory | App wiring, all route definitions, middleware, CSP | `jellyswipe/__init__.py` |
| `LibraryMediaProvider` | Abstract interface for library backends | `jellyswipe/base.py` |
| `JellyfinLibraryProvider` | Jellyfin REST client, deck fetch, images, server auth | `jellyswipe/jellyfin_library.py` |
| Token vault / DB | SQLite schema, session CRUD, migrations | `jellyswipe/db.py` |
| Auth module | Session cookie management, `@login_required` | `jellyswipe/auth.py` |
| HTTP client | Centralized outbound HTTP with timeout + logging | `jellyswipe/http_client.py` |
| Rate limiter | In-memory token-bucket, per-(endpoint, IP) | `jellyswipe/rate_limiter.py` |
| SSRF validator | Boot-time Jellyfin URL safety check | `jellyswipe/ssrf_validator.py` |
| SPA client | Single-page app, swipe UI, SSE consumer | `jellyswipe/static/app.js` |
| Service worker | PWA shell; explicitly bypasses SSE requests | `jellyswipe/static/sw.js` |

## Pattern Overview

**Overall:** Server-rendered shell SPA with REST + SSE

**Key Characteristics:**
- Single HTML shell (`jellyswipe/templates/index.html`) served by Flask; all interactivity in `jellyswipe/static/app.js`
- No client-side framework — vanilla JS DOM manipulation
- Flask factory pattern via `create_app()`, test-injectable via `test_config` dict
- One provider abstraction (`LibraryMediaProvider`) with one concrete implementation (`JellyfinLibraryProvider`)
- Module-level singletons: `_provider_singleton` (lazy init), `rate_limiter` (eager init)

## Layers

**Presentation Layer (Browser):**
- Purpose: SPA UI, drag gesture, SSE event consumption
- Location: `jellyswipe/static/app.js`, `jellyswipe/templates/index.html`, `jellyswipe/static/styles.css`
- Contains: UI state machine, swipe gesture engine, SSE listener, API calls
- Depends on: Flask JSON API, SSE stream endpoint
- Key pattern: `apiFetch()` wraps all mutating requests with `credentials: 'same-origin'` and intercepts 401s to show session-expired banner

**Application Layer (Flask routes):**
- Purpose: Request handling, auth enforcement, business logic for rooms/swipes/matches
- Location: `jellyswipe/__init__.py` (all routes defined inside `create_app()` closure)
- Contains: All Flask route handlers, middleware hooks, XSS-safe JSON provider
- Depends on: Auth module, DB, provider singleton, rate limiter
- Note: Route handlers are closures that capture `get_provider()`, `TMDB_AUTH_HEADERS`, `JELLYFIN_URL`, and `get_db`

**Auth Layer:**
- Purpose: Session identity — cookie → vault lookup → `g.user_id` + `g.jf_token`
- Location: `jellyswipe/auth.py`
- Contains: `create_session()`, `get_current_token()`, `destroy_session()`, `@login_required`
- Key design: Vault-only trust (no Jellyfin API call per request). Sessions expire after 24h. `session_id` is `secrets.token_hex(32)`.

**Library Layer:**
- Purpose: Abstract media provider — genres, deck, images, TMDB item resolution
- Location: `jellyswipe/base.py` (interface), `jellyswipe/jellyfin_library.py` (implementation)
- Contains: `LibraryMediaProvider` ABC, `JellyfinLibraryProvider` with retry + token refresh
- Depends on: `http_client.make_http_request` for TMDB calls; internal `requests.Session` for Jellyfin

**Security Layer:**
- Purpose: Defense-in-depth — SSRF guard, rate limiting, image path allowlist, CSP
- Location: `jellyswipe/ssrf_validator.py`, `jellyswipe/rate_limiter.py`, proxy regex in `jellyswipe/__init__.py`
- Applied at: boot time (SSRF), per-request (rate limiter, proxy path check), response (CSP header)

**Data Layer:**
- Purpose: SQLite persistence — rooms, swipes, matches, token vault
- Location: `jellyswipe/db.py`
- Contains: Schema init with in-place migration (ALTER TABLE), WAL mode setup, `get_db()` / `get_db_closing()`, `cleanup_expired_tokens()`
- Key design: WAL journal mode enables concurrent SSE readers without blocking write transactions

## Data Flow

### Authentication — Delegate Mode (EPIC-05 default)

1. `window.onload` in `app.js` calls `GET /me` — gets 401
2. Client calls `GET /auth/provider` — gets `{"jellyfin_browser_auth": "delegate"}`
3. Client calls `POST /auth/jellyfin-use-server-identity`
4. Server calls `get_provider().server_access_token_for_delegate()` (server's own Jellyfin API key/password)
5. `create_session()` stores `(session_id, jf_token, jf_user_id)` in `user_tokens` vault, sets `session['session_id']` cookie
6. Returns `{"userId": uid}` — client never sees a Jellyfin token

### Authentication — Username/Password Mode

1. Same `GET /auth/provider` probe
2. Client prompts for credentials, calls `POST /auth/jellyfin-login`
3. Server calls `get_provider().authenticate_user_session(username, password)` against Jellyfin
4. `create_session()` vaults the resulting user token
5. All subsequent requests resolved via vault lookup only

### Swipe & Match Detection

1. User drags card past 120px threshold in `app.js` → `POST /room/<code>/swipe`
2. Route inserts swipe record, advances `deck_position` cursor for this user
3. If `direction == right`: resolves title via Jellyfin, checks for matching right-swipe from another session
4. On match: writes to `matches` table and sets `last_match_data` on room (JSON blob with `ts` timestamp)
5. SSE stream polling detects changed `last_match_ts` → pushes `last_match` event to all connected clients
6. Clients display match popup from SSE data — the HTTP swipe response does NOT carry match info

### SSE Room Stream

1. Client calls `GET /room/<code>/stream`
2. Server opens a persistent SQLite connection for the stream lifetime (DB-02 pattern)
3. Generator polls every ~1.5s + jitter (`random.uniform(0, 0.5)`)
4. Compares `ready`, `current_genre`, `last_match_ts` against last-seen values
5. Emits `data: {JSON}\n\n` only on change — silent polls produce no bytes
6. Emits `: ping\n\n` heartbeat if no data event for ≥15 seconds
7. `closed: true` event emitted when room row disappears; client tears down `EventSource`
8. Generator handles `GeneratorExit` (client disconnect) silently
9. Hard deadline: 3600s, then stream closes naturally
10. Uses `gevent.sleep` when available; falls back to `time.sleep`

```text
Client                                  Server generator
  |--GET /room/<code>/stream---------->|
  |                                    | open SQLite conn
  |<--data: {"ready":false, ...}-------|  poll #1 — state differs from None
  |<--: ping---------------------------|  poll #N — idle for 15s
  |<--data: {"last_match": {...}}------|  match detected
  |<--data: {"closed": true}----------|  room deleted
  |  close EventSource                 | generator returns, conn.close()
```

### Image Proxy

1. Client requests `/proxy?path=jellyfin/<id>/Primary`
2. Route validates path against `^jellyfin/([0-9a-fA-F]{32}|[0-9a-fA-F-]{36})/Primary$` (403 on mismatch)
3. Calls `get_provider().fetch_library_image(path)` — same regex re-validated in provider
4. Provider fetches from Jellyfin with auth headers, returns `(bytes, content_type)`
5. Rate-limited: 200 req/min per IP

### TMDB Enrichment (trailer / cast)

1. Route calls `get_provider().resolve_item_for_tmdb(movie_id)` → `SimpleNamespace(title, year)`
2. `make_http_request()` calls TMDB `/search/movie?query=...&year=...` with `Authorization: Bearer` header
3. Second call to `/movie/{tmdb_id}/videos` or `/credits`
4. Rate-limited: 200 req/min per IP

## Key Abstractions

**`LibraryMediaProvider` (ABC):**
- Purpose: Decouples routes from Jellyfin specifics; enables test injection
- Location: `jellyswipe/base.py`
- Methods: `reset()`, `list_genres()`, `fetch_deck()`, `resolve_item_for_tmdb()`, `server_info()`, `fetch_library_image()`
- Pattern: `FakeProvider` in `tests/conftest.py` covers all methods for route tests; injected via `monkeypatch.setattr(jellyswipe_module, "_provider_singleton", fake_provider)`

**Token Vault:**
- Purpose: Server-side session storage — client holds only a session cookie, never a Jellyfin token
- Table: `user_tokens(session_id PK, jellyfin_token, jellyfin_user_id, created_at)`
- Expiry: 24h TTL enforced by `cleanup_expired_tokens()` at boot and on every new session creation

**Room:**
- Purpose: Shared swiping session between 1–2 users
- Table: `rooms(pairing_code PK, movie_data TEXT, ready, current_genre, solo_mode, last_match_data, deck_position, deck_order)`
- `movie_data`: Full deck JSON snapshot stored at room creation
- `deck_position`: Per-user cursor map stored as JSON `{"user_id": int}`
- `last_match_data`: JSON blob with `ts` field used as SSE change sentinel

## Entry Points

**HTTP Server:**
- Location: `jellyswipe/__init__.py` (module bottom: `app = create_app()`)
- Gunicorn entrypoint: `jellyswipe:app`
- Gunicorn config: `-k gevent --worker-connections 1000` (Dockerfile CMD)
- Port: 5005

**`create_app(test_config=None)`:**
- Env var validation and SSRF check fire at module import time (outside factory, before `create_app` is called)
- Factory sets up `ProxyFix`, XSS-safe JSON provider, CSP header hook, request ID injection
- Initializes SQLite DB via `init_db()`
- `test_config` dict overrides `app.config` entries; `DB_PATH` key also patches `jellyswipe.db.DB_PATH`

## SSRF Protection

- Runs at import time, not per-request
- Validates scheme (http/https only), resolves hostname via DNS, rejects RFC 1918 + loopback + cloud metadata IP ranges
- Bypass: `ALLOW_PRIVATE_JELLYFIN=1` env var (required for self-hosted Docker deployments)
- Location: `jellyswipe/ssrf_validator.py`
- Image proxy has a second defense: strict regex prevents path traversal — only `jellyfin/{id}/Primary` accepted

## Rate Limiting

- In-memory token-bucket, zero external dependencies
- Module-level singleton: `jellyswipe/rate_limiter.py` → `rate_limiter = RateLimiter()`
- Keyed by `(endpoint_name, client_ip)` tuple
- Configured limits in `_RATE_LIMITS` dict inside `jellyswipe/__init__.py`:
  - `get-trailer`: 200/min
  - `cast`: 200/min
  - `watchlist/add`: 300/min
  - `proxy`: 200/min
- 429 response includes `Retry-After` header (seconds until next token)
- Buckets evicted after 300s inactivity or when cap of 10,000 buckets exceeded

## Security Headers and XSS Defense

**CSP (applied via `@app.after_request` hook in `create_app`):**
```
default-src 'self';
script-src 'self';
object-src 'none';
img-src 'self' https://image.tmdb.org;
frame-src https://www.youtube.com
```

**XSS-safe JSON provider (`_XSSSafeJSONProvider`):**
- Replaces `<`, `>`, `&` with Unicode escapes in all JSON responses
- Applied to entire app via `app.json = _XSSSafeJSONProvider(app)`

**DOM construction in client:**
- All dynamic content uses `textContent` / `createElement` + property assignment — no `innerHTML` with user data

## v2.0 Server Identity Design (EPIC-05)

**Motivation:** Pre-v2.0, the client transmitted Jellyfin tokens in request headers. This exposed tokens and required complex client-side token management.

**Current design:**
- Server authenticates to Jellyfin once using its own credentials (API key or username/password)
- `POST /auth/jellyfin-use-server-identity` delegates the session to the server's own Jellyfin identity
- Client receives only a session cookie; `g.user_id` and `g.jf_token` are resolved from the vault per-request
- Identity alias headers (`X-Provider-User-Id`, `X-Jellyfin-User-Id`, `X-Emby-UserId`) are **rejected** as spoofing attempts — `_request_has_identity_alias_headers()` returns null user_id

**Token-to-user-id resolution cache:**
- `_token_user_id_cache` (module-level dict in `__init__.py`): caches `sha256(token) → (user_id, expires_at)` for 300s
- Prevents repeated Jellyfin `/Users/Me` calls within a session window

## Architectural Constraints

- **Threading:** Single gevent event loop (gunicorn `-k gevent`). SSE generator uses `gevent.sleep` for cooperative yield. All DB access is synchronous SQLite.
- **Global state:** `_provider_singleton` (lazy, in `jellyswipe/__init__.py`), `rate_limiter` (eager, in `jellyswipe/rate_limiter.py`), `_token_user_id_cache` (dict, in `jellyswipe/__init__.py`), `jellyswipe.db.DB_PATH` (in `jellyswipe/db.py`)
- **Circular imports:** None. `jellyswipe/__init__.py` imports from all submodules; none import back from `__init__`.
- **SSE + WAL:** SSE generator holds a persistent SQLite connection. WAL journal mode (set in `init_db`) allows concurrent readers without blocking writers. Do NOT change journal mode.
- **No async/await server-side:** Flask + gevent greenlets only. All I/O is synchronous but non-blocking via gevent monkey-patching.

## Error Handling

**Strategy:** Structured logging with sanitized JSON responses

**Patterns:**
- All 5xx responses return `{'error': 'Internal server error', 'request_id': '...'}` — actual exception never sent to client
- `log_exception()` captures `request_id`, `route`, `method`, `exception_type`, `stack_trace` as structured fields
- `request_id` format: `req_{unix_ts}_{4-byte hex}`, injected via `@app.before_request`, echoed in `X-Request-Id` response header
- Provider `RuntimeError` mapped to 404 or 503 based on message content
- Rate limit 429 includes `Retry-After` header

## Anti-Patterns

### Long-lived SQLite Connection in SSE Generator
**What happens:** `room_stream()` calls `sqlite3.connect()` directly instead of `get_db()`.
**Why it's correct:** This is intentional — the SSE generator needs a connection that lives for the full stream duration. `get_db_closing()` is designed for short request-scoped use.
**Rule:** Use `get_db_closing()` in all route handlers. Use direct `sqlite3.connect()` only in the SSE generator.

### Module-Level Env Var Validation
**What happens:** `jellyswipe/__init__.py` validates env vars and runs SSRF check at module import time (outside `create_app()`).
**Why it matters:** Requires env vars to be set before any import. Tests work around this via `os.environ.setdefault()` in `conftest.py` and `ALLOW_PRIVATE_JELLYFIN=1`.
**Rule:** Do not add new validation outside `create_app()`. New checks belong inside the factory.

---

*Architecture analysis: 2026-05-01*
