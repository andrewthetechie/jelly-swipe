# Architecture Research: Outbound HTTP Hardening (v1.6)

**Domain:** Centralized outbound HTTP, rate limiting, SSRF validation, error redaction for an existing Flask+gevent app
**Researched:** 2026-04-26
**Confidence:** HIGH

## Executive Summary

The current codebase has **six raw `requests.get()` calls** in Flask routes (TMDB trailer/cast lookups in `__init__.py`) and a `requests.Session` in `JellyfinLibraryProvider` with scattered timeout values (15s, 30s, 60s, 90s). The hardening work introduces five new capabilities that must integrate without breaking the existing provider abstraction (`LibraryMediaProvider` in `base.py`) or the gunicorn+gevent deployment model.

The recommended architecture creates **one new module** (`jellyswipe/http_client.py`) as the single point of control for all outbound HTTP, plus a **rate limiter class** that lives in the same module. The provider's existing `requests.Session` is replaced by the centralized client. TMDB calls in routes are rewritten to go through the centralized client with Bearer auth. Error redaction is a Flask `@app.errorhandler` + request ID middleware. SSRF validation is a pure function called at boot.

**Gevent compatibility is straightforward**: cooperative scheduling means plain `dict` + `time.time()` for the rate limiter is safe without `threading.Lock`. The `requests` library already works under gevent's monkey-patching.

## Current State (Pre-Hardening)

### Outbound HTTP Call Inventory

**`jellyswipe/__init__.py` — 6 raw `requests.get()` calls, zero timeouts:**

| Location | Line | Call | Current Auth | Timeout |
|----------|------|------|-------------|---------|
| `get_trailer()` | 187 | TMDB `/search/movie` | `?api_key=KEY` in URL | **None** |
| `get_trailer()` | 191 | TMDB `/movie/{id}/videos` | `?api_key=KEY` in URL | **None** |
| `get_cast()` | 206 | TMDB `/search/movie` | `?api_key=KEY` in URL | **None** |
| `get_cast()` | 210 | TMDB `/movie/{id}/credits` | `?api_key=KEY` in URL | **None** |

**`jellyswipe/jellyfin_library.py` — `requests.Session` with inconsistent timeouts:**

| Method | Line | Timeout | Notes |
|--------|------|---------|-------|
| `_api()` (central) | 144 | 90s | All generic Jellyfin calls |
| `_login_from_env()` | 91 | 30s | Auth |
| `_verify_items()` | 119 | 30s | Post-login probe |
| `_user_id()` fallback | 180 | 30s | `/Users` list |
| `server_info()` fallback | 354 | 15s | Raw `requests.get()` (not through session!) |
| `fetch_library_image()` | 369 | 60s | Binary image |
| `authenticate_user_session()` | 418 | 30s | User login |
| `resolve_user_id_from_token()` | 442 | 30s | Token → user ID |
| `resolve_user_id_from_token()` fallback | 450 | 30s | `/Users` list |
| `add_to_user_favorites()` | 476 | 30s | Favorite add |

### Existing Error Handling Pattern

Every route uses `try/except Exception as e` returning `jsonify({'error': str(e)})` with status 500. This **leaks upstream exception text** (e.g., Jellyfin error messages, connection refused details) directly to the client.

## Recommended Architecture

### New Components

```
jellyswipe/
├── __init__.py              # MODIFIED — use http_client, add rate limiter, redact errors
├── http_client.py           # NEW — centralized HTTP, rate limiter, SSRF validation
├── jellyfin_library.py      # MODIFIED — use http_client instead of raw requests.Session
├── base.py                  # UNCHANGED
└── db.py                    # UNCHANGED
```

### System Diagram (Post-Hardening)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Flask Routes (__init__.py)                    │
│                                                                      │
│  /get-trailer ─┐                                                    │
│  /cast ────────┤  rate_limited()     tmdb_get()    redact_errors()  │
│  /proxy ───────┤  ───────────►  ───────────────►  ────────────────  │
│  /watchlist/add┘     ↓                 ↓                ↓           │
│                   TokenBucket    http_client.py    error_handler    │
└──────────────────────┬───────────────┬──────────────────────────────┘
                       │               │
                       ▼               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     http_client.py (NEW)                              │
│                                                                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────────┐ │
│  │  HttpClient       │  │  tmdb_get()      │  │  TokenBucketRate   │ │
│  │  .get(url, opts)  │  │  (path, params)  │  │  Limiter           │ │
│  │  .post(url, opts) │  │  Bearer header   │  │  per-IP buckets    │ │
│  │  timeout enforce  │  │  no key in URL   │  │  gevent-safe       │ │
│  │  User-Agent       │  │  timeout enforce │  │                    │ │
│  │  structured log   │  └──────────────────┘  └────────────────────┘ │
│  └──────────────────┘                                                │
│  ┌──────────────────┐                                                │
│  │  validate_url()  │  ← SSRF guard, called at boot on JELLYFIN_URL │
│  │  reject 169.254  │                                                │
│  │  allow loopback   │                                                │
│  │  allow RFC 1918   │                                                │
│  └──────────────────┘                                                │
└──────────────────────────┬───────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│              JellyfinLibraryProvider (MODIFIED)                       │
│                                                                      │
│  Replaces self._session = requests.Session()                         │
│  with HttpClient instance for all Jellyfin calls                     │
│  (keeps existing retry/reset logic intact)                           │
└──────────────────────────────────────────────────────────────────────┘
```

### Component Boundaries

| Component | Responsibility | New or Modified | Communicates With |
|-----------|---------------|-----------------|-------------------|
| `http_client.HttpClient` | All outbound HTTP with enforced timeouts, User-Agent, structured logging | **NEW** | `requests` library (wraps it) |
| `http_client.tmdb_get()` | TMDB API calls with Bearer auth, no key in URL | **NEW** (helper on module) | `HttpClient` |
| `http_client.TokenBucketRateLimiter` | Per-IP token-bucket rate limiting | **NEW** | Flask routes (decorator) |
| `http_client.validate_jellyfin_url()` | SSRF URL validation at boot | **NEW** (pure function) | `__init__.py` at module load |
| `__init__.py` routes | Use `tmdb_get()` instead of raw `requests.get()` | **MODIFIED** | `http_client` |
| `__init__.py` error handler | `@app.errorhandler(500)` with request ID, redacted body | **MODIFIED** | Flask, `http_client` |
| `jellyfin_library.py` | Replace `requests.Session` with `HttpClient` | **MODIFIED** | `http_client` |
| `base.py` | Abstract provider contract | **UNCHANGED** | — |
| `db.py` | SQLite operations | **UNCHANGED** | — |

### Data Flow

#### TMDB Call (Post-Hardening)

```
Route handler (get_trailer)
  → @rate_limited()          # TokenBucket check on client IP
  → @redact_errors()         # Catch-all → generic 500 + request_id
  → tmdb_get("/search/movie", params={query, year})
      → HttpClient.get()
          → Enforces timeout=(3.05, 10)
          → Adds Authorization: Bearer <token> header
          → Adds User-Agent: JellySwipe/1.0
          → Logs request start/error at DEBUG level
      → Returns parsed JSON
  → Returns jsonify result or raises
```

#### Jellyfin Call (Post-Hardening)

```
JellyfinLibraryProvider._api()
  → self._client.request("GET", path, ...)
      → HttpClient.request()
          → Enforces timeout=(3.05, 30) (or caller-specified)
          → Adds User-Agent: JellySwipe/1.0
          → Logs at DEBUG level
      → Returns response
  → Provider handles 401 retry/reset as before
```

#### SSRF Validation (At Boot)

```
__init__.py module load
  → validate_jellyfin_url(JELLYFIN_URL)
      → Parse URL with urllib.parse
      → Resolve hostname to IP via socket.getaddrinfo
      → Reject: 169.254.0.0/16 (metadata)
      → Reject: 0.0.0.0/8, 224.0.0.0/4 (special)
      → Allow: 127.0.0.0/8 (loopback)
      → Allow: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16 (RFC 1918)
      → Allow: public IPs (normal Jellyfin servers)
      → Raises RuntimeError on reject → app won't start
```

## Detailed Design Decisions

### Decision 1: Single `http_client.py` Module (Not a Package)

**Use one module** rather than splitting into `jellyswipe/http/` with `__init__.py`, `client.py`, `rate_limiter.py`, `ssrf.py`.

**Why:** The total new code is ~150-200 lines. A package adds import complexity (`from jellyswipe.http.client import HttpClient`) for zero benefit at this scale. One module keeps all HTTP concerns co-located and discoverable.

**When to split:** If the module exceeds ~400 lines or a second external service (beyond TMDB/Jellyfin) is added, promote to a package.

### Decision 2: `HttpClient` Wraps `requests` (Not a Replacement)

**Wrap `requests`** with a thin class that enforces timeouts, adds User-Agent, and logs — don't reach for `httpx` or `aiohttp`.

**Why:**
- `requests` is already a dependency and already works with gevent's monkey-patching
- The provider's retry/reset/auth logic is tightly coupled to `requests.Response` objects
- Swapping HTTP libraries is a high-risk, low-reward change in a security-focused milestone
- `httpx` would add a new dependency and its gevent compatibility requires careful configuration

**HttpClient shape:**

```python
class HttpClient:
    """Centralized HTTP client with enforced timeouts and structured logging."""

    DEFAULT_TIMEOUT = (3.05, 10)  # (connect, read) in seconds
    USER_AGENT = "JellySwipe/1.0"

    def __init__(self, *, timeout=None, headers=None):
        self._session = requests.Session()
        self._timeout = timeout or self.DEFAULT_TIMEOUT
        if headers:
            self._session.headers.update(headers)
        self._session.headers["User-Agent"] = self.USER_AGENT

    def get(self, url, **kwargs):
        kwargs.setdefault("timeout", self._timeout)
        return self._session.get(url, **kwargs)

    def post(self, url, **kwargs):
        kwargs.setdefault("timeout", self._timeout)
        return self._session.post(url, **kwargs)

    def request(self, method, url, **kwargs):
        kwargs.setdefault("timeout", self._timeout)
        return self._session.request(method, url, **kwargs)
```

**Key behavior:** If a caller passes `timeout=`, the explicit value wins (allows provider's `fetch_library_image` to keep its 60s timeout for large images). The default is always applied when omitted.

### Decision 3: TMDB Bearer Auth via Module-Level Helper

TMDB's "API Read Access Token" (already stored as `TMDB_API_KEY`) doubles as a Bearer token. Per TMDB docs (HIGH confidence, verified via Context7 and official docs):

> "The default method to authenticate is with your access token... This token is expected to be sent along as an Authorization header... Using the Bearer token has the added benefit of being a single authentication process that you can use across both the v3 and v4 methods."

**This means the env var `TMDB_API_KEY` already IS the Bearer token.** No new env var needed. Just change the call pattern:

```python
# BEFORE (leaks key in URLs, no timeout)
r = requests.get(f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query=...").json()

# AFTER (Bearer header, timeout enforced, no key in URL)
def tmdb_get(path: str, *, params: dict = None) -> dict:
    """TMDB API call with Bearer auth. Never puts key in URL."""
    url = f"https://api.themoviedb.org/3{path}"
    headers = {"Authorization": f"Bearer {TMDB_API_KEY}"}
    r = _shared_client.get(url, params=params, headers=headers, timeout=(3.05, 10))
    r.raise_for_status()
    return r.json()
```

**No env var rename needed.** The existing `TMDB_API_KEY` contains the "API Read Access Token" — same string, different delivery mechanism.

### Decision 4: Token-Bucket Rate Limiter (In-Memory, Gevent-Safe)

**Use a simple dict-based token bucket** per client IP, no external store, no threading locks.

**Gevent safety reasoning:** Gevent uses cooperative scheduling. Between `time.sleep()` calls (which yield to the event loop), a single greenlet executes atomically. The rate limiter's read-check-update on a dict is a single code path with no yields, making it inherently atomic under gevent. No `threading.Lock` needed.

```python
class TokenBucketRateLimiter:
    """Per-IP token bucket rate limiter. Gevent-safe (cooperative scheduling)."""

    def __init__(self, rate: float = 10, capacity: int = 20):
        self._rate = rate          # Tokens per second
        self._capacity = capacity  # Max burst
        self._buckets: dict[str, tuple[float, float]] = {}  # ip → (tokens, last_refill)

    def allow(self, key: str) -> bool:
        now = time.time()
        tokens, last = self._buckets.get(key, (self._capacity, now))
        elapsed = now - last
        tokens = min(self._capacity, tokens + elapsed * self._rate)
        if tokens >= 1.0:
            self._buckets[key] = (tokens - 1.0, now)
            return True
        self._buckets[key] = (tokens, now)
        return False
```

**Rate/capacity tuning:** 10 tokens/sec with capacity 20 means a single IP can burst 20 requests then sustain 10/sec. This is generous for a home-network movie swiping app but prevents abuse of the TMDB proxy endpoints.

**Cleanup:** Add a periodic sweep of stale entries (IPs with no activity in >5 minutes) to prevent unbounded memory growth in long-running gunicorn workers.

**Applied via decorator:**

```python
_rate_limiter = TokenBucketRateLimiter(rate=10, capacity=20)

def rate_limited(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        ip = request.remote_addr or "unknown"
        if not _rate_limiter.allow(ip):
            return jsonify({"error": "Rate limit exceeded", "request_id": g.request_id}), 429
        return f(*args, **kwargs)
    return decorated
```

### Decision 5: Error Redaction via Flask Error Handler + Request ID

**Replace all `jsonify({'error': str(e)})` with a Flask error handler** that produces generic messages plus a request ID for log correlation.

```python
@app.before_request
def assign_request_id():
    g.request_id = secrets.token_hex(8)

@app.errorhandler(Exception)
def handle_unhandled(exc):
    request_id = g.get("request_id", "unknown")
    app.logger.error("Unhandled exception request_id=%s: %s", request_id, exc)
    return jsonify({
        "error": "Internal server error",
        "request_id": request_id,
    }), 500
```

**Route-level error handling changes:**
- Remove `except Exception as e: return jsonify({'error': str(e)}), 500` from routes
- Let exceptions propagate to the global handler
- Keep **specific** exception handlers (e.g., `RuntimeError` for "item lookup failed" → 404) where the route explicitly wants to map a known error to a specific status code
- The global handler catches everything that falls through

**This means:**
- `get_trailer()` / `get_cast()`: Remove the broad `except Exception` → let the global handler redact
- Keep `except RuntimeError` for known 404 cases ("item lookup failed")
- `add_to_watchlist()`: Remove `except Exception as e` → let propagate
- `get_server_info()`: Same pattern

### Decision 6: SSRF Validation — Pure Function at Boot

**Validate `JELLYFIN_URL` once at module load**, fail fast with `RuntimeError` if it resolves to a metadata IP.

```python
import ipaddress
import socket
from urllib.parse import urlparse

def validate_jellyfin_url(url: str) -> None:
    """Raise RuntimeError if URL resolves to a metadata or special-use IP."""
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        raise RuntimeError(f"JELLYFIN_URL has no hostname: {url}")

    # Allow if hostname is already an allowed IP literal
    try:
        ip = ipaddress.ip_address(hostname)
        if _is_blocked_ip(ip):
            raise RuntimeError(f"JELLYFIN_URL resolves to blocked address: {ip}")
        return  # Non-blocked IP literal is fine
    except ValueError:
        pass  # Not an IP literal, resolve via DNS

    # Resolve hostname
    try:
        addrs = socket.getaddrinfo(hostname, parsed.port)
    except socket.gaierror as exc:
        raise RuntimeError(f"JELLYFIN_URL hostname unresolvable: {hostname}") from exc

    for family, type_, proto, canon, sockaddr in addrs:
        ip = ipaddress.ip_address(sockaddr[0])
        if _is_blocked_ip(ip):
            raise RuntimeError(f"JELLYFIN_URL resolves to blocked address: {ip}")

def _is_blocked_ip(ip) -> bool:
    """Block metadata, link-local, and other special-use addresses."""
    blocked = [
        ipaddress.ip_network("169.254.0.0/16"),   # AWS/GCP metadata
        ipaddress.ip_network("0.0.0.0/8"),         # "this network"
        ipaddress.ip_network("224.0.0.0/4"),       # Multicast
        ipaddress.ip_network("::/128"),             # Unspecified IPv6
        ipaddress.ip_network("ff00::/8"),           # IPv6 multicast
    ]
    return any(ip in net for net in blocked)
```

**Explicitly ALLOWED:**
- `127.0.0.0/8` (loopback — Docker host networking)
- `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` (RFC 1918 — home networks)
- Public IPs (normal remote Jellyfin servers)

**Placement:** Call in `__init__.py` right after reading `JELLYFIN_URL` from env, before creating the provider singleton.

### Decision 7: Provider Integration — Minimal Interface Change

**Replace `requests.Session` inside `JellyfinLibraryProvider` with `HttpClient`**, keeping the existing `_api()`, `_auth_headers()`, retry/reset logic completely intact.

```python
# In jellyfin_library.py constructor:
def __init__(self, base_url: str) -> None:
    self._base = base_url.rstrip("/")
    self._client = HttpClient(timeout=(3.05, 30))  # Jellyfin default 30s
    self._access_token: Optional[str] = None
    # ... rest unchanged
```

**The provider calls `self._client.request()` instead of `self._session.request()`** — a find-and-replace that preserves all existing behavior. Individual methods that need different timeouts pass `timeout=` explicitly:

```python
# fetch_library_image keeps its longer timeout:
r = self._client.get(url, params={"maxHeight": 720}, headers=self._auth_headers(), timeout=(5, 60))
```

**No changes to `base.py`** — the `LibraryMediaProvider` ABC is unaffected.

## File-by-File Change Map

### `jellyswipe/http_client.py` — NEW (~120 lines)

```python
"""Centralized HTTP client with timeout enforcement, TMDB Bearer auth,
rate limiting, and SSRF URL validation."""
```

Exports:
- `HttpClient` — Wrapper class for all outbound HTTP
- `tmdb_get(path, *, params)` — TMDB-specific helper with Bearer auth
- `TokenBucketRateLimiter` — Per-IP rate limiter
- `rate_limited` — Decorator for Flask routes
- `validate_jellyfin_url(url)` — Boot-time SSRF guard
- `rate_limiter` — Module-level singleton instance

### `jellyswipe/__init__.py` — MODIFIED

| Change | Lines Affected | Description |
|--------|---------------|-------------|
| Import `http_client` | ~66 | `from .http_client import tmdb_get, rate_limited, validate_jellyfin_url, rate_limiter` |
| SSRF validation | After ~62 | `validate_jellyfin_url(JELLYFIN_URL)` — fails fast at boot |
| Request ID middleware | After ~60 | `@app.before_request` assigning `g.request_id` |
| Error handler | After middleware | `@app.errorhandler(Exception)` with redaction |
| `get_trailer()` rewrite | 182-199 | Replace 2x `requests.get()` with `tmdb_get()`, add `@rate_limited` |
| `get_cast()` rewrite | 201-225 | Replace 2x `requests.get()` with `tmdb_get()`, add `@rate_limited` |
| `/proxy` rate limit | 523-536 | Add `@rate_limited` decorator |
| `add_to_watchlist()` | 227-240 | Add `@rate_limited`, remove `str(e)` leak |
| `get_server_info()` | 430-434 | Remove `str(e)` leak |
| Remove `import requests` | ~14 | No longer needed at route level |

### `jellyswipe/jellyfin_library.py` — MODIFIED

| Change | Lines Affected | Description |
|--------|---------------|-------------|
| Import | ~11 | `from .http_client import HttpClient` |
| Constructor | 42-49 | `self._client = HttpClient(timeout=(3.05, 30))` replaces `self._session` |
| `reset()` | 51-57 | `self._client = HttpClient(...)` replaces session rebuild |
| `_api()` | 133-163 | `self._client.request()` replaces `self._session.request()` |
| `_login_from_env()` | 91-96 | `self._client.post()` replaces `self._session.post()` |
| `_verify_items()` | 119-124 | `self._client.get()` replaces `self._session.get()` |
| `_user_id()` fallback | 180 | `self._client.get()` replaces `self._session.get()` |
| `server_info()` fallback | 354 | `HttpClient` instance call replaces raw `requests.get()` |
| `fetch_library_image()` | 369-383 | `self._client.get()` with `timeout=(5, 60)` |
| `authenticate_user_session()` | 418-423 | `self._client.post()` |
| `resolve_user_id_from_token()` | 442, 450 | `self._client.get()` |
| `add_to_user_favorites()` | 476 | `self._client.post()` |

## Build Order

Dependencies determine the order. Each step produces testable, deployable code.

```
Step 1: SSRF Validation (validate_jellyfin_url)
  ↓   No dependencies on other new code
  ↓   Pure function, unit-testable in isolation
  ↓
Step 2: HttpClient class
  ↓   No dependencies on other new code
  ↓   Wraps requests, unit-testable with mocked session
  ↓
Step 3: Integrate HttpClient into JellyfinLibraryProvider
  ↓   Depends on Step 2
  ↓   Find-and-replace self._session → self._client
  ↓   Existing provider tests validate no regression
  ↓
Step 4: TMDB Bearer auth (tmdb_get helper)
  ↓   Depends on Step 2
  ↓   Rewrite 4 route-level requests.get calls
  ↓   Parallel with Step 3 (different files)
  ↓
Step 5: Error redaction (request ID + global handler)
  ↓   No code dependency on Steps 2-4
  ↓   Can be done in parallel
  ↓   Remove str(e) leaks from routes
  ↓
Step 6: Rate limiter + decorator
  ↓   Depends on request ID middleware (Step 5)
  ↓   Apply @rate_limited to 4 routes
  ↓
Step 7: Security tests
      Depends on all above
      SSRF rejection, timeout enforcement, error redaction, rate limiting
```

**Parallelization:** Steps 3, 4, 5 can run in parallel after Step 2 completes.

## Gevent Compatibility Notes

| Concern | Resolution | Confidence |
|---------|-----------|------------|
| `requests` under gevent | Works via gevent monkey-patching of `socket` (already in production) | HIGH |
| Rate limiter dict access | Safe: gevent greenlets are cooperatively scheduled, dict read-modify-write between yields is atomic | HIGH |
| `socket.getaddrinfo` in SSRF validation | Blocking call at boot, runs once before any greenlets — no issue | HIGH |
| `time.time()` monotonicity | `time.time()` is fine for rate limiting; gevent doesn't affect it | HIGH |
| `secrets.token_hex` for request IDs | Stdlib, no gevent interaction | HIGH |

## Anti-Patterns to Avoid

### Anti-Pattern 1: Global `requests.Session` Shared Across Routes and Provider

**What:** Creating one `requests.Session()` and sharing it between `__init__.py` routes and the `JellyfinLibraryProvider`.

**Why bad:** The provider sets `Authorization` headers and `Content-Type` on its session. Sharing it would leak Jellyfin auth headers into TMDB calls or vice versa.

**Instead:** Each `HttpClient` instance wraps its own `requests.Session`. The provider has its own client instance; TMDB calls use a separate shared client or the `tmdb_get()` helper.

### Anti-Pattern 2: Rate Limiter with `threading.Lock`

**What:** Adding `threading.Lock()` around rate limiter state under gevent.

**Why bad:** Under gevent's cooperative scheduling, locks are unnecessary for single-yield code paths. Adding locks introduces deadlock risk and complexity for zero benefit.

**Instead:** Plain dict + `time.time()`. Cooperative scheduling makes this safe.

### Anti-Pattern 3: Over-Abstracting Error Redaction

**What:** Creating a custom exception hierarchy with `RedactedError`, `PublicError`, etc.

**Why bad:** For a 4-route Flask app with ~6 error paths, a custom exception hierarchy adds complexity without value. The global `@app.errorhandler(Exception)` + keeping specific `RuntimeError` catches for known 404s is sufficient.

**Instead:** Global error handler redacts all unhandled exceptions. Routes that want specific status codes catch their known exceptions explicitly and return the appropriate response — without `str(e)` in the body.

### Anti-Pattern 4: Validating Every Outbound URL for SSRF

**What:** Running `validate_jellyfin_url()` on every request or validating TMDB URLs.

**Why bad:** TMDB URLs are hardcoded (`https://api.themoviedb.org/3/...`), not user-controlled. SSRF validation only matters for `JELLYFIN_URL` which comes from environment config. Over-validating wastes CPU and adds false-positive risk.

**Instead:** Validate `JELLYFIN_URL` once at boot. TMDB URLs are constant strings. The only user-controlled URL input is the `/proxy?path=` parameter, which already has regex validation.

## Scalability Considerations

| Concern | Current (1-5 users) | Moderate (50 concurrent) | Notes |
|---------|---------------------|--------------------------|-------|
| Rate limiter memory | ~0 KB | ~50 KB (50 IP entries) | Cleanup stale entries periodically |
| Request ID overhead | Negligible | Negligible | `secrets.token_hex(8)` is fast |
| HttpClient session pooling | 1 connection per host | Requests Session pools automatically | No change needed |
| SSRF DNS resolution | Once at boot | Once at boot | Not per-request |

## Sources

- **TMDB Authentication docs** — https://developer.themoviedb.org/docs/authentication-application (HIGH confidence — official docs, verified via Context7 + direct fetch)
- **Requests timeout docs** — https://requests.readthedocs.io/en/latest/user/advanced/ (HIGH confidence — official docs, verified via Context7)
- **Gevent cooperative scheduling** — Training data (HIGH confidence — well-established gevent behavior, confirmed by production use in this app since v1.2)
- **Existing codebase** — `jellyswipe/__init__.py`, `jellyswipe/jellyfin_library.py`, `jellyswipe/base.py` (HIGH confidence — direct code reading)

---
*Architecture research for: v1.6 Outbound HTTP Hardening*
*Researched: 2026-04-26*
