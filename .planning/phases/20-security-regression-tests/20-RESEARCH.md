# Phase 20 Research: Security Regression Tests

**Date:** 2026-04-25  
**Phase:** 20 — Security Regression Tests  
**Inputs:** `20-CONTEXT.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `jellyswipe/__init__.py`, `tests/conftest.py`

## Goal-Oriented Findings

Phase 20 should add route-level regression tests that prove security hardening from Phases 18 and 19 remains intact:

- Spoofed alias headers are rejected on protected routes (`VER-01`)
- Request-body `user_id` injection cannot bypass identity protections (`VER-02`)
- Valid delegate/token identity flows still succeed (`VER-03`)

## Current Test Baseline

- Existing tests focus on `db.py` and `jellyfin_library.py`; there is no route-level auth regression suite yet.
- `tests/conftest.py` already provides environment setup and isolated DB fixture patterns.
- Current `pytest` environment has a known blocker: `mocker` fixture unavailable. New tests should avoid dependence on pytest-mock and rely on `monkeypatch`/`unittest.mock`.

## Route Behavior Under Test

Protected routes in scope (`jellyswipe/__init__.py`):

- `POST /room/swipe`
- `GET /matches`
- `POST /matches/delete`
- `POST /undo`
- `POST /watchlist/add`

Expected unauthorized contract for all protected routes:
- HTTP `401`
- JSON payload `{"error": "Unauthorized"}`

## Recommended Test Architecture

1. Create a dedicated route-security test module (e.g., `tests/test_route_authorization.py`) for clarity and maintainability.
2. Use Flask `app.test_client()` for route-level contract testing.
3. Parametrize header spoofing matrix:
   - headers: `X-Provider-User-Id`, `X-Jellyfin-User-Id`, `X-Emby-UserId`
   - routes: all protected endpoints
4. Add helper fixtures for:
   - seed room/session state required by route handlers
   - patching `get_provider()` behaviors for delegate/token success paths
5. For `/room/swipe` injection cases, assert both response and DB side effects (no unauthorized writes).

## Data Integrity Assertions for Injection Safety

For unauthorized `/room/swipe` with injected body `user_id`:

- Assert response is `401` unauthorized
- Assert no swipe/match row exists for injected user identity
- Assert no cross-user writes are introduced into `matches`

## Valid-Flow Regression Strategy

For each protected route:

- Delegate flow case: session delegate identity enabled + provider delegate methods patched to return valid identity/token
- Token flow case: Authorization header token path patched to resolve valid identity
- Assert non-401 outcome and expected success/result contract for route semantics

## Risk Notes

- `/room/swipe` currently records swipe rows using session `my_user_id`; this is legacy behavior and separate from verified provider identity used in match scoping. Tests should reflect current behavior, not redesign it in this phase.
- Known `pytest-mock` fixture issue can break unrelated tests; Phase 20 tests should be written without requiring `mocker` fixture to reduce toolchain coupling.

## Verification Targets for Planning

- Full spoofed-header matrix exists and asserts `401` + payload contract.
- Body `user_id` injection tests assert unauthorized and no write side effects.
- Delegate and token valid paths are both covered across protected routes.
- New test module runs under current pytest setup without requiring `mocker`.

## Validation Architecture

### Dimension Mapping

1. **Unauthorized contract fidelity:** all protected routes return exact contract on identity failure.
2. **Spoof/injection resistance:** untrusted identity inputs cannot influence authorization.
3. **Regression safety:** legitimate delegate/token flows still function.
4. **Route-level confidence:** tests verify full request/response path and DB side effects.

### Sampling Plan

- Static checks for test matrix completeness (headers x routes).
- Targeted test execution of new route-security module during implementation.
- Full `pytest -q` run captured with known environment caveat if fixture blocker persists.

### Evidence Artifacts

- New route security test module in `tests/`
- Phase 20 plan and summary artifacts
- Test output proving `VER-01`, `VER-02`, and `VER-03` coverage
