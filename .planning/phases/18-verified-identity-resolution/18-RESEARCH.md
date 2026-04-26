# Phase 18 Research: Verified Identity Resolution

**Phase:** 18  
**Date:** 2026-04-25  
**Scope:** SEC-01, SEC-02

## Objective

Define a low-churn implementation for identity hardening that:
- accepts only trusted server-side identity sources,
- rejects spoofable identity aliases,
- preserves compatibility for valid Jellyfin token flows,
- and supports short-lived token-to-user-id caching.

## Current-State Findings

### Identity resolution flow (`jellyswipe/__init__.py`)
- `_provider_user_id_from_request()` currently checks delegated session identity first, then accepts user-controlled alias headers, then falls back to validated token lookup.
- Alias acceptance (`X-Provider-User-Id`, `X-Jellyfin-User-Id`, `X-Emby-UserId`) is the critical spoofing vector.

### Token validation flow (`jellyswipe/jellyfin_library.py`)
- `extract_media_browser_token()` uses tolerant `Token="..."` parsing.
- `resolve_user_id_from_token()` validates token by calling Jellyfin (`/Users/Me`, with fallback behavior for 400 responses).
- Existing provider caching patterns are process-local in-memory fields, making a short-lived in-memory map a consistent approach.

## Recommended Implementation Strategy

### 1) Identity resolver hardening
Update `_provider_user_id_from_request()` to:
1. Use delegated identity path first (existing behavior).
2. Detect spoofable alias headers; if present, treat as unauthorized input.
3. Otherwise parse token via `_jellyfin_user_token_from_request()` and resolve via provider.
4. Return unresolved/unauthorized result distinctly so callers can apply security behavior cleanly.

### 2) Unauthorized alias signaling
Introduce a small internal helper contract (in `jellyswipe/__init__.py`) to differentiate:
- `no identity provided`,
- `token lookup failed`,
- `spoof header detected`.

This prevents routes from silently treating malicious alias usage the same as missing auth.

### 3) Token-to-user-id cache
Add process-local cache in `jellyswipe/__init__.py`:
- key: SHA-256 hash of token (never raw token in memory map keys/logs),
- value: resolved user id + expiry timestamp,
- TTL: 300 seconds.

Behavior:
- cache hit before provider call,
- cache miss/expiry triggers provider resolution and cache refresh,
- failed resolutions do not populate cache.

### 4) Compatibility guarantees
- Keep tolerant `Token="..."` parsing unchanged.
- Keep delegated-identity priority unchanged.
- Continue to trust Jellyfin as source of truth for token->user resolution.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| False unauthorized if alias header appears from legacy client | Medium | Explicitly document header policy in code comments and API error text |
| Cache staleness for rapidly changing server permissions | Low | Short TTL (5 minutes) and process-local scope |
| Behavioral drift in routes not yet enforcing 401 uniformly | Medium | Phase 18 limits to resolver + trusted-source policy; Phase 19 handles route-level uniform auth responses |

## Validation Architecture

Phase 18 should validate identity-source behavior and compatibility with lightweight checks:
- static checks for alias-header branch removal/rejection,
- compilation check for modified modules,
- targeted route smoke checks in execution summary.

Recommended verification commands during execution:
- `python -m py_compile jellyswipe/__init__.py jellyswipe/jellyfin_library.py`
- `rg "X-Provider-User-Id|X-Jellyfin-User-Id|X-Emby-UserId" jellyswipe/__init__.py`
- `rg "_provider_user_id_from_request|extract_media_browser_token|resolve_user_id_from_token" jellyswipe/__init__.py jellyswipe/jellyfin_library.py`

## Planning Notes for Executor

- Keep changes localized to `jellyswipe/__init__.py` unless provider-layer change is strictly required.
- Do not alter parser behavior in provider token extraction.
- Do not add new external dependencies; use stdlib (`hashlib`, `time`) only.
- Preserve existing route signatures and JSON payload shapes in this phase.
