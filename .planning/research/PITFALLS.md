# Pitfalls Research

**Domain:** Flask + gevent outbound HTTP hardening (centralized client, SSRF validation, rate limiting, error redaction)
**Researched:** 2026-04-26
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: In-Memory Rate Limiter State Is Per-Worker, Not Global

**What goes wrong:**
A token-bucket rate limiter stored in a Python module-level dict or class attribute lives inside **one gunicorn worker process**. With multiple gunicorn workers (`--workers N`), each worker gets its own independent limiter. A client that hits the rate limit on worker 1 can immediately succeed on worker 2, effectively multiplying the allowed rate by the worker count.

**Why it happens:**
Gunicorn uses a pre-fork model. The gevent worker class monkey-patches inside each forked worker — not in the master. Each worker process has its own Python interpreter, its own copy of module globals, and its own in-memory data structures. Developers coming from threaded servers (gthread) or single-worker setups assume "in-memory" means "shared across all concurrent requests," but with gunicorn+gevent it only means "shared across concurrent greenlets within one OS process."

**How to avoid:**
- **Default deployment is 1 worker** (current Dockerfile has no `--workers` flag, so gunicorn defaults to 1). In-memory limiter works correctly for this.
- Document that adding `--workers N > 1` breaks the rate-limit guarantee unless the limiter uses shared storage (Redis, file-based).
- Add a startup warning if `--workers > 1` and in-memory limiter is in use: "Rate limiting is per-worker; effective limit = N × configured limit."
- Structure the limiter behind an interface so swapping to Redis later is a config change, not a rewrite.

**Warning signs:**
- `gunicorn.conf.py` or Dockerfile CMD adds `--workers 2+`
- Rate-limit tests pass in unit tests (single process) but a load test shows 2× the allowed request rate
- Users report rate limit is "not working" under load

**Phase to address:**
Phase where rate limiter is built — add the worker-isolation documentation and startup warning alongside the limiter implementation.

---

### Pitfall 2: SSRF Validation at Boot Is Defeated by DNS Rebinding

**What goes wrong:**
Validating `JELLYFIN_URL` at boot time (reject `169.254.x.x`, allow loopback + RFC 1918) only checks the hostname **at startup**. If the URL uses a hostname (not IP), DNS rebinding can resolve it to a metadata endpoint later. An attacker who controls the DNS for `evil.example.com` could:
1. Have it resolve to `192.168.1.100` at boot (passes validation)
2. Rebind it to `169.254.169.254` at request time (SSRF to cloud metadata)

**Why it happens:**
Developers implement boot-time validation because it's simpler than per-request validation. The assumption is "JELLYFIN_URL is set once and doesn't change." But DNS TTLs and external resolvers mean the IP behind a hostname can change at any time.

**How to avoid:**
- **Boot validation is still correct for this project** because `JELLYFIN_URL` is operator-configured (not user-controlled) and typically points to `http://jellyfin:8096` (Docker network) or `http://192.168.x.x:8096` (LAN IP). The threat model is operator misconfiguration, not adversarial DNS rebinding.
- For defense-in-depth: resolve the hostname to IP at boot and also revalidate the IP on each request (or cache the resolved IP and use that instead of the hostname).
- Log a warning at boot if `JELLYFIN_URL` is a hostname (not an IP), explaining the DNS rebinding risk.
- Document that operators should use IP addresses or Docker DNS names (which are not rebinding-eligible) in `JELLYFIN_URL`.

**Warning signs:**
- `JELLYFIN_URL=http://some-public-domain.com:8096` (external hostname)
- SSRF validation only checks `socket.getaddrinfo()` once at import time
- No revalidation on subsequent HTTP calls

**Phase to address:**
Boot validation phase — implement boot-time check AND document the DNS rebinding limitation. Add IP resolution + caching if time allows.

---

### Pitfall 3: Error Redaction Breaks Existing Error Contracts

**What goes wrong:**
The existing code returns `jsonify({'error': str(e)}), 500` in **8 route handlers** (`__init__.py` lines 198, 199, 223, 225, 240, 434, etc.). These handlers currently expose upstream error text (e.g., `"Jellyfin request failed (HTTP 401)"` from `JellyfinLibraryProvider._api`). If error redaction is implemented naively — replacing all `str(e)` with a generic message — the frontend JavaScript that checks `response.error` for specific strings will break silently.

**Why it happens:**
The frontend in `templates/index.html` likely checks for error strings like `'Not found'`, `'Unauthorized'`, etc. When adding centralized error handling, developers replace `str(e)` everywhere with `f"Internal error (ref={request_id})"`, assuming the frontend doesn't parse error messages. But the SPA shows these messages to users and may branch on them.

**How to avoid:**
- **Audit the frontend JavaScript** in `templates/index.html` for `error` field usage before changing error shapes.
- Preserve **known 4xx error messages** that are user-facing and expected (e.g., `'Not found'`, `'Unauthorized'`, `'Invalid Code'`).
- Only redact **5xx error messages** — replace `str(e)` with a generic message + request ID.
- Use a consistent error response shape: `{"error": "user_message", "request_id": "abc123"}` for 5xx, `{"error": "user_message"}` for 4xx.
- Implement via a Flask `@app.errorhandler(500)` or `@app.errorhandler(Exception)` to avoid changing every route handler.

**Warning signs:**
- Frontend shows "Internal error (ref=abc123)" for all errors, including expected ones like "Movie not found"
- Tests that assert on specific error messages break
- `try/except` blocks that catch specific error strings stop matching

**Phase to address:**
Error redaction phase — first audit frontend error handling, then implement 5xx-only redaction.

---

### Pitfall 4: Centralized HTTP Helper Misses Stray `requests.*` Calls

**What goes wrong:**
The codebase has two categories of HTTP calls:
1. **`JellyfinLibraryProvider._session`** (a `requests.Session`) — used for all Jellyfin API calls with timeouts
2. **Bare `requests.get()`** — used for 4 TMDB calls in `__init__.py` (lines 187, 191, 206, 210) with NO timeouts, and 1 fallback call in `jellyfin_library.py` line 354

When building a centralized HTTP helper, developers focus on the TMDB calls (the ones without timeouts) but miss the stray `requests.get()` in `jellyfin_library.py:354` (the `server_info` fallback that hits `/System/Info/Public`). This call goes through a different code path and won't get timeouts, User-Agent, or logging.

**Why it happens:**
The stray `requests.get()` in `server_info()` is outside the `_api()` method — it's a direct call using the module-level `requests` module, not `self._session`. It's easy to miss when grep-based auditing only catches calls in `__init__.py`.

**How to avoid:**
- **Grep for ALL `requests.` calls** before and after implementing the helper:
  ```bash
  rg 'requests\.(get|post|put|delete|patch|head|request)\s*\(' jellyswipe/
  ```
- The centralized helper should replace:
  - 4 TMDB calls in `__init__.py` (lines 187, 191, 206, 210)
  - 1 stray `requests.get()` in `jellyfin_library.py` (line 354)
- Use a **no-bare-requests lint rule** (or pre-commit hook) to prevent new `requests.*` calls outside the helper.
- Consider having the centralized helper wrap `requests.Session` so even `jellyfin_library.py._session` calls go through it for consistent logging/timeouts.

**Warning signs:**
- `rg 'requests\.' jellyswipe/ | grep -v '_session\.'` returns results after migration
- TMDB calls have timeouts but a new call added during the milestone doesn't
- Production monitoring shows a hung request with no timeout after 30+ minutes

**Phase to address:**
Centralized HTTP helper phase — begin with a comprehensive audit of all HTTP calls, implement helper, then verify zero stray calls remain.

---

### Pitfall 5: `requests.Session` Thread-Safety with Gevent Greenlets

**What goes wrong:**
`requests.Session` uses `urllib3` connection pools that are thread-safe via locks. With gevent monkey-patching, those locks become cooperative locks (greenlet-safe). However, `requests.Session` also stores cookies and auth state that are **not** protected by any lock — they're shared mutable state. In Jelly Swipe, `JellyfinLibraryProvider._session` is a singleton shared across all greenlets. If one greenlet triggers `self._session.headers["Authorization"] = ...` while another is mid-request, the second greenlet could send the wrong auth header.

**Why it happens:**
The current code sets `self._session.headers["Content-Type"]` in `__init__` and passes auth via per-request `headers=self._auth_headers()` (which creates a new dict each time), so per-request headers override session headers. This pattern is safe. But if the centralized HTTP helper starts setting auth on the session object itself (rather than per-request), or if cookie handling gets enabled, state leaks between greenlets.

**How to avoid:**
- **Keep the current pattern**: pass auth via per-request `headers=` kwarg, not via session-level headers.
- The centralized HTTP helper should accept auth as a parameter and pass it per-request.
- Do NOT enable `session.cookies` or `session.auth` — keep the session as a connection pool only.
- If adding TMDB Bearer auth, pass it as `headers={"Authorization": f"Bearer {token}"}` per-request, not on the session.
- Document this constraint clearly: "Session is shared across greenlets; never mutate session state."

**Warning signs:**
- `session.headers["Authorization"] = ...` or `session.auth = ...` in the helper
- `session.cookies` being read from in one request with values set by another
- Intermittent 401 errors under concurrent load (auth state corruption)

**Phase to address:**
Centralized HTTP helper phase — design the helper API to enforce per-request auth from the start.

---

## Technical Debt Patterns

Shortcuts that seem reasonable when adding HTTP hardening but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| In-memory rate limiter (no Redis) | No new dependency, simpler code | Per-worker limits with multi-worker gunicorn; state lost on restart | Acceptable now — default is 1 worker; document limitation |
| Boot-only SSRF validation | Simple, one-time check | DNS rebinding not caught; doesn't protect if URL changes mid-run | Acceptable — `JELLYFIN_URL` is operator-controlled, not user input |
| `jsonify({'error': 'Internal error'})` for all 5xx | Quick redaction, no per-route changes | Frontend may parse error messages; loss of debuggability | Never for 5xx — must include request_id; redact only upstream text |
| Centralized helper wraps only TMDB calls | Smaller diff, less risk of regression | Jellyfin calls don't get consistent logging/User-Agent | Not acceptable — all outbound calls should go through the helper |
| `except Exception as e: return jsonify({'error': str(e)}), 500` | Keeps existing pattern working | Leaks upstream errors, no request ID, no structured logging | Acceptable temporarily during migration; must be replaced in error-redaction phase |

---

## Integration Gotchas

Common mistakes when integrating HTTP hardening features with Flask + gevent.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| **Flask `@app.errorhandler`** | Register handler for all exceptions, breaking the SSE `/room/stream` generator that catches `GeneratorExit` | Only handle `Exception` (not `BaseException`); let `GeneratorExit` propagate naturally |
| **Flask `after_request`** | Add request-ID header in `after_request` but it doesn't fire on unhandled exceptions | Generate request ID at the start of request processing (via `before_request` or middleware), store in `g.request_id`, read in error handler |
| **`requests.Session` + gevent** | Create a new `requests.Session()` per request — defeats connection pooling, high overhead | Share a session across greenlets; pass auth per-request via `headers=` kwarg |
| **Token-bucket + gevent** | Use `threading.Lock` for bucket synchronization — becomes a cooperative lock under gevent (works, but `gevent.lock.Semaphore` is more explicit) | `threading.Lock` works after monkey-patching; either is fine. Just ensure the lock exists. |
| **TMDB Bearer auth** | Keep `TMDB_API_KEY` env var name but use it as Bearer token — conflates v3 API key with v4 access token | Rename to `TMDB_ACCESS_TOKEN` or `TMDB_READ_ACCESS_TOKEN`; keep backward compatibility with a clear deprecation warning |
| **Error redaction + CSP header** | `@app.after_request` CSP header runs after error handler; ensure error JSON responses also get CSP | CSP is already set in `add_csp_header()` which runs on all responses including errors — no change needed |
| **Rate limiter + SSE stream** | Rate-limit `/room/stream` — long-lived SSE connections would consume all tokens | Exclude `/room/stream` from rate limiting; only limit request-response endpoints |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| **Token bucket no cleanup** | In-memory dict grows unbounded as new IP/key entries are added and never evicted | Add TTL-based cleanup: evict buckets older than the refill window on each check, or use a periodic cleanup greenlet | At 10K+ unique IPs (unlikely for LAN app, but possible if exposed publicly) |
| **SSRF regex on every request** | Resolving and validating `JELLYFIN_URL` IP on every outbound call adds DNS latency | Cache resolved IP at boot; only re-resolve on failure | At 100+ concurrent requests to Jellyfin (unlikely for 2-4 user sessions) |
| **Rate limiter lock contention** | `threading.Lock` (cooperative under gevent) serializes all rate-limit checks | For this scale (LAN movie swiping, ~4 users), a single lock is fine. Only optimize if >100 req/sec sustained | At >100 req/sec per worker |
| **Error logging on every 5xx** | Structured JSON logging with full stack traces on every error fills disk | Log stack traces at DEBUG level; log error summary (with request_id) at WARNING level | At sustained error rates (>10/sec) |
| **Request ID generation overhead** | UUID4 generation on every request adds ~1μs — negligible | Use `uuid.uuid4()` or `os.urandom(8).hex()` — both are fast enough | Never breaks for this scale |

---

## Security Mistakes

Domain-specific security issues for HTTP hardening on Flask + gevent.

| Mistake | Risk | Prevention |
|---------|------|------------|
| **TMDB API key in URL query strings** (current state) | Key appears in access logs, browser history, referrer headers, and proxy logs | Move to `Authorization: Bearer <token>` header; TMDB supports this for both v3 and v4 APIs (confirmed: developer.themoviedb.org docs) |
| **Stray `requests.get()` without timeout** (current: `__init__.py` lines 187, 191, 206, 210) | A single hung TMDB call blocks the gevent greenlet indefinitely, consuming a worker slot forever | Enforce timeouts in the centralized helper; make `timeout` a required parameter |
| **`str(e)` in 500 responses** (current state) | Leaks internal Jellyfin server URLs, API paths, error details to clients | Replace with generic message + request_id; log the full error server-side |
| **SSRF via `JELLYFIN_URL` pointing to cloud metadata** | If `JELLYFIN_URL` is set to `http://169.254.169.254/`, the server fetches AWS/GCP metadata | Boot-time IP validation rejecting `169.254.0.0/16`, `[fd00:ec2::]/32` |
| **Rate limiter bypass via header spoofing** | `X-Forwarded-For` header spoofing bypasses IP-based rate limiting behind reverse proxy | Use `ProxyFix` (already in place: `__init__.py` line 46) — it trusts only one proxy layer. Document that rate limiter uses `request.remote_addr` after ProxyFix processing |
| **No User-Agent on outbound requests** | TMDB or Jellyfin may rate-limit or block requests with default `python-requests/X.X.X` User-Agent | Set a custom User-Agent in the centralized helper: `JellySwipe/1.6 (github.com/andrewthetechie/jelly-swipe)` |

---

## UX Pitfalls

Common user-experience mistakes when adding HTTP hardening.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| **Generic "Internal error" for all failures** | Users can't tell if it's a temporary network issue or a permanent problem | Distinguish: "Service temporarily unavailable" (5xx) vs "Not found" (404) vs "Too many requests, try again in a moment" (429) |
| **Rate limit response has no retry guidance** | Users spam retry, making the problem worse | Return `429` with `Retry-After` header and a user-friendly JSON message |
| **Silent timeout with no feedback** | TMDB trailer or cast fetch hangs, UI shows loading spinner forever | Frontend should have its own client-side timeout; server should return `504 Gateway Timeout` with a message, not hang |
| **Breaking change in error response shape** | Frontend JavaScript expects `{'error': 'specific message'}` but gets `{'error': 'Internal error', 'request_id': 'abc'}` | Keep `error` field for user messages; add `request_id` as an additional field. Don't change the existing field semantics |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **All HTTP calls have timeouts:** Verify by grepping for `requests.` — must find ZERO bare calls without `timeout=`. Check both `__init__.py` AND `jellyfin_library.py`
- [ ] **TMDB key removed from URLs:** Verify by grepping for `api_key=` in the codebase. Also check that no `api_key` appears in any constructed URL string
- [ ] **Error redaction covers ALL routes:** Verify that every `except Exception as e: return jsonify({'error': str(e)}), 500` has been converted to the redacted form. The `server_info` route (line 434) and `add_to_watchlist` (line 240) are easy to miss
- [ ] **Rate limiter applies to all 4 target routes:** Verify `/proxy`, `/get-trailer`, `/cast`, `/watchlist/add` all return 429 when over limit. `/room/stream` must NOT be rate-limited
- [ ] **SSRF validation rejects metadata IPs:** Test with `JELLYFIN_URL=http://169.254.169.254` — must fail at boot. Test with `http://192.168.1.100` — must pass. Test with `http://localhost:8096` — must pass
- [ ] **Bearer token auth works with TMDB v3 API:** TMDB docs confirm Bearer token works for v3 endpoints (search/movie, movie/videos, movie/credits). Verify with a live test or confirmed mock
- [ ] **Existing tests still pass:** The 48 existing tests mock `requests.Session` — verify they still work after introducing the centralized helper

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| **Stray `requests.get()` without timeout found in production** | LOW | 1. Add the missing call to the centralized helper<br>2. Add a grep check in CI to prevent regressions: `rg 'requests\.(get|post|put|delete|patch)\s*\(' jellyswipe/ --glob '!*http_helper*'` |
| **Rate limiter ineffective with multi-worker deployment** | LOW | 1. Add Redis-backed storage to Flask-Limiter or custom limiter<br>2. Or enforce `--workers 1` in the Dockerfile and document the limitation<br>3. Add startup warning when workers > 1 |
| **Error redaction broke frontend error handling** | MEDIUM | 1. Audit frontend for `error` field usage<br>2. Restore specific 4xx error messages that the frontend depends on<br>3. Only redact 5xx responses; keep 4xx messages user-friendly |
| **Session auth state leak between greenlets** | MEDIUM | 1. Find where session headers/auth are being mutated<br>2. Move to per-request `headers=` parameter<br>3. Add a test that verifies concurrent requests get correct auth |
| **DNS rebinding bypasses SSRF validation** | LOW (unlikely threat model) | 1. Add per-request IP validation (resolve hostname, check IP before each request)<br>2. Or pin the resolved IP at boot and use IP instead of hostname for all subsequent requests |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| **Stray `requests.get()` calls** | Centralized HTTP helper — start with comprehensive audit | `rg 'requests\.(get|post)\s*\(' jellyswipe/` returns zero results (outside helper) |
| **No timeouts on TMDB calls** | Centralized HTTP helper — make `timeout` a required parameter | Every `http_helper.*()` call has `timeout=`; test that missing timeout raises ValueError |
| **Error redaction breaks frontend** | Error redaction phase — audit frontend first, redact only 5xx | Frontend still shows specific error messages for 4xx; 5xx shows generic message + request_id |
| **Rate limiter per-worker isolation** | Rate limiter phase — document limitation, add startup warning | Startup log shows warning when `--workers > 1`; README documents in-memory limitation |
| **SSRF DNS rebinding** | Boot validation phase — implement boot check + document DNS risk | Boot rejects `169.254.x.x` IPs; README documents operator guidance for using IPs not hostnames |
| **Session state leak between greenlets** | Centralized HTTP helper phase — enforce per-request auth pattern | Code review confirms no `session.headers[...] = ...` or `session.auth = ...` mutations |
| **Missing rate limit on target routes** | Rate limiter phase — test all 4 routes | Integration test hits each route rapidly and verifies 429 response |
| **TMDB Bearer auth migration** | TMDB auth phase — rename env var, update all 4 call sites | `rg 'api_key=' jellyswipe/` returns zero; `TMDB_API_KEY` renamed with backward compat |

---

## Sources

- **requests documentation** (Context7): Timeout patterns, Session objects, connection pooling — HIGH confidence
- **gevent documentation** (Context7): Monkey patching behavior, DNS patching, greenlet-local storage — HIGH confidence
- **Flask documentation** (Context7): `errorhandler`, `after_request`, `before_request` patterns — HIGH confidence
- **Flask-Limiter documentation** (Context7): In-memory storage backend, gevent compatibility, storage strategies — HIGH confidence
- **gunicorn documentation** (Context7): gevent worker class, monkey patching performed in worker process — HIGH confidence
- **TMDB API documentation** (developer.themoviedb.org): Bearer token auth works for v3 API, rate limits (~40 req/sec) — HIGH confidence
- **Codebase analysis**: Direct analysis of `jellyswipe/__init__.py` (563 lines), `jellyswipe/jellyfin_library.py` (482 lines), `Dockerfile`, `pyproject.toml`, `tests/conftest.py` — HIGH confidence

---
*Pitfalls research for: Flask + gevent outbound HTTP hardening (Jelly Swipe v1.6)*
*Researched: 2026-04-26*
