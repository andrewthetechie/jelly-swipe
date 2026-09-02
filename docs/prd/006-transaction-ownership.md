# Transaction Ownership

## Problem Statement

The `get_db_uow` FastAPI dependency claims to own the transaction lifecycle — it auto-commits on clean exit and rolls back on exception. But every mutating room route in `rooms.py` calls `await uow.session.commit()` explicitly before `notifier.notify(code)`, because SSE subscribers must read committed data. The dependency's auto-commit is a silent second commit that does nothing on the happy path.

This creates two concrete problems:

1. **The transaction seam is dishonest.** The dependency's interface says "I own commit/rollback," but the rooms router actually owns commit. If a developer writes a new mutating route and trusts the dependency to commit, the commit fires *after* the response returns — and after any `notifier.notify()` call, causing a race where SSE subscribers read stale data.

2. **The commit-then-notify pattern is copy-pasted across 6 route handlers.** `join`, `swipe`, `quit`, `undo`, `genre`, and `watched-filter` all duplicate the same two-line sequence: `await uow.session.commit()` / `notifier.notify(code)`. The invariant — "commit must happen before notify" — is enforced only by convention.

## Solution

Two changes:

1. **Make `get_db_uow` honest.** Remove auto-commit. The dependency owns session lifecycle (open, rollback-on-error, close) but not commit. Add a warning log when a session with uncommitted dirty/new objects reaches `finally` without an explicit commit, so forgotten commits surface at runtime rather than silently losing data.

2. **Extract a `commit_and_wake` helper.** A free function in `jellyswipe/routers/_helpers.py` that composes `uow.session.commit()` and `notifier.notify(code)` into a single call. The 6 commit-then-notify sites in `rooms.py` use the helper. The 4 commit-only sites (`create_room`, `delete_match`, and the 2 auth routes) continue calling `await uow.session.commit()` directly.

## User Stories

1. As a developer writing a new mutating route, I want the UoW dependency to not auto-commit, so that I explicitly choose when to commit relative to post-commit side effects.
2. As a developer who forgets to commit, I want a warning log at session close, so that the bug is visible in runtime logs rather than silently losing writes.
3. As a developer writing a route that commits and then wakes SSE subscribers, I want a single `commit_and_wake` call, so that I cannot accidentally reorder the two steps or forget one.
4. As a developer writing a route that commits without notifying (e.g. room creation), I want to call `uow.session.commit()` directly, so that I am not forced through a notify path that has no subscribers.
5. As a developer reading the codebase, I want the dependency's interface to match its behavior, so that I can trust what the code says without reading every route to discover the real contract.

## Implementation Decisions

### `get_db_uow` new shape

```python
async def get_db_uow():
    session = get_sessionmaker()()
    try:
        yield DatabaseUnitOfWork(session)
    except Exception:
        await session.rollback()
        raise
    finally:
        if session.dirty or session.new:
            _logger.warning(
                "UoW session closed with uncommitted dirty/new objects — "
                "writes were silently lost. Did you forget to commit?"
            )
        await session.close()
```

No auto-commit. Rollback-on-error preserved. Warning on uncommitted writes.

### `commit_and_wake` helper

```python
# jellyswipe/routers/_helpers.py

async def commit_and_wake(uow: DatabaseUnitOfWork, code: str) -> None:
    await uow.session.commit()
    notifier.notify(code)
```

Free function. Does not live on the UoW (that would couple persistence to transport). Lives in `_helpers.py` alongside `make_error_response` and `log_exception`.

### Auth routes add explicit commit

`jellyfin_use_server_identity` and `logout` in `jellyswipe/routers/auth.py` each gain one line: `await uow.session.commit()`. They do not use `commit_and_wake` because they have no SSE subscribers to notify.

### SSE `room_stream` unchanged

The SSE generator in `rooms.py` creates its own session and UoW inside the async generator, outside the dependency. It has a fundamentally different lifecycle from request-scoped routes. No change.

### Sites after this change

| Route | Commit style | Notify? |
|---|---|---|
| `POST /room` | `await uow.session.commit()` | No |
| `POST /room/{code}/join` | `await commit_and_wake(uow, code)` | Yes |
| `POST /room/{code}/swipe` | `await commit_and_wake(uow, code)` | Yes |
| `POST /room/{code}/quit` | `await commit_and_wake(uow, code)` | Yes |
| `POST /room/{code}/undo` | `await commit_and_wake(uow, code)` (conditional on `UndoChanged`) | Yes |
| `POST /room/{code}/genre` | `await commit_and_wake(uow, code)` | Yes |
| `POST /room/{code}/watched-filter` | `await commit_and_wake(uow, code)` | Yes |
| `POST /matches/delete` | `await uow.session.commit()` (conditional on `DeleteChanged`) | No |
| `POST /auth/jellyfin-use-server-identity` | `await uow.session.commit()` | No |
| `POST /auth/logout` | `await uow.session.commit()` | No |

## Scope exclusions

- The `commit_and_wake` pattern does not replace the notifier module or change how SSE works. It is a mechanical composition of two existing calls.
- No new dependency injection variants. One `get_db_uow`, one contract.
- No changes to `DatabaseUnitOfWork` itself.

## Risks

1. **Existing tests that rely on auto-commit.** Any test using `client_real_auth` or similar fixtures that makes writes through `get_db_uow` without explicit commits will silently lose those writes. The warning log will surface these in test output. Mitigation: search for test routes that write and verify they commit.
2. **Third-party or future routers that assume auto-commit.** The warning log is the safety net. No silent failures.

