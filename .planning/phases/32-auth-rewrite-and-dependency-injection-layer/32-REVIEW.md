---
phase: 32-auth-rewrite-and-dependency-injection-layer
reviewed: 2026-05-02T12:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - jellyswipe/dependencies.py
  - tests/test_auth.py
  - tests/test_dependencies.py
findings:
  critical: 2
  warning: 4
  info: 3
  total: 9
status: issues_found
---

# Phase 32: Code Review Report

**Reviewed:** 2026-05-02T12:00:00Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed the new FastAPI dependency injection layer (`dependencies.py`) and its two test files (`test_auth.py`, `test_dependencies.py`). The dependency module is clean and well-structured, but there are two critical issues: (1) the rate limit key inference uses naive substring matching that produces false positives, and (2) the `get_provider()` dependency accesses a private module attribute (`_provider_singleton`) that can be `None` due to a race with the app lifespan teardown — the lazy import path instantiates a provider without thread safety. There are also duplicated test logic between the two test files and several test-specific quality issues.

## Critical Issues

### CR-01: `_infer_endpoint_key` uses substring matching — false positives on paths containing rate-limit keys

**File:** `jellyswipe/dependencies.py:66-68`
**Issue:** The function checks `if key in path` for each rate limit key against the URL path. This is pure substring containment, not segment or prefix matching. Any path that incidentally contains one of the key strings will be rate-limited. For example, a path like `/api/cast-info/reports` would match the `'cast'` key (because "cast" is a substring of "cast-info"). Similarly, `/watchlist/add-to-collection` would match `'watchlist/add'`. The keys in `_RATE_LIMITS` are short common strings (`cast`, `proxy`) that are likely to appear as substrings of legitimate unrelated paths. This will cause incorrect 429 responses on endpoints that should not be rate-limited.

Contrast with the existing `__init__.py` implementation (line 244-250) which uses an explicit `_check_rate_limit(endpoint, req)` function where the endpoint name is passed directly by the route handler, not inferred from the path.

**Fix:**
```python
def _infer_endpoint_key(path: str) -> Optional[str]:
    """Infer rate limit key from request path using prefix segment matching."""
    # Strip leading slash and take the first path segment
    segment = path.lstrip("/").split("/")[0]
    # Then check second segment for compound keys like 'watchlist/add'
    parts = path.lstrip("/").split("/", 2)
    if len(parts) >= 2:
        compound = f"{parts[0]}/{parts[1]}"
        if compound in _RATE_LIMITS:
            return compound
    if segment in _RATE_LIMITS:
        return segment
    return None
```

Or better yet, follow the pattern in `__init__.py` where routes explicitly pass the endpoint key rather than inferring it from the URL path.

### CR-02: `get_provider()` is not thread-safe — race condition on `_provider_singleton` check-then-set

**File:** `jellyswipe/dependencies.py:104-108`
**Issue:** The `get_provider()` function performs a check-then-set on `_app._provider_singleton` without any synchronization:

```python
if _app._provider_singleton is None:
    from jellyswipe.jellyfin_library import JellyfinLibraryProvider
    _app._provider_singleton = JellyfinLibraryProvider(_app._JELLYFIN_URL)
```

Under concurrent requests (which is the norm for FastAPI with uvicorn), multiple threads can observe `_provider_singleton is None` simultaneously, creating multiple `JellyfinLibraryProvider` instances and overwriting each other. While the existing `create_app()` code in `__init__.py` (lines 236-240) has the same pattern (so this is a pre-existing architectural issue), the new dependency layer introduces an additional access path that exacerbates it. At minimum, this can waste resources creating duplicate provider instances. At worst, if `JellyfinLibraryProvider.__init__` has side effects (network connections, state initialization), this can cause connection leaks or inconsistent state.

**Fix:**
```python
import threading

_provider_lock = threading.Lock()

def get_provider():
    """FastAPI dependency that returns the JellyfinLibraryProvider singleton."""
    import jellyswipe as _app

    if _app._provider_singleton is None:
        with _provider_lock:
            # Double-check after acquiring lock
            if _app._provider_singleton is None:
                from jellyswipe.jellyfin_library import JellyfinLibraryProvider
                _app._provider_singleton = JellyfinLibraryProvider(_app._JELLYFIN_URL)

    return _app._provider_singleton
```

## Warnings

### WR-01: `get_provider()` depends on module-level private attributes that may not be initialized in all import contexts

**File:** `jellyswipe/dependencies.py:102-106`
**Issue:** The function accesses `_app._provider_singleton` and `_app._JELLYFIN_URL` — both private module-level variables set during `jellyswipe/__init__.py` execution. The lazy import `import jellyswipe as _app` inside the function body will trigger full `__init__.py` execution on first call. If `JELLYFIN_URL` env var is not set (e.g., in certain test configurations or misconfigured deployments), `__init__.py` raises `RuntimeError` at line 67 before `_JELLYFIN_URL` is assigned at line 73. This means the `get_provider()` dependency will crash with an unhelpful error on the first authenticated request in a misconfigured environment, rather than failing fast at startup.

**Fix:** Consider initializing `_JELLYFIN_URL` before the validation check in `__init__.py`, or wrapping the lazy import with a clearer error message. This is also relevant for the test in `test_dependencies.py:225-236` which calls `get_provider()` directly — see WR-03.

### WR-02: Test fixtures `db_path` redefined locally in `test_auth.py` — shadows `conftest.py` fixture

**File:** `tests/test_auth.py:33-38`
**Issue:** The `db_path` fixture in `test_auth.py` is defined identically to the one in `conftest.py` (lines 82-93), but additionally calls `jellyswipe.db.init_db()`. This shadows the shared fixture. Both fixtures yield the same type and name, which means pytest will use the locally-defined one in `test_auth.py` but the conftest one elsewhere. The subtle difference (`init_db()` call) means the local fixture creates the schema, while the conftest one does not. Tests that use `db_path` from conftest without also calling `init_db()` will fail. This is already visible in `test_auth.py` where nearly every test redundantly calls `monkeypatch.setattr(jellyswipe.db, "DB_PATH", db_path)` and `jellyswipe.db.init_db()` despite the fixture already doing both.

**Fix:** Remove the local `db_path` fixture from `test_auth.py` and use the one from `conftest.py`. If `init_db()` is needed, add it to the conftest fixture or create a separate `db_path_with_schema` fixture.

### WR-03: `test_returns_same_instance_on_multiple_calls` calls `get_provider()` without mocking — may trigger real Jellyfin connection

**File:** `tests/test_dependencies.py:225-236`
**Issue:** This test sets `app._provider_singleton = None` and then calls `get_provider()` twice. When `_provider_singleton` is `None`, `get_provider()` will execute `JellyfinLibraryProvider(_app._JELLYFIN_URL)` — this creates a real `JellyfinLibraryProvider` instance using the test env var `http://test.jellyfin.local`. If `JellyfinLibraryProvider.__init__` makes network calls (common for library provider singletons), this will fail or hang in offline CI environments. Even if it doesn't connect in `__init__`, it creates a real object when a mock would be more appropriate and faster.

**Fix:**
```python
def test_returns_same_instance_on_multiple_calls(self, monkeypatch):
    """Calling get_provider() multiple times returns the same instance (singleton)."""
    import jellyswipe as app
    from unittest.mock import MagicMock, patch

    app._provider_singleton = None

    with patch("jellyswipe.dependencies.JellyfinLibraryProvider", autospec=True) as MockProvider:
        mock_instance = MagicMock()
        MockProvider.return_value = mock_instance

        # Need to also patch the lazy import inside get_provider
        # ...
        provider1 = get_provider()
        provider2 = get_provider()

    assert provider1 is provider2
    assert app._provider_singleton is not None
```

Or more simply, test singleton behavior by setting a mock, verifying it returns the same mock on subsequent calls (as done in the first test), and then testing the None → initialized path separately with proper mocking.

### WR-04: `test_create_session_calls_cleanup` patches wrong import path — may not intercept actual cleanup call

**File:** `tests/test_auth.py:169`
**Issue:** The test patches `'jellyswipe.auth.cleanup_expired_tokens'`, but `auth.py` imports `cleanup_expired_tokens` directly at the top level: `from jellyswipe.db import get_db_closing, cleanup_expired_tokens`. Since the import is already resolved at module load time, patching `'jellyswipe.auth.cleanup_expired_tokens'` patches the reference in the `auth` module's namespace, which is correct for this case. However, the test then goes through a full HTTP round-trip (TestClient POST), which means `jellyswipe.auth.create_session` is called indirectly. The mock assertion `mock_cleanup.assert_called_once()` will pass, but only because the patch target matches the import. If the import were ever changed to a different style (e.g., `jellyswipe.db.cleanup_expired_tokens()`), this test would silently stop catching the call. This is fragile.

**Fix:** Patch at the source module `'jellyswipe.db.cleanup_expired_tokens'` which is the canonical location. This ensures the mock intercepts regardless of how the function is imported in `auth.py`.

## Info

### IN-01: Duplicated test logic across `test_auth.py` and `test_dependencies.py`

**Files:** `tests/test_auth.py:241-295` and `tests/test_dependencies.py:27-80`
**Issue:** Both files contain `TestRequireAuth` classes with nearly identical tests: `test_raises_401_for_unauthenticated_request`/`test_raises_401_for_empty_session`, `test_raises_401_when_session_id_not_in_vault`, etc. The difference is that `test_auth.py` tests via TestClient (integration-style) while `test_dependencies.py` tests with mock Request objects (unit-style). This duplication increases maintenance burden — changes to `require_auth` behavior need to be reflected in both files.

**Fix:** This is acceptable as integration + unit test layers, but consider naming the test classes to distinguish their scope (e.g., `TestRequireAuthIntegration` vs `TestRequireAuthUnit`) to make the distinction explicit.

### IN-02: `TestCheckRateLimit` duplicated across both test files with identical test methods

**Files:** `tests/test_auth.py:332-371` and `tests/test_dependencies.py:120-176`
**Issue:** Both files have `TestCheckRateLimit.test_raises_429_when_limit_exceeded` and `TestCheckRateLimit.test_passes_through_unlisted_paths` with functionally identical implementations. The `test_dependencies.py` version adds an extra `test_passes_through_when_under_limit` and asserts the response body detail, but the core test logic is duplicated.

**Fix:** Consolidate the rate limit tests into one file, or clearly delineate which file is responsible for which aspect of the dependency testing.

### IN-03: `test_auth.py:TestGetDbDep` and `test_dependencies.py:TestGetDbDep` are identical

**Files:** `tests/test_auth.py:301-326` and `tests/test_dependencies.py:87-114`
**Issue:** These two test classes have the exact same test method (`test_yields_connection_and_closes`) with the same logic. This is pure duplication with no difference in test scope or approach.

**Fix:** Remove from one file. Since `get_db_dep` is defined in `dependencies.py`, the test in `test_dependencies.py` is the natural home.

---

_Reviewed: 2026-05-02T12:00:00Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
