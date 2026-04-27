# Phase 23: HTTP Client Centralization

**Created:** 2026-04-26
**Status:** Planning
**Milestone:** v1.6 — Harden Outbound HTTP

---

## Phase Goal

All outbound HTTP requests use a centralized helper function that enforces security best practices: timeouts, User-Agent headers, structured logging, and proper error handling.

---

## Depends On

Nothing — this is the first phase of v1.6.

---

## Requirements

This phase addresses the following requirements from M04-REQUIREMENTS.md:

- **HTTP-01**: Centralized HTTP Client Helper — Create `make_http_request()` helper function in `jellyswipe/http_client.py`
- **HTTP-02**: All requests.get Calls Use Helper — Replace all direct `requests.get()` calls with the centralized helper
- **HTTP-03**: All requests.post Calls Use Helper — Replace all direct `requests.post()` calls with the centralized helper
- **HTTP-04**: All requests Calls Have Timeouts — Ensure every HTTP request has explicit timeout parameters
- **TEST-01**: HTTP Client Helper Tests — Unit tests for the centralized HTTP client helper

---

## Success Criteria

From M04-ROADMAP.md, the following must be TRUE when this phase is complete:

1. Centralized `make_http_request()` helper function exists in `jellyswipe/http_client.py`
2. All `requests.get()` and `requests.post()` calls replaced with helper
3. Every HTTP request has explicit timeout parameters (default: 5s connect, 30s read)
4. Helper sets consistent User-Agent header and logs structured outcomes
5. Unit tests validate timeout enforcement, header setting, and error handling

---

## Context from Milestone

### Problem: No Timeout on TMDB Requests

**Severity:** High
**Location:** `jellyswipe/__init__.py:187, 191, 206, 210`

Multiple `requests.get()` calls for TMDB API lack timeout parameters:
- `get_trailer()` — lines 187, 191
- `get_cast()` — lines 206, 210

A slow TMDB response stalls a gunicorn-gevent worker indefinitely (effectively forever). The Jellyfin client uses `timeout=30/60/90`, but module-level `requests.get` in `__init__.py` does not.

**Impact:** Worker exhaustion, denial of service, degraded application performance.

---

### Problem: Inconsistent HTTP Client Usage

**Current State:**
- Direct `requests.get()` calls scattered throughout codebase
- Some calls have timeouts, some don't
- Inconsistent User-Agent headers
- No structured logging for HTTP operations
- Error handling varies by location

**Desired State:**
- Single `make_http_request()` helper function
- All HTTP calls go through helper
- Consistent timeout enforcement (default: 5s connect, 30s read)
- Consistent User-Agent header: `JellySwipe/1.6 (+https://github.com/andrewthetechie/jelly-swipe)`
- Structured logging for all HTTP operations (method, url, status_code, duration_ms, success/failure)
- Consistent error handling with context preservation

---

## Technical Approach

### Centralized Helper Function

Create `jellyswipe/http_client.py` with:

```python
import requests
import logging
import time
from typing import Dict, Optional, Tuple, Any

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "JellySwipe/1.6 (+https://github.com/andrewthetechie/jelly-swipe)"
DEFAULT_TIMEOUT = (5, 30)  # (connect, read) in seconds

def make_http_request(
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Dict[str, Any]] = None,
    timeout: Tuple[int, int] = DEFAULT_TIMEOUT,
    **kwargs
) -> requests.Response:
    """
    Centralized HTTP request helper with security best practices.

    Args:
        method: HTTP method (GET, POST, etc.)
        url: Request URL
        headers: Request headers (User-Agent will be added if not present)
        params: Query parameters
        json: JSON body for POST/PUT
        timeout: (connect, read) timeout tuple
        **kwargs: Additional arguments passed to requests.request

    Returns:
        requests.Response object

    Raises:
        requests.exceptions.RequestException: On network or HTTP errors
    """
    start_time = time.time()

    # Ensure User-Agent header
    if headers is None:
        headers = {}
    if 'User-Agent' not in headers:
        headers['User-Agent'] = DEFAULT_USER_AGENT

    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json,
            timeout=timeout,
            **kwargs
        )

        duration_ms = (time.time() - start_time) * 1000

        # Structured logging
        logger.info(
            "http_request",
            extra={
                'method': method,
                'url': url,
                'status_code': response.status_code,
                'duration_ms': round(duration_ms, 2),
                'success': 200 <= response.status_code < 300
            }
        )

        response.raise_for_status()
        return response

    except requests.exceptions.RequestException as e:
        duration_ms = (time.time() - start_time) * 1000

        logger.error(
            "http_request_failed",
            extra={
                'method': method,
                'url': url,
                'duration_ms': round(duration_ms, 2),
                'error_type': type(e).__name__,
                'error_message': str(e)
            }
        )

        raise
```

---

### Migration Strategy

1. Create `jellyswipe/http_client.py` with the helper function
2. Replace all `requests.get()` calls in `jellyswipe/__init__.py`
3. Replace all `requests.post()` calls in `jellyswipe/__init__.py`
4. Update `jellyswipe/jellyfin_library.py` to use helper
5. Ensure all calls have explicit timeout parameters
6. Add unit tests for the helper function

**Files to modify:**
- `jellyswipe/http_client.py` — NEW FILE
- `jellyswipe/__init__.py` — Replace direct requests calls
- `jellyswipe/jellyfin_library.py` — Replace direct requests calls
- `tests/test_http_client.py` — NEW FILE for unit tests

---

## Discovery Level

**Level 0 (Skip)** — Pure internal work, existing patterns only:
- HTTP client patterns are standard Python requests usage
- Timeout parameters are well-understood
- Structured logging follows existing logging patterns
- No new external dependencies required
- Test patterns follow existing pytest conventions

---

## Constraints

### From CONVENTIONS.md

- Use snake_case for function names
- Error handling: wrap external IO in try/except
- Follow existing code style and patterns
- Maintain backward compatibility where possible

### From TESTING.md

- Use pytest for all tests
- Mock external HTTP requests in tests
- Use function-scoped fixtures for test isolation
- Test both success and failure paths

---

## Open Questions / Gray Areas

None identified — this phase has clear technical requirements and follows established patterns.

---

*Context created: 2026-04-26*