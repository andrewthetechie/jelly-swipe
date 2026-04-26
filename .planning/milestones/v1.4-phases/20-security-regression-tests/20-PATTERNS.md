# Phase 20 Pattern Map: Security Regression Tests

**Phase:** 20 — Security Regression Tests  
**Generated:** 2026-04-25

## Pattern 1: Fixture-driven isolated DB tests

- **Analog:** `tests/conftest.py` + `tests/test_db.py`
- **Use:** Reuse `db_connection` and `tmp_path` isolation style for deterministic route-side-effect checks.

## Pattern 2: Monkeypatch-first mocking (no pytest-mock dependency)

- **Analog:** existing tests already rely on `monkeypatch`; known `mocker` fixture issue is environment-sensitive.
- **Use:** Prefer `monkeypatch` and `unittest.mock.patch` in new route tests to keep suite resilient.

## Pattern 3: Parametrized matrix coverage

- **Analog:** current test style is explicit but repetitive; Phase 20 needs broad coverage surface.
- **Use:** Parametrize `(route, method, payload)` and `(alias_header_name, alias_value)` combinations for spoofing matrix.

## Pattern 4: Unauthorized contract assertions

- **Source behavior:** protected routes return `_unauthorized_response()` in `jellyswipe/__init__.py`
- **Use:** Assert exact `status_code == 401` and JSON payload equals `{"error":"Unauthorized"}`.

## Pattern 5: Side-effect assertions for security tests

- **Analog:** `tests/test_db.py` validates row-level outcomes.
- **Use:** For injection tests, assert DB row counts and user scoping after unauthorized attempts.

## File Targets for Phase 20

- **Primary new file:** `tests/test_route_authorization.py`
- **Optional updates:** `tests/conftest.py` for shared client/provider fixtures (if needed, minimal churn)

## Suggested Plan Sequencing

1. Add test harness fixtures and helper utilities for route authorization testing.
2. Implement spoofed-header matrix + body-injection side-effect tests.
3. Implement delegate/token valid-flow regression tests.
4. Run targeted and full-suite verification, document known environment blockers if present.
