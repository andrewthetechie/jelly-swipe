---
phase: 30-package-deployment-infrastructure
reviewed: 2026-05-02T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - pyproject.toml
  - Dockerfile
  - jellyswipe/__init__.py
  - jellyswipe/auth.py
findings:
  critical: 3
  warning: 4
  info: 1
  total: 8
status: issues_found
---

# Phase 30: Code Review Report

**Reviewed:** 2026-05-02
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

This phase ships package/deployment infrastructure: `pyproject.toml` defines the production dependency set, `Dockerfile` multi-stage build produces the container image, `__init__.py` is the application module (Flask `create_app` + module-level boot logic), and `auth.py` is the session/auth layer.

Three critical defects were found:

1. **Framework mismatch — fatal at runtime.** `pyproject.toml` lists `fastapi` and `uvicorn` as runtime dependencies but the application is implemented with Flask/Werkzeug. Flask and Werkzeug are not declared dependencies at all. The Dockerfile `CMD` invokes `uvicorn jellyswipe:app`, which serves a Flask WSGI app through an ASGI server — this is unsupported without an explicit ASGI-to-WSGI adapter (e.g. `a2wsgi` or `asgiref`). The container will either fail to start or silently malfunction under concurrent load.

2. **The `try/except ImportError` Flask guard causes a silent total failure.** If Flask is not installed (which it cannot be, given it is absent from `pyproject.toml`), the guard swallows the `ImportError` and execution continues. All subsequent code that relies on Flask names (`Flask`, `Response`, `jsonify`, `DefaultJSONProvider`, `ProxyFix`) will raise `NameError` at call time, not import time. The `try/except NameError` around `_XSSSafeJSONProvider` and the final `try/except NameError: app = None` are designed to mask this, meaning the module-level `app` silently becomes `None`. `uvicorn jellyswipe:app` loading `None` produces a `TypeError` at startup, not a clear error.

3. **Container runs as root.** The Dockerfile has no `USER` instruction. The process runs as UID 0 inside the container, violating the principle of least privilege and failing common container security scanners.

---

## Critical Issues

### CR-01: Framework mismatch — Flask app served through uvicorn with no ASGI adapter; Flask not a declared dependency

**File:** `pyproject.toml:10` / `Dockerfile:37` / `jellyswipe/__init__.py:11-15`

**Issue:** `pyproject.toml` declares `fastapi>=0.136.1` and `uvicorn[standard]>=0.46.0` as runtime dependencies. The application in `__init__.py` is entirely Flask-based (`Flask`, `ProxyFix`, `DefaultJSONProvider`, `render_template`, `session`, `g`, etc.). Flask and Werkzeug are not declared anywhere in `[project.dependencies]` or `[project.optional-dependencies]`.

Consequences:
- In a clean install from `pyproject.toml` (e.g. inside the Docker image), `import flask` will fail.
- The `try/except ImportError` guard (lines 10–15 of `__init__.py`) silently swallows this failure.
- `create_app()` then raises `NameError: name 'Flask' is not defined` at line 172.
- The module-level `try/except NameError: app = None` at line 845–848 catches this, leaving `app = None`.
- `uvicorn jellyswipe:app` receives `None` and raises `TypeError: ASGI app must be a callable`, killing the container at startup.
- Even if Flask were installed, uvicorn cannot serve a WSGI app without an explicit adapter.

**Fix:**

In `pyproject.toml`, replace `fastapi` with Flask and add werkzeug explicitly, and add an ASGI adapter if uvicorn is the intended server:

```toml
dependencies = [
    "flask>=3.1.0",
    "werkzeug>=3.1.0",
    "itsdangerous>=2.2.0",
    "jinja2>=3.1.6",
    "python-dotenv>=1.2.2",
    "python-multipart>=0.0.18",
    "requests>=2.33.0",
    "uvicorn[standard]>=0.46.0",
    "a2wsgi>=1.10.0",
]
```

And update the Dockerfile CMD to use Flask's built-in WSGI server or gunicorn, or wrap the app with `a2wsgi.WSGIMiddleware` before passing to uvicorn. The simplest correct CMD for a Flask app:

```dockerfile
CMD ["/app/.venv/bin/gunicorn", "--bind", "0.0.0.0:5005", "--workers", "2", "jellyswipe:app"]
```

Or if uvicorn is required, add in `__init__.py`:
```python
from a2wsgi import WSGIMiddleware
asgi_app = WSGIMiddleware(app)
```
and update CMD to `"jellyswipe:asgi_app"`.

---

### CR-02: `try/except ImportError` Flask guard masks dependency failures — `app` silently becomes `None`

**File:** `jellyswipe/__init__.py:10-15`, `jellyswipe/__init__.py:845-848`

**Issue:** The guard pattern is:

```python
try:
    from flask import Flask, ...
    from flask.json.provider import DefaultJSONProvider
    from werkzeug.middleware.proxy_fix import ProxyFix
except ImportError:
    pass
```

And at module bottom:

```python
try:
    app = create_app()
except NameError:
    app = None
```

This pattern is architecturally broken for a required dependency:

- It was presumably designed for "optional Flask" or test contexts, but Flask is not optional — the entire application is Flask.
- When Flask is absent, `NameError` propagates from `create_app()` at the `Flask(...)` call (line 172), is caught at line 847, and `app` is set to `None`.
- Any deployment that loads this module (uvicorn, gunicorn, tests) gets `None` instead of a clear `ImportError: No module named 'flask'`.
- The `auth.py` has the identical pattern (lines 7–10): `from flask import session, g, jsonify` in a bare `except ImportError: pass`, then immediately uses `session`, `g`, `jsonify` as if they are globals. If Flask is missing, calling `create_session()`, `login_required()`, or `get_current_token()` raises `NameError` at whichever line first references these names, not at import time.

**Fix:** Remove both guard patterns. Flask is a hard required dependency; treat it as one:

```python
# jellyswipe/__init__.py — remove the try/except, use direct imports
from flask import Flask, send_from_directory, jsonify, request, session, Response, render_template, abort, g
from flask.json.provider import DefaultJSONProvider
from werkzeug.middleware.proxy_fix import ProxyFix
```

```python
# jellyswipe/auth.py — remove the try/except
from flask import session, g, jsonify
```

And at module bottom of `__init__.py`:
```python
app = create_app()
```

---

### CR-03: Dockerfile container runs as root (no USER instruction)

**File:** `Dockerfile:22-37`

**Issue:** The final image stage has no `USER` instruction. The uvicorn process runs as UID 0 (root) inside the container. If the process is compromised, the attacker has root within the container with a direct path to container escape or volume mount abuse. This also fails PCI-DSS, SOC 2, and CIS Docker Benchmark controls, and is flagged as HIGH severity by tools like Trivy and Snyk.

**Fix:** Add a non-root user in the final stage before `CMD`:

```dockerfile
# Final stage
FROM python:3.13-slim

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/jellyswipe /app/jellyswipe

RUN mkdir -p /app/data \
    && groupadd --gid 1001 appuser \
    && useradd --uid 1001 --gid appuser --no-create-home appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 5005

CMD ["/app/.venv/bin/uvicorn", "jellyswipe:app", "--host", "0.0.0.0", "--port", "5005"]
```

---

## Warnings

### WR-01: `gevent` imported as optional but `requirements` omit it — SSE stream falls back to `time.sleep` silently

**File:** `jellyswipe/__init__.py:23-26`

**Issue:**

```python
try:
    from gevent import sleep as _gevent_sleep
except ImportError:
    _gevent_sleep = None
```

`gevent` is not in `pyproject.toml`. The SSE stream in `room_stream` (line 776–779) uses `_gevent_sleep` when available, otherwise `time.sleep`. With `time.sleep` in a gevent-based deployment the worker thread blocks. With a threading server the 1-hour SSE connection holds a thread for its full lifetime. This is a scaling cliff, not caught at startup. If gevent is intended, it must be declared; if not, the conditional should be removed.

**Fix:** Either add `gevent>=24.2.1` to dependencies and remove the fallback, or remove the gevent branch entirely and document the threading model:

```python
# Remove gevent entirely if not intentional:
# Replace _gevent_sleep calls with time.sleep(delay)
```

---

### WR-02: `_check_rate_limit` constructs two `Response` objects but returns only one — dead `resp` variable leaks a tuple

**File:** `jellyswipe/__init__.py:52-57`

**Issue:**

```python
body = jsonify({'error': 'Rate limit exceeded', 'request_id': ...})
resp = body, 429                          # ← assigned, never used
response = Response(response=body.response, status=429, content_type='application/json')
response.headers['Retry-After'] = str(int(retry_after) + 1)
return response
```

`resp` is assigned a `(Response, int)` tuple and immediately abandoned. `response` is constructed separately by manually copying `body.response`. This is dead code that introduces confusion about which object is actually returned. More critically, `body.response` is a list of byte strings (Flask's internal streaming interface) — passing it to `Response(response=...)` works today but is fragile and implementation-dependent. The standard pattern is to return `(body, 429)` from Flask view functions.

**Fix:**

```python
def _check_rate_limit(endpoint: str):
    allowed, retry_after = _rate_limiter.check(endpoint, request.remote_addr, _RATE_LIMITS[endpoint])
    if not allowed:
        _logger.warning("rate_limit_exceeded", extra={...})
        response = jsonify({'error': 'Rate limit exceeded', 'request_id': request.environ.get('jellyswipe.request_id', 'unknown')})
        response.status_code = 429
        response.headers['Retry-After'] = str(int(retry_after) + 1)
        return response
    return None
```

---

### WR-03: Module-level env-var validation and `validate_jellyfin_url` run at import time — test isolation broken

**File:** `jellyswipe/__init__.py:68-88`

**Issue:** Lines 68–88 execute at module import time (not inside `create_app`):

```python
missing = []
for v in ("TMDB_ACCESS_TOKEN", "FLASK_SECRET"):
    if not os.getenv(v):
        missing.append(v)
...
if missing:
    raise RuntimeError(f"Missing env vars: {missing}")

validate_jellyfin_url(os.getenv("JELLYFIN_URL"))
```

Any test that imports `jellyswipe` without setting all required env vars will raise `RuntimeError` before any test setup can run. This also means the module cannot be imported in CI without a fully populated `.env`, making import-level tooling (type checkers, linters, coverage import hooks) fail unless the environment is complete. The `load_dotenv` at the very top partially mitigates this for local dev, but not for CI or Docker build-time analysis.

**Fix:** Move validation inside `create_app()`, before the app object is configured:

```python
def create_app(test_config=None):
    missing = []
    for v in ("TMDB_ACCESS_TOKEN", "FLASK_SECRET"):
        if not os.getenv(v):
            missing.append(v)
    ...
    if missing:
        raise RuntimeError(f"Missing env vars: {missing}")
    validate_jellyfin_url(os.getenv("JELLYFIN_URL"))
    ...
```

---

### WR-04: `_token_user_id_cache` is a module-level dict with no size bound — unbounded memory growth

**File:** `jellyswipe/__init__.py:95`

**Issue:**

```python
_token_user_id_cache: Dict[str, Tuple[str, float]] = {}
```

Entries are evicted lazily only on cache hit of an expired key (line 310). A token that is used once and never again occupies the cache permanently. In a long-running process with many short-lived sessions, this dict grows without bound. The TTL is 300 seconds, but eviction requires a re-lookup of the same key — stale keys are never swept.

**Fix:** Add a max-size cap and periodic sweep, or use `functools.lru_cache` / a proper TTL cache:

```python
# Simple fix: cap at 1000 entries, evict oldest on overflow
MAX_TOKEN_CACHE = 1000

def _resolve_user_id_from_token_cached(token: str) -> Optional[str]:
    now = time.time()
    cache_key = _token_cache_key(token)
    cached = _token_user_id_cache.get(cache_key)
    if cached:
        user_id, expires_at = cached
        if expires_at > now:
            return user_id
        _token_user_id_cache.pop(cache_key, None)

    try:
        user_id = get_provider().resolve_user_id_from_token(token)
    except Exception:
        return None

    if len(_token_user_id_cache) >= MAX_TOKEN_CACHE:
        # evict one expired entry, or oldest
        _token_user_id_cache.pop(next(iter(_token_user_id_cache)), None)

    _token_user_id_cache[cache_key] = (user_id, now + TOKEN_USER_ID_CACHE_TTL_SECONDS)
    return user_id
```

---

## Info

### IN-01: `requires-python = ">=3.13,<3.14"` pins to a single minor version — unnecessarily restrictive

**File:** `pyproject.toml:8`

**Issue:** Pinning `<3.14` means the package cannot be installed on Python 3.14 when it is released without a `pyproject.toml` update. This is an unusual constraint for an application; it is more typical for libraries. For a Docker-deployed app this is low risk (the Dockerfile pins `python:3.13-slim`), but it blocks direct installs on newer Pythons and will require a manual bump on every minor release.

**Fix:** Relax to `>=3.13` unless there is a specific known 3.14 incompatibility:

```toml
requires-python = ">=3.13"
```

---

_Reviewed: 2026-05-02_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
