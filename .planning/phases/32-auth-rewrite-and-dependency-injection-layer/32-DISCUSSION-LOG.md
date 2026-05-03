# Phase 32: Auth Rewrite and Dependency Injection Layer - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-02
**Phase:** 32-auth-rewrite-and-dependency-injection-layer
**Areas discussed:** require_auth() design, get_db_dep() lifecycle, Phase 32 scope, check_rate_limit() pattern

---

## `require_auth()` Design

| Option | Description | Selected |
|--------|-------------|----------|
| Plain tuple `Tuple[str, str]` | Routes do `jf_token, user_id = auth` | |
| `AuthUser` dataclass | Named access: `auth.jf_token`, `auth.user_id` | ✓ |

**User's choice:** `AuthUser` dataclass return type
**Notes:** Also confirmed thin wrapper calling `auth.get_current_token()` internally. Added `destroy_session_dep()` to exports list.

---

## `get_db_dep()` Lifecycle

| Option | Description | Selected |
|--------|-------------|----------|
| Factory function | Returns open connection; route manages lifecycle | |
| Yield dependency | Opens+yields+closes per request (FastAPI-idiomatic) | ✓ |

**User's choice:** Yield dependency wrapping `get_db_closing()`
**Notes:** Also confirmed `DBConn = Annotated[sqlite3.Connection, Depends(get_db_dep)]` type alias to be exported.

---

## Phase 32 Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Wire routes now | Update `__init__.py` routes to `Depends(require_auth)` in Phase 32 | |
| Wire in Phase 33 | Phase 32 creates module only; Phase 33 wires during router extraction | ✓ |

**User's choice:** Phase 32 creates `dependencies.py` only; wiring happens in Phase 33
**Notes:** CR-01 (connection leak) and CR-02 (session/vault TTL mismatch) from Phase 31 code review are out of scope for Phase 32.

---

## `check_rate_limit()` Depends() Design

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Factory | `Depends(rate_limit_for("endpoint"))` per route | |
| (b) Path inference | Reads `request.url.path` to determine endpoint key | ✓ |
| (c) Plain helper | Regular function, not Depends-wrapped | |

**User's choice:** Request path inference — `request.url.path` as lookup key against `_RATE_LIMITS`
**Notes:** Paths not in `_RATE_LIMITS` pass through without a limit.

---

## Claude's Discretion

- `AuthUser` dataclass defined in `dependencies.py` (not `auth.py`) — it's a FastAPI DI concept
- `check_rate_limit()` raises `HTTPException(status_code=429)` directly; return value unused
- `_provider_singleton` global stays in `__init__.py` until Phase 33 extracts routers

## Deferred Ideas

- CR-01 connection leak fix — existing routes untouched until Phase 33 extraction
- CR-02 TTL mismatch — deferred to Phase 35 or standalone fix
