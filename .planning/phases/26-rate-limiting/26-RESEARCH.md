# Phase 26: Rate Limiting — Research

**Phase:** 26
**Date:** 2026-04-27
**Status:** Complete

---

## Standard Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Rate limiter algorithm | Token bucket (in-memory, pure Python) | D-01 through D-04: zero new deps, allows bursts, continuous refill |
| Storage | `dict` keyed by `(ip, endpoint)` tuple | D-05/D-07: per-endpoint buckets, simple key format |
| Thread safety | `threading.Lock` (gevent-aware via monkey-patching) | gevent monkey-patches threading.Lock to be cooperative; safe for gunicorn+gevent workers |
| Flask integration | Per-route decorator wrapping the 4 target routes | D-24: apply only to target endpoints, not global before_request |
| Error responses | Reuse `make_error_response()` from Phase 25 | D-15/D-16/D-17 |
| Logging | `app.logger.warning()` with structured `extra={}` | D-18/D-19/D-20 |
| Memory management | Lazy eviction on each check + max bucket cap | D-21/D-22/D-23 |

## Architecture Patterns

### Token Bucket Algorithm (Pure Python)
```python
class TokenBucket:
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.tokens = float(capacity)  # D-03: start full
        self.refill_rate = refill_rate  # tokens/second
        self.last_refill = time.monotonic()
    
    def consume(self) -> bool:
        # Refill tokens based on elapsed time
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False
    
    def retry_after(self) -> float:
        """Seconds until next token available."""
        if self.tokens >= 1.0:
            return 0.0
        return (1.0 - self.tokens) / self.refill_rate
```

### Rate Limiter Module Structure (`jellyswipe/rate_limiter.py`)
- `RateLimiter` class: manages dict of `TokenBucket` instances keyed by `(ip, endpoint)`
- `check_rate_limit(endpoint: str)` method: returns `(allowed: bool, retry_after: float)`
- Lazy eviction: on each check, prune buckets older than 300s (D-21/D-22)
- Max bucket cap: 10,000 (D-23), evict oldest-accessed if exceeded
- `threading.Lock` for thread safety during bucket creation/eviction

### Flask Integration Pattern
```python
from jellyswipe.rate_limiter import rate_limiter

def rate_limit(max_requests: int, per_minutes: int = 1):
    """Decorator to rate-limit a Flask route by IP."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            ip = request.remote_addr
            endpoint = request.endpoint  # Flask endpoint name (e.g., 'proxy')
            allowed, retry_after = rate_limiter.check(endpoint, ip, max_requests, per_minutes)
            if not allowed:
                # Log violation (D-18/D-19/D-20)
                app.logger.warning("rate_limit_exceeded", extra={...})
                resp = make_error_response("Rate limit exceeded", 429, extra_fields={"retry_after": int(retry_after)})
                resp.headers["Retry-After"] = str(int(retry_after))
                return resp
            return f(*args, **kwargs)
        return wrapped
    return decorator
```

### Endpoint-Specific Thresholds (D-08 to D-11)
| Endpoint | Flask `request.endpoint` | Limit | Refill Rate |
|----------|--------------------------|-------|-------------|
| `/proxy` | `'proxy'` | 10/min | 10/60 = 0.167/s |
| `/get-trailer/<movie_id>` | `'get_trailer'` | 20/min | 20/60 = 0.333/s |
| `/cast/<movie_id>` | `'get_cast'` | 20/min | 20/60 = 0.333/s |
| `/watchlist/add` | `'add_to_watchlist'` | 30/min | 30/60 = 0.500/s |

## Don't Hand-Roll These
- **Flask-Limiter** — NOT using per D-04 (zero new deps). Rolling our own token bucket is appropriate here since the scope is small and well-defined.
- **Redis/memcached** — NOT using. In-memory is sufficient for a single-home-server app. Not distributed.

## Common Pitfalls

1. **Thread safety under gevent**: `threading.Lock` is monkey-patched by gevent to be cooperative. Don't use `multiprocessing.Lock` (blocks the event loop). Using `threading.Lock` is correct here.

2. **Flask endpoint name vs URL path**: Use `request.endpoint` (the Flask route function name, e.g., `'proxy'`, `'get_trailer'`) NOT `request.path` (which includes the `<movie_id>` variable). This ensures all requests to `/get-trailer/ABC` and `/get-trailer/XYZ` share the same bucket for that IP.

3. **Retry-After must be integer seconds**: HTTP spec says `Retry-After` header value should be integer seconds. Use `ceil()` of the computed float.

4. **Token bucket starts full**: Per D-03, new buckets start at full capacity. This means a brand-new IP can burst all requests immediately.

5. **Eviction timing**: Only evict during `check()` calls (lazy). Don't create a background thread. Check all buckets and remove those with `last_refill > 300 seconds ago` (D-21).

6. **Decorator placement**: Rate limit decorator must be OUTERmost (applied first, checked first) so it runs before auth/validation (D-25). Pattern:
   ```python
   @app.route('/proxy')
   @rate_limit(10)  # OUTER: checked first
   def proxy():
       ...
   ```

7. **ProxyFix already configured**: `request.remote_addr` already returns X-Forwarded-For first value due to ProxyFix with `x_for=1` (D-12).

## Validation Architecture

### Observable Behaviors
1. First N requests to an endpoint from an IP succeed (N = limit per minute)
2. Request N+1 returns 429 with Retry-After header
3. After waiting Retry-After seconds, next request succeeds
4. Each endpoint tracks independently (hitting /proxy limit doesn't affect /cast)
5. Stale buckets (>5 min idle) are cleaned up

### Test Strategy
- Unit tests for `TokenBucket` class (consume, refill, retry_after)
- Unit tests for `RateLimiter` class (bucket creation, eviction, max cap)
- Integration tests via Flask test client hitting each of the 4 endpoints
- Test 429 response format: JSON body with error + request_id, Retry-After header
- Test that violations are logged at WARNING level

---

## RESEARCH COMPLETE
