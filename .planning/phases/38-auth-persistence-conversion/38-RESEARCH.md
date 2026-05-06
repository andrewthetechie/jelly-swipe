# Phase 38: Auth Persistence Conversion - Research

**Researched:** 2026-05-05. [VERIFIED: research audit]
**Domain:** Async SQLAlchemy auth-session persistence in FastAPI. [VERIFIED: .planning/ROADMAP.md][VERIFIED: jellyswipe/auth.py]
**Confidence:** HIGH. [VERIFIED: research audit]

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

All bullets in this section are copied verbatim from `38-CONTEXT.md`. [VERIFIED: .planning/phases/38-auth-persistence-conversion/38-CONTEXT.md]

### Auth Repository and Service Boundary
- **D-01:** Auth persistence should use a thin repository plus a thin auth service.
- **D-02:** The auth service owns `session_id` generation and `created_at` generation.
- **D-03:** Token lookup should return a small typed auth record rather than a tuple or ORM entity.
- **D-04:** `require_auth` and auth routes should call the auth service only; they should not talk to the repository directly.

### Session Lifecycle Semantics
- **D-05:** Phase 38 does not need to preserve the current 64-character hex `session_id` shape; any opaque session identifier is acceptable.
- **D-06:** Expired-token cleanup should run on every new session creation.
- **D-07:** Destroy/logout should clear cookie and session state immediately, while vault cleanup may be best-effort asynchronous.
- **D-08:** If a cookie contains a `session_id` but no vault row exists, auth should treat that as an invalid session error and clear the stale session state aggressively.

### Auth Dependency Behavior
- **D-09:** `require_auth` should continue returning a lightweight `AuthUser`-style object.
- **D-10:** `require_auth` itself should clear invalid or stale session state when auth fails due to missing or bad persisted session data.
- **D-11:** Auth should continue trusting the persisted auth record and should not revalidate against Jellyfin on each request.
- **D-12:** Auth failures should keep the exact current external contract: `401` with `{"detail": "Authentication required"}`.

### Cleanup and Invalid-Session Handling
- **D-13:** Token cleanup should live in the auth service.
- **D-14:** If best-effort destroy cleanup fails after local session state is cleared, the app should swallow and log the failure.
- **D-15:** Cleanup remains request-driven in this phase; no new background or scheduled cleanup path is required.
- **D-16:** Cleanup verification should lean on repository/service unit tests, with route tests kept lighter and focused on visible auth behavior.

### the agent's Discretion
None. The user locked the main auth-persistence and invalid-session choices for this phase.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

Requirement descriptions in this section are copied from `REQUIREMENTS.md`, and the support column maps them to the findings below. [VERIFIED: .planning/REQUIREMENTS.md]

| ID | Description | Research Support |
|----|-------------|------------------|
| MVC-01 | Auth token vault reads, writes, cleanup, and destroy operations live behind async persistence functions instead of route/controller SQL. | Use the existing request-scoped `DatabaseUnitOfWork`, expand `AuthSessionRepository`, and route all auth routes plus `require_auth` through an async auth service boundary. [VERIFIED: jellyswipe/db_uow.py][VERIFIED: jellyswipe/dependencies.py][VERIFIED: .planning/phases/38-auth-persistence-conversion/38-CONTEXT.md] |
| PAR-01 | Existing auth/session behavior remains compatible, including `session_id` token vault lookup and 14-day token cleanup. | Preserve the current `AuthUser` output, `401` contract, `14`-day cleanup cutoff, and signed-session-cookie flow while moving the persistence path to async SQLAlchemy. [VERIFIED: jellyswipe/auth.py][VERIFIED: jellyswipe/__init__.py][VERIFIED: tests/test_auth.py][VERIFIED: tests/test_route_authorization.py] |
</phase_requirements>

## Project Constraints

- `AGENTS.md` is not present in the repo root. [VERIFIED: repo grep]
- No repo-local `.codex/skills/` or `.agents/skills/` directories are present, so this phase has no extra agent-skill conventions beyond the planning artifacts. [VERIFIED: repo grep]

## Summary

Phase 38 is intentionally narrow: the only persistence that must move in this phase is the auth-session vault path used by `create_session`, `get_current_token`, `destroy_session`, cleanup-on-create, and `require_auth`; room, swipe, match, and SSE persistence remain Phase 39 work even if auth routes still touch room state such as `active_room`. [VERIFIED: .planning/phases/38-auth-persistence-conversion/38-CONTEXT.md][VERIFIED: jellyswipe/auth.py][VERIFIED: jellyswipe/dependencies.py][VERIFIED: jellyswipe/routers/auth.py]

The codebase already has the correct infrastructure seam: `get_db_uow()` yields a request-scoped `DatabaseUnitOfWork`, owns commit/rollback/close, and `db_uow.py` already contains an `AuthSessionRepository` placeholder with async cleanup behavior. The planner should extend that seam instead of inventing a second async runtime or putting raw SQLAlchemy session work in routes or dependencies. [VERIFIED: jellyswipe/dependencies.py][VERIFIED: jellyswipe/db_uow.py][VERIFIED: tests/test_dependencies.py]

The highest-risk parity detail is session clearing, not CRUD. Starlette `SessionMiddleware` only emits a cookie-deletion header when a previously non-empty session is modified and becomes empty; popping only `session_id` can leave `active_room` or `solo_mode` behind and persist a non-empty cookie, which does not satisfy D-07 or D-10. [VERIFIED: .venv/lib/python3.13/site-packages/starlette/middleware/sessions.py][VERIFIED: jellyswipe/auth.py][VERIFIED: jellyswipe/routers/auth.py][VERIFIED: .planning/phases/38-auth-persistence-conversion/38-CONTEXT.md]

**Primary recommendation:** Reuse `jellyswipe/auth.py` as the thin async auth service, expand `DatabaseUnitOfWork.auth_sessions` into the full auth repository, make `require_auth` async, and clear the entire `request.session` before best-effort vault deletion on logout or invalid-session paths. [VERIFIED: jellyswipe/auth.py][VERIFIED: jellyswipe/db_uow.py][VERIFIED: jellyswipe/dependencies.py][VERIFIED: .planning/phases/38-auth-persistence-conversion/38-CONTEXT.md][ASSUMED]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Session creation on login or delegate auth | API / Backend | Database / Storage | The routes authenticate with Jellyfin, then create a server-owned vault row and session cookie entry; the browser only receives the signed session cookie. [VERIFIED: jellyswipe/routers/auth.py][VERIFIED: jellyswipe/auth.py][CITED: https://www.starlette.io/middleware/] |
| Current-session lookup for `require_auth` | API / Backend | Database / Storage | `require_auth` reads `request.session`, resolves `session_id` through vault persistence, and returns `AuthUser`; the lookup should stay server-side. [VERIFIED: jellyswipe/dependencies.py][VERIFIED: jellyswipe/auth.py][VERIFIED: .planning/phases/38-auth-persistence-conversion/38-CONTEXT.md] |
| Invalid-session clearing and logout | API / Backend | Browser / Client | The server must clear the signed session state immediately and only then do best-effort vault deletion; the browser just stores the signed cookie set by middleware. [VERIFIED: .planning/phases/38-auth-persistence-conversion/38-CONTEXT.md][VERIFIED: .venv/lib/python3.13/site-packages/starlette/middleware/sessions.py] |
| Expired token cleanup on new session creation | API / Backend | Database / Storage | Cleanup is request-driven in this phase and runs before the new row insert; no scheduler or client participation is required. [VERIFIED: .planning/phases/38-auth-persistence-conversion/38-CONTEXT.md][VERIFIED: jellyswipe/auth.py] |
| Auth-session persistence itself | Database / Storage | API / Backend | The repository owns CRUD against `auth_sessions`, while the auth service owns ordering and semantics. [VERIFIED: jellyswipe/db_uow.py][VERIFIED: jellyswipe/models/auth_session.py][VERIFIED: .planning/phases/38-auth-persistence-conversion/38-CONTEXT.md] |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | 2.0.49, released 2026-04-03. [VERIFIED: PyPI JSON] | Async ORM queries and unit-of-work repository operations over `auth_sessions`. [CITED: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html] | The repo already depends on it, Phase 37 already standardized on `AsyncSession`, and the official async API supports request-scoped session usage plus `run_sync()` for the remaining sync bridge cases. [VERIFIED: pyproject.toml][VERIFIED: .venv metadata][CITED: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html] |
| FastAPI | 0.136.1, released 2026-04-23. [VERIFIED: PyPI JSON] | Async dependency injection for `require_auth`, request access, and route/service integration. [CITED: https://fastapi.tiangolo.com/tutorial/dependencies/] | The app already routes all auth behavior through FastAPI, and FastAPI explicitly supports mixing async dependencies with sync or async path operations. [VERIFIED: pyproject.toml][VERIFIED: jellyswipe/routers/auth.py][CITED: https://fastapi.tiangolo.com/tutorial/dependencies/][CITED: https://fastapi.tiangolo.com/async/] |
| aiosqlite | 0.22.1, released 2025-12-23. [VERIFIED: PyPI JSON] | Async SQLite driver under SQLAlchemy’s async engine. [VERIFIED: pyproject.toml] | Phase 37 already selected the async SQLite runtime path and initialized it through `db_runtime.py`; Phase 38 should stay on that path. [VERIFIED: jellyswipe/db_runtime.py][VERIFIED: .venv metadata] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Starlette | 1.0.0, released 2026-03-22. [VERIFIED: PyPI JSON] | `SessionMiddleware` owns signed cookie persistence and cookie clearing behavior. [CITED: https://www.starlette.io/middleware/] | Use its `request.session` dictionary interface for all auth-session state mutation; do not hand-roll cookie signing or deletion. [VERIFIED: jellyswipe/__init__.py][VERIFIED: .venv/lib/python3.13/site-packages/starlette/middleware/sessions.py] |
| Alembic | 1.18.4, released 2026-02-10. [VERIFIED: PyPI JSON] | Temp database bootstrap for tests and schema continuity during this phase. [VERIFIED: pyproject.toml] | Use the existing Alembic-backed test bootstrap; Phase 38 should not bring back `init_db()`-style setup. [VERIFIED: tests/conftest.py][VERIFIED: .planning/phases/37-async-database-infrastructure/37-CONTEXT.md] |
| pytest + anyio | pytest 9.0.3 and anyio 4.13.0, released 2026-04-07 and 2026-03-24. [VERIFIED: PyPI JSON] | Async service, dependency, and route parity tests. [VERIFIED: .venv metadata] | Use for the new repository/service tests and for any direct async dependency invocation tests. [VERIFIED: tests/test_auth.py][VERIFIED: tests/test_dependencies.py] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Thin auth service over the existing UoW seam | Route-level SQL or direct `AsyncSession` injection into routes | This would violate D-04, duplicate commit/rollback handling already standardized in Phase 37, and make parity behavior harder to test. [VERIFIED: .planning/phases/38-auth-persistence-conversion/38-CONTEXT.md][VERIFIED: jellyswipe/dependencies.py] |
| Keeping `jellyswipe/auth.py` as the service module | Creating a new broad `services/` package now | A new package is possible, but it adds file churn without a project-wide service taxonomy yet; Phase 38 only needs one thin domain service. [VERIFIED: repo grep][ASSUMED] |
| Request-driven cleanup on session creation | Background job or scheduler | D-15 explicitly keeps cleanup request-driven in this phase, so a scheduler would be out of scope. [VERIFIED: .planning/phases/38-auth-persistence-conversion/38-CONTEXT.md] |

**Installation:** The repo already contains the required runtime and test dependencies; Phase 38 should use the existing environment rather than add packages. [VERIFIED: pyproject.toml][VERIFIED: .venv metadata]

```bash
uv sync
```

**Version verification:** The project virtualenv currently resolves `fastapi==0.136.1`, `sqlalchemy==2.0.49`, `alembic==1.18.4`, `aiosqlite==0.22.1`, `starlette==1.0.0`, `pytest==9.0.3`, and `anyio==4.13.0`; each matches the latest version returned by PyPI JSON on 2026-05-05. [VERIFIED: .venv metadata][VERIFIED: PyPI JSON]

## Architecture Patterns

### System Architecture Diagram

This diagram reflects the current route/dependency boundaries plus the locked Phase 38 decisions. [VERIFIED: jellyswipe/routers/auth.py][VERIFIED: jellyswipe/dependencies.py][VERIFIED: .planning/phases/38-auth-persistence-conversion/38-CONTEXT.md]

```text
Jellyfin login/delegate route
        |
        v
  async auth service
        |
        +--> delete expired sessions (14-day cutoff)
        |
        +--> generate session_id + created_at
        |
        v
 AuthSessionRepository (via request-scoped UoW)
        |
        v
 AsyncSession -> auth_sessions table
        |
        v
 request.session["session_id"] set by service

Protected route
        |
        v
 async require_auth
        |
        +--> read request.session["session_id"]
        +--> auth service lookup
        +--> if missing row: request.session.clear() -> raise 401
        |
        v
 AuthUser

Logout / invalid session path
        |
        v
 async auth service
        |
        +--> capture current session_id
        +--> request.session.clear()
        +--> best-effort repository delete + log failure
```

### Recommended Project Structure

This structure reuses existing boundaries and keeps Phase 38 scoped to auth instead of introducing a broader architecture taxonomy. [VERIFIED: repo grep][ASSUMED]

```text
jellyswipe/
├── auth.py                  # Thin async auth service + typed auth record
├── db_uow.py                # Request-scoped UoW + expanded AuthSessionRepository
├── dependencies.py          # Async require_auth + get_db_uow
├── models/auth_session.py   # ORM model for auth_sessions
└── routers/auth.py          # Auth controllers that await the service
tests/
├── test_auth.py             # Service + repository behavior
├── test_dependencies.py     # require_auth + UoW semantics
└── test_route_authorization.py
                           # Visible auth parity and logout/invalidation behavior
```

### Pattern 1: Thin Async Auth Service Over the Existing UoW

**What:** The service owns semantic steps and `request.session` mutation order; the repository owns only `auth_sessions` queries and deletes. [VERIFIED: .planning/phases/38-auth-persistence-conversion/38-CONTEXT.md][VERIFIED: jellyswipe/db_uow.py]

**When to use:** Use this for login, delegate auth, `require_auth` lookup, logout, and cleanup-on-create. [VERIFIED: jellyswipe/routers/auth.py][VERIFIED: jellyswipe/dependencies.py]

**Example:**

```python
# Source pattern: SQLAlchemy async ORM docs + current repo model/UoW seam.
# Docs: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import secrets

from sqlalchemy import delete, select

from jellyswipe.models.auth_session import AuthSession


@dataclass(slots=True)
class AuthRecord:
    session_id: str
    jf_token: str
    user_id: str
    created_at: str


class AuthSessionRepository:
    async def get_by_session_id(self, session_id: str) -> AuthRecord | None:
        row = (
            await self._session.scalars(
                select(AuthSession).where(AuthSession.session_id == session_id)
            )
        ).one_or_none()
        if row is None:
            return None
        return AuthRecord(
            session_id=row.session_id,
            jf_token=row.jellyfin_token,
            user_id=row.jellyfin_user_id,
            created_at=row.created_at,
        )

    async def insert(self, record: AuthRecord) -> None:
        self._session.add(
            AuthSession(
                session_id=record.session_id,
                jellyfin_token=record.jf_token,
                jellyfin_user_id=record.user_id,
                created_at=record.created_at,
            )
        )

    async def delete_by_session_id(self, session_id: str) -> int:
        result = await self._session.execute(
            delete(AuthSession).where(AuthSession.session_id == session_id)
        )
        return result.rowcount or 0


async def create_session(jf_token: str, jf_user_id: str, session_dict: dict, uow) -> str:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    await uow.auth_sessions.delete_expired(cutoff)
    session_id = secrets.token_urlsafe(32)
    record = AuthRecord(
        session_id=session_id,
        jf_token=jf_token,
        user_id=jf_user_id,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    await uow.auth_sessions.insert(record)
    session_dict["session_id"] = session_id
    return session_id
```

### Pattern 2: Async `require_auth` That Clears Invalid Session State

**What:** `require_auth` should await the auth service, clear stale session state when lookup fails, and keep the exact `401` contract. [VERIFIED: .planning/phases/38-auth-persistence-conversion/38-CONTEXT.md][VERIFIED: jellyswipe/dependencies.py]

**When to use:** Use this for all routes that currently depend on `require_auth`, including sync path-operation functions. FastAPI supports async dependencies inside normal `def` path operations. [VERIFIED: jellyswipe/routers/auth.py][VERIFIED: jellyswipe/routers/rooms.py][VERIFIED: jellyswipe/routers/media.py][CITED: https://fastapi.tiangolo.com/tutorial/dependencies/][CITED: https://fastapi.tiangolo.com/async/]

**Example:**

```python
# Source pattern: FastAPI dependency docs + Starlette session behavior.
# Docs: https://fastapi.tiangolo.com/tutorial/dependencies/
# Docs: https://www.starlette.io/middleware/
from fastapi import HTTPException, Request

from jellyswipe.dependencies import AuthUser


async def require_auth(request: Request, uow) -> AuthUser:
    record = await auth.get_current_session(request.session, uow)
    if record is None:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Authentication required")
    return AuthUser(jf_token=record.jf_token, user_id=record.user_id)
```

### Anti-Patterns to Avoid

- **Route-level DB calls in auth code:** Do not have `routers/auth.py` or `dependencies.py` query `auth_sessions` directly; D-04 locks those callers to the service boundary. [VERIFIED: .planning/phases/38-auth-persistence-conversion/38-CONTEXT.md]
- **`asyncio.run()` inside request auth flows:** The sync wrappers in `jellyswipe/db.py` exist for off-request compatibility and startup maintenance, not for request-time auth persistence. [VERIFIED: jellyswipe/db.py][VERIFIED: .planning/phases/37-async-database-infrastructure/37-CONTEXT.md]
- **Partial session clearing:** Popping only `session_id` can leave `active_room` or `solo_mode` behind and keep a non-empty cookie alive. [VERIFIED: jellyswipe/auth.py][VERIFIED: jellyswipe/routers/auth.py][VERIFIED: .venv/lib/python3.13/site-packages/starlette/middleware/sessions.py]
- **Sharing one `AsyncSession` across concurrent tasks:** SQLAlchemy documents `AsyncSession` as not safe for concurrent tasks. [CITED: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Session cookie signing and deletion | Custom cookie format or manual logout cookie logic | Starlette `SessionMiddleware` plus `request.session.clear()` | The middleware already signs session cookies and emits an expired cookie when a previously non-empty session becomes empty. [CITED: https://www.starlette.io/middleware/][VERIFIED: .venv/lib/python3.13/site-packages/starlette/middleware/sessions.py] |
| Request transaction ownership | Manual commit/rollback in every auth helper | `get_db_uow()` dependency | The existing dependency already centralizes commit, rollback, and close, and tests assert that behavior. [VERIFIED: jellyswipe/dependencies.py][VERIFIED: tests/test_dependencies.py] |
| Legacy sync bridging for auth | New sync wrappers around async auth repo calls | Native async auth service functions | Phase 38 is the auth conversion phase, and keeping sync wrappers in the request path would preserve the wrong abstraction. [VERIFIED: .planning/ROADMAP.md][VERIFIED: jellyswipe/db.py] |
| New cleanup scheduler | Background worker or periodic task | Request-driven cleanup in `create_session` | D-06 and D-15 explicitly keep cleanup on session creation only. [VERIFIED: .planning/phases/38-auth-persistence-conversion/38-CONTEXT.md] |

**Key insight:** The repo already has the difficult pieces: migrations, async engine/sessionmaker, request-scoped UoW, and auth-specific tests. Phase 38 should add domain semantics on that seam, not another persistence abstraction stack. [VERIFIED: jellyswipe/db_runtime.py][VERIFIED: jellyswipe/db_uow.py][VERIFIED: tests/test_auth.py]

## Common Pitfalls

### Pitfall 1: Clearing Only `session_id`

**What goes wrong:** Logout or invalid-session handling returns `401` correctly but leaves `active_room` or `solo_mode` in the signed cookie, so the cookie is not actually cleared. [VERIFIED: jellyswipe/auth.py][VERIFIED: jellyswipe/routers/auth.py][VERIFIED: .venv/lib/python3.13/site-packages/starlette/middleware/sessions.py]

**Why it happens:** Starlette only emits a cookie-expiry `Set-Cookie` when a previously non-empty session becomes empty; a modified but still non-empty session is re-signed instead. [VERIFIED: .venv/lib/python3.13/site-packages/starlette/middleware/sessions.py]

**How to avoid:** Call `request.session.clear()` for logout and invalid-session cleanup paths, then do best-effort vault deletion afterward. [VERIFIED: .planning/phases/38-auth-persistence-conversion/38-CONTEXT.md][VERIFIED: .venv/lib/python3.13/site-packages/starlette/middleware/sessions.py]

**Warning signs:** `POST /auth/logout` still leaves a `session` cookie in the client jar or stale `active_room` survives after a missing-vault-row auth failure. [VERIFIED: tests/test_route_authorization.py][ASSUMED]

### Pitfall 2: Preserving the Sync Auth Helper Shape

**What goes wrong:** The code keeps sync `create_session` / `get_current_token` / `destroy_session` helpers and starts sneaking `asyncio.run()` or sync connection fallbacks into request auth flows. [VERIFIED: jellyswipe/auth.py][VERIFIED: jellyswipe/db.py]

**Why it happens:** The old auth module predates Phase 37, so its API still matches the former `sqlite3` path. [VERIFIED: jellyswipe/auth.py][VERIFIED: .planning/phases/37-async-database-infrastructure/37-CONTEXT.md]

**How to avoid:** Make the service async end-to-end and let FastAPI await it through async routes or async dependencies. [CITED: https://fastapi.tiangolo.com/async/][CITED: https://fastapi.tiangolo.com/tutorial/dependencies/]

**Warning signs:** New auth code imports `get_db_closing()`, `cleanup_expired_auth_sessions()`, or `asyncio.run()` from request handlers. [VERIFIED: jellyswipe/db.py][VERIFIED: repo grep]

### Pitfall 3: Returning ORM Entities or Tuples From Lookup

**What goes wrong:** `require_auth` becomes coupled to ORM objects or keeps a positional tuple contract that obscures intent and makes parity/error handling brittle. [VERIFIED: jellyswipe/auth.py][VERIFIED: .planning/phases/38-auth-persistence-conversion/38-CONTEXT.md]

**Why it happens:** The current sync helper returns `(jf_token, jf_user_id)`, and it is easy to preserve that shape out of habit. [VERIFIED: jellyswipe/auth.py]

**How to avoid:** Return a small typed auth record from the service/repository seam and map that into `AuthUser` inside `require_auth`. [VERIFIED: .planning/phases/38-auth-persistence-conversion/38-CONTEXT.md]

**Warning signs:** Callers unpack raw tuples or import `AuthSession` ORM entities outside the repository. [VERIFIED: repo grep][ASSUMED]

### Pitfall 4: Sharing or Escaping the Request-Scoped `AsyncSession`

**What goes wrong:** Cleanup or lookup code reuses one `AsyncSession` across concurrent tasks or stores it on global state. [CITED: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html]

**Why it happens:** Async conversions often overcorrect toward background tasks or cached sessions. [ASSUMED]

**How to avoid:** Keep one request-scoped UoW per request and keep cleanup request-driven in the same UoW. [VERIFIED: jellyswipe/dependencies.py][VERIFIED: .planning/phases/38-auth-persistence-conversion/38-CONTEXT.md]

**Warning signs:** Service methods spawn background tasks, use `asyncio.gather()` on one session, or cache the UoW/session globally. [CITED: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html][ASSUMED]

## Code Examples

Verified patterns from official sources and the current repo:

### Async ORM Lookup + Typed Mapping

```python
# Source: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
from sqlalchemy import select

result = await session.scalars(
    select(AuthSession).where(AuthSession.session_id == session_id)
)
row = result.one_or_none()
```

This is the standard lookup shape to build `AuthRecord` from `AuthSession`. [CITED: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html][VERIFIED: jellyswipe/models/auth_session.py]

### Async Dependency Inside Existing Sync Routes

```python
# Source: https://fastapi.tiangolo.com/tutorial/dependencies/
async def require_auth(request: Request, uow: DBUoW) -> AuthUser:
    record = await auth.get_current_session(request.session, uow)
    if record is None:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Authentication required")
    return AuthUser(jf_token=record.jf_token, user_id=record.user_id)
```

FastAPI can await this dependency even when the calling route function remains `def`. [CITED: https://fastapi.tiangolo.com/tutorial/dependencies/][CITED: https://fastapi.tiangolo.com/async/]

### Best-Effort Logout Ordering

```python
# Source semantics: current Phase 38 decisions + Starlette session middleware behavior.
async def destroy_session(session_dict: dict, uow: DBUoW, logger) -> None:
    session_id = session_dict.get("session_id")
    session_dict.clear()
    if not session_id:
        return
    try:
        await uow.auth_sessions.delete_by_session_id(session_id)
    except Exception:
        logger.warning("auth_session_delete_failed", extra={"session_id": session_id})
```

This ordering satisfies D-07 and D-14 because local session state clears first and vault cleanup failure becomes non-fatal. [VERIFIED: .planning/phases/38-auth-persistence-conversion/38-CONTEXT.md][VERIFIED: .venv/lib/python3.13/site-packages/starlette/middleware/sessions.py][ASSUMED]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `jellyswipe/auth.py` uses `sqlite3` via `get_db_closing()` and returns tuples. [VERIFIED: jellyswipe/auth.py] | Phase 38 should move auth onto async SQLAlchemy via the Phase 37 UoW seam and return a typed auth record. [VERIFIED: jellyswipe/db_uow.py][VERIFIED: .planning/phases/38-auth-persistence-conversion/38-CONTEXT.md] | Phase 37 introduced the runtime seam; Phase 38 is the first domain conversion on top of it. [VERIFIED: .planning/ROADMAP.md][VERIFIED: .planning/phases/37-async-database-infrastructure/37-CONTEXT.md] | The planner can focus on auth semantics instead of inventing infrastructure. [VERIFIED: jellyswipe/db_runtime.py][VERIFIED: jellyswipe/dependencies.py] |
| Logout currently pops only `session_id`. [VERIFIED: jellyswipe/auth.py] | Phase 38 should clear the whole session before best-effort row deletion. [VERIFIED: .planning/phases/38-auth-persistence-conversion/38-CONTEXT.md][VERIFIED: .venv/lib/python3.13/site-packages/starlette/middleware/sessions.py] | This becomes necessary as soon as invalid-session clearing is a locked requirement. [VERIFIED: .planning/phases/38-auth-persistence-conversion/38-CONTEXT.md] | It avoids stale `active_room` or `solo_mode` state surviving logout or bad-vault lookups. [VERIFIED: jellyswipe/routers/auth.py][VERIFIED: jellyswipe/routers/rooms.py] |

**Deprecated/outdated:**
- Growing the auth request path around `get_db_closing()`, `cleanup_expired_auth_sessions()`, or tuple-returning helpers is outdated for Phase 38 because those are the exact sync persistence seams this phase is replacing. [VERIFIED: jellyswipe/auth.py][VERIFIED: jellyswipe/db.py][VERIFIED: .planning/ROADMAP.md]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Reusing `jellyswipe/auth.py` as the thin auth service is lower-risk than introducing a new `services/` package in this phase. [ASSUMED] | Summary; Standard Stack; Architecture Patterns | Low. The planner may choose a new file layout, but broader file churn could slow the phase without changing behavior. |
| A2 | Phase 38 should leave the `/me` room-existence check on its current path unless the planner decides it is required to satisfy the auth invalid-session contract. [ASSUMED] | Summary | Medium. If the user interprets MVC-01 as banning all route-level DB access in auth routes immediately, Phase 38 may need one extra room lookup conversion. |
| A3 | Existing tests do not yet prove stale-session clearing of non-auth keys or best-effort delete failure logging, so the planner should add those assertions. [ASSUMED] | Validation Architecture; Common Pitfalls | Medium. If hidden tests already cover this, Wave 0 can be smaller than recommended. |

## Open Questions

1. **Should Phase 38 also convert the `/me` room-existence lookup to async SQLAlchemy?**
   - What we know: `/me` currently does a sync `SELECT 1 FROM rooms` via `get_db_closing()`, but the phase goal and user decisions focus on auth vault persistence, not room persistence. [VERIFIED: jellyswipe/routers/auth.py][VERIFIED: .planning/phases/38-auth-persistence-conversion/38-CONTEXT.md]
   - What's unclear: Whether the planner should treat that one room lookup as acceptable Phase 39 work or fold it into this phase for stricter auth-route purity. [ASSUMED]
   - Recommendation: Keep Phase 38 focused on vault persistence unless implementation simplicity strongly favors converting the `/me` room check at the same time. [ASSUMED]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | App runtime and tests | ✓ [VERIFIED: command -v/python3] | 3.13.9. [VERIFIED: python3 --version] | — |
| `uv` | Dependency sync and script execution | ✓ [VERIFIED: command -v uv] | 0.9.5. [VERIFIED: uv --version] | Use `.venv/bin/python` and `.venv/bin/pytest` directly. [VERIFIED: repo grep] |
| SQLite CLI | Spot checks and local DB inspection | ✓ [VERIFIED: command -v sqlite3] | 3.51.0. [VERIFIED: sqlite3 --version] | SQLAlchemy/aiosqlite runtime does not require the CLI. [VERIFIED: pyproject.toml] |
| Project virtualenv | FastAPI, SQLAlchemy, Alembic, aiosqlite, pytest, anyio | ✓ [VERIFIED: .venv metadata] | `fastapi 0.136.1`, `sqlalchemy 2.0.49`, `alembic 1.18.4`, `aiosqlite 0.22.1`, `pytest 9.0.3`, `anyio 4.13.0`. [VERIFIED: .venv metadata] | `uv sync` if the venv drifts. [VERIFIED: pyproject.toml] |

**Missing dependencies with no fallback:**
- None. [VERIFIED: local environment audit]

**Missing dependencies with fallback:**
- None. [VERIFIED: local environment audit]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest 9.0.3` with `anyio 4.13.0`. [VERIFIED: .venv metadata] |
| Config file | `pyproject.toml`. [VERIFIED: pyproject.toml] |
| Quick run command | `.venv/bin/pytest tests/test_auth.py tests/test_dependencies.py tests/test_route_authorization.py -q`. [VERIFIED: local test run] |
| Full suite command | `.venv/bin/pytest`. [VERIFIED: pyproject.toml] |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MVC-01 | Auth vault CRUD and cleanup live behind async persistence/service seams. [VERIFIED: .planning/REQUIREMENTS.md] | unit + integration | `.venv/bin/pytest tests/test_auth.py tests/test_dependencies.py -q`. [VERIFIED: local test run] | `tests/test_auth.py` and `tests/test_dependencies.py` exist. [VERIFIED: repo grep] |
| PAR-01 | Login/delegate/logout/authorization keep the existing session behavior and `401` contract. [VERIFIED: .planning/REQUIREMENTS.md] | route/integration | `.venv/bin/pytest tests/test_route_authorization.py -q`. [VERIFIED: local test run] | `tests/test_route_authorization.py` exists. [VERIFIED: repo grep] |

### Sampling Rate

- **Per task commit:** `.venv/bin/pytest tests/test_auth.py tests/test_dependencies.py -q` for service/dependency edits, and add `tests/test_route_authorization.py -q` whenever route behavior changes. [VERIFIED: local test run]
- **Per wave merge:** `.venv/bin/pytest tests/test_auth.py tests/test_dependencies.py tests/test_route_authorization.py -q`. [VERIFIED: local test run]
- **Phase gate:** `.venv/bin/pytest` green before `$gsd-verify-work`. [VERIFIED: pyproject.toml]

### Wave 0 Gaps

- [ ] Add a dedicated async repository/service test for `AuthSessionRepository.get_by_session_id()`, `insert()`, and best-effort delete behavior; current coverage is strong on route parity but still centered on the old sync helper API. [VERIFIED: tests/test_auth.py][VERIFIED: tests/test_dependencies.py][ASSUMED]
- [ ] Add an assertion that invalid-session handling clears all session state, not only `session_id`; current tests verify the `401` contract but not the cookie/session payload shape after stale-vault lookup. [VERIFIED: tests/test_auth.py][VERIFIED: tests/test_dependencies.py][ASSUMED]
- [ ] Add a route or service test that delete failure after local clear is swallowed and logged, per D-14; no existing auth test asserts that behavior. [VERIFIED: repo grep][ASSUMED]
- [ ] Review `tests/test_db.py::test_cleanup_expired_auth_sessions_stays_sync_safe_in_async_context`; that test protects the legacy sync wrapper and may need to stay focused on `jellyswipe.db` compatibility rather than request-time auth behavior after the Phase 38 conversion. [VERIFIED: tests/test_db.py][ASSUMED]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes. [VERIFIED: .planning/REQUIREMENTS.md] | `require_auth` resolves signed-cookie session state through the server-side auth vault and returns `AuthUser`. [VERIFIED: jellyswipe/dependencies.py][VERIFIED: jellyswipe/auth.py] |
| V3 Session Management | yes. [VERIFIED: jellyswipe/__init__.py] | Starlette `SessionMiddleware` signs the cookie, and Phase 38 must clear the full session on logout or stale-vault failure. [CITED: https://www.starlette.io/middleware/][VERIFIED: .venv/lib/python3.13/site-packages/starlette/middleware/sessions.py][VERIFIED: .planning/phases/38-auth-persistence-conversion/38-CONTEXT.md] |
| V4 Access Control | no new scope. [VERIFIED: .planning/phases/38-auth-persistence-conversion/38-CONTEXT.md] | This phase preserves the current authenticated-user gate rather than adding new authorization rules. [VERIFIED: jellyswipe/dependencies.py] |
| V5 Input Validation | yes. [VERIFIED: jellyswipe/routers/auth.py] | Keep request parsing minimal and keep repository queries parameterized through SQLAlchemy or bound statements. [VERIFIED: jellyswipe/routers/auth.py][CITED: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html][ASSUMED] |
| V6 Cryptography | limited. [VERIFIED: jellyswipe/__init__.py][VERIFIED: jellyswipe/auth.py] | Use framework cookie signing plus `secrets` for opaque session IDs; do not introduce custom crypto. [CITED: https://www.starlette.io/middleware/][VERIFIED: jellyswipe/auth.py] |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Cookie contains `session_id` but vault row is gone | Spoofing | Clear the full session immediately and return the unchanged `401` contract. [VERIFIED: .planning/phases/38-auth-persistence-conversion/38-CONTEXT.md][VERIFIED: .venv/lib/python3.13/site-packages/starlette/middleware/sessions.py] |
| Logout clears only auth key but leaves room/session residue | Elevation of Privilege | Use `request.session.clear()` before best-effort delete. [VERIFIED: jellyswipe/auth.py][VERIFIED: .planning/phases/38-auth-persistence-conversion/38-CONTEXT.md][VERIFIED: .venv/lib/python3.13/site-packages/starlette/middleware/sessions.py] |
| Raw SQL interpolation in auth queries | Tampering | Use ORM `select()` / `delete()` or bound parameters only. [CITED: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html][ASSUMED] |
| Sharing a request `AsyncSession` across concurrent tasks | Denial of Service / Tampering | Keep one request-scoped UoW per request and do not fan out auth repo work concurrently. [CITED: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html] |

## Sources

### Primary (HIGH confidence)

- `jellyswipe/auth.py` - current sync auth CRUD, tuple return contract, and logout behavior. [VERIFIED: jellyswipe/auth.py]
- `jellyswipe/dependencies.py` - current `require_auth` contract and Phase 37 UoW dependency seam. [VERIFIED: jellyswipe/dependencies.py]
- `jellyswipe/db_uow.py` - existing `AuthSessionRepository` and request-scoped UoW surface. [VERIFIED: jellyswipe/db_uow.py]
- `jellyswipe/__init__.py` - current `SessionMiddleware` setup and `14`-day cookie lifetime. [VERIFIED: jellyswipe/__init__.py]
- `tests/test_auth.py`, `tests/test_dependencies.py`, `tests/test_route_authorization.py`, `tests/test_db.py` - current auth parity coverage and remaining validation gaps. [VERIFIED: tests/test_auth.py][VERIFIED: tests/test_dependencies.py][VERIFIED: tests/test_route_authorization.py][VERIFIED: tests/test_db.py]
- SQLAlchemy asyncio docs - async session semantics, request-scoped use, and concurrency warning. [CITED: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html]
- FastAPI dependency and async docs - async dependency support inside sync or async routes. [CITED: https://fastapi.tiangolo.com/tutorial/dependencies/][CITED: https://fastapi.tiangolo.com/async/]
- Starlette middleware docs - `SessionMiddleware` ownership of signed cookie sessions. [CITED: https://www.starlette.io/middleware/]
- Starlette 1.0.0 installed middleware source - exact cookie-clearing behavior when `session.clear()` empties a previously non-empty session. [VERIFIED: .venv/lib/python3.13/site-packages/starlette/middleware/sessions.py]
- PyPI JSON for `sqlalchemy`, `fastapi`, `aiosqlite`, `alembic`, `starlette`, `pytest`, and `anyio` - current versions and release dates. [VERIFIED: PyPI JSON]

### Secondary (MEDIUM confidence)

- Context7 `sqlalchemy`, `fastapi`, and `starlette` lookups - corroborated the official docs topics used above. [VERIFIED: ctx7 CLI]

### Tertiary (LOW confidence)

- None. All major implementation and framework claims above were verified against repo code, installed source, or official docs. [VERIFIED: research audit]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - The repo already pins and installs the relevant versions, and each was cross-checked against PyPI JSON plus official docs. [VERIFIED: pyproject.toml][VERIFIED: .venv metadata][VERIFIED: PyPI JSON]
- Architecture: HIGH - The auth conversion seam is explicit in Phase 37 and Phase 38 context, and the codebase already exposes the required UoW boundary. [VERIFIED: .planning/phases/37-async-database-infrastructure/37-CONTEXT.md][VERIFIED: .planning/phases/38-auth-persistence-conversion/38-CONTEXT.md][VERIFIED: jellyswipe/dependencies.py]
- Pitfalls: HIGH - The biggest risks are directly visible in current repo code and Starlette’s installed middleware implementation. [VERIFIED: jellyswipe/auth.py][VERIFIED: jellyswipe/routers/auth.py][VERIFIED: .venv/lib/python3.13/site-packages/starlette/middleware/sessions.py]

**Research date:** 2026-05-05
**Valid until:** 2026-06-04 for repo-shape findings, and 2026-05-12 for version-currentness checks. [VERIFIED: research audit]
