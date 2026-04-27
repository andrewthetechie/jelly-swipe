# Technology Stack

**Project:** Jelly Swipe (v2.0 — Architecture Tier Fix)
**Researched:** 2026-04-26
**Confidence:** HIGH

## Recommended Stack

### New Runtime Dependencies

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **Flask-Session** | >=0.8.0 | Server-side session storage | Stores Jellyfin tokens and session identity server-side; client receives only an HttpOnly session cookie with a session ID (never the token). Filesystem backend via cachelib is zero-config for a single-server Docker deployment. Brings `cachelib>=0.13.0` and `msgspec>=0.18.6` as transitive deps — no additional installs needed. |

### Existing Runtime Dependencies (NO changes needed)

| Technology | Version | Purpose | Why it stays |
|------------|---------|---------|-------------|
| **Flask** | >=3.1.3 | Web framework | Already provides `SESSION_COOKIE_HTTPONLY`, `SESSION_COOKIE_SAMESITE`, `SESSION_COOKIE_SECURE` config. No upgrade needed. |
| **gevent** | >=24.10 | Async I/O for SSE streaming | Works with Flask-Session's filesystem backend — filesystem I/O is cooperative under gevent workers. No conflicts. |
| **gunicorn** | >=25.3.0 | WSGI server with gevent workers | `-k gevent` worker class is compatible with Flask-Session. SSE streams work because session lookup happens at request start, before the long-lived response begins. |
| **werkzeug** | >=3.1.8 | WSGI utilities | Provides the underlying cookie signing and `SecureCookie` that Flask-Session replaces at the session interface level. Still used for routing, debugging, proxy fix. |
| **requests** | >=2.33.1 | HTTP client for Jellyfin/TMDB APIs | No change. Used by `JellyfinLibraryProvider` for server-to-Jellyfin API calls. |
| **python-dotenv** | >=1.2.2 | .env file loading | No change. |

### Development Dependencies (NO changes needed)

| Technology | Version | Purpose | Notes |
|------------|---------|---------|-------|
| **pytest** | >=9.0.0 | Test framework | Session tests use Flask test client with `with session_transaction()` |
| **pytest-cov** | >=6.0.0 | Coverage reporting | No change |
| **pytest-mock** | >=3.14.0 | Mocking utilities | Mock `get_provider()` and session store for unit tests |
| **responses** | >=0.25.0 | HTTP request mocking | Mock Jellyfin auth endpoints in session tests |
| **pytest-timeout** | >=2.3.0 | Test timeout prevention | No change |

## Flask-Session Configuration

### Recommended setup for Jelly Swipe

```python
from flask_session import Session
from cachelib.file import FileSystemCache

# Server-side session storage — tokens never leave the server
app.config.update(
    SESSION_TYPE='cachelib',
    SESSION_CACHELIB=FileSystemCache(
        threshold=500,
        cache_dir=os.path.join(os.path.dirname(DB_PATH), 'sessions'),
    ),
    SESSION_PERMANENT=False,               # Ephemeral — cleared when browser closes
    SESSION_USE_SIGNER=True,               # Sign session ID cookie with Flask secret_key
    SESSION_KEY_PREFIX='jswipe:',          # Namespace for session keys in store
    SESSION_COOKIE_HTTPONLY=True,           # Already Flask default — JS cannot read
    SESSION_COOKIE_SAMESITE='Lax',          # Already Flask default — CSRF mitigation
    SESSION_COOKIE_SECURE=False,            # LAN users often on HTTP; set True if behind HTTPS proxy
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),  # Max session age for cleanup
)
Session(app)
```

### What changes in the session flow

**Before (current):** Client stores Jellyfin token in `localStorage` → sends it via `Authorization` header on every request → server extracts token → resolves user ID.

**After (v2.0):** Client authenticates once → server stores token in server-side session → client gets opaque HttpOnly cookie → on subsequent requests, server reads token from session store (no client-supplied identity).

### Session data shape (server-side)

After login, the session dict will contain:

```python
session = {
    "jf_token": "<jellyfin_access_token>",   # Stored server-side only
    "jf_user_id": "<jellyfin_user_uuid>",    # Resolved once at login
    "active_room": "<pairing_code>",          # Room participation
    "my_user_id": "host_<hex>"|"guest_<hex>", # In-room identity
    "solo_mode": False,                       # Solo mode flag
}
```

The client never sees `jf_token` or `jf_user_id` — they live in the filesystem session store.

## SSE + Session Compatibility

**Key insight:** EventSource (SSE) automatically sends cookies with each request. With Flask-Session:

1. Client opens `EventSource('/room/stream')` → browser sends session cookie
2. Flask-Session middleware loads session data from filesystem at request start
3. SSE generator runs with full session access (room code, user identity)
4. Long-lived SSE stream holds the response open — session was already loaded

**No conflict with gevent workers:**
- Session filesystem I/O happens at request start (cooperative, fast)
- SSE polling loop (`time.sleep(1.5)`) already works under gevent monkey patching
- Multiple concurrent SSE connections each get their own session lookup

## RESTful Endpoint Restructuring

No new libraries required. This is Flask URL pattern changes using built-in `<variable>` converters:

| Current Pattern | RESTful Pattern | HTTP Method | Notes |
|----------------|-----------------|-------------|-------|
| `/room/create` | `/rooms` | POST | Collection pattern |
| `/room/join` | `/rooms/{code}/join` | POST | Action on specific room |
| `/room/go-solo` | `/rooms/{code}/solo` | POST | Action on specific room |
| `/room/swipe` | `/rooms/{code}/swipes` | POST | Sub-collection pattern |
| `/room/status` | `/rooms/{code}` | GET | Resource read |
| `/room/stream` | `/rooms/{code}/stream` | GET | SSE stream |
| `/room/quit` | `/rooms/{code}` | DELETE | Resource deletion |
| `/matches` | `/rooms/{code}/matches` | GET | Sub-resource |
| `/matches/delete` | `/rooms/{code}/matches/{movie_id}` | DELETE | Specific match |
| `/undo` | `/rooms/{code}/swipes/{movie_id}` | DELETE | Undo last swipe |
| `/movies` | `/rooms/{code}/movies` | GET | Room's deck |
| `/genres` | `/genres` | GET | Static — no room context |

**Implementation:** Flask's built-in `<string:code>` URL converter. No additional library needed.

```python
@app.route('/rooms/<string:code>/swipes', methods=['POST'])
def create_swipe(code):
    # code comes from URL, not session
    # session provides user identity
    ...
```

**Identity from session, room from URL:** The room code moves out of session and into the URL path. The session cookie carries only identity (token + user_id). This eliminates the need for `session["active_room"]` in most routes.

## Installation

```bash
# Add Flask-Session to runtime dependencies
uv add flask-session>=0.8.0

# That's it — cachelib and msgspec come as transitive dependencies
# No other new packages needed
```

### pyproject.toml change

```toml
dependencies = [
    "flask>=3.1.3",
    "flask-session>=0.8.0",     # NEW: server-side session storage
    "gevent>=24.10",
    "gunicorn>=25.3.0",
    "python-dotenv>=1.2.2",
    "requests>=2.33.1",
    "werkzeug>=3.1.8",
]
```

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| **Flask-Session (cachelib/filesystem)** | Flask default cookie session | Cookie session stores data client-side (base64-readable even if signed). Jellyfin tokens would be exposed in the cookie payload. Server-side storage keeps tokens on the server. |
| **Flask-Session (cachelib/filesystem)** | Flask-Session with Redis backend | Redis is overkill for a single-server self-hosted Docker app. Adds an external service dependency that operators must manage. Filesystem backend is zero-config. |
| **Flask-Session (cachelib/filesystem)** | Flask-Session with SQLAlchemy backend | Would require adding Flask-SQLAlchemy as a dependency. The existing codebase uses raw `sqlite3` — adding an ORM layer for session storage alone is unnecessary complexity. |
| **Flask-Session (cachelib/filesystem)** | Custom SQLite session table | Would work but requires implementing serialization, expiry, cleanup, and cookie management from scratch. Flask-Session is a ~100-line config that handles all of this. |
| **Flask-Session** | Flask-Login | Flask-Login manages user authentication flows (login/logout/remember-me) with a User model. Jelly Swipe doesn't have a User model — identity comes from Jellyfin. The app just needs session storage, not a full auth framework. |
| **Flask-Session** | itsdangerous URL-safe serializer | Could sign tokens and store them in cookies, but this still sends token data to the client. Server-side storage is the goal. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **Flask-SQLAlchemy** | Adds ORM dependency for a codebase that uses raw sqlite3. Only needed if Flask-Session's SQLAlchemy backend is chosen. | Raw sqlite3 (existing) + Flask-Session cachelib/filesystem backend |
| **Redis** | External service that Docker operators must manage. Not justified for a self-hosted single-server app with ~2 concurrent users. | Filesystem session storage via cachelib |
| **Flask-SocketIO** | Would replace SSE with WebSocket. SSE already works with gevent workers. Switching adds a dependency and breaks the existing SSE architecture for no functional benefit. | Keep existing SSE with EventSource |
| **Flask-Login** | Requires a User model and login/logout flow. Jelly Swipe identity comes from Jellyfin — there's no local user table to manage. | Store Jellyfin identity directly in Flask-Session |
| **JWT tokens** | Moving tokens from localStorage to JWT cookies adds complexity (signing, expiry, refresh). Flask-Session's server-side storage is simpler and more secure — tokens never leave the server. | Flask-Session server-side storage |
| **Flask-Session `filesystem` backend** | Deprecated since Flask-Session 0.7.0, will be removed in 1.0.0. | `SESSION_TYPE='cachelib'` with `FileSystemCache` — identical behavior, supported future |

## Stack Patterns by Variant

**If running behind an HTTPS reverse proxy (Traefik, Caddy, nginx):**
- Set `SESSION_COOKIE_SECURE=True` via env var
- Add `proxy_set_header X-Forwarded-Proto $scheme` in nginx config
- Flask's `ProxyFix` already handles `X-Forwarded-Proto`

**If running on HTTP (LAN, Unraid default):**
- Keep `SESSION_COOKIE_SECURE=False` (default) — otherwise cookies won't be sent
- The signed session cookie still provides tamper protection
- Tokens are server-side only, so HTTP exposure is limited to the session ID

**If scaling to multiple gunicorn workers:**
- Filesystem sessions break across workers if each worker has its own filesystem view
- For Docker single-worker (`--workers 1`), this is not an issue
- If multi-worker needed, switch to `SESSION_TYPE='sqlalchemy'` with the existing SQLite DB

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| Flask-Session 0.8.0 | Flask >=2.2, Python 3.13 | Verified via pip dry-run. Uses msgspec for serialization (fast, no pickle). |
| cachelib 0.13.0 | Flask-Session >=0.7.0 | Transitive dependency of Flask-Session 0.8.0. Provides `FileSystemCache`. |
| msgspec >=0.18.6 | Python 3.13 | Transitive dependency of Flask-Session 0.8.0. Fast JSON/msgpack serialization for session data. |
| gevent >=24.10 | Flask-Session filesystem backend | Filesystem I/O is cooperative under gevent monkey patching. No conflicts. |
| gunicorn gevent worker | Flask-Session | Session lookup at request start, before SSE streaming begins. No thread-local conflicts. |

## Docker Considerations

**Session storage location:** `/app/data/sessions/` — alongside the existing SQLite database at `/app/data/jellyswipe.db`. Both should be volume-mounted for persistence:

```yaml
volumes:
  - ./data:/app/data  # Contains jellyswipe.db AND sessions/
```

**Session cleanup:** Flask-Session supports `SESSION_CLEANUP_N_REQUESTS` for non-TTL backends. For filesystem sessions with `SESSION_PERMANENT=False`, expired sessions are cleaned up on each request when the threshold is reached. Alternatively, run `flask session_cleanup` periodically.

## Sources

- **Flask-Session 0.8.0** (/pallets-eco/flask-session via Context7) — cachelib backend configuration, filesystem session setup, SESSION_USE_SIGNER, cleanup options (HIGH confidence)
- **Flask** (/pallets/palletsprojects.com via Context7) — SESSION_COOKIE_HTTPONLY defaults to True, SESSION_COOKIE_SAMESITE defaults to 'Lax', cookie security configuration (HIGH confidence)
- **Flask-Session pip dry-run** — Verified cachelib 0.13.0 and msgspec are transitive dependencies of flask-session 0.8.0 (HIGH confidence)
- **Gevent** (/gevent/gevent via Context7) — monkey patching, cooperative I/O, filesystem compatibility (HIGH confidence)
- **Flask-Session config reference** (github.com/pallets-eco/flask-session) — `filesystem` backend deprecated since 0.7.0, use `cachelib` backend with `FileSystemCache` instead (HIGH confidence)

---
*Stack research for: Jelly Swipe v2.0 — Architecture Tier Fix (server-side identity, session tokens, RESTful endpoints)*
*Researched: 2026-04-26*
