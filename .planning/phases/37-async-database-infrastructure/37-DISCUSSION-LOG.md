# Phase 37: Async Database Infrastructure - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-05
**Phase:** 37-Async Database Infrastructure
**Areas discussed:** Startup migration trigger, Async engine and session lifecycle, Test database bootstrap path, Sync/async coexistence during the transition

---

## Startup migration trigger

### Question 1

| Option | Description | Selected |
|--------|-------------|----------|
| Always run `upgrade head` during startup | Every normal boot ensures schema is current | ✓ |
| Only run when the SQLite file is missing | Skip migration on existing DBs | |
| Separate bootstrap command only | App startup never attempts migration | |

**User's choice:** Always run `upgrade head` on normal boot
**Notes:** The user wanted the runtime path to assume migrations are part of standard boot, not a manual maintenance action.

### Question 2

| Option | Description | Selected |
|--------|-------------|----------|
| Fail fast | Refuse to serve requests if migration fails | ✓ |
| Log and continue | Boot even with migration errors | |
| Environment-specific behavior | Fail only outside development | |

**User's choice:** Fail fast
**Notes:** Boot should stop if the schema is not ready.

### Question 3

| Option | Description | Selected |
|--------|-------------|----------|
| FastAPI startup owns migration | App process calls Alembic directly | |
| Bootstrap wrapper before Uvicorn | External wrapper prepares DB first | ✓ |
| Hybrid | Wrapper in some environments, app startup elsewhere | |

**User's choice:** Bootstrap wrapper before Uvicorn
**Notes:** The user clarified the tension between "run on normal boot" and "outside app process" by choosing a wrapper that runs before Uvicorn starts.

### Question 4

| Option | Description | Selected |
|--------|-------------|----------|
| `DB_PATH` primary | Derive async URL from file path | |
| `DATABASE_URL` primary | Promote full DB URL configuration now | ✓ |
| Support both equally | No single source of truth yet | |

**User's choice:** `DATABASE_URL` primary
**Notes:** Runtime config should move toward the new async/Alembic shape now.

---

## Async engine and session lifecycle

### Question 1

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated runtime module | Keep async runtime separate from schema and app factory concerns | ✓ |
| Expand `db.py` | Let one module own sync leftovers and async runtime | |
| Put it in app startup | Engine/session objects live in the app factory layer | |

**User's choice:** Dedicated runtime module
**Notes:** The user preferred a clean ownership boundary for the new runtime path.

### Question 2

| Option | Description | Selected |
|--------|-------------|----------|
| Raw `AsyncSession` | DI returns the session directly | |
| Small wrapper | DI returns a thin app-specific helper | |
| Repository registry / unit-of-work | DI exposes a higher-level persistence surface | ✓ |

**User's choice:** Repository registry / unit-of-work
**Notes:** The async boundary should be shaped for later domain conversion work, not just session plumbing.

### Question 3

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-commit/rollback in dependency | Success commits, errors roll back automatically | ✓ |
| Explicit commits by callers | Dependency only scopes the session | |
| Mixed ownership | Different rules for reads and writes | |

**User's choice:** Auto-commit/rollback in dependency
**Notes:** The user wanted the dependency boundary to own transaction completion.

### Question 4

| Option | Description | Selected |
|--------|-------------|----------|
| Lazy module-level engine | Create once and mostly keep forever | |
| Bootstrap and shutdown lifecycle | Initialize during boot, dispose during shutdown | ✓ |
| Per-request/per-test recreation | Max isolation over reuse | |

**User's choice:** Bootstrap and shutdown lifecycle
**Notes:** Engine lifecycle should align with app lifecycle rather than ad hoc lazy globals.

---

## Test database bootstrap path

### Question 1

| Option | Description | Selected |
|--------|-------------|----------|
| Alembic per fresh DB | Each fresh test database comes from `upgrade head` | ✓ |
| Shared upgraded DB | Run Alembic less often and reuse more | |
| Mixed with direct schema bootstrap | Keep old bootstrap in some tests | |

**User's choice:** Alembic per fresh DB
**Notes:** The user wanted tests to validate the new bootstrap path directly.

### Question 2

| Option | Description | Selected |
|--------|-------------|----------|
| Rewrite low-level `init_db()` callers now | Move off old bootstrap in this phase | ✓ |
| Leave for later | Defer low-level cleanup | |
| Test-only shim | Keep shapes stable with a compatibility layer | |

**User's choice:** Rewrite low-level `init_db()` callers now
**Notes:** Carrying the old bootstrap path in low-level tests was explicitly rejected.

### Question 3

| Option | Description | Selected |
|--------|-------------|----------|
| Sync helpers okay in tests | Simpler direct SQL is acceptable long-term | |
| Prefer async session/repository path | Match the runtime path where practical | ✓ |
| Mixed | Async bootstrap but direct SQL fixtures still fine | |

**User's choice:** Prefer async session/repository path
**Notes:** The user wanted tests to move with the new runtime design rather than remain mostly sync.

### Question 4

| Option | Description | Selected |
|--------|-------------|----------|
| Strict isolation first | Fidelity outweighs speed | |
| Balanced | Keep isolation strong but not absolutist | ✓ |
| Shared setup first | Favor speed unless flakes appear | |

**User's choice:** Balanced
**Notes:** The user did not want per-test migration cost to dominate every choice.

---

## Sync/async coexistence during the transition

### Question 1

| Option | Description | Selected |
|--------|-------------|----------|
| Broad sync allowance | Phase 37 is infrastructure only | |
| Sync only in unconverted domains | Limit sync leftovers to routes not yet converted | ✓ |
| No sync app DB access | Switch everything immediately | |

**User's choice:** Sync only in unconverted domains
**Notes:** Sync paths may survive briefly, but only as a temporary boundary around still-unconverted domains.

### Question 2

| Option | Description | Selected |
|--------|-------------|----------|
| Keep `DBConn` temporarily | Run both dependency surfaces side by side | |
| Replace `DBConn` immediately | Move to the new async dependency surface now | ✓ |
| Keep it only for tests/helpers | Shrink its scope but retain it | |

**User's choice:** Replace `DBConn` immediately
**Notes:** The dependency surface itself should not remain sync once the async path exists.

### Question 3

| Option | Description | Selected |
|--------|-------------|----------|
| Keep maintenance sync for now | Outside-request work can stay sync longer | |
| Move maintenance to async now | Runtime cleanup should use the new async path immediately | ✓ |
| Mixed | Startup and request-adjacent maintenance split | |

**User's choice:** Move maintenance to async now
**Notes:** Phase 37 should pull maintenance functions onto the new engine/session path too.

### Question 4

| Option | Description | Selected |
|--------|-------------|----------|
| Some duplication is fine | Lower risk over cleanliness | |
| Minimize duplication | Accept slightly broader scope to avoid parallel systems | ✓ |
| Avoid duplication almost entirely | Force early domain conversion if needed | |

**User's choice:** Minimize duplication
**Notes:** The user preferred a cleaner handoff even if it broadens Phase 37 a bit.

---

## the agent's Discretion

None.

## Deferred Ideas

None.
