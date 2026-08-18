# ADR 0004: Commit and notify at the request boundary

## Status

Accepted (issue #295).

## Context

`AGENTS.md` required all DB writes to flow through `DatabaseUnitOfWork`, but
transaction _completion_ — commit and the commit-before-notify ordering — was a
scattered convention, not an enforced rule. `get_db_uow` owned open /
rollback-on-error / close but explicitly delegated commit to the caller, and
routes called `uow.session.commit()` (or the `commit_and_wake` helper) directly
at 8 sites. The cost was a silent failure mode: if a route forgot to commit, the
only signal was a `_logger.warning` at session close about "writes silently
lost". Because the helpers and the difference between a notifying and a
non-notifying commit were invisible at the call site, `create_room` and
`delete_match` committed without ever waking SSE subscribers, and the
`BEGIN IMMEDIATE` transaction's "caller must not COMMIT/ROLLBACK" contract was
enforced only by a docstring.

## Decision

Move transaction completion into the **request boundary** (`get_db_uow`):

- The dependency owns **commit-on-success**, **rollback-on-error**, and
  **notify-after-commit**. Routes no longer call `session.commit()` or any
  `commit_and_wake` helper.
- Routes that need SSE subscribers woken declare **wake intent** via
  `uow.wake_on_commit(code)`; the boundary, after a successful commit, drains the
  declared codes and calls `notifier.notify(code)` for each. Routes that need to
  discard their writes on an error return call `uow.abort()`, which makes the
  boundary roll back instead of committing.
- After committing, the boundary asserts the session is not `dirty/new/deleted`;
  if it is, it raises `RuntimeError` (a 500). The advisory close-time warning is
  removed. Because `DBUoW` uses `scope="function"` (FastAPI ≥ 0.118 semantics),
  this teardown runs before the response is sent, so the failure is loud rather
  than a request that silently answers 200 with lost writes.
- The `BEGIN IMMEDIATE` contract becomes enforced: while an immediate transaction
  is open, `run_sync` verifies the raw sqlite connection is still in a transaction
  after the callable returns and raises if it was committed/rolled back inside.
- Background cleanup (`_cleanup_after_grace`) moves from a bare
  `asyncio.create_task` inside a service method to a visible, shutdown-aware
  `BackgroundTaskRegistry` with an injectable clock, drained on app shutdown.

## Alternatives considered

- **Auto-derive wake codes from appended `session_events`** — zero route code,
  but magical; needs instance→code lookups at drain time and does not cover
  `delete_match` (which appends no event).
- **Notifier hooks into SQLAlchemy commit events** — cannot know room codes.
- **Keep the caller-owned commit and add `abort()` only** — did not close the
  "silently forgot to commit" failure mode that motivated the issue.

## Consequences

- **Structural impossibility, not advisory.** A forgotten/incorrect commit now
  surfaces as a 500 (post-commit dirty check) or an immediate `RuntimeError`
  (in-transaction guard) rather than a log line dropped at close.
- **Commit-before-notify is preserved and tested.** An ordering test proves the
  commit is observed before `notifier.notify` within one request.
- **The `create_room` / `delete_match` notify gap is closed** (acceptance
  criterion 6) and covered by route tests.
- **New routes need no commit/notify code.** They write via the UoW and (if
  room state changed) declare `wake_on_commit`; the boundary finishes.
- No schema or migration change. The swap-transaction `BEGIN IMMEDIATE` mechanics
  are unchanged in operation — the boundary issues the same `session.commit()` the
  old `commit_and_wake` did.
